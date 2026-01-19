"""
Step1: Prompt构建器（重构版 - 精简高效）

负责构建LLM Markdown格式化所需的完整prompt。
核心策略：精简指令 + 突出上下文一致性
"""
import logging

logger = logging.getLogger('django')


class PromptBuilder:
    """LLM Markdown格式化Prompt构建器 - 精简版"""

    def __init__(self):
        """初始化Prompt构建器"""
        pass

    def build_prompt(
        self,
        text: str,
        previous_page_content: str = None
    ) -> str:
        """
        构建完整的LLM格式化prompt（精简版）

        结构：
        1. 角色与核心原则（精简）
        2. 【如果有前页】上下文参考内容 + 一致性要求（置顶突出）
        3. 格式化规则（压缩版）
        4. 原始文本

        Args:
            text: 当前页原始文本
            previous_page_content: 前一页的完整格式化内容（可选）

        Returns:
            完整的prompt字符串
        """
        # 第1部分：角色+规则
        prompt = self._build_role_and_principles()
        prompt += self._build_formatting_rules()

        # 第2部分：上文内容（如果有）
        if previous_page_content:
            prompt += self._build_context_section(previous_page_content)

        # 第3部分：待格式化文本
        full_prompt = f"{prompt}\n<current_page>\n{text}\n</current_page>"

        return full_prompt

    def _build_role_and_principles(self) -> str:
        """
        构建角色定位与核心原则

        Returns:
            角色与原则的prompt文本
        """
        return """<task>
根据上下文语义理解内容关系，并参考提供的已格式化的相关内容，对目标内容进行"一致"的格式化。
</task>

<principles>
1. 保持原文不变，只做格式化
2. 标题统一用井号格式（##/###/####），禁止用粗体作标题
3. 根据上下文理解待处理内容与"给出的相关内容"的层级关系
</principles>"""

    def _build_formatting_rules(self) -> str:
        """
        构建核心格式化规则（压缩版，去除冗余）

        Returns:
            核心格式化规则的prompt文本
        """
        return r"""

<formatting_rules>
1. 标题：
   - 章级标题用 ##，节级用 ###，子节用 ####
   - 保留原标题编号（如 2.1 Method 假设为三级标题，则 → ### 2.1 Method）

2. 数学公式：
   - 行内公式：$x = y + 1$
   - 独立公式块用 $$ 包裹
   - 如无公式编号，禁止擅自添加，如有公式编号，则必须在 $$ 外面，独立一行

3. 表格/列表：
   - 表格转为 | 列1 | 列2 | 格式
   - 保持列表编号和缩进层级

4. 段落：
   - 空行分隔段落
   - 合并同一段落的文本（去除PDF强制换行）

5. 图片：
   - 不要添加图片引用语法（后续步骤会自动插入）
   - 图表说明保持纯文本

6. URL：
   - URL后如果是中文，必须添加空格或标点分隔
</formatting_rules>

<FORBIDDEN>
- 改写/简化内容
- 擅自补充内容
- 混用标题格式（粗体与井号）
- 将公式放在代码块中
</FORBIDDEN>

<context_consistency>
如提供了已格式化的前一页内容：
- 上文与下文是连贯的文档上下文
- 必须参考上文的标题层级（##/###/####），确保同层级标题使用相同格式
- **段落续接处理**：
  * 如果当前页开头没有标题、列表、图表等明显起点标识
  * 且内容在语义上延续前页末尾的段落
  * 则应完整保留这部分续接内容，不要因为"避免重复"而删除
- 只有在出现以下情况时才视为重复内容并删除：
  * 标题/章节编号重复
  * 图表说明重复
  * 完整段落逐字重复
</context_consistency>

<special_handling>
1. 打散的表格内容：
   - current_page中的文本可能包含通过Python库提取时被打散的表格内容
   - 需要将这些打散的元素重构为正确的Markdown表格（| 列1 | 列2 | 格式）
   - 通过分析间距模式、对齐方式和语义关系识别表格行
   - 保持列标题和数据单元格的对齐关系

2. 独立呈现的图表说明：
   - 图表说明（caption）可能因为图片未嵌入而单独呈现为一段文本
   - 将这些说明保持为普通文本段落（不要使用 ![...] 图片语法）
   - 维护说明的原有格式（例如"Figure 3: Example ACE-Generated Context..."）
   - 不要尝试插入图片占位符 - 图片插入将在Step 4中处理
</special_handling>

<output_format>
CRITICAL: 直接返回格式化后的Markdown文本，不要添加任何说明、解释、推理过程！

严禁输出：
- "继续前一页的内容..."
- "当前页开头的内容在语义上..."
- "因此，我们保留..."
- 任何关于"如何处理"的说明文字

正确做法：
- 第一行就应该是实际的Markdown内容（标题、段落文本等）
- 不要用代码块包裹整个输出
- 不要添加任何元说明（meta-description）
</output_format>
"""

    def _build_context_section(self, previous_page_content: str) -> str:
        """
        构建前页内容上下文参考部分（精简版，与待格式化内容直接衔接）

        Args:
            previous_page_content: 前一页的完整格式化内容

        Returns:
            前页内容部分的prompt文本
        """
        return f"""

<previous_page>
{previous_page_content}
</previous_page>
"""
