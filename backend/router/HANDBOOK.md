# Router 模块完整手册

## 目录

1. [模块概述](#模块概述)
2. [核心架构](#核心架构)
3. [数据模型详解](#数据模型详解)
4. [配置流程](#配置流程)
5. [数据流转分析](#数据流转分析)
6. [适配器系统](#适配器系统)
7. [API接口说明](#api接口说明)
8. [集成指南](#集成指南)
9. [调试与故障排除](#调试与故障排除)
10. [最佳实践](#最佳实践)

## 模块概述

Router模块是一个统一的AI模型路由系统，负责管理和调度不同供应商的各类AI模型（LLM、Embedding、Rerank等）。它通过适配器模式处理不同供应商API的差异，提供统一的调用接口。

### 核心功能

- **多供应商管理**：支持OpenAI、Anthropic、阿里云、百度等多个AI供应商
- **多模型类型**：支持文本生成、推理、视觉、语音、嵌入、重排序等多种模型类型
- **统一接口**：通过适配器模式提供统一的调用接口，屏蔽底层差异
- **动态配置**：支持通过Django Admin或API动态配置模型参数
- **性能统计**：自动记录调用次数、成功率等统计信息

## 核心架构

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        调用方（如：Pagtive）                    │
└──────────────────────────┬──────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     ModelService                            │
│  - call_model()：统一调用入口                                 │
│  - _prepare_request()：准备请求                              │
│  - _send_request()：发送HTTP请求                             │
└──────────────────────────┬──────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     LLMModel                                │
│  - model_id：模型标识                                        │
│  - adapter_config：适配器配置                                │
│  - get_adapter()：获取适配器实例                             │
└──────────────────────────┬──────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  AdapterFactory                             │
│  - create_adapter()：创建适配器                             │
│  - 优先级：特定模型 > 供应商+类型 > 通用类型                    │
└──────────────────────────┬──────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 具体适配器（Adapter）                         │
│  - prepare_request()：转换请求格式                           │
│  - parse_response()：解析响应格式                            │
│  - get_headers()：构造请求头                                 │
└──────────────────────────┬──────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   外部API（供应商服务）                        │
└─────────────────────────────────────────────────────────────┘
```

### 关键组件

1. **Models层**（models.py）
   - `Vendor`：供应商配置
   - `VendorEndpoint`：API端点配置
   - `VendorAPIKey`：API密钥管理
   - `LLMModel`：模型配置

2. **Service层**（services/）
   - `ModelService`：统一的模型调用服务（services/model.py）
   - `BaseService`：服务基类（services/base.py）

3. **Adapter层**（adapters/）
   - `ModelAdapter`：适配器基类
   - `TextModelAdapter`：文本模型适配器
   - `EmbeddingModelAdapter`：嵌入模型适配器
   - `RerankModelAdapter`：重排序模型适配器
   - `ReasoningModelAdapter`：推理模型适配器

4. **API层**（views.py, serializers.py）
   - REST API接口
   - 数据序列化

## 数据模型详解

### 1. Vendor（供应商）

```python
{
    "vendor_id": "openai",           # 唯一标识符
    "display_name": "OpenAI",         # 显示名称
    "description": "OpenAI API",      # 描述
    "website": "https://openai.com",  # 官网
    "supported_services": [           # 支持的服务
        "文本补全",
        "图像生成",
        "语音识别"
    ],
    "config_template": {              # 配置模板
        "api_version": "2024-01-01"
    },
    "is_active": true,                # 是否启用
    "priority": 100                   # 优先级
}
```

### 2. VendorEndpoint（端点）

```python
{
    "vendor": 1,                      # 关联供应商ID
    "endpoint": "https://api.openai.com/v1",  # API地址
    "service_type": "Text Generation" # 服务类型
}
```

### 3. VendorAPIKey（API密钥）

```python
{
    "vendor": 1,                      # 关联供应商ID
    "api_key": "sk-...",             # API密钥
    "description": "生产环境密钥"      # 描述
}
```

### 4. LLMModel（模型配置）

```python
{
    "name": "GPT-4",                  # 模型名称
    "model_id": "gpt-4",              # 模型标识符
    "model_type": "text",             # 模型类型
    "endpoint": 1,                    # 关联端点ID
    "api_standard": "openai",         # API标准
    "custom_headers": {               # 自定义请求头
        "X-Custom-Header": "value"
    },
    "params": {                       # 默认参数
        "temperature": 0.7,
        "max_tokens": 2000
    },
    "adapter_config": {               # 适配器配置
        "filter_system_messages": true,
        "response_format": "openai"
    }
}
```

## 配置流程

### 1. 创建供应商

```python
# Django Shell示例
from router.vendor_models import Vendor

vendor = Vendor.objects.create(
    vendor_id="custom_vendor",
    display_name="自定义供应商",
    supported_services=["文本生成", "嵌入"],
    is_active=True,
    priority=50
)
```

### 2. 配置端点

```python
from router.models import VendorEndpoint

endpoint = VendorEndpoint.objects.create(
    vendor=vendor,
    endpoint="https://api.custom.com/v1",
    service_type="Text Generation"
)
```

### 3. 添加API密钥

```python
from router.models import VendorAPIKey

api_key = VendorAPIKey.objects.create(
    vendor=vendor,
    api_key="your-api-key-here",
    description="生产环境密钥"
)
```

### 4. 配置模型

```python
from router.models import LLMModel

model = LLMModel.objects.create(
    name="Custom Model",
    model_id="custom-model-v1",
    model_type="text",
    endpoint=endpoint,
    api_standard="openai",
    params={
        "temperature": 0.8,
        "max_tokens": 1500
    },
    adapter_config={
        "response_format": "custom",
        "extract_thinking": true
    }
)
```

## 数据流转分析

### 完整调用链路

```
1. 调用入口
   ├─ 输入：model_id + 调用参数
   └─ 位置：ModelService.call_model()

2. 获取模型配置
   ├─ 查询：LLMModel.objects.get(model_id=model_id)
   ├─ 关联：endpoint, vendor, api_key
   └─ 配置：params, adapter_config

3. 创建适配器
   ├─ 工厂：AdapterFactory.create_adapter()
   ├─ 选择逻辑：
   │   ├─ 特定模型适配器（model_id匹配）
   │   ├─ 供应商+类型适配器（vendor+type匹配）
   │   └─ 通用类型适配器（type匹配）
   └─ 实例化：adapter = AdapterClass(model_config)

4. 准备请求
   ├─ 转换：adapter.prepare_request(**kwargs)
   ├─ 数据变换：
   │   ├─ 消息格式转换
   │   ├─ 参数映射
   │   └─ 字段过滤/添加
   └─ 输出：标准化的请求体

5. 构造请求头
   ├─ 基础头：adapter.get_headers()
   ├─ 认证：添加Bearer token
   └─ 自定义：合并custom_headers

6. 发送HTTP请求
   ├─ 目标：endpoint.endpoint
   ├─ 方法：POST
   └─ 超时：60秒

7. 解析响应
   ├─ 处理：adapter.parse_response(response)
   ├─ 提取：
   │   ├─ 内容（content）
   │   ├─ 思考过程（thinking）
   │   └─ 使用统计（usage）
   └─ 格式化：统一响应格式

8. 更新统计
   ├─ call_count += 1
   └─ success_count += 1（成功时）

9. 返回结果
   └─ 统一格式的响应数据
```

### 数据转换示例

#### 文本生成模型

**输入数据**：
```python
{
    "messages": [
        {"role": "user", "content": "Hello"}
    ],
    "temperature": 0.9
}
```

**适配器转换后**：
```python
{
    "model": "gpt-4",
    "messages": [
        {"role": "user", "content": "Hello"}
    ],
    "temperature": 0.9,
    "max_tokens": 2000  # 从model.params合并
}
```

**响应解析**：
```python
# 原始响应
{
    "choices": [{
        "message": {
            "role": "assistant",
            "content": "Hi there!"
        }
    }],
    "usage": {...}
}

# 解析后
{
    "content": "Hi there!",
    "role": "assistant",
    "usage": {...}
}
```

#### 推理模型（O1）

**特殊处理**：
- 过滤system消息
- 移除不支持的参数（temperature等）
- 提取reasoning_content

**adapter_config配置**：
```json
{
    "filter_system_messages": true,
    "unsupported_params": ["temperature", "top_p"],
    "reasoning_field": "reasoning_content"
}
```

## 适配器系统

### 适配器层次结构

```
ModelAdapter（基类）
├── TextModelAdapter（文本生成）
│   └── ReasoningModelAdapter（推理）
│       ├── OpenAIO1Adapter（O1模型）
│       ├── GroqReasoningAdapter（Groq）
│       └── DeepSeekReasoningAdapter（DeepSeek）
├── EmbeddingModelAdapter（嵌入）
└── RerankModelAdapter（重排序）
```

### 自定义适配器开发

```python
# router/adapters/custom.py
from router.adapters.base import TextModelAdapter

class CustomModelAdapter(TextModelAdapter):
    """自定义模型适配器"""
    
    def prepare_request(self, messages, **kwargs):
        """准备请求"""
        # 基础处理
        request = super().prepare_request(messages, **kwargs)
        
        # 自定义转换
        adapter_config = self.model_config.get('adapter_config', {})
        if adapter_config.get('custom_format'):
            request['custom_field'] = 'custom_value'
        
        return request
    
    def parse_response(self, response):
        """解析响应"""
        # 基础解析
        result = super().parse_response(response)
        
        # 自定义提取
        if 'custom_data' in response:
            result['extra'] = response['custom_data']
        
        return result
```

### adapter_config配置规范

```json
{
    // 请求转换
    "request_transform": {
        "rename_fields": {
            "messages": "chat_messages"
        },
        "add_fields": {
            "api_version": "2024-01"
        },
        "remove_fields": ["stream"]
    },
    
    // 响应解析
    "response_parse": {
        "content_path": "choices[0].message.content",
        "custom_extractors": {
            "thinking": "reasoning_content"
        }
    },
    
    // 特殊处理
    "special_handling": {
        "filter_system_messages": true,
        "extract_thinking": true,
        "thinking_pattern": "<think>(.*?)</think>"
    },
    
    // 错误处理
    "error_handling": {
        "retry_on_errors": [429, 503],
        "max_retries": 3
    }
}
```

## API接口说明

### 基础URL
```
/api/router/
```

### 端点列表

#### 1. 模型管理

**列出所有模型**
```http
GET /api/router/models/
```

**创建模型**
```http
POST /api/router/models/
Content-Type: application/json

{
    "name": "GPT-4",
    "model_id": "gpt-4",
    "model_type": "text",
    "endpoint": 1,
    "api_standard": "openai"
}
```

**更新模型**
```http
PATCH /api/router/models/{id}/
```

**删除模型**
```http
DELETE /api/router/models/{id}/
```

#### 2. 特殊端点

**获取嵌入模型**
```http
GET /api/router/models/embedding_models/
```

**获取重排序模型**
```http
GET /api/router/models/rerank_models/
```

**模型统计**
```http
GET /api/router/models/statistics/
```

**批量导入**
```http
POST /api/router/models/batch_import/
```

#### 3. 供应商管理

**列出供应商**
```http
GET /api/router/vendors/
```

**获取活跃供应商**
```http
GET /api/router/vendors/active/
```

## 集成指南

### 1. 在其他模块中使用

```python
# 方式一：直接使用ModelService
from router.services import ModelService  # 或 from router import ModelService（向后兼容）

service = ModelService()
result = service.call_model(
    model_id="gpt-4",
    messages=[
        {"role": "user", "content": "Hello"}
    ],
    temperature=0.7
)

# 方式二：通过LLMModel获取适配器
from router.models import LLMModel

model = LLMModel.objects.get(model_id="gpt-4")
adapter = model.get_adapter()
request = adapter.prepare_request(messages=messages)
```

### 2. Pagtive集成示例

```python
# webapps/pagtive/llm_service.py
from router.models import LLMModel

class PagtiveLLMService:
    def get_pagtive_llm_config(self, scenario='generatePageCode'):
        # 获取配置的模型
        active_config = PagtiveConfig.objects.filter(is_active=True).first()
        if active_config:
            llm_model = active_config.llm_model
            
            # 构建配置
            config = {
                'model_name': llm_model.name,
                'model_id': llm_model.model_id,
                'params': {
                    'temperature': active_config.temperature,
                    'max_tokens': active_config.max_tokens
                }
            }
            
            # 合并模型默认参数
            if llm_model.params:
                config['params'].update(llm_model.params)
            
            return config
```

### 3. 流式响应处理

```python
# 支持流式响应的调用
result = service.call_model(
    model_id="gpt-4",
    messages=messages,
    stream=True
)

# 处理流式数据
for chunk in result:
    print(chunk.get('content', ''), end='')
```

## 调试与故障排除

### 1. 常见问题

#### 模型找不到
```python
# 错误：LLMModel.DoesNotExist
# 解决：检查model_id是否正确
LLMModel.objects.filter(model_id__icontains='gpt').values('model_id', 'name')
```

#### API密钥无效
```python
# 检查密钥配置
from router.models import VendorAPIKey
keys = VendorAPIKey.objects.filter(vendor__vendor_id='openai')
for key in keys:
    print(f"Vendor: {key.vendor}, Key: {key.api_key[:8]}...")
```

#### 适配器错误
```python
# 测试适配器
model = LLMModel.objects.get(model_id='test-model')
adapter = model.get_adapter()
print(f"Adapter class: {adapter.__class__.__name__}")
print(f"Config: {model.adapter_config}")
```

### 2. 日志调试

```python
# 启用详细日志
import logging
logger = logging.getLogger('router')
logger.setLevel(logging.DEBUG)

# 在代码中添加日志
logger.debug(f"Model config: {model_config}")
logger.debug(f"Request body: {request_body}")
logger.debug(f"Response: {response}")
```

### 3. 测试工具

```python
# Django Shell测试
from router.services import ModelService  # 或 from router import ModelService（向后兼容）

# 测试文本生成
service = ModelService()
result = service.call_model(
    model_id="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "test"}],
    max_tokens=10
)
print(result)

# 测试嵌入
embedding = service.call_model(
    model_id="text-embedding-3-small",
    input_text="test sentence"
)
print(f"Embedding dims: {len(embedding.get('embeddings', [[]])[0])}")
```

### 4. 性能监控

```python
# 查看模型调用统计
from router.models import LLMModel
from django.db.models import F

# 成功率最高的模型
models = LLMModel.objects.annotate(
    success_rate=F('success_count') * 100.0 / F('call_count')
).filter(call_count__gt=0).order_by('-success_rate')

for model in models[:5]:
    print(f"{model.name}: {model.success_rate:.2f}% ({model.call_count} calls)")
```

## 最佳实践

### 1. 模型配置

- **使用adapter_config**：针对特殊模型配置适配规则
- **设置默认参数**：在model.params中配置常用参数
- **合理的超时设置**：根据模型响应时间调整超时
- **启用缓存**：对于相同输入使用缓存减少调用

### 2. 安全性

- **API密钥加密**：生产环境应加密存储API密钥
- **访问控制**：使用Django权限系统限制访问
- **审计日志**：记录所有模型调用用于审计
- **限流保护**：实施调用频率限制

### 3. 可维护性

- **版本管理**：使用migration管理数据库变更
- **配置分离**：环境相关配置使用环境变量
- **文档完善**：及时更新adapter_config示例
- **测试覆盖**：为新适配器编写单元测试

### 4. 性能优化

- **连接池**：使用requests.Session复用连接
- **异步调用**：对于批量请求使用异步处理
- **智能重试**：根据错误类型实施重试策略
- **负载均衡**：多个API密钥轮询使用

### 5. 监控告警

```python
# 监控示例
from django.core.management.base import BaseCommand
from router.models import LLMModel
from datetime import datetime, timedelta

class Command(BaseCommand):
    def handle(self, *args, **options):
        # 检查失败率
        for model in LLMModel.objects.filter(call_count__gt=100):
            if model.success_count / model.call_count < 0.9:
                self.stdout.write(
                    f"Warning: {model.name} success rate below 90%"
                )
        
        # 检查最近调用
        recent = datetime.now() - timedelta(hours=1)
        if not LLMModel.objects.filter(
            updated_at__gt=recent
        ).exists():
            self.stdout.write("Warning: No model calls in last hour")
```

## 附录

### 模型类型映射

| model_type | 说明 | 适配器类 |
|------------|------|----------|
| text | 文本生成 | TextModelAdapter |
| reasoning | 推理 | ReasoningModelAdapter |
| vision | 视觉 | TextModelAdapter |
| audio2text | 语音转文本 | ModelAdapter |
| text2audio | 文本转语音 | ModelAdapter |
| text2image | 文本生成图像 | ModelAdapter |
| embedding | 向量嵌入 | EmbeddingModelAdapter |
| rerank | 重排序 | RerankModelAdapter |

### API标准映射

| api_standard | 说明 | 特点 |
|-------------|------|------|
| openai | OpenAI标准 | 最通用的格式 |
| huggingface | HuggingFace标准 | 开源模型常用 |
| custom | 自定义标准 | 需要专门适配器 |

### 供应商标识规范

- 只使用小写字母、数字和下划线
- 简短易记，如：openai、anthropic、aliyun
- 避免使用特殊字符和空格

### 错误码说明

| 状态码 | 说明 | 处理建议 |
|-------|------|----------|
| 200 | 成功 | - |
| 400 | 请求错误 | 检查参数 |
| 401 | 认证失败 | 检查API密钥 |
| 429 | 频率限制 | 重试或降低频率 |
| 500 | 服务器错误 | 联系供应商 |
| 503 | 服务不可用 | 稍后重试 |

---

*最后更新：2025-08-31*