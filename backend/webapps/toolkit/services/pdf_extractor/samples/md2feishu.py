import os
import requests
import json
from typing import Any, Dict, List, Optional

APP_ID = 'cli_a829678344fa901c' # PDF解析助手这个应用的App ID
APP_SECRET = 'RMeVij5CnH06FYpb0dqc1esKqWMkIvht' # PDF解析助手这个应用的App Secret
OPEN_ID = "ou_328940a82baece3acccefd5dd7fb4b6e" # 我的飞书账号在PDF解析助手中的 open_id；作用是将转换后的文档的所有权变为我的飞书账号，可能需要做成枚举
MAX_LINES = 200  # 因为代码在大文件场景下报错，所以需要将大的markdown文件拆分成多个小文件，每个小文件最多200行。

def get_access_token() -> str:
    try:
        url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
        payload = {'app_id': APP_ID, 'app_secret': APP_SECRET}
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        token = data.get('tenant_access_token')
        if not token:
            raise RuntimeError('未获取到访问令牌')
        return token
    except Exception as e:
        print('获取访问令牌失败:', e)
        raise


def create_document(title: str) -> str:
    try:
        access_token = get_access_token()
        url = 'https://open.feishu.cn/open-apis/docx/v1/documents'
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
        resp = requests.post(url, json={'title': title}, headers=headers)
        if resp.status_code != 200:
            print('创建文档接口返回：', resp.status_code, resp.text)
        resp.raise_for_status()
        data = resp.json()
        document_id = data.get('data', {}).get('document', {}).get('document_id')
        if not document_id:
            raise RuntimeError(f'未获取到 document_id，接口返回：{data}')
        return document_id
    except requests.HTTPError as e:
        try:
            print('创建文档失败详情（JSON）：', e.response.json())
        except Exception:
            print('创建文档失败详情（TEXT）：', e.response.text if e.response else str(e))
        raise
    except Exception as e:
        print('创建文档失败:', e)
        raise


def convert_markdown_to_blocks(markdown: str) -> Dict[str, Any]:
    try:
        access_token = get_access_token()
        url = 'https://open.feishu.cn/open-apis/docx/v1/documents/blocks/convert'
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json; charset=utf-8'}
        payload = {'content': markdown, 'content_type': 'markdown'}
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json().get('data')
        if data is None:
            raise RuntimeError('转换Markdown失败：返回数据为空')
        return data
    except Exception as e:
        print('转换Markdown内容失败:', e)
        raise


def create_nested_blocks(document_id: str, convert_results: List[Dict[str, Any]]) -> None:
    try:
        access_token = get_access_token()
        # 最多只能支持1000个块，超过会报错
        batch_size = 1000

        for convert_result in convert_results:
            blocks: List[Dict[str, Any]] = convert_result.get('blocks', [])
            processed_blocks: List[Dict[str, Any]] = []

            # 清理表格属性中的 merge_info
            for block in blocks:
                if block.get('block_type') == 31 and block.get('table') and block['table'].get('property'):
                    prop = block['table']['property']
                    if 'merge_info' in prop:
                        prop.pop('merge_info', None)
                processed_blocks.append(block)

            block_id_map: Dict[str, str] = {}

            # 分批插入块
            for i in range(0, len(processed_blocks), batch_size):
                batch_blocks = processed_blocks[i:i + batch_size]
                children_id = convert_result.get('first_level_block_ids', [])
                url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/descendant'
                headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
                payload = {'children_id': children_id, 'index': i, 'descendants': batch_blocks}

                try:
                    resp = requests.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                except requests.HTTPError as e:
                    print('创建嵌套块失败：HTTPError，状态码：', e.response.status_code if e.response else '未知')
                    try:
                        print('返回体（JSON）：', e.response.json())
                    except Exception:
                        print('返回体（TEXT）：', e.response.text if e.response else str(e))
                    continue
                except Exception as e:
                    print('创建嵌套块失败：', e)
                    raise

                data = resp.json().get('data', {})
                relations = data.get('block_id_relations', [])
                if relations:
                    for rel in relations:
                        tmp_id = rel.get('temporary_block_id')
                        new_id = rel.get('block_id')
                        if tmp_id and new_id:
                            block_id_map[tmp_id] = new_id

            # 处理图片块（如果有）
            image_map = convert_result.get('block_id_to_image_urls', [])
            if image_map:
                process_image_blocks(document_id, blocks, image_map, block_id_map)
    except Exception as e:
        print('创建嵌套块失败:', e)
        raise



