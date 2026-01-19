from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from dataset_downloader.models import Dataset, DownloadTask


class QueryAndResetAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_all_datasets_returns_paginated_structure(self):
        ds1 = Dataset.objects.create(url='https://example.com/a.zip', expected_md5='d41d8cd98f00b204e9800998ecf8427e')
        ds2 = Dataset.objects.create(url='https://example.com/b.zip', expected_md5='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', status=Dataset.Status.DOWNLOADING)
        ds3 = Dataset.objects.create(url='https://example.com/c.zip', expected_md5='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', status=Dataset.Status.COMPLETED)

        url = reverse('dataset_downloader:datasets_list')
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data['status'] == 'success'
        data = response.data['data']
        assert data['total'] == 3
        assert data['page'] == 1
        assert data['page_size'] == 20
        ids = {item['id'] for item in data['items']}
        assert str(ds1.id) in ids and str(ds2.id) in ids and str(ds3.id) in ids

    def test_list_datasets_filter_by_status(self):
        ds1 = Dataset.objects.create(url='https://example.com/a.zip', expected_md5='d41d8cd98f00b204e9800998ecf8427e', status=Dataset.Status.PENDING)
        ds2 = Dataset.objects.create(url='https://example.com/b.zip', expected_md5='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', status=Dataset.Status.PENDING)
        Dataset.objects.create(url='https://example.com/c.zip', expected_md5='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', status=Dataset.Status.DOWNLOADING)

        url = reverse('dataset_downloader:datasets_list')
        response = self.client.get(url, {'status': Dataset.Status.PENDING, 'page': 1, 'page_size': 20})
        assert response.status_code == 200
        assert response.data['status'] == 'success'
        data = response.data['data']
        assert data['total'] == 2
        ids = {item['id'] for item in data['items']}
        assert str(ds1.id) in ids and str(ds2.id) in ids

    def test_get_dataset_detail(self):
        ds = Dataset.objects.create(url='https://example.com/a.zip', expected_md5='d41d8cd98f00b204e9800998ecf8427e')
        url = reverse('dataset_downloader:dataset_detail', kwargs={'dataset_id': ds.id})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data['status'] == 'success'
        assert response.data['data']['id'] == str(ds.id)
        assert response.data['data']['url'] == ds.url

    def test_get_task_detail(self):
        ds = Dataset.objects.create(url='https://example.com/a.zip', expected_md5='d41d8cd98f00b204e9800998ecf8427e')
        task = DownloadTask.objects.create(dataset=ds, client_id='client-001', status=DownloadTask.Status.ACTIVE)
        url = reverse('dataset_downloader:task_detail', kwargs={'task_id': task.id})
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data['status'] == 'success'
        assert response.data['data']['id'] == str(task.id)
        assert response.data['data']['dataset_id'] == str(ds.id)

    def test_reset_dataset_allows_failed_and_pending(self):
        ds_failed = Dataset.objects.create(url='https://example.com/f.zip', expected_md5='ffffffffffffffffffffffffffffffff', status=Dataset.Status.FAILED)
        url_failed = reverse('dataset_downloader:dataset_reset', kwargs={'dataset_id': ds_failed.id})
        resp_failed = self.client.post(url_failed)
        assert resp_failed.status_code == 200
        assert resp_failed.data['status'] == 'success'
        ds_failed.refresh_from_db()
        assert ds_failed.status == Dataset.Status.PENDING

        ds_pending = Dataset.objects.create(url='https://example.com/p.zip', expected_md5='eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee', status=Dataset.Status.PENDING)
        url_pending = reverse('dataset_downloader:dataset_reset', kwargs={'dataset_id': ds_pending.id})
        resp_pending = self.client.post(url_pending)
        assert resp_pending.status_code == 200
        assert resp_pending.data['status'] == 'success'
        ds_pending.refresh_from_db()
        assert ds_pending.status == Dataset.Status.PENDING

    def test_reset_dataset_rejects_non_resettable_states(self):
        ds_downloading = Dataset.objects.create(url='https://example.com/d.zip', expected_md5='dddddddddddddddddddddddddddddddd', status=Dataset.Status.DOWNLOADING)
        url = reverse('dataset_downloader:dataset_reset', kwargs={'dataset_id': ds_downloading.id})
        response = self.client.post(url)
        assert response.status_code == 400
        assert response.data['status'] == 'error'