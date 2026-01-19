# 12-Factor Agents 实施思考

## 工具发现元工具（Meta-Tool）设计

### 核心理念
将"工具发现和学习"本身作为一个工具，让AI主动查询而不是被动接收所有工具信息。这是一种"惰性加载"和"按需获取"的设计模式。

### 问题背景
当前planner提示词包含所有工具的详细描述，占用大量context window（2000-5000 tokens），且随着工具增加会持续膨胀。

### 解决方案：Tool Discovery Tool

#### 1. Context Window优化效果
- **现状**：所有工具描述占用2000-5000 tokens
- **改进后**：仅需100-200 tokens提示AI有工具发现能力
- **节省**：80-90%的初始context

#### 2. 提示词对比

**当前的planner提示词模式：**
```python
prompt = """
你有以下工具可用：
1. web_search: 搜索网络获取实时信息
   参数：query(string) - 搜索关键词
   返回：搜索结果列表...
   
2. calculator: 计算数学表达式
   参数：expression(string) - 数学表达式
   返回：计算结果...
   
3. pandas_data_calculator: 处理表格数据
   参数：code(string) - Python代码, tables(dict) - 表格数据
   返回：执行结果...
   
... (20+ 工具的详细说明)

请根据任务选择合适的工具...
"""
```

**简化后的提示词：**
```python
prompt = """
你可以使用tool_discovery工具来探索可用能力：
- list_tools(): 查看所有可用工具列表
- search_tools(capability): 根据需求搜索工具  
- get_tool_info(name): 获取工具详细用法和参数
- suggest_tools(task): 获取任务相关的工具推荐

工作流程：
1. 先使用tool_discovery了解可用工具
2. 选择合适的工具执行任务
3. 根据结果决定下一步

记住：不确定时先探索，找到合适工具再执行。
"""
```

#### 3. 工具实现设计

```python
@register_tool("tool_discovery", "工具发现和学习系统")
class ToolDiscoveryTool(BaseTool):
    """元工具：帮助AI发现和学习其他工具的使用"""
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_categories", "list_tools", "search_by_capability", 
                             "get_tool_details", "suggest_tools", "get_tool_examples"],
                    "description": "要执行的发现动作"
                },
                "query": {
                    "type": "string",
                    "description": "搜索查询或工具名称"
                },
                "category": {
                    "type": "string",
                    "enum": ["data_processing", "ai_services", "external_api", 
                             "knowledge_management", "all"],
                    "description": "工具类别"
                }
            },
            "required": ["action"]
        }
    
    def execute(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        action = tool_input.get("action")
        query = tool_input.get("query", "")
        
        if action == "list_categories":
            # 返回工具分类及每个分类的简要说明
            return {
                "categories": {
                    "data_processing": "数据处理和分析工具",
                    "ai_services": "AI和语言模型服务",
                    "external_api": "外部API调用工具",
                    "knowledge_management": "知识库和记忆管理"
                }
            }
            
        elif action == "list_tools":
            # 返回工具列表（仅名称和一句话描述）
            category = tool_input.get("category", "all")
            tools = self._get_tools_by_category(category)
            return {"tools": tools}
            
        elif action == "search_by_capability":
            # 语义搜索：根据能力描述找工具
            # 例如："我需要处理Excel" → ["pandas_data_calculator", "table_analyzer"]
            matched_tools = self._semantic_search(query)
            return {"matched_tools": matched_tools}
            
        elif action == "get_tool_details":
            # 返回特定工具的完整信息
            tool_info = self._get_full_tool_info(query)
            return {
                "name": query,
                "description": tool_info["description"],
                "input_schema": tool_info["schema"],
                "examples": tool_info["examples"],
                "best_practices": tool_info["tips"]
            }
            
        elif action == "suggest_tools":
            # 基于任务描述推荐工具组合
            suggestions = self._analyze_task_and_suggest(query)
            return {
                "task_analysis": suggestions["analysis"],
                "recommended_tools": suggestions["tools"],
                "workflow_suggestion": suggestions["workflow"]
            }
            
        elif action == "get_tool_examples":
            # 获取工具使用示例
            examples = self._get_tool_examples(query)
            return {"examples": examples}
```