def process_image_blocks(document_id: str,
                         blocks: List[Dict[str, Any]],
                         imageurl: List[Dict[str, Any]],
                         block_id_map: Dict[str, str]) -> None:
    try        :
        access_token = get_access_token()

        for block in blocks:
            if block.get('block_type') == 27 and block.get('image'):
                old_block_id = block.get('block_id')
                new_block_id = block_id_map.get(old_block_id, old_block_id)

                match = next((i for i in imageurl if i.get('block_id') == old_block_id), None)
                image_url = match.get('image_url') if match else None
                if not image_url:
                    continue

                # 图片下载保护：失败则跳过当前块
                try:
                    image_resp = requests.get(image_url, timeout=10)
                    image_resp.raise_for_status()
                    image_bytes = image_resp.content
                except Exception as e:
                    print(f"下载图片失败，跳过：{image_url}，错误：{e}")
                    continue

                url = 'https://open.feishu.cn/open-apis/drive/v1/medias/upload_all'
                headers = {'Authorization': f'Bearer {access_token}'}
                data = {
                    'file_name': 'image.png',
                    'extra': json.dumps({'drive_route_token': document_id}),
                    'parent_type': 'docx_image',
                    'parent_node': new_block_id,
                    'size': str(len(image_bytes)),
                }
                files = {'file': ('image.png', image_bytes)}
                upload_resp = requests.post(url, data=data, files=files, headers=headers)
                upload_resp.raise_for_status()
                upload_data = upload_resp.json()
                print('上传图片响应：', upload_data)

                file_token = upload_data.get('data', {}).get('file_token')
                if not file_token:
                    print('上传图片失败：未获取到 file_token')
                    continue

                patch_url = f'https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{new_block_id}'
                patch_headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
                patch_payload = {'replace_image': {'token': file_token}}
                patch_resp = requests.patch(patch_url, json=patch_payload, headers=patch_headers)
                patch_resp.raise_for_status()
    except Exception as e:
        print('处理图片块失败:', e)
        raise


def transfer_document_owner(document_id: str, open_id: str, member_type: str = 'openid') -> Dict[str, Any]:
    try:
        access_token = get_access_token()
        url = f'https://open.feishu.cn/open-apis/drive/v1/permissions/{document_id}/members/transfer_owner?type=docx'
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
        payload = {'member_type': member_type, 'member_id': open_id}
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            print('转移所有者接口返回：', resp.status_code, resp.text)
        resp.raise_for_status()
        print('文档所有者转移成功！')
        return resp.json()
    except requests.HTTPError as e:
        try:
            print('转移所有者失败详情（JSON）：', e.response.json())
        except Exception:
            print('转移所有者失败详情（TEXT）：', e.response.text if e.response else str(e))
        raise
    except Exception as e:
        print('转移文档所有者失败:', e)
        raise


def markdown_to_doc(title: str, markdowns: List[str], new_owner_open_id: Optional[str] = None) -> str:
    try:
        print('创建文档...')
        document_id = create_document(title)
        print('文档创建成功，ID:', document_id)

        print('转换Markdown内容...')
        convert_results = list()
        for markdown in markdowns:
            convert_result = convert_markdown_to_blocks(markdown)
            convert_results.append(convert_result)
        print('Markdown转换成功！')

        print('创建嵌套块...')
        create_nested_blocks(document_id, convert_results)
        print('嵌套块创建成功！')

        if new_owner_open_id:
            print('转移文档所有权...')
            try:
                transfer_document_owner(document_id, new_owner_open_id, member_type='openid')
            except Exception as e:
                print('转移文档所有权失败，继续返回文档链接。', e)

        return f'https://feishu.cn/docx/{document_id}'
    except Exception as e:
        print('转换失败:', e)
        raise


# 因为https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/descendant在大文件场景下报错
# 所以需要将markdown文件做拆分。

def is_heading(line: str) -> bool:
    s = line.lstrip()
    # Markdown heading starting with '#'
    return s.startswith("#")

def is_blank(line: str) -> bool:
    return line.strip() == ""

def fence_marker(line: str) -> Optional[str]:
    s = line.strip()
    # Detect opening/closing fence lines
    if s.startswith("```"):
        return "```"
    if s.startswith("~~~"):
        return "~~~"
    return None

