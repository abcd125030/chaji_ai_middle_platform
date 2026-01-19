"""
Note analysis service for Xiaohongshu sentiment monitoring
Reuses the sentiment analysis capability from customized.customization module
"""
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

from django.utils import timezone

from ..models import XiaohongshuNote, NoteAnalysisResult

logger = logging.getLogger('django')


class NoteAnalyzer:
    """
    Xiaohongshu note analyzer
    Integrates with the existing sentiment analysis service
    """

    # Category mapping from analysis result
    CATEGORY_MAP = {
        '类别1': 'category_1',
        '类别2': 'category_2',
        '类别3': 'category_3',
        '类别4': 'category_4',
        '其他': 'other',
        'category_1': 'category_1',
        'category_2': 'category_2',
        'category_3': 'category_3',
        'category_4': 'category_4',
        'other': 'other',
    }

    def __init__(self):
        pass

    def analyze_note(
        self,
        note: XiaohongshuNote,
        llm_model_dict: Dict[str, Any],
        service_target: str,
        user_id: int,
    ) -> Dict[str, Any]:
        """
        Analyze a single note

        Args:
            note: XiaohongshuNote instance
            llm_model_dict: Available LLM model configurations
            service_target: Service target identifier
            user_id: User ID

        Returns:
            Analysis result dictionary
        """
        start_time = time.time()

        try:
            # Update note status
            note.status = 'analyzing'
            note.save(update_fields=['status'])

            # Prepare content for analysis
            content = self._prepare_content(note)

            # Call sentiment analysis service
            from customized.customization.public_opionion_analysis_service import analysis

            # Prepare payload in the format expected by the analysis service
            payload = {
                'task_id': note.note_id,
                'content': content,
                'im_body': note.images[:3] if note.images else [],  # max 3 images
            }

            # Call analysis
            result = analysis(
                payload=payload,
                input_model_dict=llm_model_dict,
                service_target=service_target,
                user_id=user_id,
                task_input_cache={},
                task_input_cache_lock=None,
            )

            # Parse and save result
            duration = time.time() - start_time
            analysis_result = self._save_analysis_result(note, result, duration)

            # Update note status
            note.status = 'completed'
            note.save(update_fields=['status'])

            return {
                'success': True,
                'note_id': note.note_id,
                'category': analysis_result.category,
                'sentiment': analysis_result.sentiment,
                'risk_score': analysis_result.risk_score,
                'reason': analysis_result.reason,
                'duration': duration,
            }

        except Exception as e:
            logger.error(f'笔记分析失败 (note_id: {note.note_id}): {e}')

            # Update note status
            note.status = 'failed'
            note.save(update_fields=['status'])

            return {
                'success': False,
                'note_id': note.note_id,
                'error': str(e),
            }

    def _prepare_content(self, note: XiaohongshuNote) -> str:
        """
        Prepare note content for analysis

        Args:
            note: XiaohongshuNote instance

        Returns:
            Formatted content string
        """
        parts = []

        # Add main content
        if note.description:
            parts.append(note.description)

        # Add tags
        if note.tags:
            tags_str = ' '.join(note.tags) if isinstance(note.tags, list) else str(note.tags)
            parts.append(f'标签: {tags_str}')

        # Add location if relevant
        if note.location and note.location not in ['刚刚', '分钟前', '小时前']:
            parts.append(f'位置: {note.location}')

        return '\n'.join(parts)

    def _save_analysis_result(
        self,
        note: XiaohongshuNote,
        result: Dict[str, Any],
        duration: float,
    ) -> NoteAnalysisResult:
        """
        Save analysis result to database

        Args:
            note: XiaohongshuNote instance
            result: Analysis result from LLM
            duration: Analysis duration in seconds

        Returns:
            NoteAnalysisResult instance
        """
        # Parse category from result
        raw_category = result.get('category', result.get('结论', 'other'))
        category = self.CATEGORY_MAP.get(raw_category, 'other')

        # Determine sentiment based on category
        if category in ['category_1', 'category_2', 'category_3', 'category_4']:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

        # Calculate risk score based on category
        risk_scores = {
            'category_1': 80,  # Negative public opinion
            'category_2': 90,  # Data leak risk
            'category_3': 85,  # Gray/black market
            'category_4': 75,  # Proxy ordering
            'other': 20,       # Others
        }
        risk_score = risk_scores.get(category, 50)

        # Get reason
        reason = result.get('reason', result.get('原因', ''))

        # Create or update analysis result
        analysis_result, created = NoteAnalysisResult.objects.update_or_create(
            note=note,
            defaults={
                'category': category,
                'sentiment': sentiment,
                'risk_score': risk_score,
                'reason': reason,
                'image_analysis': result.get('image_analysis', []),
                'llm_response': result,
                'model_used': result.get('model', ''),
                'input_tokens': result.get('input_tokens', 0),
                'output_tokens': result.get('output_tokens', 0),
                'analysis_duration': duration,
            }
        )

        return analysis_result

    def batch_analyze(
        self,
        note_ids: List[str],
        llm_model_dict: Dict[str, Any],
        service_target: str,
        user_id: int,
    ) -> Dict[str, Any]:
        """
        Batch analyze multiple notes

        Args:
            note_ids: List of note IDs to analyze
            llm_model_dict: Available LLM model configurations
            service_target: Service target identifier
            user_id: User ID

        Returns:
            Batch analysis result summary
        """
        results = []
        success_count = 0
        failed_count = 0

        for note_id in note_ids:
            try:
                note = XiaohongshuNote.objects.get(note_id=note_id)
                result = self.analyze_note(note, llm_model_dict, service_target, user_id)
                results.append(result)

                if result.get('success'):
                    success_count += 1
                else:
                    failed_count += 1

            except XiaohongshuNote.DoesNotExist:
                results.append({
                    'success': False,
                    'note_id': note_id,
                    'error': '笔记不存在',
                })
                failed_count += 1

        return {
            'total': len(note_ids),
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results,
        }


# Module-level instance for convenience
note_analyzer = NoteAnalyzer()