#### 4. 智能工具选择机制

```python
class IntelligentToolSelector:
    """基于任务的智能工具选择器"""
    
    def analyze_task(self, task_description: str) -> Dict:
        """分析任务并推荐工具"""
        
        # 任务关键词提取
        keywords = self._extract_keywords(task_description)
        
        # 任务类型识别
        task_type = self._identify_task_type(keywords)
        
        # 工具匹配
        tools = []
        if "搜索" in keywords or "查找" in keywords:
            tools.append("web_search")
        if "计算" in keywords or "统计" in keywords:
            tools.append("calculator")
        if "表格" in keywords or "Excel" in keywords:
            tools.append("pandas_data_calculator")
        if "报告" in keywords or "总结" in keywords:
            tools.append("report_generator")
            
        # 工具组合建议
        workflow = self._suggest_workflow(task_type, tools)
        
        return {
            "task_type": task_type,
            "recommended_tools": tools,
            "workflow": workflow
        }
```

### 实施策略

#### 第一阶段：混合方案
**分层工具管理：**
- **核心工具集**（5-6个）：直接嵌入prompt
  - chat（通用对话）
  - web_search（网络搜索）
  - calculator（基础计算）
  - tool_discovery（工具发现）
  
- **专业工具集**：通过tool_discovery按需获取
  - pandas_data_calculator
  - report_generator
  - knowledge_base
  - translate
  - 等等...

#### 第二阶段：智能缓存
- 在会话中缓存已发现的工具信息
- 基于使用频率动态调整"核心工具集"
- 学习用户偏好，预加载常用工具

#### 第三阶段：工具组合学习
- 记录成功的工具组合模式
- 自动推荐工具链（tool chains）
- 支持复杂工作流的模板化

### 优势总结

1. **资源优化**：大幅减少context占用
2. **可扩展性**：新增工具不影响prompt复杂度
3. **智能化**：AI主动探索和学习工具使用
4. **灵活性**：支持动态工具发现和组合
5. **可维护性**：工具管理与prompt解耦

### 潜在挑战及解决方案

#### 挑战1：额外的往返次数
- **问题**：需要先查询工具，增加1-2轮对话
- **解决**：
  - 工具预取（prefetch）机制
  - 基于任务类型的智能预测
  - 并行化工具发现和初步分析

#### 挑战2：AI学习曲线
- **问题**：AI需要学会"先探索再执行"的模式
- **解决**：
  - 在prompt中明确工作流程指导
  - 提供成功案例和模板
  - 逐步引导的渐进式提示

#### 挑战3：工具发现的准确性
- **问题**：如何确保AI找到最合适的工具
- **解决**：
  - 语义搜索 + 关键词匹配双重机制
  - 工具标签和分类体系
  - 使用反馈不断优化推荐算法

### 实施路线图

1. **Week 1-2**：实现基础tool_discovery工具
2. **Week 3-4**：优化planner提示词，集成新机制
3. **Week 5-6**：添加智能推荐和缓存功能
4. **Week 7-8**：收集反馈，优化工具发现算法

### 预期效果

- Context使用减少80%
- 工具选择准确率提升30%
- 支持无限工具扩展
- 更自然的人机交互模式

---

## 知识库驱动的Planner架构改造

### 问题分析：单一Planner的过度泛化

**核心问题**：
- 所有任务（简单到复杂）都使用同一套2000+ tokens的planner提示词
- 90%的指令对当前任务无用，产生噪音和浪费
- 简单问题被过度工程化，复杂问题缺乏定制化指导

### 解决方案：知识库驱动的智能分流架构

#### 核心理念
将知识库作为动态配置中心，让AI主动从知识库获取所需信息，而不是把所有知识硬编码在prompt里。

#### 知识库的新角色

