"""
输出工具执行器服务

负责管理输出工具(generator)的执行、重试和恢复机制。

核心职责:
1. 执行输出工具并处理异常
2. 实现指数退避重试策略
3. 分类错误类型并决定恢复策略
4. 管理备选工具切换逻辑
5. 记录详细的重试历史

设计原则:
- 单一职责: 仅处理输出工具执行相关逻辑
- 模块化: 独立于processor主流程
- 可测试: 所有方法都可独立单元测试
- 可观测: 完整的日志和历史记录

作者: Claude Code
创建日期: 2025-10-13
"""

import logging
import time
import traceback
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger('django')


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3  # 最大重试次数
    backoff_delays: List[float] = None  # 退避延迟时间列表(秒)

    def __post_init__(self):
        if self.backoff_delays is None:
            # 默认指数退避: 第1次立即, 第2次2秒, 第3次4秒
            self.backoff_delays = [0, 2, 4]


class ErrorType:
    """错误类型常量"""
    # 可恢复错误 (网络、超时、限流等)
    NETWORK_ERROR = "NetworkError"
    TIMEOUT_ERROR = "TimeoutError"
    RATE_LIMIT_ERROR = "RateLimitError"
    TEMPORARY_ERROR = "TemporaryError"

    # 不可恢复错误 (参数、权限、业务逻辑错误)
    VALIDATION_ERROR = "ValidationError"
    AUTHENTICATION_ERROR = "AuthenticationError"
    PERMISSION_ERROR = "PermissionError"
    BUSINESS_LOGIC_ERROR = "BusinessLogicError"

    # 可恢复错误集合
    RECOVERABLE_ERRORS = {
        NETWORK_ERROR,
        TIMEOUT_ERROR,
        RATE_LIMIT_ERROR,
        TEMPORARY_ERROR,
    }


