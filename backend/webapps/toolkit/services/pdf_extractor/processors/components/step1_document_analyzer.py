"""
Step1: 文档结构分析器

负责分析PDF文档的整体结构,提取标题层级规则,并管理标题规则缓存
"""
import logging
import json
import re
import fitz
from typing import Optional

logger = logging.getLogger('django')


class DocumentAnalyzer:
    """PDF文档结构分析器"""

    def __init__(self, llm_client=None, model: str = "qwen-coder-plus"):
        """
        初始化文档分析器

        Args:
            llm_client: OpenAI客户端实例（可选）
            model: 使用的LLM模型名称
        """
        self.client = llm_client
        self.model = model
        self.heading_rules = None  # 标题规则缓存

    def reset_heading_context(self):
        """
        重置标题上下文状态

        用于处理新文档时清空之前文档的标题规则缓存，
        确保每个文档的标题层级分析从干净的状态开始。
        """
        self.heading_rules = None
        logger.info("标题上下文已重置")

    def analyze_document_structure(
        self,
        pdf_path: str,
        sample_pages: int = 3
    ) -> dict:
        """
        分析PDF文档的整体结构，提取标题层级规则

        Args:
            pdf_path: PDF文件路径
            sample_pages: 采样页数（前N页）

        Returns:
            标题规则字典，例如：
            {
                "第X章": "##",
                "一、": "###",
                "（一）": "####",
                "1.": "###",
                "1.1": "####"
            }
        """
        if not self.client:
            logger.warning("LLM未启用，无法分析文档结构")
            return {}

        try:
            doc = fitz.open(pdf_path)
            sample_text = []

            # 采样前几页
            for page_num in range(min(sample_pages, doc.page_count)):
                page = doc[page_num]
                text = page.get_text("text")
                sample_text.append(text)

            doc.close()

            # 合并采样文本
            combined_sample = "\n\n=== 页面分隔 ===\n\n".join(sample_text)

            # 使用LLM分析标题规则
            analysis_prompt = """分析以下PDF文档的前几页内容，识别标题的编号模式和层级关系。

请严格按照以下JSON格式返回标题规则映射：

{
  "heading_rules": {
    "数字+空格+标题": "##",
    "数字.数字+空格+标题": "###",
    "数字.数字.数字+空格+标题": "####"
  },
  "explanation": "简要说明识别到的标题模式"
}

**重要说明**：
- heading_rules 的 key 应该是**编号模式的描述**，而不是具体的标题文本
- 例如：如果看到 "1 Introduction"、"2 Related Works"，应该返回 "数字+空格+标题": "##"
- 例如：如果看到 "2.1 Background"、"3.1 Method"，应该返回 "数字.数字+空格+标题": "###"
- 不要返回具体的标题文本如 "1 Introduction": "##"，这是错误的

识别规则：
- 识别文档中实际使用的编号模式（如"数字+空格"、"数字.数字+空格"等）
- 根据编号的层级关系分配Markdown标题级别（## / ### / ####）
- 如果没有明确的编号模式，返回空的heading_rules对象

待分析内容：

""" + combined_sample

            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": analysis_prompt
                    }
                ],
                temperature=0.1,
                stream=False
            )

            response = completion.choices[0].message.content
            logger.info(f"文档结构分析响应: {response[:200]}")

            # 解析JSON响应
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                heading_rules = analysis.get("heading_rules", {})
                logger.info(f"识别到标题规则: {heading_rules}")

                # 缓存标题规则
                self.heading_rules = heading_rules
                return heading_rules
            else:
                logger.warning("无法解析标题规则JSON")
                return {}

        except Exception as e:
            logger.error(f"分析文档结构失败: {str(e)}", exc_info=True)
            return {}

    def get_heading_rules(self) -> Optional[dict]:
        """
        获取当前缓存的标题规则

        Returns:
            标题规则字典，如果未分析则返回None
        """
        return self.heading_rules

    def set_heading_rules(self, heading_rules: dict):
        """
        手动设置标题规则

        Args:
            heading_rules: 标题规则字典
        """
        self.heading_rules = heading_rules
        logger.info(f"标题规则已更新: {heading_rules}")
