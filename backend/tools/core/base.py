from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
import logging
logger = logging.getLogger("django")
import time
import traceback
import os
from .types import ToolType
from .output_format import ToolOutputValidator

class BaseTool(ABC):
    """所有工具的基础抽象类，提供统一的状态管理和日志记录"""
    description: str = "No description available for this tool."
    tool_type: Optional[ToolType] = None  # 工具类型，由子类或注册时设置
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.tool_name = self.__class__.__name__
        
    def get_configured_model(self, tool_input: Optional[Dict[str, Any]] = None) -> str:
        """
        获取工具应该使用的模型名称
        
        优先级（从高到低）：
        1. tool_input中的model_name（运行时覆盖）
        2. config中的model_name（工具配置）
        3. 环境变量DEFAULT_MODEL
        4. 硬编码默认值
        
        Args:
            tool_input: 工具输入，可能包含model_name覆盖
            
        Returns:
            模型名称字符串
        """
        # 1. 检查运行时覆盖
        if tool_input and 'model_name' in tool_input:
            logger.info(f"[{self.tool_name}] 使用运行时覆盖模型: {tool_input['model_name']}")
            return tool_input['model_name']
        
        # 2. 检查工具配置
        if 'model_name' in self.config:
            logger.info(f"[{self.tool_name}] 使用配置的模型: {self.config['model_name']}")
            return self.config['model_name']
        
        # 3. 使用环境变量或默认值
        default_model = os.getenv('DEFAULT_MODEL', 'gemini-2.5-flash')
        logger.info(f"[{self.tool_name}] 使用默认模型: {default_model}")
        return default_model
    
    def execute_with_logging(self, tool_input: Dict[str, Any], runtime_state: Any = None, user_id: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        """
        带有统一日志记录的执行方法包装器
        
        Args:
            tool_input: 工具输入参数
            runtime_state: 运行时状态对象（可选），由执行器自动传入
            user_id: 用户标识符（可选），用于个性化服务和审计追踪
        """
        execution_id = f"{self.tool_name}_{int(time.time())}"
        start_time = time.time()
        
        logger.info(f"[{self.tool_name}] 开始执行")
        
        # 清晰记录工具收到的输入
        import json
        safe_input = self._safe_log_input(tool_input)
        try:
            formatted_input = json.dumps(safe_input, indent=2, ensure_ascii=False)
        except Exception:
            formatted_input = str(safe_input)
        logger.warning(
            f"\n{'='*60}\n[{self.tool_name}] 收到的输入参数:\n{'-'*60}\n"
            f"{formatted_input}\n{'='*60}\n"
        )
        
        try:
            # 输入验证
            validation_result = self.validate_tool_input(tool_input)
            if not validation_result["valid"]:
                error_msg = f"输入验证失败: {validation_result['error']}"
                logger.error(error_msg)
                return self.create_error_response(error_msg, execution_id)
            
            # 执行工具逻辑，传递 runtime_state 和 user_id
            result = self.execute(tool_input, runtime_state, user_id)
            
            # 标准化输出格式
            standardized_result = self._standardize_output(result, execution_id)
            
            execution_time = time.time() - start_time
            logger.info(f"[{self.tool_name}] 执行完成 - 状态: {standardized_result.get('status', 'unknown')}, 耗时: {execution_time:.2f}s")
            
            return standardized_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{self.tool_name} 执行失败 [ID: {execution_id}]\n" +
                        f"执行时间: {execution_time:.2f}秒\n" +
                        f"错误类型: {type(e).__name__}\n" +
                        f"错误信息: {str(e)}\n" +
                        f"错误堆栈: {traceback.format_exc()}")
            
            return self.create_error_response(str(e), execution_id, error_type=type(e).__name__)
    
    @abstractmethod
    def execute(self, tool_input: Dict[str, Any], runtime_state: Any = None, user_id: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        """
        执行工具逻辑的抽象方法。
        
        Args:
            tool_input: 工具输入参数
            runtime_state: 运行时状态对象（可选），由执行器自动传入
            user_id: 用户标识符（可选），用于个性化服务和审计追踪
            
        Returns:
            Dict[str, Any]: 工具的输出结果，应符合新的输出格式：
            {
                "status": "success/error/partial",
                "output": 语义化的模态数据（文本为主）,
                "type": "text/markdown/chart/image/mixed",
                "raw_data": 工具核心能力的原始输出（可选）,
                "metrics": ["指标1", "指标2", ...],
                "metadata": {...},
                "message": "一句话描述"
            }
            
        Note:
            - 所有工具都应支持 runtime_state 参数，但可以选择不使用它
            - runtime_state 由执行器自动传入，LLM 不需要构造这个参数
            - user_id 用于标识用户身份，支持个性化和审计功能
        """
        pass

    @abstractmethod
    def get_input_schema(self) -> Dict[str, Any]:
        """
        返回工具所需的输入状态（state['tool_input']）的JSON Schema定义。
        子类必须实现此方法以明确其输入要求。
        """
        pass
    
    def get_parameter_description(self) -> str:
        """
        从 JSON Schema 生成简化的参数描述
        返回格式化的参数列表字符串，用于在 prompt 中展示
        """
        schema = self.get_input_schema()
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        if not properties:
            return "- No parameters required"
        
        param_lines = []
        
        # 遍历所有属性
        for param_name, param_schema in properties.items():
            # 获取参数类型
            param_type = param_schema.get("type", "any")
            
            # 处理数组类型
            if param_type == "array":
                items_type = param_schema.get("items", {}).get("type", "any")
                param_type = f"array[{items_type}]"
            
            # 处理对象类型
            elif param_type == "object":
                # 如果有详细的属性定义，可以展示子属性
                sub_props = param_schema.get("properties", {})
                if sub_props:
                    param_type = "object"  # 简化显示，具体结构在描述中说明
            
            # 判断是否必需
            is_required = param_name in required
            required_tag = "required" if is_required else "optional"
            
            # 获取描述
            description = param_schema.get("description", "")
            
            # 获取默认值
            default_value = param_schema.get("default")
            if default_value is not None:
                description += f" (default: {default_value})"
            
            # 获取枚举值
            enum_values = param_schema.get("enum")
            if enum_values:
                description += f" (options: {', '.join(map(str, enum_values))})"
            
            # 格式化参数行
            param_line = f"- {param_name} ({param_type}, {required_tag}): {description}"
            param_lines.append(param_line)
            
            # 如果是对象类型且有子属性，添加子属性说明
            if param_type == "object" and isinstance(param_schema.get("properties"), dict):
                sub_properties = param_schema["properties"]
                for sub_key, sub_schema in sub_properties.items():
                    sub_desc = sub_schema.get("description", "")
                    param_lines.append(f"  - {sub_key}: {sub_desc}")
        
        return "\n".join(param_lines)
    
    def validate_tool_input(self, tool_input: Dict[str, Any]) -> Dict[str, bool]:
        """验证工具输入的统一方法"""
        try:
            schema = self.get_input_schema()
            required_fields = schema.get("required", [])
            
            # 检查必需字段
            for field in required_fields:
                if field not in tool_input:
                    return {
                        "valid": False,
                        "error": f"缺少必需字段: {field}"
                    }
            
            # 可以在此处添加更复杂的 JSON Schema 验证
            return {"valid": True, "error": None}
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"输入验证过程中发生错误: {str(e)}"
            }
    
    def create_success_response(self, data: Any, execution_id: str, message: str = "执行成功") -> Dict[str, Any]:
        """创建统一的成功响应格式（兼容旧版本）"""
        return {
            "status": "success",
            "message": message,
            "execution_id": execution_id,
            "tool_name": self.tool_name,
            "data": data,
            "timestamp": time.time()
        }
    
    def create_error_response(self, error_message: str, execution_id: str, error_type: str = "ToolExecutionError") -> Dict[str, Any]:
        """创建统一的错误响应格式"""
        return {
            "status": "error",
            "message": error_message,
            "output": f"执行失败: {error_message}",
            "type": "text",
            "metrics": [],
            "metadata": {
                "execution_id": execution_id,
                "tool_name": self.tool_name,
                "timestamp": time.time(),
                "error_type": error_type
            }
        }
    
    def _standardize_output(self, result: Dict[str, Any], execution_id: str) -> Dict[str, Any]:
        """
        标准化工具输出格式，符合新的 ToolOutputFormat 规范。
        
        新的统一输出格式：
        - status: 执行状态 (success/error/partial)
        - output: 语义化的模态数据（文本为主）
        - type: 输出类型 (text/markdown/chart/image/mixed)
        - raw_data: 工具核心能力的原始输出
        - metrics: 文本化的关键指标列表
        - metadata: 执行元数据
        - message: 一句话描述
        """
        # 如果已经是标准格式，只需补充元数据
        if ToolOutputValidator.validate(result):
            if "metadata" not in result:
                result["metadata"] = {}
            result["metadata"].update({
                "execution_id": execution_id,
                "tool_name": self.tool_name,
                "timestamp": time.time()
            })
            return result
        
        # 使用验证器进行智能转换
        standardized = ToolOutputValidator.ensure_format(result)
        
        # 补充元数据
        standardized["metadata"].update({
            "execution_id": execution_id,
            "tool_name": self.tool_name,
            "timestamp": time.time()
        })
        
        # 如果没有消息，生成默认消息
        if not standardized.get("message"):
            if standardized["status"] == "error":
                standardized["message"] = f"{self.tool_name}执行失败"
            else:
                standardized["message"] = f"{self.tool_name}执行成功"
        
        return standardized
    
    def _safe_log_input(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """安全地记录输入参数，避免敏感信息泄露"""
        safe_input = {}
        sensitive_keys = {"api_key", "password", "token", "secret"}
        
        for key, value in tool_input.items():
            if key.lower() in sensitive_keys:
                safe_input[key] = "***HIDDEN***"
            elif isinstance(value, str):
                if len(value) > 500:
                    safe_input[key] = f"{value[:500]}... [截断，总长度: {len(value)}]"
                else:
                    safe_input[key] = value
            elif isinstance(value, dict):
                # 递归处理嵌套字典
                safe_input[key] = self._safe_log_dict(value, max_depth=3)
            elif isinstance(value, list):
                # 处理列表
                if len(value) > 5:
                    safe_input[key] = value[:5] + [f"... 还有 {len(value) - 5} 项"]
                else:
                    safe_input[key] = value
            elif isinstance(value, bytes):
                # 处理二进制数据
                safe_input[key] = f"<二进制数据，长度: {len(value)} 字节>"
            else:
                safe_input[key] = value
        
        return safe_input
    
    def _safe_log_dict(self, d: Dict[str, Any], max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
        """递归处理嵌套字典，限制深度"""
        if current_depth >= max_depth:
            return "<嵌套过深，已省略...>"
        
        safe_dict = {}
        for k, v in d.items():
            if isinstance(v, dict):
                safe_dict[k] = self._safe_log_dict(v, max_depth, current_depth + 1)
            elif isinstance(v, str) and len(v) > 200:
                safe_dict[k] = f"{v[:200]}... [截断]"
            else:
                safe_dict[k] = v
        
        return safe_dict
    
    def _ensure_text_format(self, data: Any) -> str:
        """
        确保数据是用户友好的文本格式
        
        将 JSON 字符串、字典等格式转换为易读的纯文本
        """
        if data is None:
            return ""
        
        if isinstance(data, str):
            # 检测是否为 JSON 字符串
            if data.strip().startswith('{') and data.strip().endswith('}'):
                try:
                    import json
                    json_obj = json.loads(data)
                    return self._format_json_to_text(json_obj)
                except json.JSONDecodeError:
                    # 不是有效的 JSON，直接返回
                    return data
            return data
        
        elif isinstance(data, dict):
            return self._format_json_to_text(data)
        
        elif isinstance(data, list):
            # 格式化列表
            formatted_items = []
            for i, item in enumerate(data, 1):
                if isinstance(item, dict):
                    formatted_items.append(f"{i}. {self._format_json_to_text(item)}")
                else:
                    formatted_items.append(f"{i}. {str(item)}")
            return "\n".join(formatted_items)
        
        else:
            return str(data)
    
    def _format_json_to_text(self, json_obj: Dict[str, Any], level: int = 0) -> str:
        """
        将 JSON 对象格式化为易读的文本
        
        支持嵌套结构，自动处理中英文混合的键名
        """
        if not json_obj:
            return ""
        
        if level > 3:  # 防止过深的嵌套
            return str(json_obj)
        
        formatted_parts = []
        indent = "  " * level
        
        for key, value in json_obj.items():
            # 清理和格式化键名
            clean_key = key
            
            # 处理常见的格式
            if '(' in clean_key and ')' in clean_key:
                # 将英文括号转换为中文括号
                clean_key = clean_key.replace('(', '（').replace(')', '）')
            
            # 格式化值
            if isinstance(value, dict):
                if level == 0:
                    formatted_parts.append(f"### {clean_key}\n")
                else:
                    formatted_parts.append(f"{indent}**{clean_key}**:")
                formatted_parts.append(self._format_json_to_text(value, level + 1))
            elif isinstance(value, list):
                if level == 0:
                    formatted_parts.append(f"### {clean_key}\n")
                else:
                    formatted_parts.append(f"{indent}**{clean_key}**:")
                for item in value:
                    if isinstance(item, dict):
                        formatted_parts.append(f"{indent}  - {self._format_json_to_text(item, level + 2)}")
                    else:
                        formatted_parts.append(f"{indent}  - {str(item)}")
            elif value:  # 只显示非空值
                if level == 0:
                    # 顶级字段使用三级标题
                    formatted_parts.append(f"### {clean_key}\n\n{value}")
                else:
                    formatted_parts.append(f"{indent}**{clean_key}**: {value}")
        
        return "\n\n".join(formatted_parts) if level == 0 else "\n".join(formatted_parts)