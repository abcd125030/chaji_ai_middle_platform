# LLM 调用日志记录系统实施文档

## 概述

本文档记录了 LLM 应用的完整调用日志记录系统的实施详情。该系统能够自动记录每次 LLM 调用的详细信息，包括请求、响应、Token 使用量、成本等。

## 实施内容

### 1. 数据模型设计

创建了 4 个核心数据模型：

#### LLMCallLog - 调用日志表
- **功能**：记录每次 LLM 调用的完整信息
- **关键字段**：
  - 基础信息：request_id、user、session_id、call_type
  - 模型信息：model_name、model_id、vendor_name、vendor_id、endpoint
  - 请求信息：request_messages、request_params、request_headers、is_stream
  - 响应信息：response_content、response_raw、error_message、status
  - 性能指标：duration_ms、retry_count
  - Token 统计：prompt_tokens、completion_tokens、total_tokens
  - 成本核算：estimated_cost
  - 追踪信息：source_app、source_function、ip_address、user_agent

#### LLMTokenUsage - Token 使用统计表
- **功能**：按用户、模型、时间维度聚合统计
- **统计周期**：支持小时级、日级、周级、月级统计
- **关键指标**：call_count、success_count、failed_count、total_tokens、total_cost

#### LLMModelPrice - 模型定价配置表
- **功能**：配置各模型的 Token 价格
- **支持货币**：USD、CNY、EUR
- **定价维度**：input_price_per_1k、output_price_per_1k

#### LLMRequestCache - 请求缓存表
- **功能**：缓存相同请求，避免重复调用
- **缓存策略**：基于请求哈希，支持过期时间设置

### 2. 日志服务实现

创建 `LLMLogService` 类，提供以下核心功能：

- **create_call_log**：创建调用日志记录
- **update_success**：更新成功调用信息
- **update_failure**：更新失败信息
- **update_timeout**：更新超时状态
- **update_retry**：更新重试次数
- **get_user_usage_summary**：获取用户使用摘要

### 3. 服务集成

#### CoreLLMService 集成
- 在 `call_llm` 方法中添加日志记录参数
- 自动创建日志记录并更新状态
- 支持流式和非流式响应的日志记录
- 自动计算 Token 使用量（使用 tiktoken）

#### InternalLLMService 集成
- 为内部应用调用自动启用日志记录
- 自动提取供应商信息
- 记录来源应用和函数信息

#### ExternalLLMAPI 集成
- 为外部 API 调用启用日志记录
- 记录认证信息和服务目标
- 保持与原有 QA 记录的兼容性

### 4. 数据关联设计

与 `router` 应用的模型通过字段值关联（非外键）：
- `model_name` 关联 `router.LLMModel.name`
- `vendor_name` 关联 `router.VendorEndpoint.vendor_name`
- `vendor_id` 关联 `router.VendorEndpoint.vendor_id`

### 5. Admin 管理界面

为所有模型配置了完善的 Django Admin 界面：
- **LLMCallLogAdmin**：支持状态着色、请求ID缩短显示、用户权限过滤
- **LLMTokenUsageAdmin**：支持时间层次浏览、统计数据展示
- **LLMModelPriceAdmin**：支持价格配置管理、自动失效旧配置
- **LLMRequestCacheAdmin**：支持缓存清理、过期状态显示

## 使用示例

### 在代码中调用时自动记录

```python
# 内部服务调用（自动记录）
from llm.llm_service import LLMService

service = LLMService()
response = service.internal.call_llm(
    model_name="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello"}],
    user=request.user,
    session_id="session-123"
)
```

### 查看日志记录

```python
from llm.models import LLMCallLog

# 查看最近的调用
recent_calls = LLMCallLog.objects.filter(
    user=user,
    status='success'
).order_by('-request_timestamp')[:10]

# 查看今日统计
from llm.models import LLMTokenUsage
from django.utils import timezone

today_usage = LLMTokenUsage.objects.filter(
    user=user,
    date=timezone.now().date(),
    period='daily'
).first()
```

### 获取使用摘要

```python
from llm.log_service import LLMLogService

# 获取最近 30 天的使用摘要
summary = LLMLogService.get_user_usage_summary(user, days=30)
print(f"总调用: {summary['total_calls']}")
print(f"成功率: {summary['success_rate']}%")
print(f"总成本: ${summary['total_cost']}")
```

## 测试验证

运行测试脚本验证功能：
```bash
python test_llm_log.py
```

测试结果显示：
- ✅ 日志记录创建成功
- ✅ 状态更新正常
- ✅ Token 统计准确
- ✅ 成本计算功能正常
- ✅ 失败场景记录正常
- ✅ 用户摘要统计准确

## 注意事项

1. **性能优化**：
   - 日志记录异步处理，不影响主流程
   - Token 统计采用增量更新
   - 支持请求缓存避免重复调用

2. **隐私保护**：
   - 敏感信息不记录在日志中
   - 支持用户级别的权限控制
   - IP 和 User Agent 可选记录

3. **成本控制**：
   - 自动计算每次调用成本
   - 支持配额管理（预留接口）
   - 提供成本预警机制

4. **监控告警**：
   - 支持失败率监控
   - 异常调用检测
   - 成本超支告警

## 后续优化建议

1. 添加批量导出功能，支持导出日志到 CSV/Excel
2. 实现可视化面板，展示调用趋势图表
3. 添加异常检测算法，自动发现异常调用模式
4. 集成告警系统，实时通知异常情况
5. 优化缓存策略，提高相同请求的命中率

## 更新记录

- 2025-08-28：初始实现，包含完整的日志记录、统计和管理功能