**1. 提示词库**
```python
# 存储在知识库中的分级提示词
{
    "id": "planner_simple",
    "type": "prompt_template", 
    "content": "简单任务规划：{task}，直接执行...",
    "tags": ["simple", "direct"],
    "usage_condition": "task_complexity < 3"
}

{
    "id": "planner_complex",
    "type": "prompt_template",
    "content": "复杂工作流规划：需要分析依赖关系...",
    "tags": ["complex", "workflow"],
    "usage_condition": "task_complexity >= 7"  
}
```

**2. 工具使用指南**
```python
# 工具文档不再嵌入prompt，而是按需查询
{
    "id": "tool_guide_pandas",
    "type": "tool_documentation",
    "tool_name": "pandas_data_calculator",
    "best_practices": "处理大型数据集时，先用head()查看...",
    "common_patterns": [
        "数据清洗: df.dropna()",
        "分组统计: df.groupby().agg()"
    ]
}
```

**3. 问题解决模式库**
```python
{
    "id": "pattern_data_analysis",
    "type": "solution_pattern",
    "problem_type": "数据分析",
    "steps": [
        "1. 使用table_analyzer了解数据结构",
        "2. 使用pandas_data_calculator进行处理", 
        "3. 使用report_generator生成报告"
    ]
}
```

### 流程对比：现有 vs 改造后

#### 现有流程（单一路径，Context累积膨胀）

```
用户输入(20 tokens)
    ↓
完整Planner(2000+ tokens静态prompt)
    ↓
工具执行 → 结果累积到state
    ↓
Planner(2500+ tokens，含历史)
    ↓  
工具执行 → 继续累积
    ↓
Planner(3000+ tokens，持续增长)
    ↓
... 每轮增加500-1000 tokens
```

**问题**：
- 初始就是2000+ tokens的庞大prompt
- 历史记录累积导致context持续膨胀
- 简单任务也要承担完整prompt开销

#### 改造后流程（智能分流，按需加载）

```
用户输入(20 tokens)
    ↓
预分析器(50 tokens极简prompt) → 知识库查询任务类型
    ↓
智能路由分流
    ├─→ 简单任务 → 直接Chat工具(100 tokens) → 返回
    ├─→ 单工具 → 知识库获取工具指南 → MiniPlanner(200 tokens) → 返回
    └─→ 复杂任务 → 知识库获取工作流模板 → SmartPlanner(500 tokens定制)
                    ↓
                  工具执行 → 结果存知识库(仅传引用)
                    ↓
                  继续规划(300 tokens，仅必要上下文)
                    ↓
                  学习反馈 → 成功模式存入知识库
```

**优势**：
- 根据任务复杂度动态选择处理路径
- 历史结果存储在知识库，通过引用访问
- 成功模式自动沉淀，持续优化

### 详细数据流分析

#### 现有系统数据流（累积增长模式）
```python
# 初始输入
{"user_input": "分析销售数据并生成报告", "tokens": 20}

# Step 1: Planner输入（2000+ tokens）
{
    "prompt": """
    任务规划专家指令...(500 tokens)
    20+个工具详细说明...(2000 tokens)
    任务：分析销售数据并生成报告
    """,
    "state": {"action_logs": []}
}

# Step 2-N: 循环执行（指数增长）
{
    "prompt": "原始prompt + 所有历史记录",
    "state": {
        "action_logs": [
            {"tool": "pandas_data", "result": "...", "tokens": 500},
            {"tool": "calculator", "result": "...", "tokens": 500},
            {"tool": "report_gen", "result": "...", "tokens": 1000}
        ]
    },
    "total_tokens": 5000+  # 持续累积
}
```

