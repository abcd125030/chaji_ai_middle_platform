from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch
from datetime import timedelta

from dataset_downloader.services.heartbeat_service import HeartbeatService
from dataset_downloader.models import Dataset, DownloadTask


class HeartbeatServiceTests(TestCase):
    @patch('dataset_downloader.models.SystemConfig.get_heartbeat_timeout', return_value=30)
    def test_timeout_marks_task_and_resets_dataset(self, mock_timeout):
        ds = Dataset.objects.create(
            url='http://example.com/a', expected_md5='a'*32, status=Dataset.Status.DOWNLOADING
        )
        past = timezone.now() - timedelta(seconds=31)
        t = DownloadTask.objects.create(
            dataset=ds, client_id='c1', status=DownloadTask.Status.ACTIVE, last_heartbeat=past
        )

        result = HeartbeatService.check_timeout()

        self.assertEqual(len(result), 1)
        t.refresh_from_db()
        ds.refresh_from_db()
        self.assertEqual(t.status, DownloadTask.Status.TIMEOUT)
        self.assertEqual(ds.status, Dataset.Status.PENDING)
        self.assertEqual(result[0]['task_id'], str(t.id))
        self.assertEqual(result[0]['dataset_id'], str(ds.id))
        self.assertEqual(result[0]['dataset_url'], ds.url)
        self.assertEqual(result[0]['client_id'], t.client_id)
        self.assertEqual(result[0]['last_heartbeat'], past)
        self.assertEqual(result[0]['timeout_seconds'], 30)

    @patch('dataset_downloader.models.SystemConfig.get_heartbeat_timeout', return_value=30)
    def test_recent_heartbeat_not_timeout(self, mock_timeout):
        ds = Dataset.objects.create(
            url='http://example.com/b', expected_md5='b'*32, status=Dataset.Status.DOWNLOADING
        )
        recent = timezone.now() - timedelta(seconds=10)
        t = DownloadTask.objects.create(
            dataset=ds, client_id='c2', status=DownloadTask.Status.ACTIVE, last_heartbeat=recent
        )

        result = HeartbeatService.check_timeout()

        self.assertEqual(len(result), 0)
        t.refresh_from_db()
        ds.refresh_from_db()
        self.assertEqual(t.status, DownloadTask.Status.ACTIVE)
        self.assertEqual(ds.status, Dataset.Status.DOWNLOADING)

    @patch('dataset_downloader.models.SystemConfig.get_heartbeat_timeout', return_value=30)
    def test_none_last_heartbeat_not_timeout(self, mock_timeout):
        ds = Dataset.objects.create(
            url='http://example.com/c', expected_md5='c'*32, status=Dataset.Status.DOWNLOADING
        )
        t = DownloadTask.objects.create(
            dataset=ds, client_id='c3', status=DownloadTask.Status.ACTIVE, last_heartbeat=None
        )

        result = HeartbeatService.check_timeout()

        self.assertEqual(len(result), 0)
        t.refresh_from_db()
        ds.refresh_from_db()
        self.assertEqual(t.status, DownloadTask.Status.ACTIVE)
        self.assertEqual(ds.status, Dataset.Status.DOWNLOADING)

    @patch('dataset_downloader.models.SystemConfig.get_heartbeat_timeout', return_value=45)
    def test_multiple_timeouts(self, mock_timeout):
        ds1 = Dataset.objects.create(
            url='http://example.com/d1', expected_md5='d'*32, status=Dataset.Status.DOWNLOADING
        )
        ds2 = Dataset.objects.create(
            url='http://example.com/d2', expected_md5='e'*32, status=Dataset.Status.DOWNLOADING
        )
        past1 = timezone.now() - timedelta(seconds=50)
        past2 = timezone.now() - timedelta(seconds=46)
        recent = timezone.now() - timedelta(seconds=10)

        t1 = DownloadTask.objects.create(
            dataset=ds1, client_id='c4', status=DownloadTask.Status.ACTIVE, last_heartbeat=past1
        )
        t2 = DownloadTask.objects.create(
            dataset=ds2, client_id='c5', status=DownloadTask.Status.ACTIVE, last_heartbeat=past2
        )
        ds3 = Dataset.objects.create(
            url='http://example.com/d3', expected_md5='f'*32, status=Dataset.Status.DOWNLOADING
        )
        t3 = DownloadTask.objects.create(
            dataset=ds3, client_id='c6', status=DownloadTask.Status.ACTIVE, last_heartbeat=recent
        )

        result = HeartbeatService.check_timeout()

        self.assertEqual(len(result), 2)
        t1.refresh_from_db(); t2.refresh_from_db(); t3.refresh_from_db()
        ds1.refresh_from_db(); ds2.refresh_from_db(); ds3.refresh_from_db()
        self.assertEqual(t1.status, DownloadTask.Status.TIMEOUT)
        self.assertEqual(t2.status, DownloadTask.Status.TIMEOUT)
        self.assertEqual(t3.status, DownloadTask.Status.ACTIVE)
        self.assertEqual(ds1.status, Dataset.Status.PENDING)
        self.assertEqual(ds2.status, Dataset.Status.PENDING)
        self.assertEqual(ds3.status, Dataset.Status.DOWNLOADING)
        tids = {r['task_id'] for r in result}
        self.assertSetEqual(tids, {str(t1.id), str(t2.id)})