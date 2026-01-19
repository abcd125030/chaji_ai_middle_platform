"""
Google Search Tool - 网络搜索与信息检索工具

文件功能概述：
===============
本文件实现了基于Google AI Studio的网络搜索工具，通过Gemini模型的search功能执行网络搜索，
自动提取信息、生成总结，并附带引用链接标记。

输入与输出：
===========
输入 (GoogleSearchInput):
- query (str): 搜索查询字符串

execute方法参数:
- tool_input (Dict[str, Any]): 包含上述输入参数
- runtime_state (Any): 运行时状态信息
- user_id (Optional[Union[str, int]]): 用户标识符，用于个性化服务和日志追踪

输出 (WebSearchOutput):
- status (str): 执行状态 ("success" | "error")
- output (str): 带引用标记的搜索结果总结文本（Markdown格式）
- type (str): 输出类型标识 ("markdown")
- raw_data (dict): 原始数据，包含引用信息和API响应
- metrics (list): 搜索指标统计
- metadata (dict): 元数据，包含输入参数和使用的模型
- message (str): 执行结果描述

内部处理流程：
=============
1. 输入验证 - 解析并验证 WebSearchInput 参数
2. 模型配置 - 获取 gemini-2.5-flash 模型的API配置
3. 提示词构建 - 基于PTCF框架构建专业的搜索分析提示词
4. API调用 - 调用Google AI Studio的搜索API执行网络搜索
5. 结果解析 - 从API响应中提取生成的文本和grounding metadata
6. 引用处理 - 提取引用信息并在文本中插入引用标记
7. 格式化输出 - 构建标准化的工具输出格式

执行逻辑说明：
=============
- 使用Google官方PTCF (Persona-Task-Context-Format) 框架优化搜索提示词
- 采用temperature=0确保事实性任务的输出稳定性
- 自动处理搜索结果的引用提取和标记插入
- 支持Vertex AI Search跳转链接的检测和处理
- 提供详细的错误处理和日志记录

函数调用关系：
=============
主要函数：
- GoogleSearchTool.execute() - 主执行入口
  ├── WebSearchInput() - 输入验证
  ├── ModelConfigManager.get_model_config() - 获取模型配置
  ├── requests.post() - HTTP API调用
  ├── get_citations() - 提取引用信息
  ├── insert_citation_markers() - 插入引用标记
  └── WebSearchOutput() - 构建输出对象

辅助函数：
- get_citations() - 从Gemini响应中提取结构化引用信息
- insert_citation_markers() - 在文本中插入引用标记
- get_current_date() - 获取当前日期格式化字符串

外部函数依赖：
=============
核心框架依赖：
- tools.core.base.BaseTool - 工具基类
- tools.core.registry.register_tool - 工具注册装饰器
- tools.core.types.ToolType - 工具类型枚举
- llm.config_manager.ModelConfigManager - 模型配置管理器

数据模型依赖：
- WebSearchInput/WebSearchOutput - 输入输出数据模型 (本地定义)
- Citation/CitationSegment - 引用数据结构 (本地定义)

特殊说明：
=========
1. 必须使用gemini-2.5-flash模型，因为只有Gemini系列支持GoogleSearch功能
2. API调用通过frago.ai代理服务转发到Google AI Studio
3. 引用链接包含对Vertex AI Search跳转链接的特殊处理
4. 输出格式遵循系统统一的工具输出规范

作者: 系统生成
最后更新: 2025-09-27
版本: 1.0
"""

# file: backend/tools/advanced/web_search.py
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, HttpUrl

from tools.core.base import BaseTool
from tools.core.registry import register_tool
from tools.core.types import ToolType
from llm.config_manager import ModelConfigManager

import logging
logger = logging.getLogger(__name__)

# --- Pydantic Schemas for Input/Output ---

class CitationSegment(BaseModel):
    label: str = Field(description="The title of the source.")
    short_url: str = Field(description="A short, unique URL for the source.")
    value: HttpUrl = Field(description="The original, full URL of the source.")

