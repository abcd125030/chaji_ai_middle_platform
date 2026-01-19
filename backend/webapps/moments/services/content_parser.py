"""
飞书公司圈帖子内容解析器

解析富文本二维数组格式，提取纯文本内容

富文本格式说明：
- 外层数组：段落列表
- 内层数组：元素列表
- 元素类型：text(纯文本)、a(超链接)、at(@用户)、hashtag(话题标签)
"""
import json
from typing import List, Dict, Any, Union


class MomentsContentParser:
    """帖子内容解析器"""

    @classmethod
    def parse_to_text(cls, content: Union[str, List[List[Dict[str, Any]]]]) -> str:
        """
        将富文本内容解析为纯文本

        Args:
            content: 富文本二维数组或其 JSON 字符串
                外层: 段落列表
                内层: 元素列表 (text/a/at/hashtag)

        Returns:
            解析后的纯文本，段落间用换行分隔
        """
        # 如果是字符串，尝试解析为 JSON
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                return content  # 解析失败则直接返回原字符串

        if not content:
            return ''

        paragraphs = []

        for paragraph in content:
            if not isinstance(paragraph, list):
                continue

            elements = []
            for element in paragraph:
                if not isinstance(element, dict):
                    continue

                tag = element.get('tag', '')

                if tag == 'text':
                    elements.append(element.get('text', ''))

                elif tag == 'a':
                    text = element.get('text', '')
                    href = element.get('href', '')
                    if href:
                        elements.append(f'{text}({href})')
                    else:
                        elements.append(text)

                elif tag == 'at':
                    user_name = element.get('user_name', '')
                    elements.append(f'@{user_name}' if user_name else '')

                elif tag == 'hashtag':
                    elements.append(element.get('text', ''))

            if elements:
                paragraphs.append(''.join(elements))

        return '\n'.join(paragraphs)

    @classmethod
    def extract_mentions(cls, content: List[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
        """
        提取所有@的用户

        Returns:
            用户列表 [{'user_id': '...', 'user_name': '...'}]
        """
        mentions = []

        for paragraph in content or []:
            for element in paragraph or []:
                if element.get('tag') == 'at':
                    mentions.append({
                        'user_id': element.get('user_id', ''),
                        'user_name': element.get('user_name', '')
                    })

        return mentions

    @classmethod
    def extract_links(cls, content: List[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
        """
        提取所有超链接

        Returns:
            链接列表 [{'text': '...', 'href': '...'}]
        """
        links = []

        for paragraph in content or []:
            for element in paragraph or []:
                if element.get('tag') == 'a':
                    links.append({
                        'text': element.get('text', ''),
                        'href': element.get('href', '')
                    })

        return links

    @classmethod
    def extract_hashtags(cls, content: List[List[Dict[str, Any]]]) -> List[str]:
        """
        提取所有话题标签

        Returns:
            话题列表 ['#话题1', '#话题2']
        """
        hashtags = []

        for paragraph in content or []:
            for element in paragraph or []:
                if element.get('tag') == 'hashtag':
                    hashtags.append(element.get('text', ''))

        return hashtags