def split_markdown_lines(lines: List[str], max_lines: int = 200) -> List[str]:
    parts: List[List[str]] = []
    current: List[str] = []
    current_len = 0

    inside_fence = False
    current_fence: Optional[str] = None

    # index within current where we can safely split (prefer headings)
    last_safe_idx: Optional[int] = None

    for line in lines:
        # Update fence state before considering split points
        marker = fence_marker(line)
        if marker:
            if not inside_fence:
                inside_fence = True
                current_fence = marker
            else:
                # Only close if same marker
                if marker == current_fence:
                    inside_fence = False
                    current_fence = None

        # Append line
        current.append(line)
        current_len += 1

        # Update safe split index only when not inside a code fence
        if not inside_fence:
            # Prefer headings; they are better split points so that new part starts at a section
            if is_heading(line):
                # Split before this heading (i.e., current[:idx] stays, current[idx:] goes to next part)
                last_safe_idx = len(current) - 1
            elif is_blank(line):
                # Blank lines are also acceptable split points
                last_safe_idx = len(current)

        # If we exceed limit, split at the last safe point if possible
        if current_len > max_lines:
            if last_safe_idx is not None and last_safe_idx > 0:
                # chunk is everything before last_safe_idx
                chunk = current[:last_safe_idx]
                remainder = current[last_safe_idx:]
                if chunk:
                    parts.append(chunk)
                # Reset current to remainder
                current = remainder
                current_len = len(current)
                # We need to recompute fence state for remainder
                inside_fence = False
                current_fence = None
                last_safe_idx = None
                for rem_line in current:
                    m = fence_marker(rem_line)
                    if m:
                        if not inside_fence:
                            inside_fence = True
                            current_fence = m
                        else:
                            if m == current_fence:
                                inside_fence = False
                                current_fence = None
                    if not inside_fence:
                        if is_heading(rem_line):
                            last_safe_idx = current.index(rem_line)
                            break  # earliest heading is fine
                        elif is_blank(rem_line):
                            last_safe_idx = current.index(rem_line) + 1
                    continue
            else:
                # No safe split yet
                if inside_fence:
                    # Avoid breaking inside code fence: allow overflow until fence closes
                    pass
                else:
                    # Hard split at exact boundary to respect max_lines
                    chunk = current[:max_lines]
                    remainder = current[max_lines:]
                    parts.append(chunk)
                    current = remainder
                    current_len = len(current)
                    # Recompute fence and safe split for remainder
                    inside_fence = False
                    current_fence = None
                    last_safe_idx = None
                    for rem_line in current:
                        m = fence_marker(rem_line)
                        if m:
                            if not inside_fence:
                                inside_fence = True
                                current_fence = m
                            else:
                                if m == current_fence:
                                    inside_fence = False
                                    current_fence = None
                        if not inside_fence:
                            if is_heading(rem_line):
                                last_safe_idx = current.index(rem_line)
                                break
                            elif is_blank(rem_line):
                                last_safe_idx = current.index(rem_line) + 1
                    continue

    if current:
        parts.append(current)

    # 先将每个分块整合成文本，再反转顺序
    parts_text: List[str] = [''.join(chunk) for chunk in parts]
    parts_text.reverse()
    return parts_text


def main(contents: List[str], open_id: Optional[str] = None, title: Optional[str] = None) -> str:
    res = markdown_to_doc(title, contents, open_id)
    return res

# 为了测试效果所写的markdown文件的读取函数
def read_lines_safely(path: str) -> List[str]:
    encodings = ["utf-8", "utf-8-sig", "gbk", "ansi"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc, errors="strict") as f:
                return f.readlines()
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            raise
    # Fallback with replacement to avoid crash
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.readlines()


if __name__ == "__main__":
    BASE_DIR = os.path.dirname(__file__)
    TITLE = "生产操作手册 5、开早打烊流程0620" # 飞书文档的标题
    MD_FILE_PATH = os.path.join(BASE_DIR, "生产操作手册 5、开早打烊流程0620.md")
    lines = read_lines_safely(MD_FILE_PATH)
    contents = split_markdown_lines(lines, max_lines=MAX_LINES)
    url = main(contents, OPEN_ID, TITLE)
    print("文档已创建，访问链接：", url)