#### 改造后数据流（引用模式）
```python
# Step 1: 预分析（50 tokens）
{
    "mini_prompt": "判断任务类型：分析销售数据并生成报告",
    "response": {"complexity": 7, "type": "data_analysis"}
}

# Step 2: 知识库查询（向量搜索）
{
    "query": "type:pattern AND category:data_analysis",
    "results": [{
        "pattern_id": "data_analysis_workflow",
        "recommended_tools": ["pandas_data", "report_generator"],
        "prompt_template_id": "compact_analysis_prompt"  # 300 tokens
    }]
}

# Step 3: 智能执行（轻量prompt + 引用）
{
    "context": {
        "task": "分析销售数据",
        "workflow_ref": "kb://patterns/data_analysis_workflow",
        "data_ref": "kb://results/step1",  # 引用而非嵌入
        "relevant_tools": ["pandas_data", "report_generator"]  # 仅2个
    },
    "prompt_tokens": 500,  # vs 现有2000+
    "execution_tokens": 300  # 每步固定，不累积
}

# Step 4: 学习反馈
{
    "success_pattern": {
        "task_type": "data_analysis",
        "total_tokens": 1200,  # vs 现有8000+
        "quality_score": 0.95
    },
    "action": "store_to_knowledge_base"
}
```

### Token消耗对比分析

| 任务类型 | 任务占比 | 现有系统 | 改造后 | 节省比例 |
|---------|---------|---------|--------|---------|
| 简单问答 | 40% | 2000 tokens | 100 tokens | 95% |
| 单工具任务 | 30% | 4000 tokens | 400 tokens | 90% |
| 多步骤任务 | 20% | 8000 tokens | 1200 tokens | 85% |
| 复杂工作流 | 10% | 15000 tokens | 3000 tokens | 80% |
| **加权平均** | - | **5500 tokens** | **750 tokens** | **86%** |

### 实施策略

#### Phase 1: 知识库基础建设（Week 1-2）
```python
class KnowledgeBaseMigration:
    """将现有prompt和模式迁移到知识库"""
    
    def migrate_prompts(self):
        # 拆分现有mega-prompt为模块化组件
        prompts = self.parse_existing_prompts()
        for prompt in prompts:
            self.kb.store(
                type="prompt_template",
                content=prompt.content,
                tags=prompt.tags,
                conditions=prompt.usage_conditions
            )
    
    def create_tool_guides(self):
        # 为每个工具创建使用指南
        for tool in self.registry.list_tools():
            guide = self.generate_tool_guide(tool)
            self.kb.store(
                type="tool_guide",
                tool_name=tool.name,
                content=guide
            )
```

#### Phase 2: 智能路由实现（Week 3-4）
```python
class SmartRouter:
    """任务智能路由器"""
    
    def __init__(self):
        self.pre_analyzer = PreAnalyzer(max_tokens=50)
        self.kb = KnowledgeBase()
    
    def route(self, user_input: str) -> Handler:
        # 1. 快速分析
        complexity = self.pre_analyzer.analyze(user_input)
        
        # 2. 查询合适的处理模式
        pattern = self.kb.search(
            f"complexity:{complexity.level} type:{complexity.type}"
        )
        
        # 3. 选择处理器
        if complexity.level <= 3:
            return DirectChatHandler()
        elif complexity.level <= 6:
            return MiniPlannerHandler(pattern)
        else:
            return SmartPlannerHandler(pattern)
```

#### Phase 3: 动态Prompt组装（Week 5-6）
```python
class DynamicPromptBuilder:
    """根据任务动态组装prompt"""
    
    def build(self, task_analysis):
        # 基础框架（50 tokens）
        base = "你是AI助手，使用提供的工具完成任务。"
        
        # 按需添加模块
        modules = []
        
        if task_analysis.needs_planning:
            planning_module = self.kb.get("prompt_module:planning")
            modules.append(planning_module)
        
        if task_analysis.needs_error_handling:
            error_module = self.kb.get("prompt_module:error_handling")
            modules.append(error_module)
        
        # 仅包含相关工具（不是全部20+）
        relevant_tools = self.kb.search_tools(task_analysis.keywords)
        tool_section = self.format_tools(relevant_tools[:3])  # 最多3个
        
        return base + "\n".join(modules) + tool_section
```

