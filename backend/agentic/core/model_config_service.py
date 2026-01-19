"""
节点模型配置服务 (NodeModelConfigService)
================================================================================

文件描述:
    提供统一的接口来获取和管理AI节点的模型配置，支持多层级配置优先级管理。
    该服务是agentic系统中模型配置管理的核心组件，负责处理节点模型的动态分配和配置验证。

主要功能:
    - 节点模型配置的获取和管理
    - 多级配置优先级处理（运行时覆盖 > nodes_map > 数据库 > 环境变量 > 默认值）
    - 模型存在性验证
    - 工具节点配置管理
    - 可用模型列表查询

输入:
    - node_name (str): 节点名称，用于标识具体的AI处理节点
    - nodes_map (Optional[Dict]): 运行时节点配置映射表
    - override_model (Optional[str]): 运行时模型覆盖参数
    - tool_name (str): 工具名称，用于获取工具节点配置
    - model_name (str): 需要验证的模型名称

输出:
    - 模型名称 (Optional[str]): 根据优先级返回的模型标识
    - 配置字典 (Dict[str, Any]): 包含模型和其他配置参数的完整配置
    - 验证结果 (bool): 模型存在性验证结果
    - 模型列表 (list): 系统可用模型信息列表

内部处理流程:
    1. get_model_for_node(): 
       运行时覆盖检查 -> nodes_map查找 -> 数据库查询 -> 环境变量获取 -> 默认值返回
    
    2. validate_model_exists(): 
       数据库查询 -> 模型存在性检查 -> 布尔结果返回
    
    3. get_tool_config(): 
       nodes_map配置合并 -> 数据库配置合并 -> 默认模型补充 -> 完整配置返回
    
    4. get_available_models(): 
       数据库模型表查询 -> 模型信息列表构建 -> 结果返回

执行逻辑:
    - 采用级联配置模式，优先级从高到低依次检查各配置源
    - 使用数据库连接恢复机制确保配置读取的可靠性
    - 异常处理确保配置获取失败时的服务稳定性
    - 日志记录提供配置决策的可追溯性

函数调用关系:
    NodeModelConfigService.get_model_for_node()
    ├── get_default_model() (内部调用)
    ├── Node.objects.filter() (数据库查询)
    └── ensure_db_connection_safe() (连接管理)
    
    NodeModelConfigService.validate_model_exists()
    └── LLMModel.objects.filter() (模型验证)
    
    NodeModelConfigService.get_tool_config()
    ├── get_default_model() (内部调用)
    └── Node.objects.filter() (数据库查询)
    
    NodeModelConfigService.get_available_models()
    └── LLMModel.objects.all() (模型列表查询)

外部函数依赖 (非Python标准库):
    - agentic.models.Node: 节点数据模型，用于存储和查询节点配置信息
    - router.models.LLMModel: LLM模型数据模型，用于模型管理和验证
    - backend.utils.db_connection.ensure_db_connection_safe: 数据库连接恢复工具，确保数据库操作的可靠性

配置优先级 (从高到低):
    1. override_model: 运行时传入的模型覆盖参数
    2. nodes_map: 内存中的节点配置映射
    3. 数据库Node表: 持久化的节点配置
    4. DEFAULT_MODEL环境变量: 系统级默认模型配置
    5. None: 无配置时的默认返回值

使用场景:
    - AI节点执行时的模型选择
    - 工具节点的配置管理  
    - 模型配置的动态调整
    - 系统模型可用性检查
"""

