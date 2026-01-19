"""
自定义Django Admin站点配置
优化菜单顺序和首页模块展示
"""
from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _
from django.urls import path
from django.shortcuts import render
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta


class CoreAdminSite(AdminSite):
    """自定义管理站点"""

    site_header = "X AI中台管理系统"
    site_title = "X AI中台"
    index_title = "控制面板"

    def get_app_list(self, request, app_label=None):
        """
        重写获取应用列表方法，自定义菜单顺序
        """
        app_list = super().get_app_list(request, app_label)

        # 定义应用优先级（数字越小优先级越高）
        app_priority = {
            # 业务核心模块 - 最高优先级
            'agentic': 1,              # Agentic工作流
            'agentic_graph': 2,        # Agentic Graph引擎
            'knowledge': 3,            # 知识库

            # 业务功能模块
            'customized': 5,           # 定制功能
            'webapps': 6,              # Web应用
            'payment': 7,              # 支付管理

            # 基础服务模块
            'authentication': 10,       # 认证管理
            'access_control': 11,      # 访问控制
            'router': 12,              # 路由配置

            # 基础设施模块
            'llm': 20,                 # LLM配置
            'tools': 21,               # 工具管理
            'mineru': 23,              # PDF处理
            'service_api': 24,         # 服务API

            # 系统模块 - 最低优先级
            'auth': 30,                # Django认证
            'contenttypes': 31,        # 内容类型
            'sessions': 32,            # Django会话
            'admin': 33,               # Admin日志
        }

        # 根据优先级排序应用
        app_list.sort(key=lambda x: app_priority.get(x['app_label'], 99))

        # 优化每个应用的显示名称
        name_mapping = {
            'agentic': '🚀 Agentic 工作流',
            'agentic_graph': '🔷 Agentic Graph 引擎',
            'knowledge': '📚 知识库管理',
            'customized': '🎨 定制功能',
            'webapps': '🌐 Web应用',
            'payment': '💰 支付管理',
            'authentication': '🔐 用户认证',
            'access_control': '🛡️ 访问控制',
            'router': '🔧 模型路由',
            'llm': '🤖 LLM配置',
            'tools': '🔨 工具管理',
            'mineru': '📄 PDF处理',
            'service_api': '🔌 服务API',
            'auth': '👥 用户组权限',
            'contenttypes': '📋 内容类型',
            'sessions': '🔄 会话管理',
            'admin': '📝 操作日志',
        }

        for app in app_list:
            app_label = app['app_label']
            if app_label in name_mapping:
                app['name'] = name_mapping[app_label]

            # 为每个应用内的模型也进行排序（可选）
            if app_label == 'agentic':
                # Agentic应用内模型排序
                model_order = ['Graph', 'Node', 'Edge', 'AgentTask', 'ActionSteps']
                app['models'].sort(key=lambda x: model_order.index(x['object_name']) if x['object_name'] in model_order else 99)

            elif app_label == 'agentic_graph':
                # Agentic Graph应用内模型排序
                model_order = ['GraphDefinition', 'NodeDefinition', 'EdgeDefinition', 'TaskExecution', 'StepRecord']
                app['models'].sort(key=lambda x: model_order.index(x['object_name']) if x['object_name'] in model_order else 99)

        return app_list

    def index(self, request, extra_context=None):
        """
        自定义首页，添加统计信息和快速操作
        """
        extra_context = extra_context or {}

        # 获取统计数据（使用try-except防止模型不存在）
        stats = {}

        # Agentic 统计
        try:
            from agentic.models import Graph, AgentTask
            stats['agentic'] = {
                'graph_count': Graph.objects.count(),
                'task_total': AgentTask.objects.count(),
                'task_running': AgentTask.objects.filter(status='running').count(),
                'task_completed': AgentTask.objects.filter(status='completed').count(),
                'task_failed': AgentTask.objects.filter(status='failed').count(),
            }
        except:
            pass

        # Agentic Graph 统计
        try:
            from agentic_graph.models import GraphDefinition, TaskExecution
            stats['agentic_graph'] = {
                'graph_count': GraphDefinition.objects.filter(is_active=True).count(),
                'execution_total': TaskExecution.objects.count(),
                'execution_running': TaskExecution.objects.filter(status='running').count(),
                'execution_today': TaskExecution.objects.filter(
                    created_at__gte=timezone.now() - timedelta(days=1)
                ).count(),
            }
        except:
            pass

        # 会话统计 - chat_sessions已弃用，改为使用webapps.chat
        try:
            from webapps.chat.models import ChatHistory
            stats['sessions'] = {
                'chat_total': ChatHistory.objects.count(),
                'chat_today': ChatHistory.objects.filter(
                    created_at__gte=timezone.now() - timedelta(days=1)
                ).count(),
            }
        except:
            pass

        # 知识库统计
        try:
            from knowledge.models import KnowledgeCollection, KnowledgeItem
            stats['knowledge'] = {
                'kb_count': KnowledgeCollection.objects.count(),
                'collection_active': KnowledgeCollection.objects.filter(status='active').count(),
                'collection_processing': KnowledgeCollection.objects.filter(status='processing').count(),
            }
        except:
            pass

        # 用户统计
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            stats['users'] = {
                'total': User.objects.count(),
                'active': User.objects.filter(is_active=True).count(),
                'staff': User.objects.filter(is_staff=True).count(),
                'new_today': User.objects.filter(
                    date_joined__gte=timezone.now() - timedelta(days=1)
                ).count(),
            }
        except:
            pass

        extra_context['stats'] = stats

        # 获取最近的任务执行
        recent_tasks = []
        try:
            from agentic.models import AgentTask
            recent_tasks = AgentTask.objects.select_related('graph').order_by('-created_at')[:10]
        except:
            pass

        recent_executions = []
        try:
            from agentic_graph.models import TaskExecution
            recent_executions = TaskExecution.objects.select_related('graph', 'user').order_by('-created_at')[:10]
        except:
            pass

        extra_context['recent_tasks'] = recent_tasks
        extra_context['recent_executions'] = recent_executions

        return super().index(request, extra_context)

    def get_urls(self):
        """添加自定义URL"""
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='dashboard'),
            path('stats/', self.admin_view(self.stats_view), name='stats'),
        ]
        return custom_urls + urls

    def dashboard_view(self, request):
        """自定义仪表板视图"""
        context = {
            'title': '系统仪表板',
            'site_header': self.site_header,
            'site_title': self.site_title,
            'has_permission': True,
        }

        # 添加Django admin的context
        context.update(self.each_context(request))

        # 收集更详细的统计数据
        # TODO: 根据需要添加更多统计

        return render(request, 'admin/custom_dashboard.html', context)

    def stats_view(self, request):
        """统计视图"""
        context = {
            'title': '系统统计',
            'site_header': self.site_header,
            'site_title': self.site_title,
            'has_permission': True,
        }

        # 添加Django admin的context
        context.update(self.each_context(request))

        return render(request, 'admin/custom_stats.html', context)


# 创建自定义admin站点实例
admin_site = CoreAdminSite(name='core_admin')

# 注册Django默认的认证模型
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin

admin_site.register(User, UserAdmin)
admin_site.register(Group, GroupAdmin)

# 注册所有已配置的模型
def register_existing_models():
    """
    将所有已在默认admin注册的模型重新注册到自定义站点
    """
    from django.apps import apps

    # 需要注册的应用列表
    apps_to_register = [
        'agentic',
        'agentic_graph',
        'knowledge',
        'authentication',
        'access_control',
        'router',
        'llm',
        'tools',
        'mineru',
        'service_api',
        'customized.customization',
        'customized.image_editor',
        'webapps.payment',
        'webapps.chat',
        'webapps.pagtive',
    ]

    for app_label in apps_to_register:
        try:
            app = apps.get_app_config(app_label.split('.')[-1])
            for model in app.get_models():
                if admin.site.is_registered(model):
                    # 获取原始的ModelAdmin
                    model_admin = admin.site._registry[model].__class__
                    # 重新注册到自定义站点
                    if not admin_site.is_registered(model):
                        admin_site.register(model, model_admin)
        except Exception as e:
            print(f"注册应用 {app_label} 时出错: {e}")