"""
Step1: LLM Markdown格式化器

负责使用LLM将PDF提取的原始文本格式化为Markdown格式
"""
import logging
from typing import Tuple, Optional
from .step1_prompt_builder import PromptBuilder

logger = logging.getLogger('django')


class LLMFormatter:
    """LLM Markdown格式化器"""

    # 最小文本长度阈值
    MIN_TEXT_LENGTH = 50
    # 最大允许的输出/输入比例
    MAX_LENGTH_RATIO = 3.0

    def __init__(
        self,
        llm_client,
        model: str = "qwen-coder-plus",
        prompt_builder: Optional[PromptBuilder] = None
    ):
        """
        初始化LLM格式化器

        Args:
            llm_client: OpenAI客户端实例
            model: 使用的LLM模型名称
            prompt_builder: Prompt构建器实例（可选，默认创建新实例）
        """
        if not llm_client:
            raise RuntimeError("LLM客户端未提供，无法初始化格式化器")

        self.client = llm_client
        self.model = model
        self.prompt_builder = prompt_builder or PromptBuilder()

        logger.info(f"LLM格式化器初始化完成，模型: {model}")

    def format_text(
        self,
        text: str,
        previous_page_content: str = None,
        output_dir = None,
        page_number: int = None
    ) -> Tuple[str, dict]:
        """
        使用LLM格式化文本为Markdown

        Args:
            text: 原始文本
            previous_page_content: 前一页的格式化内容（可选，用于上下文参考）
                - 传递前一页的完整markdown内容，帮助LLM保持跨页格式一致性
                - Prompt中包含Few-shot示例，教LLM如何维持标题层级和列表样式的一致性
            heading_rules: 标题规则字典（可选，用于保持全文档一致性）

        Returns:
            (格式化后的Markdown文本, 调试信息字典)

            调试信息字典包含以下字段:
            - model: 使用的LLM模型名称
            - input_length: 输入文本长度
            - output_length: 输出文本长度
            - length_ratio: 输出/输入长度比例
            - prompt_tokens: prompt消耗的token数
            - completion_tokens: 生成内容消耗的token数
            - raw_response: LLM的原始响应
            - original_text: 原始输入文本
            - full_prompt: 完整的prompt内容(包含规则、Few-shot示例、上下文参考、原始文本)
            - llm_response_raw: LLM的原始响应(同raw_response)

        Raises:
            ValueError: 输入文本过短或输出异常
            RuntimeError: LLM调用失败
        """
        # 【措施1】输入长度检查
        if len(text.strip()) < self.MIN_TEXT_LENGTH:
            warning_msg = (
                f"输入文本过短（{len(text)} 字符 < {self.MIN_TEXT_LENGTH}），"
                f"跳过LLM格式化以避免幻觉"
            )
            logger.warning(warning_msg)
            raise ValueError(warning_msg)

        try:
            logger.info(f"调用LLM格式化文本，原始长度: {len(text)} 字符")

            # 构建完整的prompt
            full_prompt = self.prompt_builder.build_prompt(
                text=text,
                previous_page_content=previous_page_content
            )

            # 【措施4】调用API，降低温度到0.0
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ],
                temperature=0.0,  # 降低到0.0以最大程度减少随机性和幻觉
                stream=False
            )

            formatted_text = completion.choices[0].message.content
            logger.info(f"LLM格式化完成，输出长度: {len(formatted_text)} 字符")

            # 清理LLM响应中可能存在的markdown代码块标识
            formatted_text = self._clean_llm_response(formatted_text)

            # 保存prompt和response到文件（如果提供了output_dir和page_number）
            if output_dir and page_number is not None:
                from pathlib import Path
                output_dir = Path(output_dir)

                # 保存完整prompt
                prompt_file = output_dir / f"page_{page_number}_step1_llm_format_prompt.txt"
                with open(prompt_file, 'w', encoding='utf-8') as f:
                    f.write(full_prompt)
                logger.info(f"✓ LLM格式化prompt已保存: {prompt_file}")

                # 保存LLM响应
                response_file = output_dir / f"page_{page_number}_step1_llm_format_response.md"
                with open(response_file, 'w', encoding='utf-8') as f:
                    f.write(formatted_text)
                logger.info(f"✓ LLM格式化响应已保存: {response_file}")

            # 【措施2】输出长度异常检测
            input_len = len(text)
            output_len = len(formatted_text)
            length_ratio = output_len / input_len if input_len > 0 else 0

            if length_ratio > self.MAX_LENGTH_RATIO:
                error_msg = (
                    f"输出长度异常：输入 {input_len} 字符，输出 {output_len} 字符，"
                    f"增长比例 {length_ratio:.1f}x 超过阈值 {self.MAX_LENGTH_RATIO}x，"
                    f"疑似LLM幻觉（虚构内容）"
                )
                logger.error(error_msg)
                logger.error(f"异常输出内容（前500字符）: {formatted_text[:500]}")
                raise ValueError(error_msg)

            # 构建调试信息
            debug_info = {
                "model": self.model,
                "input_length": input_len,
                "output_length": output_len,
                "length_ratio": round(length_ratio, 2),
                "prompt_tokens": completion.usage.prompt_tokens if hasattr(completion, 'usage') else None,
                "completion_tokens": completion.usage.completion_tokens if hasattr(completion, 'usage') else None,
                "raw_response": formatted_text,
                "original_text": text,
                "full_prompt": full_prompt,  # 完整的prompt(包含规则+上下文+原始文本)
                "llm_response_raw": formatted_text  # LLM的原始响应
            }

            return formatted_text, debug_info

        except Exception as e:
            logger.error(f"LLM格式化失败: {str(e)}", exc_info=True)
            raise RuntimeError(f"LLM格式化失败: {str(e)}")

    def _clean_llm_response(self, text: str) -> str:
        """
        清理LLM响应中可能存在的markdown代码块标识和推理性文字

        LLM有时会：
        1. 将整个输出用```markdown```包裹
        2. 在输出开头添加推理性说明（如"继续前一页的内容..."）

        Args:
            text: LLM原始响应文本

        Returns:
            清理后的文本
        """
        import re

        # 移除开头的```markdown或```
        text = re.sub(r'^```markdown\s*\n', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*\n', '', text, flags=re.MULTILINE)

        # 移除结尾的```
        text = re.sub(r'\n```\s*$', '', text, flags=re.MULTILINE)

        # 【新增】移除推理性文字
        # 这些文字通常出现在跨页处理时，LLM会解释"为什么保留这部分内容"
        reasoning_patterns = [
            r'^继续前一页的内容[^。！？\n]*[。！？]\s*',  # "继续前一页的内容..."句子
            r'^当前页开头的内容在语义上[^。！？\n]*[。！？]\s*',  # "当前页开头的内容在语义上..."句子
            r'^因此，我们保留[^。！？\n]*[。！？]\s*',  # "因此，我们保留..."句子
            r'^根据上下文[^。！？\n]*[。！？]\s*',  # "根据上下文..."句子
        ]

        for pattern in reasoning_patterns:
            text = re.sub(pattern, '', text, flags=re.MULTILINE)

        # 如果第一段是完整的推理说明（可能包含多句话），也删除
        # 特征：不是Markdown结构（标题、列表、表格），纯文本段落，内容是元说明
        lines = text.split('\n')
        if lines and not lines[0].strip().startswith(('#', '-', '*', '|', '>', '`', '[')):
            # 检查第一段是否包含推理性关键词
            first_paragraph = lines[0].strip()
            meta_keywords = ['继续', '当前页', '因此', '保留', '语义上', '承接', '上文', '格式化规则']
            if any(keyword in first_paragraph for keyword in meta_keywords):
                logger.warning(f"检测到推理性文字（第一段），已删除: {first_paragraph[:100]}...")
                # 删除第一段及其后的空行
                while lines and (not lines[0].strip() or
                                 any(kw in lines[0] for kw in meta_keywords)):
                    lines.pop(0)
                text = '\n'.join(lines)

        # 去除首尾空白
        text = text.strip()

        return text
