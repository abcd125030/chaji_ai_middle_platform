from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from dataset_downloader.models import Dataset, DownloadTask

class TaskCompleteAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dataset = Dataset.objects.create(
            url='https://example.com/a.zip',
            expected_md5='d41d8cd98f00b204e9800998ecf8427e',
            status=Dataset.Status.DOWNLOADING
        )
        self.task = DownloadTask.objects.create(
            dataset=self.dataset,
            client_id='client-001',
            status=DownloadTask.Status.ACTIVE
        )
        self.url = reverse('dataset_downloader:task_complete', kwargs={'task_id': self.task.id})

    def test_md5_mismatch_marks_failed(self):
        payload = {'client_id': 'client-001', 'actual_md5': 'a' * 32}
        response = self.client.post(self.url, payload, format='json')
        assert response.status_code == 200
        assert response.data['status'] == 'success'
        assert response.data['code'] == 200
        assert response.data['message'] == 'MD5不匹配，任务失败'
        data = response.data['data']
        assert data['task_id'] == str(self.task.id)
        assert data['dataset_id'] == str(self.dataset.id)
        assert data['task_status'] == 'failed'
        assert data['dataset_status'] == 'failed'
        assert data.get('storage_path') is None
        self.dataset.refresh_from_db()
        self.task.refresh_from_db()
        assert self.dataset.status == Dataset.Status.FAILED
        assert self.task.status == DownloadTask.Status.FAILED
        assert self.task.actual_md5 == 'a' * 32
        assert self.task.error_message == 'MD5不匹配'
        assert self.task.completed_at is not None