"""Motor inicial, explícitamente provisional hasta conciliar con el Excel oficial."""
import calendar
import copy
import hashlib
import json
import math
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_FLOOR
from io import BytesIO
from openpyxl import load_workbook


class Invalid(ValueError):
    def __init__(self, errors):
        self.errors = errors if isinstance(errors, list) else [str(errors)]
        super().__init__("; ".join(self.errors))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def default_params():
    roles = {}
    for role, duration in [("Kinesiología", 30), ("Terapia ocupacional", 40),
                           ("Psicología", 45), ("Educación", 60)]:
        roles[role] = {"minutes_direct": duration, "minutes_indirect": 30,
                       "group_pct": 0.2 if role == "Educación" else 0,
                       "patients_group": 4,
                       "bands": {"40+": [0.65, 0.25, 0.10],
                                 "22-40": [0.70, 0.25, 0.05],
                                 "0-22": [0.75, 0.25, 0]}}
    return {"year": 2026, "management_pct": 0.90, "legal_change": "2026-05-01",
            "legal_cap_before": 44, "legal_cap_after": 42,
            "max_assignments_over_30": 2,
            "assignments": {"Líder de equipo": {"weekly_hours": 2, "approval_required": False},
                            "Tutor docente": {"weekly_hours": 1, "approval_required": False},
                            "Comité nacional": {"weekly_hours": 0.5, "approval_required": True}},
            "roles": roles, "calendar": [], "group_overrides": []}


def number(v, label, low=0, high=1000000):
    if isinstance(v, bool):
        raise Invalid(f"{label}: se esperaba un número")
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise Invalid(f"{label}: se esperaba un número")
    if not math.isfinite(n) or not low <= n <= high:
        raise Invalid(f"{label}: debe estar entre {low} y {high}")
    return n


def iso(v, label):
    if isinstance(v, (datetime, date)):
        return v.date().isoformat() if isinstance(v, datetime) else v.isoformat()
    try:
        return date.fromisoformat(str(v)).isoformat()
    except (ValueError, TypeError):
        raise Invalid(f"{label}: fecha ISO AAAA-MM-DD inválida")


def integer(v, label, low, high):
    n = number(v, label, low, high)
    if n != int(n):
        raise Invalid(f'{label}: debe ser entero')
    return int(n)


def validate_params(raw):
    p = copy.deepcopy(raw)
    if not isinstance(p, dict):
        raise Invalid("Parámetros: se esperaba un objeto JSON")
    required = set(default_params())
    if not required <= p.keys():
        raise Invalid(f"Parámetros: faltan {', '.join(sorted(required - p.keys()))}")
    p["year"] = integer(p["year"], "Año", 2026, 2026)
    p["management_pct"] = number(p["management_pct"], "Meta", 0, 1)
    p["legal_change"] = iso(p["legal_change"], "Cambio legal")
    for k in ("legal_cap_before", "legal_cap_after"):
        p[k] = number(p[k], k, 1, 80)
    p["max_assignments_over_30"] = integer(p["max_assignments_over_30"], "Máximo asignaciones", 0, 10)
    if not isinstance(p["roles"], dict) or not p["roles"]:
        raise Invalid("Se requiere al menos un cargo")
    try:
        for name, r in p["roles"].items():
            for k in ("minutes_direct", "minutes_indirect"):
                r[k] = number(r[k], f"{name}: {k}", 1, 480)
            r["group_pct"] = number(r["group_pct"], f"{name}: grupal", 0, 1)
            r["patients_group"] = integer(r["patients_group"], f"{name}: pacientes", 1, 100)
            for band in ("40+", "22-40", "0-22"):
                vals = r["bands"][band]
                if len(vals) != 3:
                    raise Invalid(f"{name} / {band}: se requieren directa, indirecta y NAS")
                vals = [number(v, f"{name} / {band}", 0, 1) for v in vals]
                if abs(sum(vals) - 1) > 1e-8 or vals[0] + vals[1] == 0:
                    raise Invalid(f"{name} / {band}: porcentajes deben sumar 100% y tener atención")
                r["bands"][band] = vals
        for name, a in p["assignments"].items():
            a["weekly_hours"] = number(a["weekly_hours"], name, 0, 40)
            if not isinstance(a["approval_required"], bool):
                raise Invalid(f"{name}: approval_required debe ser booleano")
        seen = set()
        for c in p["calendar"]:
            month = str(c["month"])
            if month not in [f'{p["year"]}-{i:02}' for i in range(1, 13)]:
                raise Invalid("Calendario: mes fuera del año")
            if not str(c["institute"]).strip():
                raise Invalid("Calendario: instituto requerido")
            key = (c["institute"], month)
            if key in seen:
                raise Invalid(f"Calendario duplicado: {key}")
            seen.add(key)
            days = len(weekdays(p["year"], int(month[-2:])))
            h = number(c["holidays"], "Feriados", 0, days)
            v = number(c["vacation_days"], "Vacaciones", 0, days)
            if h + v > days:
                raise Invalid(f"Calendario {key}: descuentos superan días hábiles")
        seen = set()
        for g in p["group_overrides"]:
            key = (g["institute"], g["role"])
            if key in seen or g["role"] not in p["roles"]:
                raise Invalid("Regla grupal duplicada o cargo desconocido")
            seen.add(key)
            g["group_pct"] = number(g["group_pct"], "Grupal", 0, 1)
            g["patients_group"] = integer(g["patients_group"], "Pacientes", 1, 100)
    except (KeyError, TypeError, AttributeError) as e:
        raise Invalid(f"Estructura de parámetros incompleta: {e}")
    return p


