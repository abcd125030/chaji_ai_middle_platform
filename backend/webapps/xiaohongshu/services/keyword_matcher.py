"""
Keyword matching service for Xiaohongshu notes
"""
import re
import logging
from typing import List

from ..models import MonitorKeyword, XiaohongshuNote

logger = logging.getLogger('django')


def match_keywords(note: XiaohongshuNote) -> List[str]:
    """
    Match note content against active keywords and update note.matched_keywords

    Args:
        note: XiaohongshuNote instance

    Returns:
        List of matched keyword strings
    """
    # Build search text from note content
    search_text = build_search_text(note)

    # Get all active keywords
    active_keywords = MonitorKeyword.objects.filter(is_active=True).order_by('-priority')

    matched_keywords = []
    matched_keyword_objects = []

    for keyword_obj in active_keywords:
        if is_match(keyword_obj, search_text):
            matched_keywords.append(keyword_obj.keyword)
            matched_keyword_objects.append(keyword_obj)

    # Update note's matched_keywords
    if matched_keyword_objects:
        note.matched_keywords.set(matched_keyword_objects)
        logger.info(f'笔记 {note.note_id} 命中关键词: {matched_keywords}')
    else:
        note.matched_keywords.clear()

    return matched_keywords


def build_search_text(note: XiaohongshuNote) -> str:
    """
    Build search text from note content

    Args:
        note: XiaohongshuNote instance

    Returns:
        Combined search text
    """
    parts = []

    # Add description (main content)
    if note.description:
        parts.append(note.description)

    # Add tags
    if note.tags:
        for tag in note.tags:
            if isinstance(tag, str):
                parts.append(tag)

    # Add location
    if note.location:
        parts.append(note.location)

    # Add author name
    if note.author_name:
        parts.append(note.author_name)

    # Add top comments
    if note.top_comments:
        for comment in note.top_comments:
            if isinstance(comment, dict) and 'content' in comment:
                parts.append(comment['content'])
            elif isinstance(comment, str):
                parts.append(comment)

    return ' '.join(parts).lower()


def is_match(keyword_obj: MonitorKeyword, search_text: str) -> bool:
    """
    Check if keyword matches the search text

    Args:
        keyword_obj: MonitorKeyword instance
        search_text: Text to search in (lowercase)

    Returns:
        True if matched, False otherwise
    """
    keyword = keyword_obj.keyword.lower()
    match_type = keyword_obj.match_type

    try:
        if match_type == 'exact':
            # Exact match - keyword must be a complete word/phrase
            # Use word boundaries for Chinese/English
            pattern = rf'(^|[\s\W]){re.escape(keyword)}($|[\s\W])'
            return bool(re.search(pattern, search_text))

        elif match_type == 'contains':
            # Contains match - keyword appears anywhere
            return keyword in search_text

        elif match_type == 'regex':
            # Regex match - use keyword as regex pattern
            try:
                return bool(re.search(keyword, search_text, re.IGNORECASE))
            except re.error as e:
                logger.warning(f'正则表达式错误 (关键词: {keyword_obj.keyword}): {e}')
                return False

        else:
            # Default to contains match
            return keyword in search_text

    except Exception as e:
        logger.error(f'关键词匹配错误 (关键词: {keyword_obj.keyword}): {e}')
        return False


def match_all_notes():
    """
    Re-match all notes against current active keywords
    Useful when keywords are updated
    """
    notes = XiaohongshuNote.objects.all()
    total = notes.count()
    matched_count = 0

    for note in notes:
        matched = match_keywords(note)
        if matched:
            matched_count += 1

    logger.info(f'关键词重新匹配完成: 共{total}条笔记, {matched_count}条命中')
    return {
        'total': total,
        'matched_count': matched_count,
    }
