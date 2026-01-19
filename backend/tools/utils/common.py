"""
通用工具函数模块
"""

def handle_error(state: dict) -> dict:
    """
    一个通用的错误处理节点。

    当图执行过程中遇到可恢复的错误或需要人工干预时，可以路由到此节点。
    它会记录错误信息，并可以根据配置决定是终止流程还是尝试恢复。

    Args:
        state (dict): 当前的图执行状态。

    Returns:
        dict: 更新后的状态。
    """
    print("进入错误处理流程...")
    error_message = state.get("error", "未知的错误")
    print(f"捕获到错误: {error_message}")
    
    # 在实际应用中，这里可以增加更复杂的逻辑，
    # 例如发送通知、尝试重试或进入一个等待人工干预的状态。
    
    state["final_status"] = "Error"
    state["final_message"] = f"处理失败，错误信息: {error_message}"
    
    return state


def end_process(state: dict) -> dict:
    """
    图执行的终点节点。

    这是一个空操作，标志着一个工作流程的正常或异常结束。
    它不执行任何操作，只是作为图的最终汇合点。

    Args:
        state (dict): 当前的图执行状态。

    Returns:
        dict: 未经修改的状态。
    """
    print("图执行流程结束。")
    return state