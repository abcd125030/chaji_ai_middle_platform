# HUMAN TALKING

## 目的

本文档由人类撰写，用于精确描述需求，约束开发路线，对齐不同流程环节的数据结构和数据流转，确保AI开发的结果不违背人类预期。

## 背景信息

**项目架构：**
- 核心能力集中在 backend目录，作为大后端，集ai infra / agentic / 数据存储 / 向量化存储 等能力
- 业务能力集中在 web 和 mini-app 等，用于提供ui/ux交互和请求的代理层

**为什么需要请求代理层，为什么不直接转发到backend？**

多业务部署需要多种不同的请求模式，由业务代理层统一构建符合backend接口标准的请求结构，而不是让后端构建大量的接口视图来响应前端多样化的数据结构需求。

## 对ai infra的期望

- 管理多个vendors
- 管理vendor 提供的多个key，多个key的原因是用于不同用户或不同业务的计量/访问权等
- 管理vendor下的多个endpoint，越来越多的实际情况表明一个vendor可能因为模型类型的差别存在多个endpoint
- 管理vendor下的多个模型，模型有不同类型、版本等
- 管理模型的分类，例如 text / reasoning / embedding / 多模态 / 文生图 / 文生视频等等
- 不同模型的响应体结构可能不一样，应该如何预设面向响应体的序列化或结构化模型，用在`当调用模型时，自动使用该结构解析响应数据`

## 思路

我感觉现在的 runtimestate 的字段细节定义得太复杂了, 我想收敛一下. 

当前RuntimeState类的__init__方法定义（schemas.py:237-297） 

- user_context: 结构不变, 只在初始化时用一个固定方法根据user id从数据库提取;
- memory: 列表, 需要依赖向量数据库检索, 找到相关历史
- 输出风格: 预定义但留空, 字符串
- output_strcture: 预定义但留空, 列表, {id, 预期结果, content, type}, 是对输出结果的预结构化,需要在过程中动态生成
- 场景: 预定义但留空, 字符串
- prompt: 用户发来的消息
- task_goal: 预定义但留空,需要由特定工具分析生成
- origin_files: 结构为 [{name: "", type: "", mapping: {provider: "aliyun|tencent|aws|gcc", path: ""}}] 
- preprocessed_files: 语义不变,结构不变
- todo: 语义不变,结构不变
- action_history: 合并原contexts的功能，结构为列表，每个元素包含执行信息和上下文信息
- chat_history: 语义不变,结构不变
- usage: 记录token用量的统计总数

核心重点在 action_history, 次重点在 chat_history 和 origin_files 及 preprocessed_files

整个agentic Graph processor 的处理流程,实际上是对 state的添砖加瓦.

无论是 planner 还是 reflection 还是 call tool, 都是在对 action_history 进行数据维护.

背景信息依靠 prompt / user_context / origin_files(用户给了什么内容是什么) / preprocessed_files（对需要解析的内容进行处理后分析用户给了什么内容是什么）/ memory（当前话题与历史话题的相关性）

输出风格 / output_structure 则是在理解了用户意图后的提前准备工作,

usage 则随着每一次action返回的结果进行更新.

最终,所有节点流转构建的完整信息结构, 通过end节点转交给指定的output工具, 在其内部自动完成最终final_answer的生成.

在这个过程中, action_history的结构必须是固定的, 它对应了每一步的:
- node: 哪个节点
- preparation: 准备工作（节点内部流程的积累）
- summary: 干了什么（摘要）  
- result: 结果（完整数据）
- context: 上下文信息，包含:
  - type: "text|image|data" 内容类型
  - content: 实际内容
  - important: 重要性标记（boolean）
  - usage_type: "refactor|modify|reference|analysis|output" 使用类型
  - mapping: 资源映射（可选）{provider: "aliyun|tencent|aws|gcc|local", path: "", public: ""}
- relevance: 该结果对最终输出的相关性（0-1的浮点数）
- usage: 用量统计，用于追加到总usage里
- next: 下一步节点列表,主要由planner提供,其他节点都是固定的,例如 call tool 产出的next 是["reflection"] 这是固定的. 

所有的工具只需要一个state的输入,由工具内部逻辑决定如何使用数据. processor只需要根据上一个action_history的`谁`和`Next`来决定导向,自身不再处理任何数据.

这个数据结构和执行逻辑调整,与当前差异有多大? 是否存在缺陷?

## 期望的agentic核心流程

### 1. 任务初始化
- celery从 redis 获取任务
- runtimestate初始化

