# 适配器配置示例

## 概述

适配器系统用于处理不同类型模型的请求/响应格式差异。通过在`adapter_config`字段配置规则，可以自定义模型的行为。

## 配置示例

### 1. Groq Reasoning模型

Groq的推理模型将thinking内容用`<think></think>`标签包裹在content中：

```json
{
  "response_format": "groq_thinking",
  "thinking_pattern": "<think>(.*?)</think>",
  "extract_thinking": true
}
```

### 2. DeepSeek Reasoning模型

DeepSeek的推理模型在usage中包含reasoning_tokens：

```json
{
  "response_format": "deepseek_reasoning",
  "extract_reasoning_tokens": true,
  "thinking_separator": "\n---\n"
}
```

### 3. OpenAI O1模型

O1模型不支持system消息和某些参数：

```json
{
  "filter_system_messages": true,
  "unsupported_params": ["temperature", "top_p", "frequency_penalty"],
  "reasoning_field": "reasoning_content"
}
```

### 4. 自定义Embedding模型

某些嵌入模型可能有特殊的输入格式：

```json
{
  "input_format": "single_string",
  "max_input_length": 8192,
  "normalize_embeddings": true
}
```

### 5. 自定义Rerank模型

重排序模型的配置：

```json
{
  "max_documents": 100,
  "score_field": "relevance_score",
  "return_documents": false
}
```

## 通用配置选项

### 请求转换

```json
{
  "request_transform": {
    "rename_fields": {
      "messages": "chat_messages",
      "model": "model_name"
    },
    "add_fields": {
      "api_version": "2024-01-01"
    },
    "remove_fields": ["stream"]
  }
}
```

### 响应解析

```json
{
  "response_parse": {
    "content_path": "choices[0].message.content",
    "usage_path": "usage",
    "error_path": "error.message",
    "custom_extractors": {
      "thinking": "choices[0].message.reasoning_content"
    }
  }
}
```

### 错误处理

```json
{
  "error_handling": {
    "retry_on_errors": [429, 503],
    "max_retries": 3,
    "retry_delay": 1000,
    "fallback_model": "gpt-3.5-turbo"
  }
}
```

## 使用方法

1. 在Django Admin中编辑LLMModel
2. 在"适配器配置"部分输入JSON配置
3. 保存后，系统会自动使用配置的规则处理请求和响应

## 高级用法

### 自定义适配器类

如果内置配置不够用，可以创建自定义适配器类：

```python
# router/adapters/custom.py
from router.adapters.base import TextModelAdapter

class MyCustomAdapter(TextModelAdapter):
    def prepare_request(self, messages, **kwargs):
        # 自定义请求处理逻辑
        request = super().prepare_request(messages, **kwargs)
        # 添加特殊处理
        return request
    
    def parse_response(self, response):
        # 自定义响应解析逻辑
        result = super().parse_response(response)
        # 添加特殊处理
        return result
```

然后在adapter_config中指定使用自定义适配器：

```json
{
  "adapter_class": "router.adapters.custom.MyCustomAdapter"
}
```

## 注意事项

1. adapter_config是可选的，不配置时使用默认适配器
2. 配置必须是有效的JSON格式
3. 错误的配置可能导致模型调用失败
4. 建议先在测试环境验证配置