BUK_COLUMNS = ["contract_id", "professional_id", "institute", "area", "role", "hours_weekly",
               "start_date", "end_date", "effective_from", "assignments", "approved_assignments",
               "leave_start", "leave_end"]
SIC_COLUMNS = ["professional_id", "institute", "month", "actual"]


def read_excel(data, sheet, required):
    if len(data) > 8 * 1024 * 1024:
        raise Invalid(f"{sheet}: archivo supera 8 MB")
    # Limit decompressed workbook size before openpyxl processes the archive.
    import zipfile
    try:
        with zipfile.ZipFile(BytesIO(data)) as z:
            if sum(i.file_size for i in z.infolist()) > 40 * 1024 * 1024:
                raise Invalid(f"{sheet}: contenido expandido demasiado grande")
        wb = load_workbook(BytesIO(data), read_only=True, data_only=False)
        try:
            if sheet not in wb.sheetnames:
                raise Invalid(f"Hoja requerida: {sheet}")
            rows = wb[sheet].iter_rows(values_only=True)
            header = [str(v).strip() if v is not None else "" for v in next(rows, [])]
            if len(header) != len(set(header)):
                raise Invalid(f"{sheet}: columnas duplicadas")
            if not set(required) <= set(header):
                raise Invalid(f"{sheet}: faltan columnas {', '.join(sorted(set(required)-set(header)))}")
            result = []
            for idx, values in enumerate(rows, 2):
                if idx > 20001:
                    raise Invalid(f"{sheet}: límite de 20.000 filas")
                if not any(v is not None for v in values):
                    continue
                if any(isinstance(v, str) and v.startswith("=") for v in values):
                    raise Invalid(f"{sheet}, fila {idx}: se requieren valores, no fórmulas")
                row = dict(zip(header, values))
                row["_row"] = idx
                result.append(row)
            return result
        finally:
            wb.close()
    except Invalid:
        raise
    except Exception:
        raise Invalid(f"{sheet}: Excel .xlsx ilegible o corrupto")


def normalize_buk(rows, p):
    if not isinstance(rows, list) or not rows:
        raise Invalid("BUK: se requiere al menos un contrato")
    result, errors, seen = [], [], set()
    for idx, raw in enumerate(rows, 2):
        label = f'BUK, fila {raw.get("_row", idx)}' if isinstance(raw, dict) else f'BUK, fila {idx}'
        try:
            r = {}
            for k in ("contract_id", "professional_id", "institute", "area", "role"):
                v = raw.get(k)
                if v is None or not str(v).strip() or len(str(v)) > 120:
                    raise Invalid(f"{k}: requerido, máximo 120 caracteres")
                r[k] = str(v).strip()
            if r["role"] not in p["roles"]:
                raise Invalid(f'cargo sin homologar: {r["role"]}')
            r["hours_weekly"] = number(raw.get("hours_weekly"), "hours_weekly", 0, 80)
            r["start_date"] = iso(raw.get("start_date"), "start_date")
            r["effective_from"] = iso(raw.get("effective_from") or r["start_date"], "effective_from")
            r["end_date"] = iso(raw["end_date"], "end_date") if raw.get("end_date") else None
            if r["effective_from"] < r["start_date"] or (r["end_date"] and r["end_date"] < r["effective_from"]):
                raise Invalid("vigencias fuera de orden (inicio ≤ efecto ≤ término)")
            for k in ("assignments", "approved_assignments"):
                val = raw.get(k) or []
                r[k] = [s.strip() for s in val.split(";") if s.strip()] if isinstance(val, str) else list(val)
                if len(set(r[k])) != len(r[k]):
                    raise Invalid(f"{k}: asignaciones duplicadas")
            for a in r["assignments"]:
                if a not in p["assignments"]:
                    raise Invalid(f"asignación desconocida: {a}")
                if p["assignments"][a]["approval_required"] and a not in r["approved_assignments"]:
                    raise Invalid(f"asignación requiere autorización: {a}")
            if r["hours_weekly"] > 30 and len(r["assignments"]) > p["max_assignments_over_30"]:
                raise Invalid("supera máximo de asignaciones para jornada >30 h")
            if sum(p["assignments"][a]["weekly_hours"] for a in r["assignments"]) > r["hours_weekly"]:
                raise Invalid("asignaciones superan jornada")
            for k in ("leave_start", "leave_end"):
                r[k] = iso(raw[k], k) if raw.get(k) else None
            if bool(r["leave_start"]) != bool(r["leave_end"]) or (r["leave_start"] and r["leave_end"] < r["leave_start"]):
                raise Invalid("licencia requiere inicio y fin ordenados")
            key = (r["contract_id"], r["effective_from"])
            if key in seen:
                raise Invalid("contrato y fecha efectiva duplicados")
            seen.add(key)
            result.append(r)
        except (Invalid, TypeError, AttributeError) as e:
            errors.append(f"{label}: {e}")
    if errors:
        raise Invalid(errors[:100])
    return sorted(result, key=lambda r: (r["contract_id"], r["effective_from"]))


