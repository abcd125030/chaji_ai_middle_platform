import base64
import logging
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import PDFParseTask, ParseResult
from .serializers import (
    PDFParseTaskSerializer, FileUploadSerializer,
    TaskCreateSerializer, TaskListSerializer, TaskStatusSerializer
)
from .services import MinerUService
from .tasks import process_document_task

logger = logging.getLogger('django')


class PDFParseTaskViewSet(viewsets.ModelViewSet):
    """PDF解析任务视图集"""
    serializer_class = PDFParseTaskSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def get_queryset(self):
        """只返回当前用户的任务"""
        return PDFParseTask.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        """根据动作返回不同的序列化器"""
        if self.action == 'list':
            return TaskListSerializer
        return PDFParseTaskSerializer
    
    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def upload(self, request):
        """上传文件并创建解析任务"""
        serializer = FileUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        file = serializer.validated_data['file']
        parse_method = serializer.validated_data.get('parse_method', 'auto')
        debug_enabled = serializer.validated_data.get('debug_enabled', False)
        
        try:
            # 读取文件内容
            file_bytes = file.read()
            
            # 验证文件
            service = MinerUService()
            is_valid, message, file_ext = service.validate_file(file_bytes)
            if not is_valid:
                return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
            
            # 创建任务记录
            task = PDFParseTask.objects.create(
                user=request.user,
                original_filename=file.name,
                file_type=file_ext,
                file_size=len(file_bytes),
                parse_method=parse_method,
                debug_enabled=debug_enabled,
                status='pending'
            )
            
            # 保存文件
            file_path = service.save_uploaded_file(
                file_bytes, file.name, str(task.task_id)
            )
            task.file_path = file_path
            task.save()
            
            # 异步处理任务
            process_document_task.delay(str(task.task_id))
            
            return Response(
                PDFParseTaskSerializer(task).data,
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}")
            return Response(
                {'error': f'文件处理失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """查询任务状态"""
        task = self.get_object()
        
        # 计算进度
        progress = 0
        message = ""
        
        if task.status == 'pending':
            progress = 0
            message = "任务等待处理"
        elif task.status == 'processing':
            progress = 50
            message = "正在处理中..."
        elif task.status == 'completed':
            progress = 100
            message = "处理完成"
        elif task.status == 'failed':
            progress = 0
            message = task.error_message or "处理失败"
        
        data = {
            'task_id': task.task_id,
            'status': task.status,
            'status_display': task.get_status_display(),
            'progress': progress,
            'message': message
        }
        
        # 如果任务完成，包含结果
        if task.status == 'completed' and hasattr(task, 'result'):
            from .serializers import ParseResultSerializer
            data['result'] = ParseResultSerializer(task.result).data
        
        return Response(data)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """下载解析结果文件"""
        task = self.get_object()
        
        if task.status != 'completed':
            return Response(
                {'error': '任务尚未完成'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取请求的文件类型
        file_type = request.query_params.get('type', 'markdown')
        
        try:
            if file_type == 'markdown' and task.result.markdown_path:
                file_path = task.result.markdown_path
                filename = f"{task.task_id}.md"
            elif file_type == 'json' and task.result.json_path:
                file_path = task.result.json_path
                filename = f"{task.task_id}.json"
            else:
                raise Http404("文件不存在")
            
            response = FileResponse(
                open(file_path, 'rb'),
                as_attachment=True,
                filename=filename
            )
            return response
            
        except Exception as e:
            logger.error(f"文件下载失败: {str(e)}")
            raise Http404("文件不存在")
    
    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        """重新处理任务"""
        task = self.get_object()
        
        if task.status == 'processing':
            return Response(
                {'error': '任务正在处理中'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 重置任务状态
        task.status = 'pending'
        task.error_message = None
        task.processing_time = None
        task.completed_at = None
        task.save()
        
        # 删除旧的结果
        if hasattr(task, 'result'):
            task.result.delete()
        
        # 重新提交任务
        process_document_task.delay(str(task.task_id))
        
        return Response({'message': '任务已重新提交'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_task_from_base64(request):
    """通过 Base64 编码的文件创建任务"""
    serializer = TaskCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # 解码文件
        file_base64 = serializer.validated_data['file_base64']
        file_bytes = base64.b64decode(file_base64)
        
        # 验证文件
        service = MinerUService()
        is_valid, message, file_ext = service.validate_file(file_bytes)
        if not is_valid:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
        
        # 创建任务
        task = PDFParseTask.objects.create(
            user=request.user,
            original_filename=serializer.validated_data['filename'],
            file_type=file_ext,
            file_size=len(file_bytes),
            parse_method=serializer.validated_data.get('parse_method', 'auto'),
            debug_enabled=serializer.validated_data.get('debug_enabled', False),
            status='pending'
        )
        
        # 保存文件
        file_path = service.save_uploaded_file(
            file_bytes, task.original_filename, str(task.task_id)
        )
        task.file_path = file_path
        task.save()
        
        # 异步处理
        process_document_task.delay(str(task.task_id))
        
        return Response(
            PDFParseTaskSerializer(task).data,
            status=status.HTTP_201_CREATED
        )
        
    except Exception as e:
        logger.error(f"Base64任务创建失败: {str(e)}")
        return Response(
            {'error': f'任务创建失败: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
