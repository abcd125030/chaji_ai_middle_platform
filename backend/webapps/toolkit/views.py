"""
工具集应用视图
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.uploadedfile import UploadedFile
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .services import DocumentProcessorService, PDFExtractorService
from .models import PDFExtractorTask
from .utils import FileManager, RequestValidator, TaskProgressManager
from .tasks import process_pdf_extraction

logger = logging.getLogger('django')

# 懒加载服务实例（避免模块加载时的重复初始化）
_document_processor = None
_pdf_extractor_service = None


def get_document_processor():
    """获取文档处理器服务实例（懒加载）"""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessorService()
    return _document_processor


def get_pdf_extractor_service():
    """获取PDF提取器服务实例（懒加载）"""
    global _pdf_extractor_service
    if _pdf_extractor_service is None:
        _pdf_extractor_service = PDFExtractorService()
    return _pdf_extractor_service


@api_view(['GET'])
def get_supported_formats(request):
    """
    获取支持的文档格式列表

    Returns:
        支持的格式信息
    """
    try:
        formats_info = get_document_processor().get_supported_formats()
        return Response({
            'status': 'success',
            'data': formats_info,
            'code': 200
        })
    except Exception as e:
        logger.error(f"获取支持格式失败: {str(e)}")
        return Response({
            'status': 'error',
            'message': '获取支持格式失败',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def upload_pdf_documents(request):
    """
    接收PDF文档列表并创建提取任务

    Request:
        - files: PDF文件列表，每个文件包含：
          - filename: 原始文件名
          - data: base64编码的文件数据

    Returns:
        创建的任务UUID列表
    """
    try:
        # 1. 获取当前用户
        user = request.user
        if not user.is_authenticated:
            return Response({
                'status': 'error',
                'message': '用户未登录',
                'code': 401
            }, status=status.HTTP_401_UNAUTHORIZED)

        # 2. 接收并验证请求数据
        files = request.data.get('files', [])

        # 3. 验证文件列表
        is_valid, error_msg = RequestValidator.validate_file_list(files)
        if not is_valid:
            return Response({
                'status': 'error',
                'message': error_msg,
                'code': 400
            }, status=status.HTTP_400_BAD_REQUEST)

        # 4. 确保基础目录存在
        FileManager.ensure_directory(FileManager.EXTRACTOR_BASE_DIR)

        task_ids = []

        # 5. 为每个PDF文件创建任务
        for file_info in files:
            original_filename = file_info.get('filename', 'unknown.pdf')
            file_data = file_info.get('data', '')

            # 获取翻译和页码范围参数
            translate = file_info.get('translate', False)
            target_language = file_info.get('target_language', 'zh')
            page_range_start = file_info.get('page_range_start')
            page_range_end = file_info.get('page_range_end')

            # 创建PDFExtractorTask数据库记录，关联到当前用户
            task = PDFExtractorTask.objects.create(
                user=user,
                original_filename=original_filename,
                file_path='',  # 稍后更新
                status='pending',
                translate=translate,
                target_language=target_language,
                page_range_start=page_range_start,
                page_range_end=page_range_end
            )

            # 为任务创建专属目录
            task_dir = FileManager.create_task_directory(str(task.id))

            # 保存base64文件到任务目录，使用UUID作为文件名
            file_path = FileManager.save_base64_file(file_data, f"{task.id}.pdf", task_dir)

            # 更新任务记录的文件路径
            task.file_path = file_path
            task.save()

            # 提交Celery异步任务到pdf_extractor队列
            process_pdf_extraction.apply_async(
                args=[str(task.id), file_path],
                queue='pdf_extractor'
            )

            task_ids.append(str(task.id))
            logger.info(f"创建PDF提取任务: {task.id}, 文件: {original_filename}, 已发送到pdf_extractor队列")

        return Response({
            'status': 'success',
            'data': {
                'task_ids': task_ids,
                'message': f'成功创建{len(task_ids)}个任务'
            },
            'code': 200
        })

    except Exception as e:
        logger.error(f"上传PDF文档失败: {str(e)}", exc_info=True)
        return Response({
            'status': 'error',
            'message': f'上传失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def query_task_progress(request):
    """
    查询任务处理进度（仅返回当前用户的任务）

    Request:
        - task_ids: 任务UUID列表（最多20个）

    Returns:
        任务进度信息列表
    """
    try:
        # 1. 获取当前用户
        user = request.user
        if not user.is_authenticated:
            return Response({
                'status': 'error',
                'message': '用户未登录',
                'code': 401
            }, status=status.HTTP_401_UNAUTHORIZED)

        # 2. 接收任务UUID列表
        task_ids = request.data.get('task_ids', [])

        # 3. 验证列表
        is_valid, error_msg = RequestValidator.validate_task_ids(task_ids)
        if not is_valid:
            return Response({
                'status': 'error',
                'message': error_msg,
                'code': 400
            }, status=status.HTTP_400_BAD_REQUEST)

        # 4. 查询每个任务的进度（仅限当前用户的任务）
        tasks_progress = []

        for task_id in task_ids:
            try:
                # 从数据库获取任务基本信息，仅限当前用户的任务
                task = PDFExtractorTask.objects.get(id=task_id, user=user)

                # 读取task.json文件获取详细进度
                task_json_path = FileManager.get_task_json_path(str(task.id))
                pages_info = []

                if task_json_path.exists():
                    try:
                        with open(task_json_path, 'r', encoding='utf-8') as f:
                            task_data = json.load(f)

                        # 获取各页面的详细状态
                        pages_info = task_data.get('pages', [])

                        # 从task.json更新处理页数（更准确）
                        processed_pages = task_data.get('processed_pages', task.processed_pages)
                        total_pages = task_data.get('total_pages', task.total_pages)
                    except Exception as e:
                        logger.warning(f"读取task.json失败: {str(e)}")
                        processed_pages = task.processed_pages
                        total_pages = task.total_pages
                else:
                    # task.json不存在，使用数据库数据
                    processed_pages = task.processed_pages
                    total_pages = task.total_pages

                # 构建返回信息
                task_info = {
                    'task_id': str(task.id),
                    'original_filename': task.original_filename,
                    'status': task.status,
                    'total_pages': total_pages,
                    'processed_pages': processed_pages,
                    'created_at': task.created_at.isoformat(),
                    'updated_at': task.updated_at.isoformat(),
                    'pages': pages_info  # 包含每页的详细状态
                }

                tasks_progress.append(task_info)

            except PDFExtractorTask.DoesNotExist:
                logger.warning(f"任务不存在: {task_id}")
                tasks_progress.append({
                    'task_id': task_id,
                    'status': 'not_found',
                    'message': '任务不存在'
                })

        return Response({
            'status': 'success',
            'data': {
                'tasks': tasks_progress
            },
            'code': 200
        })

    except Exception as e:
        logger.error(f"查询任务进度失败: {str(e)}", exc_info=True)
        return Response({
            'status': 'error',
            'message': f'查询失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_task_content(request, task_id):
    """
    获取任务处理后的内容（仅限当前用户的任务）

    Args:
        task_id: 任务UUID

    Returns:
        任务生成的markdown内容和图片列表
    """
    try:
        # 1. 获取当前用户
        user = request.user
        if not user.is_authenticated:
            return Response({
                'status': 'error',
                'message': '用户未登录',
                'code': 401
            }, status=status.HTTP_401_UNAUTHORIZED)

        # 2. 验证任务是否存在且属于当前用户
        try:
            task = PDFExtractorTask.objects.get(id=task_id, user=user)
        except PDFExtractorTask.DoesNotExist:
            return Response({
                'status': 'error',
                'message': '任务不存在或无权访问',
                'code': 404
            }, status=status.HTTP_404_NOT_FOUND)

        # 2. 检查任务状态
        if task.status != 'completed':
            return Response({
                'status': 'error',
                'message': f'任务尚未完成，当前状态: {task.status}',
                'code': 400
            }, status=status.HTTP_400_BAD_REQUEST)

        # 3. 读取最终的 result.md 文件
        try:
            md_path = FileManager.get_result_markdown_path(str(task_id))
            with open(md_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()

            logger.info(f"成功读取 Markdown 文件: {md_path}, 大小: {len(markdown_content)} 字节")
        except FileNotFoundError as e:
            logger.error(f"Markdown 文件未找到: {str(e)}")
            return Response({
                'status': 'error',
                'message': f'内容文件未找到: {str(e)}',
                'code': 404
            }, status=status.HTTP_404_NOT_FOUND)

        # 4. 根据环境处理 Markdown 中的图片路径
        # 开发环境：保持 /media/ 路径
        # 生产环境：替换为 OSS 直链
        processed_markdown = FileManager.process_markdown_for_environment(
            markdown_content,
            str(task_id)
        )

        # 5. 图片已经嵌入在 Markdown 中，不需要单独返回图片列表
        # 前端会通过 MarkdownRenderer 自动渲染 Markdown 中的图片引用

        return Response({
            'status': 'success',
            'data': {
                'task_id': str(task_id),
                'original_filename': task.original_filename,
                'markdown': processed_markdown,
                'images': [],  # 图片已嵌入 Markdown，不单独列出
                'total_pages': task.total_pages,
                'feishu_doc_url': task.feishu_doc_url,  # 飞书文档链接（nullable）
            },
            'code': 200
        })

    except Exception as e:
        logger.error(f"获取任务内容失败: {str(e)}", exc_info=True)
        return Response({
            'status': 'error',
            'message': f'获取内容失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_user_tasks(request):
    """
    获取当前用户的所有PDF提取任务列表

    Query params:
        - page: 页码（默认1）
        - page_size: 每页数量（默认20，最大100）
        - status: 状态过滤（可选：pending, processing, completed, error）

    Returns:
        任务列表（按更新时间倒序）和分页信息
    """
    try:
        # 1. 获取当前用户
        user = request.user
        if not user.is_authenticated:
            return Response({
                'status': 'error',
                'message': '用户未登录',
                'code': 401
            }, status=status.HTTP_401_UNAUTHORIZED)

        # 2. 获取查询参数
        page = int(request.GET.get('page', 1))
        page_size = min(int(request.GET.get('page_size', 20)), 100)  # 最大100
        status_filter = request.GET.get('status', '')

        # 3. 查询当前用户的任务
        queryset = PDFExtractorTask.objects.filter(user=user).order_by('-updated_at')

        # 4. 状态过滤
        if status_filter and status_filter in ['pending', 'processing', 'completed', 'error']:
            queryset = queryset.filter(status=status_filter)

        # 5. 计算总数
        total_count = queryset.count()

        # 6. 分页
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        tasks = queryset[start_index:end_index]

        # 7. 构建返回数据
        tasks_data = []
        for task in tasks:
            tasks_data.append({
                'task_id': str(task.id),
                'original_filename': task.original_filename,
                'status': task.status,
                'total_pages': task.total_pages,
                'processed_pages': task.processed_pages,
                'created_at': task.created_at.isoformat(),
                'updated_at': task.updated_at.isoformat(),
                'translate': task.translate,
                'target_language': task.target_language,
                'page_range_start': task.page_range_start,
                'page_range_end': task.page_range_end,
            })

        return Response({
            'status': 'success',
            'data': {
                'tasks': tasks_data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size,
                }
            },
            'code': 200
        })

    except Exception as e:
        logger.error(f"获取用户任务列表失败: {str(e)}", exc_info=True)
        return Response({
            'status': 'error',
            'message': f'获取任务列表失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def health_check(request):
    """
    健康检查端点

    Returns:
        服务状态
    """
    try:
        return Response({
            'status': 'success',
            'data': {
                'service': 'toolkit',
                'version': '1.0.0',
                'features': {
                    'pdf_analysis': True,
                    'document_processing': True,
                    'pdf_conversion': True,
                    'docx_conversion': True,
                    'pdf_extractor': True
                }
            },
            'message': 'Toolkit service is running',
            'code': 200
        })
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'健康检查失败: {str(e)}',
            'code': 500
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)