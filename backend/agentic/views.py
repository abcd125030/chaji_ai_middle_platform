from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.http import StreamingHttpResponse
import time
import json

from .models import Graph, Node, Edge, AgentTask, ActionSteps
from .serializers import GraphSerializer, NodeSerializer, EdgeSerializer
import logging
logger = logging.getLogger(__name__)  # 获取Django默认日志器

# 图结构视图集 - 管理LangGraph工作流定义
class GraphViewSet(viewsets.ModelViewSet):
    """
    处理图的 CRUD 操作的视图集
    功能：
    - 创建/读取/更新/删除LangGraph工作流定义
    - 提供工作流执行端点
    """
    queryset = Graph.objects.all()  # 获取所有图定义
    serializer_class = GraphSerializer  # 使用图序列化器

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """
        执行特定图的端点
        参数:
        - pk: 图的主键ID
        返回:
        - 202 Accepted: 包含执行启动消息
        POST /api/agentic/graphs/{pk}/execute/
        """
        graph = self.get_object()  # 获取图实例
        # TODO: 实现图的执行逻辑（通常调用AgentService）
        return Response({"message": f"Graph {graph.name} execution started"})

# 通过接口调用的方式处理节点和边的 CRUD 操作
class NodeViewSet(viewsets.ModelViewSet):
    """
    处理节点的 CRUD 操作的视图集
    功能：
    - 管理LangGraph工作流中的节点定义
    - 支持按图ID过滤节点
    """
    queryset = Node.objects.all()  # 获取所有节点
    serializer_class = NodeSerializer  # 使用节点序列化器

    def get_queryset(self):
        """
        支持按图过滤节点
        查询参数:
        - graph: 图ID (可选)
        返回:
        - QuerySet: 过滤后的节点查询集
        """
        queryset = super().get_queryset()
        graph_id = self.request.query_params.get('graph', None)
        if graph_id is not None:
            queryset = queryset.filter(graph_id=graph_id)  # 按图ID过滤
        return queryset


class EdgeViewSet(viewsets.ModelViewSet):
    """
    处理边的 CRUD 操作的视图集
    功能：
    - 管理LangGraph工作流中的边定义
    - 支持按图ID过滤边
    """
    queryset = Edge.objects.all()  # 获取所有边
    serializer_class = EdgeSerializer  # 使用边序列化器

    def get_queryset(self):
        """
        支持按图过滤边
        查询参数:
        - graph: 图ID (可选)
        返回:
        - QuerySet: 过滤后的边查询集
        """
        queryset = super().get_queryset()
        graph_id = self.request.query_params.get('graph', None)
        if graph_id is not None:
            queryset = queryset.filter(graph_id=graph_id)  # 按图ID过滤
        return queryset


def execute_graph(request, graph_pk):
    """
    执行特定图的函数视图
    POST /api/agentic/graphs/{graph_pk}/execute/
    """
    graph = get_object_or_404(Graph, pk=graph_pk)
    # TODO: 实现图的执行逻辑
    return Response(
        {"message": f"Graph {graph.name} execution started"},
        status=status.HTTP_202_ACCEPTED
    )


from rest_framework import mixins
from .serializers import AgentTaskInputSerializer, AgentTaskSerializer
from .services import AgentService

def format_log_for_frontend(log):
    """
    格式化日志数据供前端显示任务步骤
    返回格式与前端 TaskStepsDisplay 组件期望的格式一致
    """
    try:
        # 根据日志类型映射到前端期望的 type
        type_mapping = {
            ActionSteps.LogType.PLANNER: "plan",
            ActionSteps.LogType.TOOL_RESULT: "tool_output",
            ActionSteps.LogType.REFLECTION: None,  # 不再发送reflection事件到前端
            ActionSteps.LogType.FINAL_ANSWER: "final_answer",
            ActionSteps.LogType.TODO_UPDATE: "todo_update"  # 新增TODO更新类型
        }
        
        frontend_type = type_mapping.get(log.log_type)
        if frontend_type is None:
            # 显式为None表示不发送此类型事件
            return None
            
        # 获取 tool_name - 优先从 details 根级别获取
        tool_name = log.details.get("tool_name") or log.details.get("node_name")
        
        # 构建返回数据
        result = {
            "type": frontend_type,
            "data": {}
        }
        
        # 根据不同类型填充 data
        if log.log_type == ActionSteps.LogType.PLANNER:
            action = log.details.get("action", "")
            
            # TODO动作已弃用，TODO管理应通过todo_generator工具实现
            
            # 常规planner动作
            result["data"] = {
                "output": log.details.get("thought", ""),  # 统一使用output字段
                "tool_name": tool_name
            }
        
        elif log.log_type == ActionSteps.LogType.TOOL_RESULT:
            tool_output = log.details.get("tool_output", {})
            
            # todo_handler已弃用，TODO管理应通过todo_generator工具实现
            
            # 常规工具输出处理
            result["data"] = tool_output
            # 将 tool_name 添加到顶层，符合前端期望
            result["tool_name"] = tool_name
            
            
        elif log.log_type == ActionSteps.LogType.REFLECTION:
            # 不发送reflection数据到前端，直接返回None
            return None
            
        elif log.log_type == ActionSteps.LogType.FINAL_ANSWER:
            result["data"] = {
                "output": log.details.get("final_answer", "")  # 统一使用output字段
            }
        
        elif log.log_type == ActionSteps.LogType.TODO_UPDATE:
            # 处理TODO更新日志
            result["data"] = {
                "total_count": log.details.get("total_count", 0),
                "completed_count": log.details.get("completed_count", 0),
                "todo_list": log.details.get("todo_list", [])
            }
            logger.info(f"[SSE调试] TODO更新事件: {result['data']['completed_count']}/{result['data']['total_count']} 任务完成")
        
        return result
        
    except Exception as e:
        logger.error(f"Error formatting log for frontend: {e}", exc_info=True)
        return None

