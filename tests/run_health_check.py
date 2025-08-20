import json
import os
import sys
import traceback


def _write_output(content: str):
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'output'))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'test_health.txt')
    with open(out_path, 'w') as f:
        f.write(content)
    print(content)


def main():
    try:
        # Ensure project root is on sys.path so `flask_server` can be imported
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        # Import inside try to capture import errors in output file
        from flask_server import app

        result = {
            'request': {'method': 'GET', 'path': '/health'},
            'response': None,
            'assertions': [],
            'passed': False,
        }
        with app.test_client() as client:
            resp = client.get('/health')
            try:
                data = resp.get_json()
            except Exception:
                data = None
            result['response'] = {
                'status_code': resp.status_code,
                'content_type': resp.content_type,
                'json': data,
            }
            a1 = (resp.status_code == 200)
            a2 = (resp.content_type.startswith('application/json'))
            a3 = (data == {'status': 'healthy'})
            result['assertions'] = [
                {'name': 'status_code_is_200', 'passed': a1},
                {'name': 'content_type_is_json', 'passed': a2},
                {'name': 'body_is_expected', 'passed': a3},
            ]
            result['passed'] = a1 and a2 and a3

        lines = []
        lines.append('HEALTH ENDPOINT TEST')
        lines.append(f"Status Code: {result['response']['status_code']}")
        lines.append(f"Content-Type: {result['response']['content_type']}")
        lines.append(f"JSON: {json.dumps(result['response']['json'])}")
        lines.append('Assertions:')
        for a in result['assertions']:
            lines.append(f" - {a['name']}: {'PASS' if a['passed'] else 'FAIL'}")
        lines.append(f"OVERALL: {'PASS' if result['passed'] else 'FAIL'}")
        _write_output('\n'.join(lines))
    except Exception:
        err_lines = [
            'HEALTH ENDPOINT TEST',
            'ERROR OCCURRED DURING TEST EXECUTION',
            traceback.format_exc(),
        ]
        _write_output('\n'.join(err_lines))


if __name__ == '__main__':
    main()