#### Phase 4: 学习反馈机制（Week 7-8）
```python
class LearningFeedback:
    """执行结果的学习和优化"""
    
    def record_execution(self, task, execution, result):
        if result.quality_score > 0.9:
            # 高质量执行存为模式
            pattern = {
                "task_pattern": self.extract_pattern(task),
                "execution_flow": execution.flow,
                "tool_sequence": execution.tools_used,
                "prompt_used": execution.prompt_template,
                "performance": {
                    "tokens": execution.total_tokens,
                    "time": execution.duration,
                    "quality": result.quality_score
                }
            }
            
            self.kb.store(
                type="success_pattern",
                content=pattern,
                embeddings=self.generate_embeddings(task)
            )
            
            # 更新工具推荐权重
            self.update_tool_recommendations(pattern)
```

### 关键架构优势

1. **智能适配**：不同任务使用不同复杂度的处理流程
2. **按需加载**：只获取当前任务需要的知识和工具
3. **防止膨胀**：历史结果通过引用访问，不累积在prompt中
4. **持续学习**：成功模式自动沉淀，系统越用越智能
5. **无限扩展**：新工具、新知识随时添加，无需改代码

### 核心洞察

**现有系统**："背着整个图书馆去解决每个问题"
**改造后系统**："知道去哪查什么书的智能助手"

这种架构真正实现了：
- **惰性加载**：用到才加载
- **智能缓存**：常用知识优先
- **持续进化**：从经验中学习
- **成本优化**：平均节省86% tokens

## 智能学习去重的辩证分析

### 理想与现实的差距

#### 初始设想（过度工程化）

我们最初设计了复杂的去重机制：
- 语义相似性判断
- 模式指纹识别  
- 智能冲突检测
- 自动模式抽象

**问题实例**：
```python
# 期望：识别深层逻辑相似性
"能量总是从热环境流向冷环境"
"风从北方高压区吹向南方低压区"
# 两者都是"梯度驱动的流动"，但现有技术无法识别
```

即使使用向量嵌入，这两个句子的相似度可能只有0.3，因为表面词汇完全不同。

#### 现实的技术限制

1. **语义理解的局限**：当前AI无法真正理解抽象概念的深层关联
2. **向量嵌入的表面性**：主要捕捉词汇相似，而非逻辑相似
3. **过度泛化风险**：自动抽象容易产生错误的模式归纳

### 务实的解决方案

#### 1. 基于工具序列的客观去重
```python
class SimpleToolSequenceDedup:
    """只看工具调用序列，100%准确"""
    
    def get_signature(self, execution):
        tools = [step.tool for step in execution.steps]
        return "->".join(tools)
        # "excel_processor->pandas_data->report_generator"
    
    def is_duplicate(self, execution):
        signature = self.get_signature(execution)
        return self.kb.exists(f"signature:{signature}")
```

**优势**：
- 判断100%准确
- 实现简单可靠
- 无歧义性

#### 2. 统计学习而非语义理解
```python
class StatisticalLearning:
    """不试图'理解'，只做统计"""
    
    def record_execution(self, task_input, execution, result):
        # 全部记录，不判断相似性
        self.kb.append({
            "task": task_input,
            "tools_used": execution.tools,
            "success": result.success,
            "tokens": execution.tokens
        })
    
    def recommend_approach(self, new_task):
        # 简单关键词匹配
        keywords = self.extract_keywords(new_task)
        
        # 统计成功率
        stats = self.kb.aggregate(
            filter={"keywords": {"$overlap": keywords}},
            group_by="tools_used",
            metrics=["success_rate"]
        )
        
        return max(stats, key=lambda x: x.success_rate)
```

#### 3. 人工标注的可靠性
```python
class ExplicitPatternManagement:
    """依赖人工标注而非自动判断"""
    
    def add_pattern(self, execution, human_annotation):
        pattern_type = human_annotation.get("pattern_type")
        # 人类明确告诉系统这是什么类型的任务
        
        existing = self.kb.find(f"type:{pattern_type}")
        if existing:
            existing.count += 1
            existing.examples.append(execution)
        else:
            self.kb.create_new(pattern_type, execution)
```

