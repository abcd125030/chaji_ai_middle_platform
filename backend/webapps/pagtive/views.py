"""
Pagtive 应用视图 - 使用服务层重构版本
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from datetime import datetime
import logging
import json
import os

logger = logging.getLogger(__name__)

from .models import Project, ProjectDetail, ProjectLLMLog
from .serializers import (
    ProjectSerializer, 
    CreateProjectSerializer,
    ProjectDetailSerializer,
    PageSerializer,
    GenerateRequestSerializer,
    LLMLogSerializer
)

# 导入服务层
from .services import (
    ProjectService,
    PageGenerationService,
    ConfigurationService,
    StorageService
)

# 文件存储相关
import shutil
from datetime import datetime


class ProjectViewSet(viewsets.ModelViewSet):
    """项目管理视图集 - 使用服务层"""
    
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # 支持文件上传
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 初始化服务
        self.project_service = ProjectService()
        self.page_service = PageGenerationService()
        self.generation_service = PageGenerationService()  # 用于metadata生成
        self.config_service = ConfigurationService()
    
    def get_queryset(self):
        """获取当前用户的项目"""
        return Project.objects.filter(user=self.request.user).order_by('-created_at')
    
    def get_serializer_class(self):
        """根据操作返回不同的序列化器"""
        if self.action == 'create':
            return CreateProjectSerializer
        return ProjectSerializer
    
    def perform_create(self, serializer):
        """创建项目 - 使用服务层"""
        # 获取创建参数
        project_data = serializer.validated_data
        
        # 处理特殊字段转换
        generate_outline = self.request.data.get('generate_outline', False)
        if isinstance(generate_outline, str):
            generate_outline = generate_outline.lower() == 'true'
        
        # 处理style_tags字段（可能是JSON字符串）
        style_tags = self.request.data.get('style_tags', [])
        if isinstance(style_tags, str):
            try:
                import json
                style_tags = json.loads(style_tags)
            except:
                style_tags = []
        
        # 处理文件上传
        reference_files = []
        uploaded_files = self.request.FILES.getlist('files')
        
        if uploaded_files:
            try:
                # 确定保存目录
                from django.conf import settings
                base_dir = os.path.join(settings.MEDIA_ROOT, 'oss-bucket')
                date_path = datetime.now().strftime('%Y/%m/%d')
                save_dir = os.path.join(base_dir, 'pagtive', date_path)
                os.makedirs(save_dir, exist_ok=True)
                
                for uploaded_file in uploaded_files:
                    # 生成唯一文件名
                    timestamp = datetime.now().strftime('%H%M%S%f')
                    file_ext = os.path.splitext(uploaded_file.name)[1]
                    unique_filename = f"{timestamp}_{uploaded_file.name}"
                    file_path = os.path.join(save_dir, unique_filename)
                    
                    # 保存文件
                    with open(file_path, 'wb+') as destination:
                        for chunk in uploaded_file.chunks():
                            destination.write(chunk)
                    
                    # 生成相对路径（相对于 media/oss-bucket）
                    relative_path = os.path.relpath(file_path, base_dir)
                    
                    # 记录文件信息
                    reference_files.append({
                        'file_id': timestamp,  # 使用时间戳作为唯一ID
                        'filename': uploaded_file.name,
                        'file_key': relative_path,
                        'oss_url': f"/media/oss-bucket/{relative_path}",  # 本地URL路径
                        'size': uploaded_file.size,
                        'content_type': uploaded_file.content_type,
                        'uploaded_at': datetime.now().isoformat()
                    })
                    
                logger.info(f"[Pagtive] 成功保存 {len(reference_files)} 个文件到本地")
                
            except Exception as e:
                logger.error(f"[Pagtive] 文件保存失败: {str(e)}")
                # 文件保存失败不阻止项目创建，继续执行
        
        try:
            # 使用服务层创建项目
            project = self.project_service.create_project(
                user=self.request.user,
                project_name=project_data['project_name'],
                project_description=project_data.get('project_description', ''),
                project_style=project_data.get('project_style', ''),
                global_style_code=project_data.get('global_style_code', ''),
                generate_outline=generate_outline,
                is_public=project_data.get('is_public', False),
                is_published=project_data.get('is_published', False),
                is_featured=project_data.get('is_featured', False),
                style_tags=style_tags,  # 使用处理后的style_tags
                reference_files=reference_files  # 添加文件信息
            )
            
            # 更新序列化器实例
            serializer.instance = project
            
            logger.info(f"[Pagtive] 项目 {project.id} 创建成功，包含 {len(project.pages) if project.pages else 0} 个页面，{len(reference_files)} 个参考文件")
            
        except Exception as e:
            logger.error(f"[Pagtive] 创建项目失败: {str(e)}")
            raise
    
    def perform_update(self, serializer):
        """更新项目 - 使用服务层"""
        instance = serializer.instance
        update_data = serializer.validated_data
        
        try:
            # 使用服务层更新项目
            project = self.project_service.update_project(
                project=instance,
                update_data=update_data
            )
            
            # 更新序列化器实例
            serializer.instance = project
            
            logger.info(f"[Pagtive] 项目 {project.id} 更新成功")
            
        except Exception as e:
            logger.error(f"[Pagtive] 更新项目失败: {str(e)}")
            raise
    
    def perform_destroy(self, instance):
        """删除项目 - 使用服务层"""
        try:
            # 使用服务层删除项目
            success = self.project_service.delete_project(instance)
            
            if not success:
                raise Exception("删除项目失败")
            
            logger.info(f"[Pagtive] 项目 {instance.id} 删除成功")
            
        except Exception as e:
            logger.error(f"[Pagtive] 删除项目失败: {str(e)}")
            raise
    
    @action(detail=True, methods=['get', 'post', 'put', 'delete'])
    def pages(self, request, pk=None):
        """管理项目的页面 - 使用服务层"""
        project = self.get_object()
        
        if request.method == 'GET':
            # 获取页面列表及内容
            pages = project.pages or []
            
            # 为每个页面获取详情
            for page in pages:
                page_id = page.get('id')
                if page_id:
                    try:
                        page_id_int = int(page_id)
                        detail = self.project_service.get_page_detail(project, page_id_int)
                        
                        if detail:
                            page['html'] = detail.html
                            page['styles'] = detail.styles
                            page['script'] = detail.script
                            page['mermaid_content'] = detail.mermaid_content
                        else:
                            # 设置默认值
                            page.setdefault('html', '')
                            page.setdefault('styles', '')
                            page.setdefault('script', '')
                            page.setdefault('mermaid_content', '')
                    except (ValueError, TypeError):
                        # 非数字ID，设置默认值
                        page.setdefault('html', '')
                        page.setdefault('styles', '')
                        page.setdefault('script', '')
                        page.setdefault('mermaid_content', '')
            
            return Response(pages)
        
        elif request.method == 'POST':
            # 检查是更新还是创建
            is_update = request.data.get('isUpdate', False)
            page_id = request.data.get('id')
            
            if is_update and page_id:
                # 更新现有页面
                try:
                    page_id_int = int(page_id)
                    
                    # 获取HTML内容用于生成metadata
                    html_content = request.data.get('html', '')
                    page_title = request.data.get('title', f'页面 {page_id}')
                    
                    # 生成metadata（如果有HTML内容）
                    metadata = {}
                    if html_content:
                        try:
                            metadata = self.generation_service.generate_page_metadata(
                                project_name=project.project_name,
                                html_content=html_content,
                                page_title=page_title
                            )
                        except Exception as e:
                            logger.warning(f"[Pagtive] 生成metadata失败: {str(e)}")
                            metadata = {}
                    
                    # 更新页面内容到 project_details 表
                    from webapps.pagtive.models import ProjectDetail, ProjectLLMLog
                    import uuid
                    
                    new_version_id = uuid.uuid4()
                    
                    detail, created = ProjectDetail.objects.update_or_create(
                        project=project,
                        page_id=page_id_int,
                        defaults={
                            'html': html_content,
                            'styles': request.data.get('styles', ''),
                            'script': request.data.get('script', ''),
                            'mermaid_content': request.data.get('mermaid_content', ''),
                            'version_id': new_version_id
                        }
                    )
                    
                    # 更新关联的LLM日志版本
                    version_id = request.data.get('versionId')
                    if version_id:
                        ProjectLLMLog.objects.filter(
                            id=version_id,
                            project=project,
                            page_id=page_id_int
                        ).update(version_id=new_version_id)
                    
                    # 更新页面的metadata信息到project.pages
                    if project.pages:
                        pages_updated = False
                        for page in project.pages:
                            if str(page.get('id')) == str(page_id):
                                # 追加用户prompt到历史记录
                                if 'user_prompts' not in page:
                                    page['user_prompts'] = []
                                page['user_prompts'].append({
                                    'prompt': page_title,
                                    'timestamp': datetime.now().isoformat(),
                                    'action': 'update'
                                })
                                
                                # 直接覆盖metadata字段
                                if metadata:
                                    if metadata.get('title'):
                                        page['title'] = metadata['title']
                                    if metadata.get('description'):
                                        page['description'] = metadata['description']
                                    if metadata.get('keywords'):
                                        page['keywords'] = metadata['keywords']
                                else:
                                    # 如果没有生成metadata，保留原始prompt作为标题
                                    page['title'] = page_title
                                
                                pages_updated = True
                                break
                        if pages_updated:
                            project.save()
                    
                    return Response({
                        'status': 'success',
                        'message': '页面更新成功',
                        'data': {
                            'page_id': page_id_int,
                            'version_id': str(new_version_id),
                            'metadata': metadata
                        }
                    })
                    
                except Exception as e:
                    logger.error(f"[Pagtive] 更新页面失败: {str(e)}")
                    return Response(
                        {'status': 'error', 'message': f'更新页面失败: {str(e)}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            
            # 创建新页面 - 使用服务层
            serializer = PageSerializer(data=request.data)
            if serializer.is_valid():
                try:
                    new_page = self.project_service.add_page_to_project(
                        project=project,
                        page_title=serializer.validated_data['title'],
                        page_id=None  # 自动分配ID
                    )
                    
                    # 保存页面内容到 project_details 表
                    page_id = new_page.get('id')
                    if page_id:
                        # 创建或更新页面详情
                        from webapps.pagtive.models import ProjectDetail, ProjectLLMLog
                        import uuid
                        
                        # 获取HTML内容用于生成metadata
                        html_content = request.data.get('html', '')
                        
                        # 生成metadata（如果有HTML内容）
                        metadata = {}
                        if html_content:
                            try:
                                metadata = self.generation_service.generate_page_metadata(
                                    project_name=project.project_name,
                                    html_content=html_content,
                                    page_title=serializer.validated_data.get('title')
                                )
                            except Exception as e:
                                logger.warning(f"[Pagtive] 生成metadata失败: {str(e)}")
                                metadata = {}
                        
                        ProjectDetail.objects.update_or_create(
                            project=project,
                            page_id=int(page_id),
                            defaults={
                                'html': html_content,
                                'styles': request.data.get('styles', ''),
                                'script': request.data.get('script', ''),
                                'mermaid_content': request.data.get('mermaid_content', ''),
                                'version_id': uuid.uuid4()
                            }
                        )
                        
                        # 更新页面的metadata信息 - 直接合并到页面对象中
                        if new_page:
                            # 初始化user_prompts字段，记录创建时的prompt
                            new_page['user_prompts'] = [{
                                'prompt': serializer.validated_data.get('title', ''),
                                'timestamp': datetime.now().isoformat(),
                                'action': 'create'
                            }]
                            
                            # 直接覆盖metadata字段
                            if metadata:
                                if metadata.get('title'):
                                    new_page['title'] = metadata['title']
                                if metadata.get('description'):
                                    new_page['description'] = metadata['description']
                                if metadata.get('keywords'):
                                    new_page['keywords'] = metadata['keywords']
                        
                        # 如果有临时页面ID，更新对应的LLM日志
                        temp_page_id = request.data.get('tempPageId')
                        if temp_page_id:
                            ProjectLLMLog.objects.filter(
                                temporary_page_id=temp_page_id
                            ).update(page_id=int(page_id))
                    
                    # 处理插入位置（如果需要调整顺序）
                    insert_after_id = request.data.get('insertAfterId')
                    if insert_after_id:
                        self._adjust_page_order(project, new_page, insert_after_id)
                    
                    return Response(new_page, status=status.HTTP_201_CREATED)
                    
                except Exception as e:
                    logger.error(f"[Pagtive] 创建页面失败: {str(e)}")
                    return Response(
                        {'detail': f'创建页面失败: {str(e)}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'PUT':
            # 更新页面 - 使用服务层
            page_id = request.data.get('id')
            if not page_id:
                return Response(
                    {'detail': '缺少页面ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                page_id_int = int(page_id)
                serializer = PageSerializer(data=request.data)
                
                if serializer.is_valid():
                    # 更新页面元信息
                    success = self.project_service.update_page_in_project(
                        project=project,
                        page_id=page_id_int,
                        page_title=serializer.validated_data.get('title'),
                        order=serializer.validated_data.get('order')
                    )
                    
                    if success:
                        # 如果有内容更新，同时更新内容
                        if any(key in request.data for key in ['html', 'styles', 'script', 'mermaid_content']):
                            self.project_service.update_page_content(
                                project=project,
                                page_id=page_id_int,
                                html=request.data.get('html'),
                                styles=request.data.get('styles'),
                                script=request.data.get('script'),
                                mermaid_content=request.data.get('mermaid_content')
                            )
                        
                        return Response({'detail': '页面更新成功'})
                    else:
                        return Response(
                            {'detail': '页面不存在'},
                            status=status.HTTP_404_NOT_FOUND
                        )
                
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
            except (ValueError, TypeError):
                return Response(
                    {'detail': '无效的页面ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        elif request.method == 'DELETE':
            # 删除页面 - 使用服务层
            page_id = request.data.get('id')
            if not page_id:
                return Response(
                    {'detail': '缺少页面ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                page_id_int = int(page_id)
                success = self.project_service.delete_page_from_project(
                    project=project,
                    page_id=page_id_int
                )
                
                if success:
                    return Response({'detail': '页面删除成功'})
                else:
                    return Response(
                        {'detail': '页面不存在'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                    
            except (ValueError, TypeError):
                return Response(
                    {'detail': '无效的页面ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )
    
    @action(detail=True, methods=['get', 'put'])
    def page_detail(self, request, pk=None):
        """获取或更新页面详情 - 使用服务层"""
        project = self.get_object()
        page_id = request.query_params.get('page_id') or request.data.get('page_id')
        
        if not page_id:
            return Response(
                {'detail': '缺少页面ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            page_id_int = int(page_id)
            
            if request.method == 'GET':
                # 获取页面详情
                detail = self.project_service.get_page_detail(project, page_id_int)
                
                if detail:
                    serializer = ProjectDetailSerializer(detail)
                    return Response(serializer.data)
                else:
                    return Response(
                        {'detail': '页面不存在'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            elif request.method == 'PUT':
                # 更新页面内容
                detail = self.project_service.update_page_content(
                    project=project,
                    page_id=page_id_int,
                    html=request.data.get('html'),
                    styles=request.data.get('styles'),
                    script=request.data.get('script'),
                    mermaid_content=request.data.get('mermaid_content'),
                    images=request.data.get('images')
                )
                
                serializer = ProjectDetailSerializer(detail)
                return Response(serializer.data)
                
        except (ValueError, TypeError):
            return Response(
                {'detail': '无效的页面ID'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], url_path='pages/(?P<page_id>[^/.]+)/restore')
    def restore_version(self, request, pk=None, page_id=None):
        """恢复页面到指定的版本"""
        try:
            project = self.get_object()
            llm_log_id = request.data.get('llm_log_id')
            
            if not llm_log_id:
                return Response(
                    {'status': 'error', 'message': '缺少 llm_log_id 参数'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 获取对应的LLM日志记录
            try:
                llm_log = ProjectLLMLog.objects.get(
                    id=llm_log_id,
                    project=project,
                    page_id=int(page_id)
                )
            except ProjectLLMLog.DoesNotExist:
                return Response(
                    {'status': 'error', 'message': '未找到指定的历史版本'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # 从LLM日志中提取生成的内容
            response_content = llm_log.response_content
            if not response_content:
                return Response(
                    {'status': 'error', 'message': '该历史版本没有可恢复的内容'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 解析响应内容（根据实际格式调整）
            import json
            try:
                if isinstance(response_content, str):
                    content_data = json.loads(response_content)
                else:
                    content_data = response_content
                    
                # 提取 HTML、CSS、JS 等内容
                # 需要根据实际的响应格式调整
                if isinstance(content_data, dict):
                    html = content_data.get('html', '')
                    styles = content_data.get('styles', '') or content_data.get('css', '')
                    script = content_data.get('script', '') or content_data.get('js', '') or content_data.get('javascript', '')
                    mermaid_content = content_data.get('mermaidContent', '') or content_data.get('mermaid_content', '')
                else:
                    # 如果是纯文本，可能需要其他处理方式
                    return Response(
                        {'status': 'error', 'message': '无法解析历史版本内容'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"解析历史版本内容失败: {e}")
                return Response(
                    {'status': 'error', 'message': '历史版本内容格式错误'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 生成新的版本ID
            from uuid import uuid4
            new_version_id = uuid4()
            
            # 生成metadata（如果有HTML内容）
            metadata = {}
            if html:
                try:
                    # 从pages列表中获取页面标题
                    page_title = None
                    if project.pages:
                        for page in project.pages:
                            if str(page.get('id')) == str(page_id):
                                page_title = page.get('title')
                                break
                    
                    metadata = self.generation_service.generate_page_metadata(
                        project_name=project.project_name,
                        html_content=html,
                        page_title=page_title
                    )
                except Exception as e:
                    logger.warning(f"[Pagtive] 生成metadata失败: {str(e)}")
                    metadata = {}
            
            # 更新页面内容
            detail, created = ProjectDetail.objects.update_or_create(
                project=project,
                page_id=int(page_id),
                defaults={
                    'html': html,
                    'styles': styles,
                    'script': script,
                    'mermaid_content': mermaid_content,
                    'version_id': new_version_id
                }
            )
            
            # 更新页面的metadata信息到project.pages
            if project.pages:
                pages_updated = False
                for page in project.pages:
                    if str(page.get('id')) == str(page_id):
                        # 追加恢复版本的记录到user_prompts
                        if 'user_prompts' not in page:
                            page['user_prompts'] = []
                        page['user_prompts'].append({
                            'prompt': f"恢复到版本 {llm_log_id}",
                            'timestamp': datetime.now().isoformat(),
                            'action': 'restore'
                        })
                        
                        # 直接覆盖metadata字段
                        if metadata:
                            if metadata.get('title'):
                                page['title'] = metadata['title']
                            if metadata.get('description'):
                                page['description'] = metadata['description']
                            if metadata.get('keywords'):
                                page['keywords'] = metadata['keywords']
                        
                        pages_updated = True
                        break
                if pages_updated:
                    project.save()
            
            # 更新LLM日志的version_id（标记这个版本被恢复了）
            llm_log.version_id = new_version_id
            llm_log.save()
            
            # 返回恢复的内容
            return Response({
                'status': 'success',
                'data': {
                    'html': html,
                    'styles': styles,
                    'script': script,
                    'mermaid_content': mermaid_content,
                    'version_id': str(new_version_id),
                    'restored_from': str(llm_log_id)
                }
            })
            
        except Exception as e:
            logger.error(f"恢复版本失败: {e}")
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def public(self, request):
        """获取公开的项目列表"""
        # 获取查询参数
        is_featured = request.query_params.get('is_featured')
        style_tag = request.query_params.get('style_tag')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        
        # 构建查询
        queryset = Project.objects.filter(is_public=True, is_published=True)
        
        if is_featured is not None:
            queryset = queryset.filter(is_featured=(is_featured.lower() == 'true'))
        
        if style_tag:
            queryset = queryset.filter(style_tags__contains=[style_tag])
        
        # 排序：推荐项目优先，然后按更新时间
        queryset = queryset.order_by('-is_featured', '-updated_at')
        
        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        projects = queryset[start:end]
        
        serializer = ProjectSerializer(projects, many=True)
        
        return Response({
            'results': serializer.data,
            'count': queryset.count(),
            'page': page,
            'page_size': page_size
        })
    
    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """克隆项目"""
        source_project = self.get_object()
        
        # 只能克隆公开的项目或自己的项目
        if not source_project.is_public and source_project.user != request.user:
            return Response(
                {'detail': '无权限克隆此项目'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # 创建新项目（克隆）
            new_project = self.project_service.create_project(
                user=request.user,
                project_name=f"{source_project.project_name} (副本)",
                project_description=source_project.project_description,
                project_style=source_project.project_style,
                global_style_code=source_project.global_style_code,
                generate_outline=False,  # 不生成大纲，直接复制页面
                is_public=False,  # 克隆的项目默认私有
                is_published=False,
                is_featured=False,
                style_tags=source_project.style_tags
            )
            
            # 复制页面结构
            new_project.pages = source_project.pages.copy() if source_project.pages else []
            new_project.save()
            
            # 复制页面内容
            source_details = ProjectDetail.objects.filter(project=source_project)
            for detail in source_details:
                ProjectDetail.objects.create(
                    project=new_project,
                    page_id=detail.page_id,
                    html=detail.html,
                    styles=detail.styles,
                    script=detail.script,
                    mermaid_content=detail.mermaid_content,
                    images=detail.images
                )
            
            serializer = ProjectSerializer(new_project)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"[Pagtive] 克隆项目失败: {str(e)}")
            return Response(
                {'detail': f'克隆项目失败: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def llm_logs(self, request, pk=None):
        """获取项目的LLM调用日志"""
        project = self.get_object()
        
        # 获取查询参数
        page_id = request.query_params.get('page_id')
        scenario = request.query_params.get('scenario')
        status_filter = request.query_params.get('status')
        limit = int(request.query_params.get('limit', 20))
        
        # 构建查询
        queryset = ProjectLLMLog.objects.filter(project=project)
        
        if page_id:
            try:
                queryset = queryset.filter(page_id=int(page_id))
            except (ValueError, TypeError):
                pass
        
        if scenario:
            queryset = queryset.filter(scenario=scenario)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # 排序和限制
        logs = queryset.order_by('-request_timestamp')[:limit]
        
        serializer = LLMLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    def _adjust_page_order(self, project, new_page, insert_after_id):
        """调整页面顺序的辅助方法"""
        pages = project.pages or []
        
        # 先移除新页面（如果已存在）
        pages = [p for p in pages if p.get('id') != new_page['id']]
        
        if insert_after_id == 'start':
            # 插入到开头
            pages.insert(0, new_page)
        elif insert_after_id == 'end' or not insert_after_id:
            # 插入到末尾
            pages.append(new_page)
        else:
            # 在指定页面之后插入
            insert_index = None
            for i, p in enumerate(pages):
                if str(p.get('id')) == str(insert_after_id):
                    insert_index = i + 1
                    break
            
            if insert_index is not None:
                pages.insert(insert_index, new_page)
            else:
                pages.append(new_page)
        
        # 重新计算order值
        for i, page in enumerate(pages):
            page['order'] = (i + 1) * 100
        
        project.pages = pages
        project.save()


class ShareViewSet(viewsets.ViewSet):
    """分享视图集 - 无需认证即可访问公开项目"""
    permission_classes = []  # 无需认证即可访问
    
    def retrieve(self, request, pk=None):
        """获取分享的项目（无需认证）"""
        try:
            project = Project.objects.get(
                id=pk,
                is_public=True,
                is_published=True  # 只能访问已发布的项目
            )
            
            # 获取项目详情
            serializer = ProjectSerializer(project)
            data = serializer.data
            
            # 获取所有页面的详情
            pages = project.pages or []
            for page in pages:
                page_id = page.get('id')
                if page_id:
                    try:
                        page_id_int = int(page_id)
                        detail = ProjectDetail.objects.filter(
                            project=project,
                            page_id=page_id_int
                        ).first()
                        
                        if detail:
                            page['html'] = detail.html
                            page['styles'] = detail.styles
                            page['script'] = detail.script
                            page['mermaid_content'] = detail.mermaid_content
                        else:
                            page.setdefault('html', '')
                            page.setdefault('styles', '')
                            page.setdefault('script', '')
                            page.setdefault('mermaid_content', '')
                    except (ValueError, TypeError):
                        page.setdefault('html', '')
                        page.setdefault('styles', '')
                        page.setdefault('script', '')
                        page.setdefault('mermaid_content', '')
            
            data['pages'] = pages
            
            return Response(data)
            
        except Project.DoesNotExist:
            return Response(
                {'detail': '项目不存在或未公开'},
                status=status.HTTP_404_NOT_FOUND
            )


class GenerateViewSet(viewsets.ViewSet):
    """AI生成视图集 - 兼容旧接口"""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """生成页面内容 - 使用服务层"""
        serializer = GenerateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        # 获取项目
        try:
            project = Project.objects.get(
                id=data['projectId'],
                user=request.user
            )
        except Project.DoesNotExist:
            return Response(
                {'error': '项目不存在或无权访问'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 初始化服务
        page_service = PageGenerationService()
        
        # 准备参数
        page_id = data.get('pageId')
        if page_id:
            try:
                page_id = int(page_id)
            except (ValueError, TypeError):
                page_id = None
        
        # 准备参考内容
        references = []
        for ref in data.get('references', []):
            references.append({
                'title': f"参考内容",
                'content': ref.get('content', '')
            })
        
        # 准备图片
        images = []
        for img in data.get('images', []):
            images.append({
                'name': img.get('name', ''),
                'url': img.get('url', '')
            })
        
        try:
            # 判断是编辑还是生成
            scenario = data.get('template', 'generatePageCode')
            
            if scenario == 'editPageCode' and page_id:
                # 编辑页面
                result = page_service.edit_page_content(
                    project=project,
                    user=request.user,
                    page_id=page_id,
                    edit_prompt=data['prompt']
                )
            else:
                # 生成页面
                result = page_service.generate_page_content(
                    project=project,
                    user=request.user,
                    prompt=data['prompt'],
                    template=data.get('template', 'default'),
                    references=references,
                    images=images,
                    page_id=page_id
                )
            
            if result.get('status') == 'success':
                return Response(result['data'])
            else:
                return Response(
                    {'error': result.get('message', '生成失败')},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"生成页面失败: {str(e)}")
            return Response(
                {'error': f'生成失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def outline(self, request):
        """生成项目大纲 - 使用服务层"""
        # 获取请求数据
        project_id = request.data.get('project_id')
        project_name = request.data.get('project_name', '')
        project_description = request.data.get('project_description', '')
        project_style = request.data.get('project_style', '')
        
        # 如果提供了 project_id，则从数据库获取项目信息
        if project_id:
            try:
                project = Project.objects.get(
                    id=project_id,
                    user=request.user
                )
                project_name = project_name or project.project_name
                project_description = project_description or project.project_description
                project_style = project_style or project.project_style
            except Project.DoesNotExist:
                return Response(
                    {'error': '项目不存在或无权访问'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # 验证必要参数
        if not project_name:
            return Response(
                {'error': '项目名称不能为空'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 初始化服务
        page_service = PageGenerationService()
        
        try:
            # 生成大纲
            outline = page_service.generate_project_outline(
                project_name=project_name,
                project_description=project_description,
                project_style=project_style
            )
            
            # 如果提供了 project_id，更新项目的页面结构
            if project_id and project:
                project.pages = outline
                project.save()
                
                # 为每个页面创建空的 ProjectDetail
                from .models import ProjectDetail
                for page in outline:
                    page_id = page.get('id')
                    if page_id:
                        ProjectDetail.objects.get_or_create(
                            project=project,
                            page_id=int(page_id),
                            defaults={
                                'html': '',
                                'styles': '',
                                'script': '',
                                'mermaid_content': '',
                                'images': []
                            }
                        )
            
            return Response({
                'status': 'success',
                'data': {
                    'pages': outline
                }
            })
            
        except Exception as e:
            logger.error(f"生成大纲失败: {str(e)}")
            return Response(
                {'error': f'生成大纲失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )