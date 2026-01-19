import logging
from typing import List, Dict, Any
from django.db import transaction
from ..models import Dataset

logger = logging.getLogger('django')

class DatasetService:
    @staticmethod
    @transaction.atomic
    def batch_register(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        urls = [i.get('url') for i in items if i.get('url')]
        existing_urls = set(Dataset.objects.filter(url__in=urls).values_list('url', flat=True))
        seen_urls = set()
        to_create = []
        errors = []
        skipped_count = 0

        for i in items:
            url = i.get('url')
            md5 = i.get('expected_md5')
            if not url or not md5:
                errors.append({'url': url or '<missing>', 'error': '缺少必填字段'})
                continue
            if len(md5) != 32:
                errors.append({'url': url, 'error': 'expected_md5必须是32字符'})
                continue
            if url in existing_urls or url in seen_urls:
                errors.append({'url': url, 'error': '数据集地址已存在'})
                skipped_count += 1
                seen_urls.add(url)
                continue
            ds = Dataset(
                url=url,
                expected_md5=md5,
                file_size=i.get('file_size'),
                metadata=i.get('metadata') or {}
            )
            to_create.append(ds)
            seen_urls.add(url)

        if to_create:
            Dataset.objects.bulk_create(to_create)

        datasets_out = [{'id': str(ds.id), 'url': ds.url, 'status': ds.status} for ds in to_create]
        logger.info(f"批量登记数据集: 创建 {len(to_create)}，跳过 {skipped_count}，错误 {len(errors)}")
        return {
            'created_count': len(to_create),
            'skipped_count': skipped_count,
            'datasets': datasets_out,
            'errors': errors
        }

    @staticmethod
    @transaction.atomic
    def reset_dataset(dataset_id: str) -> Dict[str, Any]:
        try:
            ds = Dataset.objects.select_for_update().get(id=dataset_id)
        except Dataset.DoesNotExist:
            return {'ok': False, 'message': '数据集不存在', 'code': 404}
        if ds.status not in [Dataset.Status.FAILED, Dataset.Status.PENDING]:
            return {'ok': False, 'message': '当前状态不可重置', 'code': 400}
        ds.status = Dataset.Status.PENDING
        ds.save(update_fields=['status', 'updated_at'])
        logger.info(f"重置数据集为pending: dataset_id={ds.id} url={ds.url}")
        return {'ok': True, 'dataset': {'id': str(ds.id), 'status': ds.status}}