### 关键洞察

#### 可行的方法 ✅
1. **工具序列去重**：客观、准确、可实现
2. **关键词分类**：简单但有效
3. **统计不理解**：让数据说话而非推理
4. **人工标注**：最可靠的分类方式
5. **预定义类别**：基于业务领域的固定分类

#### 不可行的方法 ❌
1. **深层语义相似性判断**：技术不成熟
2. **自动模式抽象**：容易过度泛化
3. **智能冲突检测**："冲突"定义本身就很主观
4. **复杂的模式指纹**：无法捕捉逻辑本质

### 实施建议

```python
class RealisticImplementation:
    """真正可实施的方案"""
    
    def __init__(self):
        # 预定义的简单分类
        self.categories = {
            "data_analysis": ["分析", "数据", "统计"],
            "search": ["搜索", "查找", "了解"],
            "calculation": ["计算", "求和", "平均"]
        }
    
    def learn(self, execution):
        # 1. 简单记录原始数据
        self.record_raw(execution)
        
        # 2. 基于工具序列的去重
        tool_seq = self.get_tool_sequence(execution)
        if not self.exists(tool_seq):
            self.save_pattern(tool_seq, execution)
        
        # 3. 更新统计信息
        self.update_stats(execution)
        
        # 不做复杂推理，保持简单
```

### 反思总结

**过度工程化的教训**：
- 不要高估当前AI的语义理解能力
- 简单可靠比复杂智能更重要
- 工程实践需要可预测性

**务实的原则**：
- 能用规则解决的不用AI
- 能用统计解决的不用推理
- 能用人工标注的不用自动判断

**最终认识**：
真正的"智能"去重可能是个伪命题。与其追求让系统"理解"相似性，不如：
1. 接受重复，通过统计发现模式
2. 依赖人工标注提供高质量分类
3. 专注于可客观判断的特征（如工具序列）

这种务实的方法虽然看起来"不够智能"，但在实际工程中更可能成功。

## Rerank模型在预分类和模式匹配中的应用

### 核心思路：Embedding + Rerank的分层架构

#### 1. 预分类场景分析

**初始设想的问题**：
使用Rerank匹配抽象的"处理策略"描述，如"使用单个工具完成任务"、"数据处理分析流水线"等，这种抽象描述与用户实际输入（如"查查今天的天气"）难以准确匹配。

**改进方案：直接工具相关性评分**

```python
class ToolBasedPreClassifier:
    """基于工具相关性的预分类器"""
    
    def pre_classify(self, user_input):
        # Step 1: 直接对用户输入与每个工具描述进行Rerank评分
        tool_scores = {}
        for tool_name, tool_desc in self.tool_descriptions.items():
            score = self.rerank.score(
                query=user_input,
                document=tool_desc
            )
            tool_scores[tool_name] = score
        
        # Step 2: 选出相关性较高的工具（动态阈值）
        sorted_tools = sorted(tool_scores.items(), key=lambda x: x[1], reverse=True)
        top_score = sorted_tools[0][1]
        threshold = max(0.5, top_score * 0.6)  # 动态阈值
        
        relevant_tools = [
            (tool, score) for tool, score in sorted_tools 
            if score >= threshold
        ][:5]
        
        # Step 3: 基于工具组合决定处理策略
        return self.determine_strategy(relevant_tools)
```

#### 2. 基于工具组合的策略决定

```python
def determine_strategy(self, relevant_tools):
    """根据相关工具及其分数决定处理策略"""
    
    tool_names = [t[0] for t in relevant_tools]
    scores = [t[1] for t in relevant_tools]
    
    # Case 1: 单一工具主导（分数差距大）
    if len(scores) >= 2 and scores[0] - scores[1] > 0.3:
        return {
            "strategy": "single_tool",
            "primary_tool": tool_names[0],
            "prompt_complexity": "minimal"  # 100 tokens
        }
    
    # Case 2: 无相关工具（所有分数都低）
    if scores[0] < 0.4:
        return {
            "strategy": "direct_chat",
            "prompt_complexity": "simple"  # 200 tokens
        }
    
    # Case 3: 多工具组合（多个高分工具）
    if len([s for s in scores if s > 0.6]) >= 2:
        pattern = self.identify_tool_pattern(tool_names)
        return {
            "strategy": pattern.strategy,
            "tools": tool_names[:3],
            "prompt_complexity": "full"  # 1000+ tokens
        }
```

