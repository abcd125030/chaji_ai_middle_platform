"""
项目管理服务
============

负责项目的创建、更新、删除，以及页面管理等核心业务逻辑。
"""

import json
import logging
from typing import Optional, Dict, Any, List
from uuid import uuid4
from datetime import datetime

from django.db import transaction
from django.contrib.auth import get_user_model

from ..models import Project, ProjectDetail, ProjectLLMLog
from ..serializers import ProjectSerializer
from .configuration_service import ConfigurationService

logger = logging.getLogger(__name__)
User = get_user_model()


class ProjectService:
    """项目管理服务类"""
    
    def __init__(self):
        self.config_service = ConfigurationService()
    
    @transaction.atomic
    def create_project(
        self,
        user: User,
        project_name: str,
        project_description: str = "",
        project_style: str = "",
        global_style_code: str = "",
        generate_outline: bool = False,
        **kwargs
    ) -> Project:
        """
        创建新项目
        
        Args:
            user: 用户对象
            project_name: 项目名称
            project_description: 项目描述
            project_style: 项目风格
            global_style_code: 全局样式代码
            generate_outline: 是否生成项目大纲
            **kwargs: 其他项目字段
            
        Returns:
            创建的项目对象
        """
        # 创建项目
        project = Project.objects.create(
            user=user,
            project_name=project_name,
            project_description=project_description,
            project_style=project_style,
            global_style_code=global_style_code,
            pages=[],  # 初始化为空列表
            **kwargs
        )
        
        # 如果需要生成大纲
        if generate_outline:
            try:
                outline = self._generate_project_outline(project)
                if outline:
                    project.pages = outline
                    project.save()
                    # 为每个页面创建空的 ProjectDetail
                    self._create_empty_page_details(project, outline)
            except Exception as e:
                logger.error(f"生成项目大纲失败: {str(e)}")
                # 不影响项目创建，继续返回项目
        
        return project
    
    def update_project(
        self,
        project: Project,
        update_data: Dict[str, Any]
    ) -> Project:
        """
        更新项目信息
        
        Args:
            project: 项目对象
            update_data: 更新数据字典
            
        Returns:
            更新后的项目对象
        """
        # 不允许更新的字段
        protected_fields = ['id', 'user', 'created_at']
        
        for field, value in update_data.items():
            if field not in protected_fields and hasattr(project, field):
                setattr(project, field, value)
        
        project.save()
        return project
    
    @transaction.atomic
    def delete_project(self, project: Project) -> bool:
        """
        删除项目及其所有相关数据
        
        Args:
            project: 项目对象
            
        Returns:
            是否删除成功
        """
        try:
            # 删除相关的 ProjectDetail
            ProjectDetail.objects.filter(project=project).delete()
            
            # 删除相关的 ProjectLLMLog
            ProjectLLMLog.objects.filter(project=project).delete()
            
            # 删除项目本身
            project.delete()
            
            return True
        except Exception as e:
            logger.error(f"删除项目失败: {str(e)}")
            return False
    
    def get_project_by_id(
        self,
        project_id: str,
        user: Optional[User] = None
    ) -> Optional[Project]:
        """
        根据ID获取项目
        
        Args:
            project_id: 项目ID
            user: 用户对象（可选，用于权限检查）
            
        Returns:
            项目对象或None
        """
        try:
            query = Project.objects.filter(id=project_id)
            if user:
                query = query.filter(user=user)
            return query.first()
        except Exception as e:
            logger.error(f"获取项目失败: {str(e)}")
            return None
    
    def list_user_projects(
        self,
        user: User,
        page: int = 1,
        page_size: int = 10,
        is_public: Optional[bool] = None,
        is_published: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        列出用户的项目
        
        Args:
            user: 用户对象
            page: 页码
            page_size: 每页大小
            is_public: 是否公开
            is_published: 是否发布
            
        Returns:
            项目列表和分页信息
        """
        query = Project.objects.filter(user=user)
        
        if is_public is not None:
            query = query.filter(is_public=is_public)
        if is_published is not None:
            query = query.filter(is_published=is_published)
        
        # 排序
        query = query.order_by('-updated_at')
        
        # 计算分页
        total = query.count()
        start = (page - 1) * page_size
        end = start + page_size
        
        projects = query[start:end]
        
        return {
            'results': ProjectSerializer(projects, many=True).data,
            'count': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        }
    
    # ==================== 页面管理 ====================
    
    def add_page_to_project(
        self,
        project: Project,
        page_title: str,
        page_id: Optional[int] = None,
        order: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        向项目添加新页面
        
        Args:
            project: 项目对象
            page_title: 页面标题
            page_id: 页面ID（可选，不提供则自动生成）
            order: 页面顺序（可选）
            
        Returns:
            新创建的页面信息
        """
        # 生成页面ID
        if page_id is None:
            # 从project.pages中获取已存在的ID
            existing_ids_from_pages = [int(p.get('id', 0)) for p in project.pages if p.get('id')]
            
            # 从ProjectDetail表中获取已存在的ID
            existing_ids_from_details = list(
                ProjectDetail.objects.filter(project=project).values_list('page_id', flat=True)
            )
            
            # 合并所有已存在的ID
            all_existing_ids = set(existing_ids_from_pages + existing_ids_from_details)
            
            # 找到最大的ID并加1，如果没有则从1开始
            page_id = max(all_existing_ids) + 1 if all_existing_ids else 1
        
        # 确定顺序
        if order is None:
            existing_orders = [p.get('order', 0) for p in project.pages]
            order = (max(existing_orders) + 100) if existing_orders else 100
        
        # 创建页面配置
        new_page = {
            'id': str(page_id),
            'title': page_title,
            'order': order,
            'created_at': datetime.now().isoformat()
        }
        
        # 更新项目的pages字段
        if not project.pages:
            project.pages = []
        project.pages.append(new_page)
        project.save()
        
        # 创建空的 ProjectDetail
        ProjectDetail.objects.create(
            project=project,
            page_id=page_id,
            html='',
            styles='',
            script='',
            mermaid_content='',
            images=[]
        )
        
        return new_page
    
    def update_page_in_project(
        self,
        project: Project,
        page_id: int,
        page_title: Optional[str] = None,
        order: Optional[int] = None
    ) -> bool:
        """
        更新项目中的页面信息
        
        Args:
            project: 项目对象
            page_id: 页面ID
            page_title: 新的页面标题
            order: 新的页面顺序
            
        Returns:
            是否更新成功
        """
        page_id_str = str(page_id)
        
        for page in project.pages:
            if str(page.get('id')) == page_id_str:
                if page_title is not None:
                    page['title'] = page_title
                if order is not None:
                    page['order'] = order
                page['updated_at'] = datetime.now().isoformat()
                project.save()
                return True
        
        return False
    
    @transaction.atomic
    def delete_page_from_project(
        self,
        project: Project,
        page_id: int
    ) -> bool:
        """
        从项目中删除页面
        
        Args:
            project: 项目对象
            page_id: 页面ID
            
        Returns:
            是否删除成功
        """
        page_id_str = str(page_id)
        
        # 从pages列表中移除
        original_count = len(project.pages)
        project.pages = [p for p in project.pages if str(p.get('id')) != page_id_str]
        
        if len(project.pages) < original_count:
            project.save()
            
            # 删除对应的 ProjectDetail
            ProjectDetail.objects.filter(
                project=project,
                page_id=page_id
            ).delete()
            
            return True
        
        return False
    
    def get_page_detail(
        self,
        project: Project,
        page_id: int
    ) -> Optional[ProjectDetail]:
        """
        获取页面详情
        
        Args:
            project: 项目对象
            page_id: 页面ID
            
        Returns:
            页面详情对象或None
        """
        try:
            return ProjectDetail.objects.get(
                project=project,
                page_id=page_id
            )
        except ProjectDetail.DoesNotExist:
            return None
    
    def update_page_content(
        self,
        project: Project,
        page_id: int,
        html: Optional[str] = None,
        styles: Optional[str] = None,
        script: Optional[str] = None,
        mermaid_content: Optional[str] = None,
        images: Optional[List[Dict]] = None
    ) -> ProjectDetail:
        """
        更新页面内容
        
        Args:
            project: 项目对象
            page_id: 页面ID
            html: HTML内容
            styles: CSS样式
            script: JavaScript脚本
            mermaid_content: Mermaid图表内容
            images: 图片列表
            
        Returns:
            更新后的页面详情对象
        """
        detail, created = ProjectDetail.objects.get_or_create(
            project=project,
            page_id=page_id,
            defaults={
                'html': '',
                'styles': '',
                'script': '',
                'mermaid_content': '',
                'images': []
            }
        )
        
        # 更新内容
        if html is not None:
            detail.html = html
        if styles is not None:
            detail.styles = styles
        if script is not None:
            detail.script = script
        if mermaid_content is not None:
            detail.mermaid_content = mermaid_content
        if images is not None:
            detail.images = images
        
        # 更新版本ID
        detail.version_id = uuid4()
        detail.save()
        
        return detail
    
    # ==================== 私有方法 ====================
    
    def _generate_project_outline(self, project: Project) -> List[Dict[str, Any]]:
        """
        生成项目大纲（页面列表）
        
        Args:
            project: 项目对象
            
        Returns:
            页面列表
        """
        from .page_generation_service import PageGenerationService
        
        service = PageGenerationService()
        return service.generate_project_outline(
            project_name=project.project_name,
            project_description=project.project_description,
            project_style=project.project_style
        )
    
    def _create_empty_page_details(
        self,
        project: Project,
        pages: List[Dict[str, Any]]
    ) -> None:
        """
        为页面列表创建空的 ProjectDetail 记录
        
        Args:
            project: 项目对象
            pages: 页面列表
        """
        for page in pages:
            page_id = int(page.get('id', 0))
            if page_id:
                ProjectDetail.objects.get_or_create(
                    project=project,
                    page_id=page_id,
                    defaults={
                        'html': '',
                        'styles': '',
                        'script': '',
                        'mermaid_content': '',
                        'images': []
                    }
                )