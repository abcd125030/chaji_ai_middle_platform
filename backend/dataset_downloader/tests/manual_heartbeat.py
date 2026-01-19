import argparse
import json
import sys
import requests

def post_json(url, payload):
    try:
        resp = requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f'HTTP error: {e}')
        sys.exit(1)
    print(f'Status: {resp.status_code}')
    try:
        data = resp.json()
    except ValueError:
        print(resp.text)
        sys.exit(1)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return resp.status_code, data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://localhost:8000')
    parser.add_argument('--client-id', default='client-1')
    parser.add_argument('--task-id', default='')
    args = parser.parse_args()

    base = args.base_url.rstrip('/')
    task_id = args.task_id

    if not task_id:
        req_url = base + '/api/dataset-downloader/tasks/request/'
        print('Requesting task...')
        code, resp = post_json(req_url, {'client_id': args.client_id})
        if code != 200 or not resp.get('data'):
            print('No task available')
            sys.exit(0)
        task_id = resp['data']['task_id']

    hb_url = base + f'/api/dataset-downloader/tasks/{task_id}/heartbeat/'
    print(f'Sending heartbeat for task {task_id}...')
    post_json(hb_url, {'client_id': args.client_id})

if __name__ == '__main__':
    main()