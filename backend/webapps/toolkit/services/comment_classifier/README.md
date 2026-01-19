# 评论分类服务 - 组件式架构

## 架构概述

本服务采用组件式架构设计，将分类流程拆分为可独立替换和扩展的组件。

## 目录结构

```
comment_classifier/
├── __init__.py              # 模块入口
├── service.py               # 服务主类
├── config.py                # 配置管理
├── README.md               # 本文档
│
├── components/             # 组件目录
│   ├── __init__.py
│   ├── base.py            # 组件基类
│   ├── loader.py          # 数据加载组件
│   ├── preprocessor.py   # 预处理组件
│   ├── classifier.py      # 分类组件
│   ├── postprocessor.py   # 后处理组件
│   └── exporter.py        # 导出组件
│
├── engines/               # 分类引擎目录
│   ├── __init__.py
│   ├── base.py           # 引擎基类
│   ├── ai_engine.py      # AI分类引擎
│   ├── rule_engine.py    # 规则分类引擎
│   └── hybrid_engine.py  # 混合分类引擎
│
└── processors/           # AI处理器目录
    ├── __init__.py
    ├── base_processor.py # 处理器基类
    ├── qwen_processor.py # Qwen处理器
    ├── gemini_processor.py # Gemini处理器(TODO)
    └── openai_processor.py # OpenAI处理器(TODO)
```

## 组件说明

### 核心组件流程

```
DataLoader -> Preprocessor -> Classifier -> Postprocessor -> Exporter
```

### 1. DataLoaderComponent（数据加载组件）
- **职责**：从各种数据源加载原始数据
- **输入**：文件路径、数据库连接等
- **输出**：标准化的数据结构

### 2. PreprocessorComponent（预处理组件）
- **职责**：数据清洗、格式化、验证
- **输入**：原始数据
- **输出**：清洗后的标准格式数据

### 3. ClassifierComponent（分类组件）
- **职责**：执行实际的分类操作
- **输入**：预处理后的数据
- **输出**：带分类结果的数据
- **支持模式**：
  - AI模式（纯AI分类）
  - 规则模式（纯规则分类）
  - 混合模式（规则+AI）

### 4. PostprocessorComponent（后处理组件）
- **职责**：优化分类结果、添加元数据
- **输入**：分类结果
- **输出**：优化后的最终结果

### 5. ExporterComponent（导出组件）
- **职责**：将结果导出为各种格式
- **输入**：最终处理结果
- **输出**：文件或数据流
- **支持格式**：Excel、CSV、JSON

## 分类引擎

### AIClassifierEngine
- 使用AI模型进行分类
- 支持多种AI提供商（Qwen、Gemini、OpenAI）
- 异步批量处理能力

### RuleClassifierEngine  
- 基于预定义规则进行分类
- 高性能、高一致性
- 支持动态规则加载

### HybridClassifierEngine
- 结合规则和AI的优势
- 智能选择最佳分类策略
- 优先使用规则，AI作为补充

## 使用示例

```python
from backend.webapps.toolkit.services.comment_classifier import (
    CommentClassifierService,
    ClassifierConfig
)

# 创建配置
config = ClassifierConfig(
    use_ai_only=True,
    ai_provider='qwen',
    output_format='excel',
    batch_size=100
)

# 初始化服务
service = CommentClassifierService(config)

# 执行分类
result = service.process(
    input_path='data.xlsx',
    output_path='result.xlsx'
)

# 获取特定组件
classifier = service.get_component('classifier')
```

## 扩展性

### 添加新组件
1. 继承 `BaseComponent` 类
2. 实现 `execute` 方法
3. 注册到服务中

```python
from comment_classifier.components.base import BaseComponent

class CustomComponent(BaseComponent):
    def execute(self, **kwargs):
        # 自定义逻辑
        pass

# 注册组件
service.register_component('custom', CustomComponent(config))
```

### 添加新的AI处理器
1. 继承 `BaseAIProcessor` 类
2. 实现 `process_single` 和 `process_batch` 方法
3. 在引擎中配置使用

## 配置说明

```python
@dataclass
class ClassifierConfig:
    # 基础配置
    use_ai_only: bool = False           # 是否仅使用AI
    
    # AI配置
    ai_provider: str = 'qwen'           # AI提供商
    ai_model_name: str = 'qwen-plus'    # 模型名称
    
    # 并发配置
    max_concurrent: int = 20            # 最大并发数
    requests_per_second: int = 4        # 每秒请求数
    
    # 分类配置
    min_confidence_score: float = 0.1   # 最小置信度
    
    # 输出配置
    output_format: str = 'excel'        # 输出格式
    generate_report: bool = True        # 是否生成报告
```

## 优势

1. **模块化设计**：各组件独立，易于维护和测试
2. **可扩展性**：轻松添加新组件或引擎
3. **灵活配置**：支持细粒度的配置管理
4. **多模式支持**：AI、规则、混合模式灵活切换
5. **高性能**：异步处理、批量操作、并发控制
6. **易于集成**：标准化接口，易于集成到Django服务

## 后续计划

- [ ] 实现Gemini和OpenAI处理器
- [ ] 添加缓存机制
- [ ] 实现分布式处理
- [ ] 添加监控和日志
- [ ] 支持更多数据源和输出格式
- [ ] 实现自动规则学习