```json
{
	"prompts": [                                                   // 多轮对话的用户输入，按轮次顺序
		"第1轮用户的提示词",
		"第2轮用户的提示词"
	],
	"user_context": {},                                            // 根据user id从数据库提取（全局共享）
	"memory": [],                                                  // 向量数据库检索的相关历史（累积）
	"output_style": "",                                             // 输出风格：预定义但留空，字符串（全局）
	"output_structure": [],                                        // {id, 预期结果, content, type} 输出预结构化（全局）
	"scenario": "",                                                // 场景：预定义但留空，字符串（全局）
	"task_goals": [                                                // 每轮的任务目标
		"第1轮任务目标",
		"第2轮任务目标"
	],
	"origin_files": [                                              // 会话级文件资源（跨轮共享）
		{
			"name": "",
			"type": "",
			"local_path": "",
			"mapping": {
				"provider": "aliyun|tencent|aws|gcc",
				"path": "",
			}
		}
	],
	"preprocessed_files": {                                        // 预处理后的文件（跨轮共享）
		"documents": {},
		"tables": {},
		"other_files": {}
	},
	"todos": [                                                     // 多轮对话的TODO清单，每轮是一个子列表
		[                                                          // 第1轮的todo列表
			{
				"id": "1",                                         // 任务唯一标识
				"task": "任务描述",                                 // 任务内容描述
				"status": "pending/processing/completed/failed",   // 任务状态
				"dependencies": ["task_id1", "task_id2"],         // 依赖的任务ID列表
				"suggested_tools": ["tool1", "tool2"],            // 建议使用的工具列表
				"priority": 5,                                     // 优先级（默认5，数值越大越优先）
				"execution_tips": "执行提示",                      // 执行建议或注意事项
				"success_criteria": "成功标准",                    // 任务完成的判断标准
				"critical_path_length": 0,                        // 关键路径长度（自动计算）
				"retry": 0,                                       // 当前重试次数
				"max_retry": 3,                                   // 最大重试次数（默认3）
				"retry_after": "2025-01-01T12:00:00",            // 重试延迟时间（ISO格式）
				"error_history": [                                // 错误历史记录
					{
						"timestamp": "2025-01-01T11:59:00",
						"attempt": 1,
						"tool_used": "tool_name", 
						"error": "错误信息",
						"retry_count": 1,
						"execution_time": 1.23
					}
				],
				"completion_details": {                           // 任务完成详情
					"completed_at": "2025-01-01T12:01:00",
					"tool_used": "tool_name",
					"execution_time": 2.34,
					"output": "执行结果"
				}
			}
		],
		[                                                          // 第2轮的todo列表
			// ...
		]
	],
	"action_history": [                                            // 多轮对话历史，每轮是一个子列表
		[                                                          // 第1轮对话的actions
			{
				"id": 1,                                           // 自增ID，用于精确定位和重连恢复
				"node": "",                                        // 谁（哪个节点）
				"preparation": "",                                 // 准备工作（节点内部流程的积累）
				"summary": "",                                     // 干了什么（摘要）
				"result": {},                                      // 结果（完整数据）
				"usage": {                                         // 用量：用于追加到usage里
					"prompt_tokens": 0,
					"completion_tokens": 0,
					"total_tokens": 0
				},
				"next": []                                         // Next：导向列表
			}
		],
		[                                                          // 第2轮对话的actions（多轮对话时追加）
			// ...
		]
	],
	"chat_history": [],                                            // 语义不变，结构不变
	"usage": [                                                     // 多轮对话的token用量，每轮一个对象
		{                                                          // 第1轮用量
			"prompt_tokens": 0,
			"completion_tokens": 0,
			"total_tokens": 0
		},
		{                                                          // 第2轮用量
			"prompt_tokens": 0,
			"completion_tokens": 0,
			"total_tokens": 0
		}
	] // 累计tokens
}
```

### 2. 执行器处理流程
调整 RuntimeState的目的，是为了：
- 满足多轮对话数据继承、复用
- 简化节点的输入输出，避免大量的节点外数据处理逻辑，把特定环节的数据处理都放在节点内部，节点始终只对state进行修改，不再输出自己的数据结构
- 简化 Processor 处理器的工作，只负责传递，而不负责数据处理或存储
- state数据的checkpoint应该是一个共用方法，由各个节点自己调用
- 基本流程：初始化state -> 同会话state继承 -> 用户数据提取(user_context字段) -> 数据预处理（origin_files和preprocessed_files字段） -> 历史挖掘（memory字段） -> 确定起点和方向（scenario/） -> 开始进入 <planner / call tool/ reflection> 循环 -> 决定FINISH -> OUTPUT节点output类工具，根据planner的最终要求导向具体工具 -> END节点（后面可能还有负责整理信息和归档到专门工具）
- 每个工具对应一个节点，每个工具都至少有一个类型，工具可能同时是output和call类型
- 工具只接收state，在内部按需提取数据字段，拼接直接使用或者拼接后调用llm生成特定内容，再进行多重处理，最终生成的数据需要写回action_history（包含context信息，当结果有用的情况下）
- 总的来说， Graph实际上是一个分析意图、掌握背景、工作（收集和分析各类信息）、结合全部上下文产出的一个复杂工作，并且试图对用户使用情况/偏好/知识点不断总结更新与复用，使Graph越来越了解用户。

# AI Executing

## 基本要求
- 按要求执行。
- 禁止按你自己的设想擅自做指令要求以外的修改。但你仍可以给出建议然后停止。

## 步骤目标：最终要创建收集用户信息的共用工具，放在 agentic 目录下的子目录中
- ✅从 UserProfile 中获取用户信息，首先打印出来我们看一下结构
	- backend/tests/agentic/test_user_profile.py
- ✅确定要添加到State的user_context结构
- ✅创建工具
	- backend/tests/agentic/test_user_context_tool.py
- ✅创建拼接 user_context 各字段值变成描述用户的提示词构建工具
	- 思考：agentic下提示词是怎么构建的？
	- 模仿
	- 基于固定的提示词模板，条件式代入，避免过多赘述
	- 工具放在哪里
	- 测试脚本
	- 输出一个prompt测试结果到工具所在目录，命名user_context_prompt.sample
	