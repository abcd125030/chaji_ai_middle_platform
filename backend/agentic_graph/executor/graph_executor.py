"""
Graph 执行器
"""
import logging
from typing import Dict, Any, Optional, List
from django.db import transaction

from ..models import GraphDefinition, NodeDefinition, EdgeDefinition
from ..models_extension import GraphTask, GraphCheckpoint
from ..core.schemas import RuntimeState
from .checkpoint import CheckpointManager
from ..nodes import NodeRegistry

logger = logging.getLogger('django')


class GraphExecutor:
    """Graph 执行器主类"""
    
    def __init__(
        self,
        task_id: str,
        graph_name: str,
        initial_query: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        preprocessed_files: Optional[Dict] = None,
        conversation_history: Optional[List[Dict]] = None
    ):
        """
        初始化 Graph 执行器
        
        参数:
            task_id: 任务ID
            graph_name: Graph名称
            initial_query: 初始查询
            user_id: 用户ID
            session_id: 会话ID
            preprocessed_files: 预处理的文件
            conversation_history: 对话历史
        """
        self.task_id = task_id
        self.graph_name = graph_name
        self.user_id = user_id
        self.session_id = session_id
        
        # 初始化组件
        self.checkpoint_manager = CheckpointManager()
        self.node_registry = NodeRegistry()
        
        # 加载或创建任务
        self._load_or_create_task()
        
        # 加载 Graph 定义
        self._load_graph_definition()
        
        # 初始化或恢复状态
        self._initialize_state(
            initial_query=initial_query,
            preprocessed_files=preprocessed_files,
            conversation_history=conversation_history
        )
        
        logger.info(f"Graph执行器初始化完成 - task_id: {task_id}, graph: {graph_name}")
    
    def _load_or_create_task(self):
        """加载或创建任务"""
        try:
            self.task = GraphTask.objects.select_related('graph_definition').get(
                task_id=self.task_id
            )
            logger.info(f"加载现有任务: {self.task_id}")
        except GraphTask.DoesNotExist:
            # 创建新任务
            graph_def = GraphDefinition.objects.get(name=self.graph_name)
            self.task = GraphTask.objects.create(
                task_id=self.task_id,
                graph_definition=graph_def,
                user_id=self.user_id,
                session_id=self.session_id,
                status=GraphTask.TaskStatus.PENDING
            )
            logger.info(f"创建新任务: {self.task_id}")
    
    def _load_graph_definition(self):
        """加载 Graph 定义"""
        self.graph_def = self.task.graph_definition
        
        # 加载节点定义
        self.nodes = {}
        node_defs = NodeDefinition.objects.filter(graph=self.graph_def)
        for node_def in node_defs:
            self.nodes[node_def.name] = node_def
        
        # 加载边定义
        self.edges = {}
        edge_defs = EdgeDefinition.objects.filter(graph=self.graph_def)
        for edge_def in edge_defs:
            if edge_def.source_node not in self.edges:
                self.edges[edge_def.source_node] = []
            self.edges[edge_def.source_node].append(edge_def)
        
        logger.info(f"加载Graph定义完成 - 节点数: {len(self.nodes)}, 边数: {len(edge_defs)}")
    
    def _initialize_state(self, initial_query: str, preprocessed_files: Optional[Dict], 
                         conversation_history: Optional[List[Dict]]):
        """初始化或恢复运行时状态"""
        # 尝试从检查点恢复
        checkpoint_data = self.checkpoint_manager.load(self.task_id)
        
        if checkpoint_data:
            self.state = RuntimeState(**checkpoint_data)
            logger.info(f"从检查点恢复状态 - checkpoint_count: {self.state.checkpoint_count}")
        else:
            # 创建新状态
            self.state = RuntimeState(
                task_id=self.task_id,
                session_id=self.session_id,
                user_id=self.user_id,
                user_query=initial_query,
                preprocessed_files=preprocessed_files or {},
                conversation_history=conversation_history or []
            )
            
            # 如果有历史会话，继承状态
            if self.session_id:
                self._inherit_session_state()
            
            # 设置起始节点
            self.state.current_node = self.graph_def.entry_point or "START"
            
            logger.info(f"创建新状态 - 起始节点: {self.state.current_node}")
    
    def _inherit_session_state(self):
        """继承同会话的历史状态"""
        if not self.session_id:
            return
        
        # 查找同会话的历史任务
        historical_tasks = GraphTask.objects.filter(
            session_id=self.session_id,
            status=GraphTask.TaskStatus.COMPLETED
        ).exclude(task_id=self.task_id).order_by('created_at')
        
        historical_states = []
        for task in historical_tasks:
            checkpoint_data = self.checkpoint_manager.load(task.task_id)
            if checkpoint_data:
                historical_states.append(RuntimeState(**checkpoint_data))
        
        if historical_states:
            self.state.inherit_from_session(historical_states)
            logger.info(f"继承了 {len(historical_states)} 个历史状态")
    
    def run(self):
        """执行 Graph"""
        logger.info(f"开始执行Graph - task_id: {self.task_id}")
        
        try:
            # 更新任务状态为运行中
            with transaction.atomic():
                self.task.status = GraphTask.TaskStatus.RUNNING
                self.task.save()
            
            # 主执行循环
            max_iterations = 50  # 防止无限循环
            iteration = 0
            
            while self.state.current_node != "END" and iteration < max_iterations:
                iteration += 1
                logger.info(f"执行迭代 {iteration} - 当前节点: {self.state.current_node}")
                
                # 执行当前节点
                self._execute_node(self.state.current_node)
                
                # 保存检查点
                if iteration % 5 == 0:  # 每5次迭代保存一次
                    self._save_checkpoint()
                
                # 确定下一个节点
                next_node = self._determine_next_node()
                if next_node:
                    self.state.current_node = next_node
                else:
                    logger.warning(f"无法确定下一个节点，结束执行")
                    break
            
            # 执行结束
            self._finalize_execution()
            
        except Exception as e:
            logger.error(f"Graph执行失败 - task_id: {self.task_id}, 错误: {e}", exc_info=True)
            self._handle_execution_error(e)
            raise
    
    def _execute_node(self, node_name: str):
        """执行单个节点"""
        if node_name not in self.nodes:
            raise ValueError(f"节点 {node_name} 不存在")
        
        node_def = self.nodes[node_name]
        logger.info(f"执行节点: {node_name} (类型: {node_def.node_type})")
        
        # 获取节点实现
        node_class = self.node_registry.get_node_class(node_def.node_type)
        if not node_class:
            raise ValueError(f"未找到节点类型 {node_def.node_type} 的实现")
        
        # 创建节点实例并执行
        node_instance = node_class(
            name=node_name,
            config=node_def.config or {}
        )
        
        # 执行节点
        result = node_instance.execute(self.state)
        
        # 更新状态
        self.state.update_action_history({
            "node": node_name,
            "type": node_def.node_type,
            "result": result
        })
        
        logger.info(f"节点 {node_name} 执行完成")
    
    def _determine_next_node(self) -> Optional[str]:
        """确定下一个执行节点"""
        current_node = self.state.current_node
        
        # 获取当前节点的出边
        if current_node not in self.edges:
            logger.info(f"节点 {current_node} 没有出边")
            return "END"
        
        edges = self.edges[current_node]
        
        # 根据条件选择边
        for edge in edges:
            if self._evaluate_edge_condition(edge):
                logger.info(f"选择边: {current_node} -> {edge.target_node}")
                return edge.target_node
        
        # 如果没有匹配的边，使用默认边
        default_edge = next((e for e in edges if not e.condition), None)
        if default_edge:
            logger.info(f"使用默认边: {current_node} -> {default_edge.target_node}")
            return default_edge.target_node
        
        return None
    
    def _evaluate_edge_condition(self, edge: EdgeDefinition) -> bool:
        """评估边的条件"""
        if not edge.condition:
            return False  # 空条件表示默认边
        
        # TODO: 实现条件评估逻辑
        # 这里可以根据 state 中的数据评估条件
        return False
    
    def _save_checkpoint(self):
        """保存检查点"""
        checkpoint_data = self.state.checkpoint()
        self.checkpoint_manager.save(self.task_id, checkpoint_data)
        logger.info(f"保存检查点 - checkpoint_count: {self.state.checkpoint_count}")
    
    def _finalize_execution(self):
        """完成执行"""
        logger.info(f"Graph执行完成 - task_id: {self.task_id}")
        
        # 最后保存一次检查点
        self._save_checkpoint()
        
        # 更新任务状态
        with transaction.atomic():
            self.task.status = GraphTask.TaskStatus.COMPLETED
            self.task.output_data = {
                "final_output": self.state.final_output,
                "action_count": len(self.state.action_history),
                "checkpoint_count": self.state.checkpoint_count
            }
            self.task.save()
    
    def _handle_execution_error(self, error: Exception):
        """处理执行错误"""
        logger.error(f"处理执行错误 - task_id: {self.task_id}")
        
        # 保存错误状态
        self.state.final_output = {"error": str(error)}
        self._save_checkpoint()
        
        # 更新任务状态
        with transaction.atomic():
            self.task.status = GraphTask.TaskStatus.FAILED
            self.task.output_data = {"error": str(error)}
            self.task.save()