def normalize_sic(rows, p):
    result, seen, errors = [], set(), []
    if not isinstance(rows, list):
        raise Invalid("SIC: se esperaba una lista")
    for idx, raw in enumerate(rows, 2):
        try:
            r = {k: str(raw.get(k) or "").strip() for k in ("professional_id", "institute", "month")}
            if not r["professional_id"] or not r["institute"]:
                raise Invalid("identificador e instituto requeridos")
            if r["month"] not in [f'{p["year"]}-{i:02}' for i in range(1, 13)]:
                raise Invalid("mes inválido; usar AAAA-MM dentro del año")
            r["actual"] = number(raw.get("actual"), "actual", 0, 1000000)
            if r["actual"] != int(r["actual"]):
                raise Invalid("actual debe ser entero")
            r["actual"] = int(r["actual"])
            key = (r["professional_id"], r["institute"], r["month"])
            if key in seen:
                raise Invalid("profesional, instituto y mes duplicados")
            seen.add(key)
            result.append(r)
        except (Invalid, AttributeError) as e:
            errors.append(f'SIC, fila {raw.get("_row", idx) if isinstance(raw, dict) else idx}: {e}')
    if errors:
        raise Invalid(errors[:100])
    return sorted(result, key=lambda r: (r["professional_id"], r["institute"], r["month"]))


def merge_contracts(previous, incoming):
    merged = {(r["contract_id"], r["effective_from"]): r for r in previous}
    counts = {"added": 0, "changed": 0, "ended": 0, "unchanged": 0}
    changes = []
    old_ids = {r["contract_id"] for r in previous}
    for r in incoming:
        history = [a for a in previous if a["contract_id"] == r["contract_id"] and a["effective_from"] <= r["effective_from"]]
        before = max(history, key=lambda a: a["effective_from"], default=None)
        kind = "added" if r["contract_id"] not in old_ids else "changed"
        if before == r:
            kind = "unchanged"
        elif before and r["end_date"] and before.get("end_date") != r["end_date"]:
            kind = "ended"
        counts[kind] += 1
        if kind != "unchanged":
            changes.append({"contract_id": r["contract_id"], "kind": kind,
                            "effective_from": r["effective_from"], "before": before, "after": r})
        merged[(r["contract_id"], r["effective_from"])] = r
    return sorted(merged.values(), key=lambda r: (r["contract_id"], r["effective_from"])), counts, changes


def weekdays(year, month):
    return [date(year, month, d) for d in range(1, calendar.monthrange(year, month)[1] + 1)
            if date(year, month, d).weekday() < 5]


def floor(v):
    return int(Decimal(str(round(v, 9))).to_integral_value(rounding=ROUND_FLOOR))