class AgentTaskView(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    Agent 任务视图 - 处理LangGraph工作流任务
    功能：
    - `POST /api/agentic/tasks/`: 异步创建新任务
    - `GET /api/agentic/tasks/{task_id}/`: 查询任务状态和结果
    注意：
    - 使用UUID(task_id)作为主键而非自增ID
    """
    queryset = AgentTask.objects.all()  # 获取所有任务
    lookup_field = 'task_id'  # 使用 UUID 作为查询字段
    authentication_classes = [JWTAuthentication]  # 显式指定JWT认证类
    permission_classes = [IsAuthenticated]  # 确保只有认证用户才能访问

    def get_queryset(self):
        """
        过滤查询集，确保用户只能访问自己的任务
        """
        return self.queryset.filter(user=self.request.user)

    def get_serializer_class(self):
        """
        根据action选择序列化器
        返回:
        - 创建时: AgentTaskInputSerializer (输入验证)
        - 其他操作: AgentTaskSerializer (完整任务展示)
        """
        if self.action == 'create':
            return AgentTaskInputSerializer
        return AgentTaskSerializer

    def retrieve(self, request, *args, **kwargs):
        """
        获取任务详情，支持SSE流式响应用于实时任务步骤更新
        """
        task_id = self.kwargs.get('task_id')
        if "text/event-stream" in request.headers.get("Accept", ""):
            def stream():
                last_log_id = 0
                while True:
                    try:
                        task = AgentTask.objects.get(task_id=task_id, user=request.user)
                        new_logs = ActionSteps.objects.filter(task=task, id__gt=last_log_id).order_by('id')
                        
                        if new_logs:
                            formatted_steps = [s for s in (format_log_for_frontend(log) for log in new_logs) if s]
                            if formatted_steps:
                                yield f"data: {json.dumps({'type': 'task_update', 'action_history': formatted_steps, 'status': task.get_status_display()})}\n\n"
                            last_log_id = new_logs.last().id

                        if task.status in [AgentTask.TaskStatus.COMPLETED, AgentTask.TaskStatus.FAILED, AgentTask.TaskStatus.CANCELLED]:
                            final_data = {
                                'type': 'final_result',
                                'message': {
                                    'role': 'assistant',
                                    'content': task.output_data.get('final_conclusion', '任务已结束。'),
                                    'timestamp': task.updated_at.isoformat()
                                }
                            }
                            yield f"data: {json.dumps(final_data)}\n\n"
                            break
                        
                        time.sleep(1)
                    except AgentTask.DoesNotExist:
                        yield f"data: {json.dumps({'type': 'error', 'message': {'role': 'assistant', 'content': '任务未找到。'}})}\n\n"
                        break
                    except Exception as e:
                        logger.error(f"SSE stream error for task {task_id}: {e}", exc_info=True)
                        yield f"data: {json.dumps({'type': 'error', 'message': {'role': 'assistant', 'content': f'发生错误: {e}'}})}\n\n"
                        break
            
            response = StreamingHttpResponse(stream(), content_type='text/event-stream')
            response['Cache-Control'] = 'no-cache'
            return response
        else:
            return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        接收任务输入，异步启动LangGraph工作流
        参数:
        - prompt: 任务提示文本 (必填)
        - files: 上传文件列表 (可选)
        - graph_name: 要使用的工作流名称 (默认: 'Super-Router Agent')
        返回:
        - 200 OK: 包含task_id用于轮询
        - 400 Bad Request: 输入验证失败
        - 500 Server Error: 服务端异常
        """
        import json
        logger.info(f"[API] 收到任务请求 - files: {len(request.FILES.getlist('files'))}")
        logger.info(f"[API] 认证用户: {request.user}, 是否认证: {request.user.is_authenticated}")
        logger.info(f"[API] Authorization头: {request.headers.get('Authorization', 'None')}")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # 验证输入数据
        validated_data = serializer.validated_data
        
        session_id = validated_data.get('session_id')
        messages_str = validated_data.get('messages', [])
        messages = [json.loads(m) for m in messages_str]
        
        files = validated_data.get('files', [])  # 获取上传文件
        graph_name = validated_data.get('graph_name', 'Super-Router Agent')  # 获取工作流名称
        usage = validated_data.get('usage') # 获取 usage 参数

        logger.info(f"[API] 启动Agent图: {graph_name} for session {session_id}")

        try:
            agent_service = AgentService()  # 初始化Agent服务
            agent_task = agent_service.start_agent_task(
                session_id=session_id,
                messages=messages,
                files=files,
                graph_name=graph_name,
                usage=usage, # 传递 usage 参数
                user=request.user  # 传递当前认证用户
            )
            logger.info(f"[API] 任务提交成功 - task_id: {agent_task.task_id}")
            # 返回200 OK和task_id，客户端可以立即开始轮询
            return Response(
                {"task_id": str(agent_task.task_id)},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            logger.warning(f"[API] 任务提交失败 (数据错误): {e}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"在 AgentTaskView 的 create 方法中捕获到未知异常: {e}", exc_info=True)
            # 确保错误详情可以被JSON序列化
            error_detail = str(e)
            if hasattr(e, '__dict__'):
                # 尝试获取更详细的错误信息，但确保可序列化
                try:
                    import json
                    json.dumps({"test": error_detail})  # 测试是否可序列化
                except (TypeError, ValueError):
                    error_detail = "Internal server error occurred"
            return Response(
                {"error": "An unexpected server error occurred.", "detail": error_detail},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
