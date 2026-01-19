"""
Þf‡cÆKÕ

KÕ†Ö
- P1: ê¨Þf‡c
- P2: Þf‡cCPlû
- P3: lb1%
"""
import logging
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, Mock
from pathlib import Path
import tempfile

from webapps.toolkit.services.feishu_document import FeishuDocumentService
from webapps.toolkit.services.feishu_document.components.feishu_token_manager import FeishuTokenManager
from webapps.toolkit.services.feishu_document.components.markdown_segmentor import MarkdownSegmentor
from webapps.toolkit.services.feishu_document.components.feishu_permission_manager import FeishuPermissionManager

User = get_user_model()
logger = logging.getLogger('django')


class FeishuIntegrationTestCase(TestCase):
    """Þf‡cÆKÕ(‹"""

    @classmethod
    def setUpTestData(cls):
        """¾nKÕpn@	KÕ¹Õq«	"""
        # úKÕ(7sTÞf&÷	
        cls.user_with_feishu = User.objects.create_user(
            username='test_user_with_feishu',
            email='test@example.com',
            password='testpass123',
            external_id='ou_test_open_id_123'  # !ßÞfOpen ID
        )

        # úKÕ(7*sTÞf&÷	
        cls.user_without_feishu = User.objects.create_user(
            username='test_user_without_feishu',
            email='test2@example.com',
            password='testpass123',
            external_id=''  # *sTÞf
        )

    def test_user_without_feishu_account(self):
        """KÕ(‹T020 - (7*sTÞf&÷"""
        logger.info("KÕ(7*sTÞf&÷")

        service = FeishuDocumentService()

        # ú4öMarkdown‡ö
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test Markdown\n\nThis is a test.")
            temp_md_path = f.name

        try:
            result = service.convert_markdown_to_feishu(
                task_id='test_task_id',
                user=self.user_without_feishu,
                markdown_path=temp_md_path
            )

            # ŒÁ”åÔÞNone
            self.assertIsNone(result, "(7*sTÞf&÷ö”ÔÞNone")
            logger.info(" KÕÇ(7*sTÞf&÷öcnóÇ")

        finally:
            Path(temp_md_path).unlink(missing_ok=True)

    def test_markdown_segmentation(self):
        """KÕ(‹T008 - Markdownµ;‘"""
        logger.info("KÕMarkdownµ;‘")

        # KÕ:o1Ž200L
        lines_small = [f"Line {i}\n" for i in range(100)]
        segments_small = MarkdownSegmentor.split_markdown_lines(lines_small, max_lines=200)
        self.assertEqual(len(segments_small), 1, "Ž200L”:1µ")

        # KÕ:o2…Ç200L
        lines_large = [f"Line {i}\n" for i in range(300)]
        segments_large = MarkdownSegmentor.split_markdown_lines(lines_large, max_lines=200)
        self.assertGreaterEqual(len(segments_large), 2, "…Ç200L”ó:2µ")

        logger.info(" KÕÇMarkdownµ;‘cn")

    @patch('webapps.toolkit.services.feishu_document.components.feishu_permission_manager.requests.post')
    def test_permission_transfer_success(self, mock_post):
        """KÕ(‹T019 - CPlûŸ"""
        logger.info("KÕCPlûŸ")

        # MockCPlûAPIÔÞŸ
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "msg": "success"}
        mock_post.return_value = mock_response

        # ŒÁ”åÔÞTrue
        result = FeishuPermissionManager.transfer_document_owner(
            token='test_token',
            document_id='test_doc_id',
            open_id='test_open_id'
        )
        self.assertTrue(result, "CPlûŸö”ÔÞTrue")
        logger.info(" KÕÇCPlûŸ")

    @patch('webapps.toolkit.services.feishu_document.components.feishu_permission_manager.requests.post')
    def test_permission_transfer_failure(self, mock_post):
        """KÕ(‹T019 - CPlû1%"""
        logger.info("KÕCPlû1%")

        # MockCPlûAPIÔÞï
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = '{"code": 403, "msg": "Forbidden"}'
        mock_response.raise_for_status.side_effect = Exception("HTTP 403 Forbidden")
        mock_post.return_value = mock_response

        # ŒÁ”åÔÞFalse
        result = FeishuPermissionManager.transfer_document_owner(
            token='test_token',
            document_id='test_doc_id',
            open_id='test_open_id'
        )
        self.assertFalse(result, "CPlû1%ö”ÔÞFalse")
        logger.info(" KÕÇCPlû1%öcnÔÞFalse")