import os
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class NodeModelConfigService:
    """统一的节点模型配置服务"""
    
    @staticmethod
    def get_default_model() -> Optional[str]:
        """
        获取系统默认模型
        
        Returns:
            模型名称，如果未配置则返回None
        """
        return os.getenv('DEFAULT_MODEL')
    
    @staticmethod
    def get_model_for_node(node_name: str, nodes_map: Optional[Dict] = None, 
                           override_model: Optional[str] = None) -> Optional[str]:
        """
        获取指定节点应该使用的模型
        
        优先级（从高到低）：
        1. override_model - 运行时覆盖的模型
        2. nodes_map中的节点配置
        3. 数据库中节点的config配置
        4. 环境变量DEFAULT_MODEL
        5. 硬编码默认值
        
        Args:
            node_name: 节点名称
            nodes_map: 运行时节点配置映射
            override_model: 运行时覆盖的模型名称
            
        Returns:
            模型名称字符串
        """
        # 1. 检查运行时覆盖
        if override_model:
            logger.info(f"节点 {node_name} 使用运行时覆盖模型: {override_model}")
            return override_model
        
        # 2. 检查nodes_map中的配置
        if nodes_map and node_name in nodes_map:
            node_config = nodes_map[node_name]
            if hasattr(node_config, 'config') and node_config.config:
                model_name = node_config.config.get('model_name')
                if model_name:
                    # logger.info(f"节点 {node_name} 使用nodes_map配置的模型: {model_name}")
                    return model_name
        
        # 3. 从数据库加载节点配置
        try:
            from agentic.models import Node
            from backend.utils.db_connection import ensure_db_connection_safe
            # 确保数据库连接有效（使用更强力的连接恢复）
            ensure_db_connection_safe()
            db_node = Node.objects.filter(name=node_name).first()
            if db_node and db_node.config and 'model_name' in db_node.config:
                model_name = db_node.config['model_name']
                logger.info(f"节点 {node_name} 使用数据库配置的模型: {model_name}")
                return model_name
        except Exception as e:
            logger.warning(f"从数据库加载节点 {node_name} 配置失败: {e}")
        
        # 4. 使用默认模型
        default_model = NodeModelConfigService.get_default_model()
        if default_model:
            logger.info(f"节点 {node_name} 使用默认模型: {default_model}")
            return default_model
        
        # 5. 没有任何配置
        logger.warning(f"节点 {node_name} 没有找到任何模型配置")
        return None
    
    @staticmethod
    def validate_model_exists(model_name: str) -> bool:
        """
        验证模型是否存在于系统中
        
        Args:
            model_name: 模型名称
            
        Returns:
            模型是否存在
        """
        try:
            from router.models import LLMModel
            return LLMModel.objects.filter(model_id=model_name).exists()
        except Exception as e:
            logger.error(f"验证模型 {model_name} 失败: {e}")
            return False
    
    @staticmethod
    def get_tool_config(tool_name: str, nodes_map: Optional[Dict] = None) -> Dict[str, Any]:
        """
        获取工具节点的完整配置，包括模型配置
        
        Args:
            tool_name: 工具名称
            nodes_map: 运行时节点配置映射
            
        Returns:
            工具配置字典
        """
        config = {}
        
        # 尝试从nodes_map获取配置
        if nodes_map and tool_name in nodes_map:
            node_config = nodes_map[tool_name]
            if hasattr(node_config, 'config') and node_config.config:
                config.update(node_config.config)
        
        # 尝试从数据库获取配置
        if not config:
            try:
                from agentic.models import Node
                db_node = Node.objects.filter(name=tool_name).first()
                if db_node and db_node.config:
                    config.update(db_node.config)
            except Exception as e:
                logger.warning(f"从数据库加载工具 {tool_name} 配置失败: {e}")
        
        # 确保有model_name
        if 'model_name' not in config:
            config['model_name'] = NodeModelConfigService.get_default_model()
        
        return config
    
    @staticmethod
    def get_available_models() -> list:
        """
        获取系统中所有可用的模型列表
        
        Returns:
            模型信息列表
        """
        try:
            from router.models import LLMModel
            models = LLMModel.objects.all().values('model_id', 'name', 'model_type')
            return list(models)
        except Exception as e:
            logger.error(f"获取可用模型列表失败: {e}")
            return []