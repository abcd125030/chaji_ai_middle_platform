import argparse
import json
import sys
import requests

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://localhost:8000')
    parser.add_argument('--client-id', default='client-1')
    args = parser.parse_args()

    url = args.base_url.rstrip('/') + '/api/dataset-downloader/tasks/request/'
    try:
        resp = requests.post(url, json={'client_id': args.client_id}, timeout=10)
    except Exception as e:
        print(f'HTTP error: {e}')
        sys.exit(1)

    print(f'Status: {resp.status_code}')
    try:
        payload = resp.json()
    except ValueError:
        print(resp.text)
        sys.exit(1)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload.get('status') == 'success' and payload.get('data'):
        task_id = payload['data']['task_id']
        ds = payload['data']['dataset']
        print(f"OK task_id={task_id} url={ds.get('url')}")
    else:
        print('No task available')

if __name__ == '__main__':
    main()