#### 3. Embedding与Rerank的合理分工

| 使用场景 | 技术选择 | 原因 |
|---------|---------|------|
| **预分类（<20个工具）** | 纯Rerank | 工具数量有限，直接评分更准确 |
| **模式匹配（>1000个模式）** | Embedding召回 + Rerank精排 | 需要快速召回候选集，再精确排序 |
| **增量学习去重** | Embedding快速去重 + Rerank精确验证 | 平衡速度和准确性 |

### 实际应用示例

#### 示例1：简单查询
```python
# 用户输入："查查今天的天气"
# Rerank评分结果：
tool_scores = [
    ("web_search", 0.95),      # 高度相关
    ("knowledge_base", 0.3),    # 低相关
    ("chat", 0.2)              # 低相关
]
# 决策：single_tool策略，直接调用web_search，使用minimal prompt (100 tokens)
```

#### 示例2：复杂分析
```python
# 用户输入："分析这个月的销售数据并生成报告"
# Rerank评分结果：
tool_scores = [
    ("pandas_data_calculator", 0.85),
    ("table_analyzer", 0.82),
    ("report_generator", 0.78),
    ("calculator", 0.6)
]
# 决策：data_pipeline策略，使用工具组合，需要full prompt (1000+ tokens)
```

### 混合架构的优势

```python
class OptimizedHybridArchitecture:
    """优化的混合架构"""
    
    def __init__(self):
        self.embedder = EmbeddingModel()  # 用于大规模召回
        self.rerank = RerankModel()       # 用于精确评分
        self.pattern_index = VectorIndex() # 向量索引
    
    def process_task(self, user_input):
        # 1. 工具评分（纯Rerank，因为工具数量有限）
        tool_scores = self.score_tools_with_rerank(user_input)
        
        # 2. 策略决定
        strategy = self.determine_strategy(tool_scores)
        
        # 3. 如需模式匹配（Embedding + Rerank）
        if strategy["strategy"] in ["complex_workflow", "data_pipeline"]:
            # 从数千个模式中召回
            candidates = self.recall_patterns_with_embedding(user_input)
            # 精确排序
            patterns = self.rerank_patterns(user_input, candidates)
            strategy["patterns"] = patterns
        
        # 4. 执行
        return self.execute(strategy)
```

### 关键认识

1. **Rerank不适合抽象分类**：直接评估工具相关性比评估抽象策略更有效
2. **工具组合决定策略**：根据相关工具的分布（单一主导/多工具/无相关）决定处理复杂度
3. **动态prompt复杂度**：根据策略动态选择prompt复杂度（100-1000+ tokens）
4. **分层使用技术**：
   - 小规模精确匹配用Rerank
   - 大规模召回用Embedding
   - 高精度验证用Embedding+Rerank组合

### 实施建议

1. **预分类阶段**：
   - 放弃抽象的策略分类
   - 直接使用工具相关性评分
   - 基于工具分数分布决定策略

2. **模式匹配阶段**：
   - 保持Embedding+Rerank两阶段架构
   - Embedding负责从海量模式中快速召回
   - Rerank负责精确排序和验证

3. **成本优化**：
   - 简单任务（single_tool）避免复杂prompt
   - 只在必要时（多工具组合）使用完整prompt
   - 缓存常用模式的Embedding和Rerank结果

这种基于工具相关性的直接评分方法，比试图让Rerank理解抽象策略更加实用和准确。

---

*记录时间：2024-12*
*基于12-Factor Agents框架的实施思考*