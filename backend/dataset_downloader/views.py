import logging
import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import DatasetBatchSerializer, TaskRequestSerializer, TaskResponseSerializer, HeartbeatSerializer, TaskCompleteSerializer, TaskCompleteResponseSerializer, DatasetSerializer, DatasetListSerializer, TaskDetailSerializer
from .services.dataset_service import DatasetService
from .services.task_service import TaskService
from .services.heartbeat_service import HeartbeatService
from .models import Dataset, DownloadTask

logger = logging.getLogger('django')

class DatasetBatchCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = DatasetBatchSerializer(data=request.data)
        if not serializer.is_valid():
            error_msg = '请求参数错误'
            try:
                if 'datasets' in serializer.errors:
                    err = serializer.errors['datasets']
                    if isinstance(err, list) and err:
                        error_msg = str(err[0])
            except Exception:
                pass
            return Response({'status': 'error', 'data': None, 'message': error_msg, 'code': 400}, status=status.HTTP_400_BAD_REQUEST)

        items = serializer.validated_data['datasets']
        result = DatasetService.batch_register(items)
        created_count = result.get('created_count', 0)
        skipped_count = result.get('skipped_count', 0)
        errors = result.get('errors', [])

        if created_count > 0 and not errors:
            status_code = status.HTTP_201_CREATED
        elif created_count > 0 or skipped_count > 0:
            status_code = 207
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        message = f"成功登记{created_count}个数据集" + (f"，{skipped_count}个被跳过" if skipped_count > 0 else '')
        response_body = {
            'status': 'success' if status_code != status.HTTP_400_BAD_REQUEST else 'error',
            'data': {
                'created_count': created_count,
                'skipped_count': skipped_count,
                'datasets': result.get('datasets', []),
                'errors': errors
            } if status_code != status.HTTP_400_BAD_REQUEST else None,
            'message': message if status_code != status.HTTP_400_BAD_REQUEST else (errors[0]['error'] if errors else '请求参数错误'),
            'code': status_code
        }
        logger.info(f"/api/dataset-downloader/datasets/batch/ 批量登记: {response_body['message']} (created={created_count}, skipped={skipped_count}, errors={len(errors)})")
        return Response(response_body, status=status_code)

class TaskRequestView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = TaskRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'status': 'error', 'data': None, 'message': '请求参数错误', 'code': 400}, status=status.HTTP_400_BAD_REQUEST)

        client_id = serializer.validated_data['client_id']
        result = TaskService.request_task(client_id)

        if not result:
            logger.info(f"/api/dataset-downloader/tasks/request/ 无可用任务 (client_id={client_id})")
            return Response({'status': 'success', 'data': None, 'message': '无可用任务', 'code': 200}, status=status.HTTP_200_OK)

        resp_serializer = TaskResponseSerializer(data=result)
        resp_serializer.is_valid(raise_exception=True)
        response_body = {
            'status': 'success',
            'data': resp_serializer.validated_data,
            'message': '任务分发成功',
            'code': 200
        }
        logger.info(f"/api/dataset-downloader/tasks/request/ 分发任务: task_id={result['task_id']} dataset_url={result['dataset']['url']} client_id={client_id}")
        return Response(response_body, status=status.HTTP_200_OK)

class TaskHeartbeatView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, task_id, *args, **kwargs):
        serializer = HeartbeatSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'status': 'error', 'data': None, 'message': '请求参数错误', 'code': 400}, status=status.HTTP_400_BAD_REQUEST)
        client_id = serializer.validated_data['client_id']
        result = HeartbeatService.receive_heartbeat(task_id=str(task_id), client_id=client_id)
        if not result['ok']:
            code = result.get('code', 400)
            return Response({'status': 'error', 'data': None, 'message': result['message'], 'code': code}, status=code)
        response_body = {
            'status': 'success',
            'data': {'task_id': str(task_id), 'last_heartbeat': result['last_heartbeat'].isoformat()},
            'message': '心跳已更新',
            'code': 200
        }
        logger.info(f"/api/dataset-downloader/tasks/{task_id}/heartbeat/ 心跳更新 (client_id={client_id})")
        return Response(response_body, status=status.HTTP_200_OK)

