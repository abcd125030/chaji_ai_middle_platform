from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .core.registry import ToolRegistry
from .utils.helpers import execute_tool
from .core.exceptions import ToolError, ToolNotFoundError

def tool_list(request):
    """获取所有可用工具的列表"""
    try:
        registry = ToolRegistry()
        tools = registry.list_tools()
        return JsonResponse({
            'success': True,
            'tools': tools,
            'count': len(tools)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def execute_tool_endpoint(request, tool_name):
    """执行指定工具的端点"""
    try:
        data = json.loads(request.body)
        state = data.get('state', {})
        config = data.get('config', {})
        
        result = execute_tool(tool_name, state, config)
        
        # execute_tool 已经处理了错误，并返回了包含 'success' 字段的字典
        # 这里直接返回 result
        return JsonResponse(result)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f"请求处理失败: {str(e)}"
        }, status=500)

def health_check(request):
    """工具系统健康检查"""
    try:
        registry = ToolRegistry()
        tools = registry.list_tools()
        return JsonResponse({
            'success': True,
            'status': 'healthy',
            'tools_count': len(tools),
            'tools': tools
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'status': 'unhealthy',
            'error': str(e)
        }, status=500)