class OutputToolExecutor:
    """
    输出工具执行器

    管理generator工具的执行、重试和恢复流程
    """

    def __init__(self, retry_config: Optional[RetryConfig] = None):
        """
        初始化执行器

        Args:
            retry_config: 重试配置，默认使用标准配置
        """
        self.retry_config = retry_config or RetryConfig()
        self.retry_history: List[Dict[str, Any]] = []

    def classify_error(self, exception: Exception) -> str:
        """
        分类错误类型

        根据异常类型判断是否可恢复:
        - 可恢复错误: 触发重试机制
        - 不可恢复错误: 直接标记失败

        Args:
            exception: 捕获的异常对象

        Returns:
            错误类型字符串 (ErrorType常量)

        Examples:
            >>> executor = OutputToolExecutor()
            >>> executor.classify_error(TimeoutError("timeout"))
            'TimeoutError'
            >>> executor.classify_error(ValueError("invalid param"))
            'ValidationError'
        """
        exception_type = type(exception).__name__
        exception_message = str(exception).lower()

        # 超时错误
        if 'timeout' in exception_type.lower() or 'timeout' in exception_message:
            return ErrorType.TIMEOUT_ERROR

        # 网络错误
        if any(keyword in exception_type.lower() for keyword in ['connection', 'network', 'socket']):
            return ErrorType.NETWORK_ERROR

        # 限流错误
        if 'rate' in exception_message or 'limit' in exception_message or 'throttle' in exception_message:
            return ErrorType.RATE_LIMIT_ERROR

        # 认证/权限错误
        if any(keyword in exception_type.lower() for keyword in ['auth', 'permission', 'forbidden']):
            if 'auth' in exception_type.lower():
                return ErrorType.AUTHENTICATION_ERROR
            return ErrorType.PERMISSION_ERROR

        # 参数验证错误
        if any(keyword in exception_type.lower() for keyword in ['value', 'type', 'attribute', 'key']):
            return ErrorType.VALIDATION_ERROR

        # 默认为临时错误(可恢复)
        return ErrorType.TEMPORARY_ERROR

    def is_recoverable(self, error_type: str) -> bool:
        """
        判断错误是否可恢复

        Args:
            error_type: 错误类型字符串

        Returns:
            True 如果可恢复, False 否则
        """
        return error_type in ErrorType.RECOVERABLE_ERRORS

    def execute_with_retry(
        self,
        tool_func: callable,
        tool_name: str,
        tool_args: Dict[str, Any],
        task_id: str,
    ) -> Tuple[bool, Optional[Any], Optional[Dict[str, Any]]]:
        """
        执行工具并在失败时重试

        实现指数退避重试策略:
        - 第1次: 立即执行
        - 第2次: 等待2秒后重试
        - 第3次: 等待4秒后重试

        Args:
            tool_func: 工具函数可调用对象
            tool_name: 工具名称
            tool_args: 工具参数字典
            task_id: 任务ID

        Returns:
            (success, result, error_details)
            - success: 是否成功
            - result: 执行结果(成功时)
            - error_details: 错误详情(失败时)

        Side Effects:
            - 更新 self.retry_history
            - 记录详细的重试日志
        """
        self.retry_history = []  # 重置历史

        for attempt in range(1, self.retry_config.max_attempts + 1):
            try:
                logger.info(f"""
[OUTPUT_TOOL_EXECUTOR] 开始执行输出工具
任务ID: {task_id}
工具名称: {tool_name}
尝试次数: {attempt}/{self.retry_config.max_attempts}
""")

                # 如果不是第一次尝试，等待退避时间
                if attempt > 1:
                    delay = self.retry_config.backoff_delays[attempt - 1]
                    if delay > 0:
                        logger.warning(f"""
[OUTPUT_TOOL_EXECUTOR] 重试前等待
工具: {tool_name}
等待时间: {delay}秒
尝试次数: {attempt}/{self.retry_config.max_attempts}
""")
                        time.sleep(delay)

                # 执行工具
                start_time = time.time()
                result = tool_func(**tool_args)
                execution_time_ms = int((time.time() - start_time) * 1000)

                logger.info(f"""
[OUTPUT_TOOL_EXECUTOR] 工具执行成功
工具: {tool_name}
执行时间: {execution_time_ms}ms
尝试次数: {attempt}
""")

                # 记录成功的尝试
                self.retry_history.append({
                    "attempt": attempt,
                    "tool_name": tool_name,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "error": None,
                    "recovered": attempt > 1,
                    "execution_time_ms": execution_time_ms,
                })

                return True, result, None

            except Exception as e:
                error_type = self.classify_error(e)
                is_recoverable = self.is_recoverable(error_type)

                logger.warning(f"""
[OUTPUT_TOOL_EXECUTOR] 工具执行失败
工具: {tool_name}
尝试次数: {attempt}/{self.retry_config.max_attempts}
错误类型: {error_type}
错误消息: {str(e)}
可恢复: {is_recoverable}
""")

                # 记录失败的尝试
                self.retry_history.append({
                    "attempt": attempt,
                    "tool_name": tool_name,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "error": str(e),
                    "error_type": error_type,
                    "recovered": False,
                })

                # 如果是不可恢复错误，立即放弃
                if not is_recoverable:
                    logger.error(f"""
[OUTPUT_TOOL_EXECUTOR] 检测到不可恢复错误，停止重试
工具: {tool_name}
错误类型: {error_type}
""")
                    return False, None, {
                        "error_type": error_type,
                        "error_message": str(e),
                        "stack_trace": traceback.format_exc(),
                        "recovery_attempts": attempt,
                        "recoverable": False,
                    }

                # 如果已达最大重试次数
                if attempt >= self.retry_config.max_attempts:
                    logger.error(f"""
[OUTPUT_TOOL_EXECUTOR] 已达最大重试次数，执行失败
工具: {tool_name}
总尝试次数: {attempt}
""")
                    return False, None, {
                        "error_type": error_type,
                        "error_message": str(e),
                        "stack_trace": traceback.format_exc(),
                        "recovery_attempts": attempt,
                        "recoverable": True,
                    }

        # 不应该到达这里
        return False, None, {
            "error_type": "UnknownError",
            "error_message": "Unexpected execution path",
            "recovery_attempts": self.retry_config.max_attempts,
        }

    def try_alternative_tool(
        self,
        available_tools: List[Dict[str, Any]],
        failed_tools: List[str],
    ) -> Optional[str]:
        """
        尝试切换到备选输出工具

        从可用的generator工具列表中选择下一个备选工具，
        排除已经失败的工具。

        Args:
            available_tools: 可用工具列表，每个工具是字典 {"name": str, "priority": int}
            failed_tools: 已失败的工具名称列表

        Returns:
            备选工具名称，如果没有可用备选则返回None

        Examples:
            >>> executor = OutputToolExecutor()
            >>> tools = [
            ...     {"name": "TextGenerator", "priority": 1},
            ...     {"name": "MarkdownGenerator", "priority": 2},
            ... ]
            >>> executor.try_alternative_tool(tools, ["TextGenerator"])
            'MarkdownGenerator'
        """
        # 过滤掉已失败的工具
        remaining_tools = [
            tool for tool in available_tools
            if tool.get("name") not in failed_tools
        ]

        if not remaining_tools:
            logger.warning("""
[OUTPUT_TOOL_EXECUTOR] 无可用备选工具
已失败工具: {failed_tools}
""")
            return None

        # 按优先级排序(priority越小越优先)
        remaining_tools.sort(key=lambda t: t.get("priority", 999))

        alternative_tool = remaining_tools[0]["name"]

        logger.info(f"""
[OUTPUT_TOOL_EXECUTOR] 找到备选工具
备选工具: {alternative_tool}
剩余工具数: {len(remaining_tools)}
已失败工具: {', '.join(failed_tools)}
""")

        return alternative_tool

    def get_retry_history(self) -> List[Dict[str, Any]]:
        """
        获取重试历史记录

        Returns:
            重试历史列表，每个条目包含:
            - attempt: 尝试次数
            - tool_name: 工具名称
            - timestamp: 时间戳
            - error: 错误信息(如有)
            - recovered: 是否恢复成功
        """
        return self.retry_history.copy()