class TaskCompleteView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, task_id, *args, **kwargs):
        serializer = TaskCompleteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'status': 'error', 'data': None, 'message': '请求参数错误', 'code': 400}, status=status.HTTP_400_BAD_REQUEST)
        client_id = serializer.validated_data['client_id']
        actual_md5 = serializer.validated_data['actual_md5']
        storage_path = serializer.validated_data.get('storage_path')
        result = TaskService.complete_task(task_id=str(task_id), client_id=client_id, actual_md5=actual_md5, storage_path=storage_path)
        if not result['ok']:
            code = result.get('code', 400)
            return Response({'status': 'error', 'data': None, 'message': result['message'], 'code': code}, status=code)
        resp_serializer = TaskCompleteResponseSerializer(data=result['result'])
        resp_serializer.is_valid(raise_exception=True)
        task_status = resp_serializer.validated_data['task_status']
        message = '任务完成' if task_status == 'completed' else 'MD5不匹配，任务失败'
        response_body = {
            'status': 'success',
            'data': resp_serializer.validated_data,
            'message': message,
            'code': 200
        }
        logger.info(f"/api/dataset-downloader/tasks/{task_id}/complete/ 任务完成状态: {task_status} (client_id={client_id})")
        return Response(response_body, status=status.HTTP_200_OK)

class DatasetListView(APIView):
    """
    GET /datasets/ 分页查询，支持状态过滤
    Query Params:
    - status: pending|downloading|completed|failed (可选)
    - page: 页码，默认1
    - page_size: 每页数量，默认20
    Response: { items, page, page_size, total }
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        status_filter = request.query_params.get('status')
        qs = Dataset.objects.all()
        if status_filter in {Dataset.Status.PENDING, Dataset.Status.DOWNLOADING, Dataset.Status.COMPLETED, Dataset.Status.FAILED}:
            qs = qs.filter(status=status_filter)
        total = qs.count()
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        start = (page - 1) * page_size
        end = start + page_size
        items = qs.order_by('-created_at')[start:end]
        serializer = DatasetListSerializer(items, many=True)
        data = {
            'items': serializer.data,
            'page': page,
            'page_size': page_size,
            'total': total
        }
        return Response({'status': 'success', 'data': data, 'message': '查询成功', 'code': 200}, status=status.HTTP_200_OK)

class DatasetDetailView(APIView):
    """
    GET /datasets/{id}/ 单个查询
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, dataset_id, *args, **kwargs):
        try:
            ds = Dataset.objects.get(id=dataset_id)
        except Dataset.DoesNotExist:
            return Response({'status': 'error', 'data': None, 'message': '数据集不存在', 'code': 404}, status=status.HTTP_404_NOT_FOUND)
        serializer = DatasetSerializer(ds)
        return Response({'status': 'success', 'data': serializer.data, 'message': '查询成功', 'code': 200}, status=status.HTTP_200_OK)

class TaskDetailView(APIView):
    """
    GET /tasks/{id}/ 查询任务状态
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, task_id, *args, **kwargs):
        try:
            task = DownloadTask.objects.get(id=task_id)
        except DownloadTask.DoesNotExist:
            return Response({'status': 'error', 'data': None, 'message': '任务不存在', 'code': 404}, status=status.HTTP_404_NOT_FOUND)
        serializer = TaskDetailSerializer(task)
        return Response({'status': 'success', 'data': serializer.data, 'message': '查询成功', 'code': 200}, status=status.HTTP_200_OK)

class DatasetResetView(APIView):
    """
    POST /datasets/{id}/reset/ 重置为 pending 状态
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request, dataset_id, *args, **kwargs):
        result = DatasetService.reset_dataset(dataset_id=str(dataset_id))
        if not result['ok']:
            code = result.get('code', 400)
            return Response({'status': 'error', 'data': None, 'message': result['message'], 'code': code}, status=code)
        return Response({'status': 'success', 'data': result['dataset'], 'message': '重置成功', 'code': 200}, status=status.HTTP_200_OK)


class TaskStatusView(APIView):
    """
    API状态查询
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        logger.debug(f"/api/dataset-downloader/status/ API状态查询 - IP: {request.META.get('REMOTE_ADDR')}")
        return Response({
            "status": "healthy",
            "service": "Dataset Downloader API",
            "version": "1.0.2",
            "timestamp": int(time.time())
        }, status=status.HTTP_200_OK)
