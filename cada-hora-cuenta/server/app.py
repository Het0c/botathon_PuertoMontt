import argparse
import csv
import io
import json
import logging
import os
import secrets
import sys
import atexit
from pathlib import Path
from flask import Flask, request, jsonify, send_file, g
from werkzeug.serving import make_server
from werkzeug.exceptions import HTTPException
from .domain import Invalid, BUK_COLUMNS, SIC_COLUMNS, read_excel
from .storage import Store

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def create_app(db_path, token, read_token=None):
    if not token or len(token) < 12:
        raise ValueError("Se requiere un token de al menos 12 caracteres")
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 18 * 1024 * 1024
    store = Store(db_path)
    app.store = store

    @app.before_request
    def access():
        allowed_origins = {'tauri://localhost', 'http://tauri.localhost', 'https://tauri.localhost'}
        origin = request.headers.get('Origin')
        if origin and origin not in allowed_origins and origin not in ('http://localhost:1420', 'http://127.0.0.1:1420', 'http://localhost:4173', 'http://127.0.0.1:4173'):
            return jsonify(error='Origen no permitido'), 403
        if request.method == 'OPTIONS':
            return '', 204
        # Require loopback + bearer for every route, including health and downloads.
        if request.remote_addr not in ('127.0.0.1', '::1', None):
            return jsonify(error="Acceso local requerido"), 403
        host = request.host.split(':')[0]
        if host not in ('127.0.0.1', 'localhost', '[', '::1'):
            return jsonify(error="Host no permitido"), 403
        auth = request.headers.get('Authorization', '')
        supplied = auth[7:] if auth.startswith('Bearer ') else ''
        if secrets.compare_digest(supplied.encode(), token.encode()):
            g.role = 'editor'
        elif read_token and secrets.compare_digest(supplied.encode(), read_token.encode()):
            g.role = 'viewer'
        else:
            return jsonify(error="Token de sesión inválido"), 401
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and g.role != 'editor':
            return jsonify(error="Esta sesión es de solo lectura"), 403
        g.actor = 'equipo-local' if g.role == 'editor' else 'consulta-local'

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        origin = request.headers.get('Origin')
        if origin in {'tauri://localhost', 'http://tauri.localhost', 'https://tauri.localhost', 'http://localhost:1420', 'http://127.0.0.1:1420', 'http://localhost:4173', 'http://127.0.0.1:4173'}:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
            response.headers['Vary'] = 'Origin'
        return response

    @app.errorhandler(Invalid)
    def invalid(e):
        run_id = None
        if request.path in ('/api/import', '/api/batches', '/api/demo'):
            run_id = store.reject(e.errors, g.actor, 'ingesta')
        return jsonify(error='Validación rechazada', errors=e.errors, run_id=run_id), 422

    @app.errorhandler(HTTPException)
    def http_error(e):
        return jsonify(error=e.description), e.code

    @app.errorhandler(Exception)
    def unexpected(e):
        app.logger.exception('Error interno')
        return jsonify(error='Error interno. La versión publicada se conserva.'), 500

    @app.get('/api/health')
    def health():
        return jsonify(status='ok', database='sqlite', role=g.role, app_version='0.1.0')

    @app.get('/api/plan')
    def plan():
        return jsonify(store.snapshot(request.args.get('version', type=int)))

    @app.get('/api/runs')
    def runs():
        return jsonify(store.history())

    @app.get('/api/parameters')
    def parameters():
        return jsonify(store.params())

    @app.put('/api/parameters')
    def save_parameters():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or 'params' not in data:
            raise Invalid('Se requiere el objeto params')
        return jsonify(store.save_params(data['params'], g.actor))

    @app.post('/api/import')
    def upload():
        buk = request.files.get('buk')
        sic = request.files.get('sic')
        if not buk or not buk.filename.lower().endswith('.xlsx'):
            raise Invalid('BUK: seleccionar un archivo .xlsx')
        try:
            b = read_excel(buk.read(), 'BUK', BUK_COLUMNS[:8])
        except Invalid as e:
            raise Invalid([f'{buk.filename}: {v}' for v in e.errors])
        s = None
        if sic and sic.filename:
            if not sic.filename.lower().endswith('.xlsx'):
                raise Invalid('SIC: seleccionar un archivo .xlsx')
            try:
                s = read_excel(sic.read(), 'SIC', SIC_COLUMNS)
            except Invalid as e:
                raise Invalid([f'{sic.filename}: {v}' for v in e.errors])
        elif request.form.get('reuse_sic') != 'true':
            raise Invalid('Adjuntar SIC o marcar la reutilización de SIC vigente')
        try:
            return jsonify(store.publish(b, s, g.actor, 'excel'))
        except Invalid as e:
            names = buk.filename + (f' / {sic.filename}' if sic and sic.filename else '')
            raise Invalid([f'{names}: {v}' for v in e.errors])

    @app.post('/api/batches')
    def batches():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or data.get('schema_version') != 1 or 'buk' not in data:
            raise Invalid('Contrato JSON: schema_version=1 y buk requeridos')
        # Actor derives from authenticated session; supplied actor is never identity proof.
        return jsonify(store.publish(data['buk'], data.get('sic'), g.actor, 'blue-prism', data.get('params_hash')))

    @app.post('/api/recalculate')
    def recalculate():
        with store.lock, store.connect() as db:
            current = db.execute('SELECT v.contracts FROM versions v JOIN publication p ON p.version_id=v.id').fetchone()
            if not current:
                raise Invalid('Primero se debe publicar una carga BUK y SIC')
            return jsonify(store.publish(json.loads(current['contracts']), None, g.actor, 'recalculo'))

    @app.post('/api/demo')
    def demo():
        data = json.loads((BASE / 'examples' / 'lote_base.json').read_text(encoding='utf-8'))
        return jsonify(store.publish(data['buk'], data['sic'], g.actor, 'demo-ficticia'))

    @app.get('/api/templates/<name>')
    def template(name):
        allowed = {'Plantilla_Botathon_2026.xlsx', 'BUK_base_demo.xlsx', 'BUK_cambio_julio.xlsx',
                   'BUK_invalido.xlsx', 'SIC_demo.xlsx'}
        if name not in allowed:
            return jsonify(error='Plantilla desconocida'), 404
        return send_file(BASE / 'examples' / name, as_attachment=True, download_name=name)

    @app.get('/api/export')
    def export():
        snapshot = store.snapshot()
        fields = ['professional_id', 'institute', 'area', 'role', 'month', 'contracted', 'direct',
                  'indirect', 'nas', 'absence', 'planned_direct', 'planned_indirect', 'planned', 'target', 'actual', 'foja']
        output = io.StringIO()
        writer = csv.DictWriter(output, fields, extrasaction='ignore')
        writer.writeheader()
        for row in snapshot['rows']:
            # Neutralize spreadsheet formulas in externally supplied text.
            writer.writerow({k: ("'" + v if isinstance(v, str) and v[:1] in ('=', '+', '-', '@') else v)
                             for k, v in row.items()})
        return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), as_attachment=True,
                         download_name=f'plan_v{snapshot["version"] or 0}.csv', mimetype='text/csv')
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data-dir', default=str(Path.cwd() / 'work' / 'data'))
    parser.add_argument('--demo-dev', action='store_true')
    parser.add_argument('--seed-demo', action='store_true')
    args = parser.parse_args()
    token = os.environ.get('BOTATHON_TOKEN')
    if args.demo_dev:
        token = token or 'demo-local-cambiar'
    if not token:
        parser.error('Definir BOTATHON_TOKEN o usar --demo-dev solo en desarrollo')
    app = create_app(Path(args.data_dir) / 'botathon.sqlite3', token, os.environ.get('BOTATHON_READ_TOKEN'))
    if args.seed_demo and not app.store.snapshot()['version']:
        data = json.loads((BASE / 'examples' / 'lote_base.json').read_text(encoding='utf-8'))
        app.store.publish(data['buk'], data['sic'], source='demo-ficticia')
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    httpd = make_server('127.0.0.1', args.port, app, threaded=True)
    # Local bridge for a bot under the same OS account. Never print the token.
    connection_path = Path(args.data_dir) / 'connection.json'
    fd = os.open(connection_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump({'port': httpd.server_port, 'token': token}, f)
    if os.name != 'nt':
        connection_path.chmod(0o600)
    atexit.register(lambda: connection_path.unlink(missing_ok=True))
    print(json.dumps({'ready': True, 'port': httpd.server_port}), flush=True)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
