# Tools 应用使用文档

## 概述

tools 应用为 agentic 系统提供了丰富的工具集，支持基础工具和高级工具两大类别。

## 架构设计

### 核心组件
- **BaseTool**: 所有工具的基础抽象类
- **ToolRegistry**: 工具注册中心
- **执行接口**: 统一的工具调用接口

### 目录结构
```
tools/
├── basic/          # 基础工具
├── advanced/       # 高级工具
├── core/           # 核心框架
└── utils/          # 工具函数
```

## 基础工具

### 1. 天气查询工具 (weather_query)
**功能**: 查询指定地点的天气信息
**参数**:
- location: 地点名称 (默认: 北京)
- unit: 温度单位 (celsius/fahrenheit)

**使用示例**:
```json
{
  "tool_input": {
    "location": "上海",
    "unit": "celsius"
  }
}
```

### 2. 数学计算工具 (math_calculation)
**功能**: 计算数学表达式
**参数**:
- expression: 数学表达式

**使用示例**:
```json
{
  "tool_input": {
    "expression": "2+3*4"
  }
}
```

### 3. 文档搜索工具 (document_search)
**功能**: 在项目文档中搜索相关内容
**参数**:
- query: 搜索关键词
- path: 搜索路径 (默认: docs/)

**使用示例**:
```json
{
  "tool_input": {
    "query": "架构设计",
    "path": "docs/plans/"
  }
}
```

### 4. 通用聊天工具 (general_chat)
**功能**: 集成项目中的 LLM 服务，处理普通对话请求
**参数**:
- query / message: 用户消息
- model_name: LLM 模型名称 (默认: gpt-3.5-turbo)

**使用示例**:
```json
{
  "tool_input": {
    "query": "你好，请问有什么可以帮助你的？"
  }
}
```

## 高级工具

### 1. 数据库查询工具 (database_query)
**功能**: 安全的数据库查询操作
**参数**:
- query_type: 预定义查询类型 (如: user_count, recent_graphs, model_stats)
- model: Django 模型名称 (如: authentication.User)

**使用示例**:
```json
{
  "tool_input": {
    "query_type": "user_count"
  }
}
```

### 2. API 调用工具 (api_call)
**功能**: 调用外部 REST API
**参数**:
- url: API 地址
- method: HTTP 方法 (GET, POST, PUT, DELETE)
- headers: 请求头 (可选)
- params: URL 查询参数 (可选)
- data: 请求体数据 (POST/PUT, 可选)
- timeout: 超时时间 (秒, 默认: 30)

**使用示例**:
```json
{
  "tool_input": {
    "url": "https://api.example.com/data",
    "method": "GET",
    "params": {"id": 123}
  }
}
```

### 3. 文件处理工具 (file_processing)
**功能**: 读取、写入、分析各种格式的文件
**参数**:
- file_path: 文件路径
- operation: 操作类型 (read, write, analyze)
- content: 写入内容 (仅当 operation 为 'write' 时需要)

**使用示例**:
```json
{
  "tool_input": {
    "file_path": "data.json",
    "operation": "read"
  }
}
```

### 4. 高级 LLM 工具 (llm_advanced)
**功能**: 支持复杂的 LLM 调用场景，如总结、翻译、分析等
**参数**:
- task_type: 任务类型 (summarize, translate, analyze, extract, classify)
- content: 待处理内容
- model_name: LLM 模型名称 (默认: gpt-4)
- params: 额外参数 (如: source_lang, target_lang, categories, temperature, max_tokens)

**使用示例**:
```json
{
  "tool_input": {
    "task_type": "summarize",
    "content": "这是一段很长的文本，需要进行总结。",
    "model_name": "gpt-4"
  }
}
```

## 与 agentic 集成

### Node 配置示例
```json
{
  "graph": 1,
  "name": "weather_tool_node",
  "node_type": "tool",
  "python_callable": "tools.utils.helpers.weather_query",
  "config": {}
}
```

**注意**: `python_callable` 路径应指向 `tools.utils.helpers` 中对应的便利函数。`config` 字典将作为工具实例的配置参数传入。