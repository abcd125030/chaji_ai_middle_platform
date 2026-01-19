from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from django.utils import timezone
from dataset_downloader.models import Dataset, DownloadTask, SystemConfig

class TaskRequestAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('dataset_downloader:tasks_request')

    def test_no_available_task_returns_success_with_none(self):
        response = self.client.post(self.url, {'client_id': 'client-001'}, format='json')
        assert response.status_code == 200
        assert response.data['status'] == 'success'
        assert response.data['code'] == 200
        assert response.data['data'] is None

    def test_assigns_oldest_pending_fifo_and_updates_status(self):
        ds1 = Dataset.objects.create(url='https://example.com/a.zip', expected_md5='d41d8cd98f00b204e9800998ecf8427e')
        ds2 = Dataset.objects.create(url='https://example.com/b.zip', expected_md5='a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4')
        earlier = timezone.now() - timezone.timedelta(seconds=60)
        Dataset.objects.filter(id=ds1.id).update(created_at=earlier)
        ds1 = Dataset.objects.get(id=ds1.id)

        response1 = self.client.post(self.url, {'client_id': 'client-001'}, format='json')
        assert response1.status_code == 200
        assert response1.data['status'] == 'success'
        assert 'task_id' in response1.data['data']
        assert response1.data['data']['dataset']['id'] == str(ds1.id)

        ds1.refresh_from_db()
        ds2.refresh_from_db()
        assert ds1.status == Dataset.Status.DOWNLOADING
        assert ds2.status == Dataset.Status.PENDING
        assert DownloadTask.objects.count() == 1
        task1 = DownloadTask.objects.order_by('created_at').first()
        assert task1.client_id == 'client-001'
        assert str(task1.dataset_id) == str(ds1.id)

        response2 = self.client.post(self.url, {'client_id': 'client-002'}, format='json')
        assert response2.status_code == 200
        assert response2.data['data']['dataset']['id'] == str(ds2.id)
        ds2.refresh_from_db()
        assert ds2.status == Dataset.Status.DOWNLOADING
        task2 = DownloadTask.objects.order_by('created_at').last()
        assert task2.client_id == 'client-002'
        assert str(task2.dataset_id) == str(ds2.id)

        response3 = self.client.post(self.url, {'client_id': 'client-003'}, format='json')
        assert response3.status_code == 200
        assert response3.data['data'] is None

    def test_requires_client_id(self):
        response = self.client.post(self.url, {}, format='json')
        assert response.status_code == 400
        assert response.data['status'] == 'error'
        assert response.data['code'] == 400

    def test_heartbeat_defaults_and_config_override(self):
        SystemConfig.objects.create(key='heartbeat_interval_seconds', value='20')
        SystemConfig.objects.create(key='heartbeat_timeout_seconds', value='45')
        Dataset.objects.create(url='https://example.com/c.zip', expected_md5='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
        response = self.client.post(self.url, {'client_id': 'client-001'}, format='json')
        assert response.status_code == 200
        assert response.data['data']['heartbeat_interval_seconds'] == 20
        assert response.data['data']['heartbeat_timeout_seconds'] == 45

    def test_ignores_non_pending_datasets(self):
        Dataset.objects.create(url='https://example.com/d.zip', expected_md5='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', status=Dataset.Status.DOWNLOADING)
        ds_pending = Dataset.objects.create(url='https://example.com/e.zip', expected_md5='cccccccccccccccccccccccccccccccc')
        response = self.client.post(self.url, {'client_id': 'client-001'}, format='json')
        assert response.status_code == 200
        assert response.data['data']['dataset']['id'] == str(ds_pending.id)