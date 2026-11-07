"""Ejecutable por Blue Prism: lee Excel/JSON, llama al servicio y escribe estado."""
import argparse
import json
import sys
import http.client
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server.domain import BUK_COLUMNS, SIC_COLUMNS, read_excel, Invalid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--connection', required=True, help='connection.json local; contiene token efímero')
    parser.add_argument('--manifest')
    parser.add_argument('--buk')
    parser.add_argument('--sic')
    parser.add_argument('--reuse-sic', action='store_true')
    parser.add_argument('--status', required=True)
    args = parser.parse_args()
    code = 3
    try:
        connection = json.loads(Path(args.connection).read_text(encoding='utf-8'))
        port = int(connection['port'])
        if not 1 <= port <= 65535:
            raise ValueError('Puerto inválido')
        if args.manifest:
            data = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
        else:
            if not args.buk or not (args.sic or args.reuse_sic):
                raise Invalid('Informar --buk y --sic, o --reuse-sic explícito')
            data = {'schema_version': 1, 'buk': read_excel(Path(args.buk).read_bytes(), 'BUK', BUK_COLUMNS[:8])}
            if args.sic:
                data['sic'] = read_excel(Path(args.sic).read_bytes(), 'SIC', SIC_COLUMNS)
        payload = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
        # Fixed loopback HTTP transport. Avoid proxies and unrelated HTTPS/CA initialization
        # in the frozen executable; no remote hostname is accepted from connection.json.
        client = http.client.HTTPConnection('127.0.0.1', port, timeout=60)
        try:
            client.request('POST', '/api/batches', body=payload, headers={
                'Authorization': f'Bearer {connection["token"]}', 'Content-Type': 'application/json'})
            response = client.getresponse()
            result = json.loads(response.read())
            if response.status >= 400:
                result['status'] = 'rejected' if response.status == 422 else 'failed'
                code = 2 if response.status == 422 else 3
            else:
                code = 0
        finally:
            client.close()
    except Invalid as e:
        result = {'status': 'rejected', 'errors': e.errors}
        code = 2
    except FileNotFoundError as e:
        result = {'status': 'failed', 'error': f'Archivo local no encontrado: {e.filename}'}
    except Exception as e:
        result = {'status': 'failed', 'error': f'{type(e).__name__}: no se pudo procesar el lote local'}
    status = Path(args.status)
    status.parent.mkdir(parents=True, exist_ok=True)
    temp = status.with_suffix(status.suffix + '.tmp')
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(status)
    print(json.dumps({k:v for k,v in result.items() if k != 'token'}, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
