import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .domain import (Invalid, fingerprint, default_params, validate_params,
                     normalize_buk, normalize_sic, merge_contracts, calculate, attach_sic)


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
                INSERT OR IGNORE INTO schema_version VALUES(1);
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs(
                    id TEXT PRIMARY KEY, status TEXT NOT NULL, created_at TEXT NOT NULL,
                    actor TEXT NOT NULL, source TEXT NOT NULL, input_hash TEXT,
                    errors TEXT NOT NULL, summary TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS versions(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL UNIQUE REFERENCES runs(id),
                    fingerprint TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, params TEXT NOT NULL,
                    contracts TEXT NOT NULL, sic TEXT NOT NULL, changes TEXT NOT NULL,
                    rows_json TEXT NOT NULL, comparisons TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS publication(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    version_id INTEGER NOT NULL REFERENCES versions(id));
                CREATE TABLE IF NOT EXISTS audit(
                    id INTEGER PRIMARY KEY, created_at TEXT NOT NULL,
                    actor TEXT NOT NULL, operation TEXT NOT NULL, detail TEXT NOT NULL);
            ''')
            db.execute("INSERT OR IGNORE INTO settings VALUES('params',?)", (json.dumps(validate_params(default_params())),))
        import os
        if os.name != 'nt':
            self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def params(self):
        with self.connect() as db:
            p = validate_params(json.loads(db.execute("SELECT value FROM settings WHERE key='params'").fetchone()[0]))
        return {"params": p, "hash": fingerprint(p)}

    def save_params(self, params, actor):
        p = validate_params(params)
        with self.lock, self.connect() as db:
            db.execute("UPDATE settings SET value=? WHERE key='params'", (json.dumps(p),))
            self.audit(db, actor, "parameters_saved", fingerprint(p))
        return {"params": p, "hash": fingerprint(p)}

    def audit(self, db, actor, operation, detail):
        db.execute("INSERT INTO audit(created_at,actor,operation,detail) VALUES(?,?,?,?)",
                   (now(), actor, operation, json.dumps(detail, ensure_ascii=False)))

    def reject(self, errors, actor, source):
        run_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)",
                       (run_id, "rejected", now(), actor, source, None, json.dumps(errors), '{}'))
            self.audit(db, actor, "run_rejected", {"run_id": run_id, "errors": errors})
        return run_id

    def publish(self, buk, sic, actor="equipo-local", source="archivo", expected_params=None):
        # Serialize input merge + parameter snapshot + publication to avoid lost updates.
        with self.lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            p = validate_params(json.loads(db.execute("SELECT value FROM settings WHERE key='params'").fetchone()[0]))
            if expected_params and expected_params != fingerprint(p):
                raise Invalid("La versión de parámetros cambió. Leer parámetros y reintentar.")
            previous = db.execute("SELECT v.* FROM versions v JOIN publication p ON p.version_id=v.id").fetchone()
            old_contracts = json.loads(previous["contracts"]) if previous else []
            incoming = normalize_buk(buk, p)
            contracts, counts, changes = merge_contracts(old_contracts, incoming)
            # Revalidate preserved segments after changes to catalogs or assignment rules.
            contracts = normalize_buk(contracts, p)
            if sic is None:
                if not previous:
                    raise Invalid("Primera carga: se requiere SIC; puede ser una hoja válida sin filas")
                sic = json.loads(previous["sic"])
            sic = normalize_sic(sic, p)
            digest = fingerprint({"contracts": contracts, "sic": sic, "params": p})
            found = db.execute("SELECT id,run_id FROM versions WHERE fingerprint=?", (digest,)).fetchone()
            if found:
                # A replay never moves the visible pointer backwards to an older version.
                self.audit(db, actor, "replay_skipped", {"existing_version": found["id"]})
                active_id = previous["id"] if previous else found["id"]
                return {"status": "reused", "version": found["id"], "active_version": active_id,
                        "run_id": found["run_id"], "summary": counts}
            rows, comparisons = calculate(contracts, [], p)
            if previous and fingerprint(json.loads(previous['params'])) == fingerprint(p):
                # Incremental BUK publication freezes earlier complete months even if the
                # weighted annual band changes. Parameter changes explicitly recalculate all.
                cutoffs = {}
                for change in changes:
                    person = change['after']['professional_id']
                    effective = change['effective_from'][:7]
                    cutoffs[person] = min(cutoffs.get(person, effective), effective)
                old_rows = json.loads(previous['rows_json'])
                frozen = [r for r in old_rows if r['professional_id'] not in cutoffs or
                          r['month'] < cutoffs[r['professional_id']]]
                frozen_keys = {(r['professional_id'], r['institute'], r['area'], r['role'], r['month']) for r in frozen}
                rows = [r for r in rows if (r['professional_id'], r['institute'], r['area'], r['role'], r['month']) not in frozen_keys]
                rows.extend(frozen)
            rows, comparisons = attach_sic(rows, sic)
            if not rows:
                raise Invalid("No hay contratos vigentes en el año de planificación")
            run_id = str(uuid.uuid4())
            db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)",
                       (run_id, "published", now(), actor, source, digest, '[]', json.dumps(counts)))
            cur = db.execute('''INSERT INTO versions(run_id,fingerprint,created_at,params,contracts,sic,changes,rows_json,comparisons)
                                VALUES(?,?,?,?,?,?,?,?,?)''',
                             (run_id, digest, now(), json.dumps(p), json.dumps(contracts), json.dumps(sic),
                              json.dumps(changes), json.dumps(rows), json.dumps(comparisons)))
            version = cur.lastrowid
            db.execute("INSERT INTO publication VALUES(1,?) ON CONFLICT(singleton) DO UPDATE SET version_id=excluded.version_id", (version,))
            self.audit(db, actor, "plan_published", {"version": version, "run_id": run_id, "params_hash": fingerprint(p)})
            return {"status": "published", "version": version, "active_version": version,
                    "run_id": run_id, "summary": counts}

    def snapshot(self, version=None):
        with self.connect() as db:
            if version is None:
                row = db.execute("SELECT v.* FROM versions v JOIN publication p ON p.version_id=v.id").fetchone()
            else:
                row = db.execute("SELECT * FROM versions WHERE id=?", (version,)).fetchone()
            if not row:
                return {"version": None, "rows": [], "comparisons": [], "changes": []}
            return {"version": row["id"], "run_id": row["run_id"], "created_at": row["created_at"],
                    "params_hash": fingerprint(json.loads(row["params"])),
                    "rows": json.loads(row["rows_json"]), "comparisons": json.loads(row["comparisons"]),
                    "changes": json.loads(row["changes"])}

    def history(self):
        with self.connect() as db:
            runs = [dict(r) for r in db.execute('''SELECT r.*,v.id AS version FROM runs r
                      LEFT JOIN versions v ON v.run_id=r.id ORDER BY r.created_at DESC LIMIT 100''')]
            for r in runs:
                r["errors"] = json.loads(r["errors"])
                r["summary"] = json.loads(r["summary"])
            audit = [dict(r) for r in db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 100")]
            return {"runs": runs, "audit": audit}
