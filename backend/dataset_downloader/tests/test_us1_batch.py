from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from dataset_downloader.models import Dataset

class DatasetBatchAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('dataset_downloader:datasets_batch')

    def test_partial_success_duplicate_in_request(self):
        payload = {
            "datasets": [
                {
                    "url": "https://example.com/data/file1.zip",
                    "expected_md5": "d41d8cd98f00b204e9800998ecf8427e",
                    "file_size": 1048576
                },
                {
                    "url": "https://example.com/data/file1.zip",
                    "expected_md5": "d41d8cd98f00b204e9800998ecf8427e"
                }
            ]
        }
        response = self.client.post(self.url, payload, format='json')
        assert response.status_code == 207
        assert response.data['status'] == 'success'
        assert response.data['code'] == 207
        assert response.data['data']['created_count'] == 1
        assert response.data['data']['skipped_count'] == 1
        assert len(response.data['data']['datasets']) == 1
        assert Dataset.objects.count() == 1
        ds = Dataset.objects.first()
        assert ds.url == "https://example.com/data/file1.zip"
        assert ds.status == Dataset.Status.PENDING

    def test_all_valid_returns_201(self):
        payload = {
            "datasets": [
                {
                    "url": "https://example.com/data/file1.zip",
                    "expected_md5": "d41d8cd98f00b204e9800998ecf8427e"
                },
                {
                    "url": "https://example.com/data/file2.zip",
                    "expected_md5": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
                }
            ]
        }
        response = self.client.post(self.url, payload, format='json')
        assert response.status_code == 201
        assert response.data['status'] == 'success'
        assert response.data['code'] == 201
        assert response.data['data']['created_count'] == 2
        assert response.data['data']['skipped_count'] == 0
        assert Dataset.objects.count() == 2

    def test_invalid_md5_returns_400(self):
        payload = {
            "datasets": [
                {
                    "url": "https://example.com/data/file1.zip",
                    "expected_md5": "abc"
                }
            ]
        }
        response = self.client.post(self.url, payload, format='json')
        assert response.status_code == 400
        assert response.data['status'] == 'error'
        assert response.data['code'] == 400
        assert response.data['data'] is None

    def test_empty_array_returns_400(self):
        payload = {"datasets": []}
        response = self.client.post(self.url, payload, format='json')
        assert response.status_code == 400
        assert response.data['status'] == 'error'
        assert response.data['code'] == 400
        assert response.data['data'] is None

    def test_duplicate_existing_returns_207(self):
        Dataset.objects.create(url="https://example.com/data/file1.zip", expected_md5="d41d8cd98f00b204e9800998ecf8427e")
        payload = {
            "datasets": [
                {
                    "url": "https://example.com/data/file1.zip",
                    "expected_md5": "d41d8cd98f00b204e9800998ecf8427e"
                }
            ]
        }
        response = self.client.post(self.url, payload, format='json')
        assert response.status_code == 207
        assert response.data['status'] == 'success'
        assert response.data['code'] == 207
        assert response.data['data']['created_count'] == 0
        assert response.data['data']['skipped_count'] == 1
        assert Dataset.objects.count() == 1