class Citation(BaseModel):
    start_index: int = Field(description="The starting index of the citation in the text.")
    end_index: int = Field(description="The ending index of the citation in the text.")
    segments: List[CitationSegment] = Field(description="A list of citation segments.")

class GoogleSearchInput(BaseModel):
    """谷歌搜索工具输入参数模型"""
    query: str = Field(description="搜索查询字符串")

class WebSearchOutput(BaseModel):
    text: str = Field(description="The generated text with citation markers.")
    citations: List[Citation] = Field(description="A list of structured citation details.")

# --- Helper Functions (模仿 agentic_sample_codes/utils.py) ---

def get_citations(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extracts and formats citation information from a Gemini model's response dictionary.
    """
    citations = []
    if not response_data or not response_data.get("candidates"):
        return citations

    candidate = response_data["candidates"][0]
    grounding_metadata = candidate.get("groundingMetadata")
    if not grounding_metadata or not grounding_metadata.get("groundingSupports"):
        return citations

    for support in grounding_metadata.get("groundingSupports", []):
        citation = {}
        segment = support.get("segment")
        if not segment:
            continue

        start_index = segment.get("startIndex", 0)
        end_index = segment.get("endIndex")
        if end_index is None:
            continue

        citation["start_index"] = start_index
        citation["end_index"] = end_index
        citation["segments"] = []

        if "groundingChunkIndices" in support and support["groundingChunkIndices"]:
            for ind in support["groundingChunkIndices"]:
                try:
                    chunk = grounding_metadata["groundingChunks"][ind]
                    # 获取 URL（可能是直接链接或 Vertex AI Search 跳转链接）
                    uri = chunk["web"]["uri"]
                    title = chunk["web"].get("title", "Unknown")
                    
                    # 检测是否是 Vertex AI Search 跳转链接
                    if "vertexaisearch.cloud.google.com" in uri:
                        # Vertex AI Search 跳转链接无法直接解析为真实 URL
                        # 保留原始链接，但记录警告
                        logger.debug(f"检测到 Vertex AI Search 跳转链接: {title}")
                        final_url = uri
                    else:
                        # 直接链接，保持原样
                        final_url = uri
                    
                    # 处理标题，如果是域名格式（如 "mayoclinic.org"），保留；否则截取
                    if "." in title and len(title.split(".")) >= 2:
                        label = title
                    else:
                        label = title.split(".")[0] if "." in title else title
                    
                    citation["segments"].append(
                        {
                            "label": label,
                            "short_url": final_url,  # 使用最终的 URL
                            "value": final_url,      # 使用最终的 URL
                        }
                    )
                except (IndexError, KeyError, AttributeError):
                    pass
        citations.append(citation)
    return citations

def insert_citation_markers(text, citations_list):
    """
    Inserts citation markers into a text string based on start and end indices.
    (完全模仿 agentic_sample_codes/utils.py 的实现)
    """
    # Sort citations by end_index in descending order.
    # If end_index is the same, secondary sort by start_index descending.
    # This ensures that insertions at the end of the string don't affect
    # the indices of earlier parts of the string that still need to be processed.
    sorted_citations = sorted(
        citations_list, key=lambda c: (c["end_index"], c["start_index"]), reverse=True
    )

    modified_text = text
    for citation_info in sorted_citations:
        # These indices refer to positions in the *original* text,
        # but since we iterate from the end, they remain valid for insertion
        # relative to the parts of the string already processed.
        end_idx = citation_info["end_index"]
        marker_to_insert = ""
        for segment in citation_info["segments"]:
            marker_to_insert += f" [{segment['label']}]({segment['short_url']})"
        # Insert the citation marker at the original end_idx position
        modified_text = (
            modified_text[:end_idx] + marker_to_insert + modified_text[end_idx:]
        )

    return modified_text

def get_current_date():
    """Get current date in a readable format"""
    return datetime.now().strftime("%B %d, %Y")

# Web searcher instructions - 基于 Google 官方 PTCF (Persona-Task-Context-Format) 框架
# PTCF 是 Google 推荐的 Gemini API 最佳实践框架，用于获得最佳输出质量
# 官方文档：https://ai.google.dev/gemini-api/docs/prompting-strategies
# 
# 重要说明：
# 1. GoogleSearch 工具会自动根据查询内容决定搜索策略
# 2. 模型会自动处理搜索、处理和引用信息的整个工作流
# 3. 不需要指示"多次搜索"，工具会根据需要自动执行多个查询
web_searcher_instructions = """[角色定位]
你是一位专业的信息分析师，擅长从网络搜索结果中提取和整合信息。

[任务]
针对以下查询进行搜索和分析：{research_topic}

[背景信息]
- 今天的日期：{current_date}
- 用户需要基于实际搜索结果的准确信息
- GoogleSearch 工具将自动执行搜索
- 你将收到搜索结果并需要进行分析和总结

[输出格式]
请按以下结构组织你的回答：

### 核心发现
简要概述搜索结果中的关键信息（2-3段）

### 详细信息
- 从搜索结果中提取的要点
- 每个要点都应基于具体的搜索结果
- 保持客观，只报告搜索到的内容

### 信息来源
系统会自动附加搜索结果的引用链接

[重要原则]
- 严格基于搜索结果回答，不要添加训练数据中的信息
- 如果搜索结果不充分，明确说明缺少哪些信息
- 保持信息的准确性和可验证性
"""

# --- Tool Implementation ---

@register_tool(
    name="GoogleSearch", 
    description="通过Google AI Search工具执行网络搜索并生成总结。输入：要搜索的内容以及对内容的预期，。用途：深度信息研究、事实核查、市场分析、新闻追踪等。特点：使用Gemini-2.5-flash模型、PTCF框架提示词、自动提取并标记引用。",
    tool_type=ToolType.RETRIEVAL,
    category="retrieval"
)
class GoogleSearchTool(BaseTool):

    def get_input_schema(self) -> Dict[str, Any]:
        return GoogleSearchInput.model_json_schema()

    def execute(self, tool_input: Dict[str, Any], runtime_state: Any = None, user_id: Optional[Union[str, int]] = None) -> Dict[str, Any]:
        # 使用Pydantic模型验证输入
        try:
            parsed_input = GoogleSearchInput(**tool_input)
        except Exception as e:
            return {
                "status": "error",
                "output": f"输入参数验证失败: {str(e)}",
                "type": "text",
                "raw_data": None,
                "metrics": [],
                "metadata": {
                    "error": str(e),
                    "error_type": "ValidationError",
                    "user_id": user_id
                },
                "message": f"输入参数验证失败: {str(e)}"
            }
        
        try:
            query = parsed_input.query
            
            model_name = "gemini-2.5-flash"  # Web search 必须使用 Gemini 模型
            
            
            model_name = "gemini-2.5-flash"  # Web search 必须使用 Gemini 模型
            config_manager = ModelConfigManager()
            model_config = config_manager.get_model_config(model_name)
            api_key = model_config.get("api_key")
            if not api_key:
                raise RuntimeError(f"API key for model '{model_name}' not found in database.")

            url = "https://go.frago.ai/api/v2/forward/google-ai-studio/"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            }
            
            current_date = get_current_date()
            formatted_prompt = web_searcher_instructions.format(
                current_date=current_date,
                research_topic=query,
            )
            
            # Generation配置 - 基于官方最佳实践
            # temperature=0: 确保事实性搜索任务的输出稳定性和准确性
            # maxOutputTokens: 设置合理的输出长度限制，避免过长或截断
            # topP=0.95: 保持一定的输出多样性，同时避免低概率的不相关内容
            # topK=40: 限制候选词汇表大小，提高输出质量
            gemini_payload = {
                "model": model_name,
                "contents": [{"parts": [{"text": formatted_prompt}]}],
                "tools": [{"google_search": {}}],  # 使用 google_search 固定名称
                "generationConfig": {
                    "temperature": 0,        # 事实性任务使用0，确保输出稳定
                    "maxOutputTokens": 4096, # 更充分的输出长度，约2400-3200字
                    "topP": 0.95,           # 标准设置，平衡准确性和多样性
                    "topK": 40              # 标准设置，限制候选词汇
                }
            }

            import requests
            response = requests.post(url, headers=headers, json=gemini_payload)
            response.raise_for_status()
            response_data = response.json()
            
            # 打印 Google AI SDK 调用 Google Search 返回的全部结果
            # logger.info("=" * 10)
            # logger.info("[WebSearch] Google AI SDK 返回的完整结果:")
            # logger.info(json.dumps(response_data, indent=4, ensure_ascii=False))
            # logger.info("=" * 10)
            
            # 更详细的响应调试
            if "candidates" in response_data and response_data["candidates"]:
                candidate = response_data["candidates"][0]
                
            
            if (response_data.get("candidates") and
                response_data["candidates"][0].get("content") and
                response_data["candidates"][0]["content"].get("parts") and
                response_data["candidates"][0]["content"]["parts"][0].get("text")):
                generated_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                generated_text = "No summary available."

            citations_dict_list = []
            modified_text = generated_text
            
            candidate = response_data.get("candidates", [{}])[0]
            grounding_metadata = candidate.get("groundingMetadata")
            
            if grounding_metadata and grounding_metadata.get("groundingChunks"):
                citations_dict_list = get_citations(response_data)
                modified_text = insert_citation_markers(generated_text, citations_dict_list)
            else:
                logger.warning(f"[WebSearch警告] 没有找到 groundingChunks，无法提取引用链接")
            
            # 转换为 Pydantic 模型格式以保持输出接口不变
            citations_pydantic = []
            for citation_dict in citations_dict_list:
                segments_pydantic = []
                for segment_dict in citation_dict["segments"]:
                    segments_pydantic.append(CitationSegment(
                        label=segment_dict["label"],
                        short_url=segment_dict["short_url"],
                        value=HttpUrl(segment_dict["value"])
                    ))
                
                citations_pydantic.append(Citation(
                    start_index=citation_dict["start_index"],
                    end_index=citation_dict["end_index"],
                    segments=segments_pydantic
                ))
            
            output = WebSearchOutput(text=modified_text, citations=citations_pydantic)
            
            # 新的统一输出格式
            return_result = {
                "status": "success",
                "output": modified_text,  # 语义化输出：带引用标记的搜索结果文本
                "type": "markdown",  # 输出类型：markdown（包含引用链接）
                "raw_data": {
                    "citations": output.model_dump(mode='json')['citations'],
                    "original_response": response_data
                },
                "metrics": [
                    f"找到 {len(citations_pydantic)} 个引用源",
                    f"搜索关键词长度 {len(query)} 字符",
                    f"生成内容 {len(modified_text)} 字符"
                ],
                "metadata": {
                    "tool_input": {"query": query},
                    "user_id": user_id,
                    "model_used": model_name
                },
                "message": f"成功搜索 '{query[:30]}...' 并生成摘要"
            }
            # logger 打印 return_result 的内容（已注释，减少日志输出）
            # logger.info(f"[WebSearch] 返回结果: {json.dumps(return_result, indent=4, ensure_ascii=False)}")
            return return_result

        except Exception as e:
            logger.error(f"Web search error: {str(e)}")
            return {
                "status": "error",
                "output": f"Web搜索失败: {str(e)}",
                "type": "text",
                "raw_data": None,
                "metrics": [],
                "metadata": {
                    "error": str(e),
                    "user_id": user_id
                },
                "message": f"Web搜索失败: {str(e)}"
            }