def calculate(contracts, sic, p):
    # One effective segment per contractual link/day; distinct links support multi-institute.
    histories = {}
    for c in contracts:
        histories.setdefault(c["contract_id"], []).append(c)
    calendar_map = {(c["institute"], c["month"]): c for c in p["calendar"]}
    totals = {}
    all_active = []
    identities = {}
    for contract_id, history in histories.items():
        history.sort(key=lambda c: c["effective_from"])
        if len({c["professional_id"] for c in history}) != 1:
            raise Invalid(f'{contract_id}: un vínculo contractual no puede cambiar de profesional')
        active = []
        for m in range(1, 13):
            for day in weekdays(p["year"], m):
                eligible = [c for c in history if c["effective_from"] <= day.isoformat()]
                if not eligible:
                    continue
                c = eligible[-1]
                if day.isoformat() < c["start_date"] or (c["end_date"] and day.isoformat() > c["end_date"]):
                    continue
                cap = p["legal_cap_after"] if day.isoformat() >= p["legal_change"] else p["legal_cap_before"]
                active.append((day, c, min(c["hours_weekly"], cap)))
        all_active.extend(active)
    # The band belongs to the professional, adding simultaneous multi-institute links.
    for day, c, h in all_active:
        daily = identities.setdefault(c['professional_id'], {})
        daily[day] = daily.get(day, 0) + h
    averages = {pid: sum(d.values()) / len(d) for pid, d in identities.items()}
    for day, c, h in all_active:
        avg = averages[c['professional_id']]
        band = "40+" if avg >= 40 else "22-40" if avg >= 22 else "0-22"
        contract_id = c['contract_id']
        month = day.strftime("%Y-%m")
        key = (c["professional_id"], c["institute"], c["area"], c["role"], month)
        row = totals.setdefault(key, {"professional_id": key[0], "institute": key[1], "area": key[2],
                                     "role": key[3], "month": month, "contracted": 0, "direct": 0,
                                     "indirect": 0, "nas": 0, "absence": 0,
                                     "individual_raw": 0, "group_raw": 0, "indirect_raw": 0})
        rule = p["roles"][c["role"]]
        dist = rule["bands"][band]
        cal = calendar_map.get((c["institute"], month), {"holidays": 0, "vacation_days": 0})
        ratio = 1 - (float(cal["holidays"]) + float(cal["vacation_days"])) / len(weekdays(p["year"], day.month))
        licensed = bool(c["leave_start"] and c["leave_start"] <= day.isoformat() <= c["leave_end"])
        gross = h / 5
        available = 0 if licensed else gross * ratio
        assignment = sum(p["assignments"][a]["weekly_hours"] for a in c["assignments"]) / 5 * (0 if licensed else ratio)
        nas = available * dist[2] + assignment
        if nas > available + 1e-9:
            raise Invalid(f'{contract_id} / {month}: NAS y asignaciones superan horas disponibles')
        attention = max(0, available - nas)
        direct = attention * dist[0] / (dist[0] + dist[1])
        indirect = attention - direct
        row["contracted"] += gross
        row["direct"] += direct
        row["indirect"] += indirect
        row["nas"] += nas
        row["absence"] += gross - available
        group = next((g for g in p["group_overrides"] if g["institute"] == c["institute"] and g["role"] == c["role"]), rule)
        row["individual_raw"] += direct * (1-group["group_pct"]) * 60 / rule["minutes_direct"]
        row["group_raw"] += direct * group["group_pct"] * 60 / rule["minutes_direct"]
        row["indirect_raw"] += indirect * 60 / rule["minutes_indirect"]
        row["patients_group"] = group["patients_group"]
    result = []
    for row in totals.values():
        row["planned_direct"] = floor(row.pop("individual_raw")) + floor(row.pop("group_raw")) * row.pop("patients_group")
        row["planned_indirect"] = floor(row.pop("indirect_raw"))
        row["planned"] = row["planned_direct"] + row["planned_indirect"]
        row["target"] = row["planned"] * p["management_pct"]
        for k in ("contracted", "direct", "indirect", "nas", "absence", "target"):
            row[k] = round(row[k], 6)
        row["actual"] = None
        row["foja"] = row["direct"] / row["contracted"] if row["contracted"] else None
        result.append(row)
    return attach_sic(result, sic)


def attach_sic(result, sic):
    # SIC has no area/role: attach it only if a professional/institute/month resolves to one row.
    # Ambiguous matches stay at a separate comparison grain instead of duplicating actuals.
    comparisons, by_key = [], {}
    for r in result:
        r['actual'] = None
        by_key.setdefault((r["professional_id"], r["institute"], r["month"]), []).append(r)
    for s in sic:
        key = (s["professional_id"], s["institute"], s["month"])
        matches = by_key.get(key, [])
        if not matches:
            raise Invalid(f'SIC: sin contrato para {key}; no se publica el cruce huérfano')
        comparisons.append({**s, "planned_direct": sum(r["planned_direct"] for r in matches),
                            "ambiguous": len(matches) > 1})
        if len(matches) == 1:
            matches[0]["actual"] = s["actual"]
    return sorted(result, key=lambda r: (r["month"], r["institute"], r["professional_id"], r["role"])), comparisons
