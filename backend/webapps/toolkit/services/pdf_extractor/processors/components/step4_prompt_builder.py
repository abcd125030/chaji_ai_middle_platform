"""
Step4 提示词构建器

负责构建图片插入位置分析的提示词，使用 tag 化结构以提高可读性和可维护性
"""
import logging

logger = logging.getLogger('django')


class InsertionPromptBuilder:
    """插入位置分析提示词构建器 - 使用 tag 化结构"""

    @staticmethod
    def build_insertion_prompt(
        page_number: int,
        image_count: int
    ) -> str:
        """
        构建图片插入位置分析提示词（JSON返回）

        结构：
        1. 任务说明
        2. 图片索引说明
        3. 分析任务步骤
        4. 锚点文本提取规则（核心）
        5. 返回格式说明
        6. 字段说明
        7. 注意事项

        Args:
            page_number: 页码
            image_count: 分割图片数量

        Returns:
            完整的 prompt 字符串
        """
        prompt = InsertionPromptBuilder._build_task_description()
        prompt += InsertionPromptBuilder._build_image_indices(image_count)
        prompt += InsertionPromptBuilder._build_analysis_steps()
        prompt += InsertionPromptBuilder._build_anchor_extraction_rules()
        prompt += InsertionPromptBuilder._build_return_format(image_count)
        prompt += InsertionPromptBuilder._build_field_descriptions(image_count)
        prompt += InsertionPromptBuilder._build_important_notes()

        return prompt

    @staticmethod
    def _build_task_description() -> str:
        """
        构建任务描述部分

        Returns:
            任务描述的 prompt 文本
        """
        return """<task>
请分析文本内容和图片内容的语义关系，确定每张分割图片应该插入到文本的哪个位置。
</task>
"""

    @staticmethod
    def _build_image_indices(image_count: int) -> str:
        """
        构建图片索引说明部分

        Args:
            image_count: 分割图片数量

        Returns:
            图片索引说明的 prompt 文本
        """
        image_indices = []
        for i in range(image_count):
            image_indices.append(f"- 图片{i + 1}: 消息中第{i + 2}张图（第1张是完整页面）")

        indices_text = "\n".join(image_indices)

        return f"""
<image_indices>
{indices_text}
</image_indices>
"""

    @staticmethod
    def _build_analysis_steps() -> str:
        """
        构建分析步骤部分

        Returns:
            分析步骤的 prompt 文本
        """
        return """
<analysis_steps>
1. **理解完整页面布局**：第1张图是完整页面，用于理解整体排版和图片位置
2. **识别图片类型**：判断每张分割图是表格/图表/公式/示意图/其他
3. **定位插入点**：找到文本中与图片语义相关的段落或标题
4. **确定操作类型**：
   - `insert_before`: 在文本前插入图片
   - `insert_after`: 在文本后插入图片
</analysis_steps>
"""

    @staticmethod
    def _build_anchor_extraction_rules() -> str:
        """
        构建锚点文本提取规则部分（核心规则）

        Returns:
            锚点提取规则的 prompt 文本
        """
        return """
<anchor_extraction_rules>
<CRITICAL_RULE>
⚠️ ⚠️ ⚠️ 锚点文本必须从消息开头的"原始文本内容："中精确复制 ⚠️ ⚠️ ⚠️

❌ 禁止使用图片OCR识别的文本
✅ 必须保留Markdown格式符号（如 ** ## * 等）
✅ 必须保留换行符（在JSON中使用 \\n）
✅ 必须保留所有标点符号和大小写
</CRITICAL_RULE>

## 核心规则详解

### 1. 从原始文本内容中精确复制

锚点文本用于定位插入位置，必须与原文完全一致：

- **禁止使用图片OCR识别的文本**：必须从消息开头"原始文本内容："后面的文本中提取锚点
- **精确匹配原文格式**：包括Markdown格式符号（如 `**`、`#`、`*` 等）、标点符号、换行符
- **保持换行符**：如果原文中文本跨多行，必须在JSON中使用 \\n 保留换行符
- **保持标点符号**：完全复制句号、冒号、逗号等标点
- **保持大小写**：不要改变原文的大小写
- **保持空格**：保留原文的空格位置

## 2. 正例与反例对比（非常重要！）

### 示例1：Markdown格式符号处理

**场景**：图片OCR显示 "Fig. 1."，但原始文本是 "**Figure 1:**"

❌ **错误**：使用OCR结果
```json
{"anchor_text": "Fig. 1. Based on a novel parametric representation"}
```
**为什么错**：使用了OCR文本，原文中根本不存在"Fig. 1."

✅ **正确**：从原文复制
```json
{"anchor_text": "**Figure 1:** Based on a novel parametric representation"}
```
**为什么对**：从原始文本精确提取，保留了 ** 粗体标记和完整拼写

---

### 示例2：章节标题的井号保留

**场景**：原始文本包含 "## 3. Experimental Results"

❌ **错误**：省略格式符号
```json
{"anchor_text": "3. Experimental Results"}
```
**为什么错**：丢失了 ## Markdown标题符号

✅ **正确**：保留格式
```json
{"anchor_text": "## 3. Experimental Results"}
```
**为什么对**：保留了原文的 ## 标题格式

---

### 示例3：换行符处理

**场景**：原文跨行 "Overall Performance Results. Our framework\nconsistently outperforms"

❌ **错误**：合并成一行
```json
{"anchor_text": "Overall Performance Results. Our framework consistently outperforms"}
```
**为什么错**：丢失了原文的换行符，匹配会失败

✅ **正确**：保留换行
```json
{"anchor_text": "Overall Performance Results. Our framework\\nconsistently outperforms"}
```
**为什么对**：使用 \\n 在JSON中表示换行符，与原文一致

---

### 示例4：不要添加额外的格式

**场景**：原文是 "Figure 1: Performance comparison"（无粗体）

❌ **错误**：添加格式美化
```json
{"anchor_text": "**Figure 1:** Performance comparison"}
```
**为什么错**：原文没有 **，不要自己添加

✅ **正确**：原样复制
```json
{"anchor_text": "Figure 1: Performance comparison"}
```
**为什么对**：完全按原文，不添加不删除

---

### 示例5：中文标点符号

**场景**：原文是 "如下图所示，系统架构包括三层："

❌ **错误**：改用英文标点
```json
{"anchor_text": "如下图所示, 系统架构包括三层:"}
```
**为什么错**：把中文逗号、冒号改成了英文标点

✅ **正确**：保持原文标点
```json
{"anchor_text": "如下图所示，系统架构包括三层："}
```
**为什么对**：保留了中文标点符号（，：）

## 3. 锚点长度建议

- 单行文本：10-50 字符
- 跨行文本：可以更长，但不超过 150 字符
- 确保锚点在原文中唯一存在

## 4. 锚点类型推荐

- 图表说明文字（如 "**Figure 1:**"、"**Table 2.**"，注意包含Markdown格式）
- 段落开头的独特文字
- 章节标题（如 "## 实验结果"，注意包含井号）
</anchor_extraction_rules>
"""

    @staticmethod
    def _build_return_format(image_count: int) -> str:
        """
        构建返回格式说明部分

        Args:
            image_count: 分割图片数量

        Returns:
            返回格式说明的 prompt 文本
        """
        return """
<return_format>
返回JSON数组，每个元素描述一张图片的插入操作：

```json
[
  {
    "image_index": 1,
    "image_type": "table",
    "description": "性能对比表格",
    "anchor_text": "**Table 1.** Performance\\ncomparison results",
    "operation": "insert_after",
    "reason": "表格图片应插入在标题后面，保留说明文字"
  },
  {
    "image_index": 2,
    "image_type": "diagram",
    "description": "系统架构图",
    "anchor_text": "如下图所示，系统采用了分层架构设计",
    "operation": "insert_before",
    "reason": "架构图应插入在描述文字之前"
  }
]
```

**注意**：上述示例中的 anchor_text 都包含了Markdown格式符号（`**`、`##`），这是因为它们必须从原始文本中精确提取。
</return_format>
"""

    @staticmethod
    def _build_field_descriptions(image_count: int) -> str:
        """
        构建字段说明部分

        Args:
            image_count: 分割图片数量

        Returns:
            字段说明的 prompt 文本
        """
        return f"""
<field_descriptions>
- `image_index`: 图片序号（1到{image_count}）
- `image_type`: 图片类型（table/chart/formula/diagram/image_text/other）
- `description`: 图片简短描述（10字以内）
- `anchor_text`: 锚点文本，从原文精确提取（注意保留换行符 \\n）
- `operation`: 操作类型（仅支持 insert_before/insert_after）
- `reason`: 简短理由说明（20字以内）
</field_descriptions>
"""

    @staticmethod
    def _build_important_notes() -> str:
        """
        构建注意事项部分

        Returns:
            注意事项的 prompt 文本
        """
        return """
<IMPORTANT_NOTES>
1. **最重要**：锚点文本必须从消息开头的"原始文本内容："中提取，不要使用图片OCR识别结果
2. **Markdown格式**：如果原文包含 `**`、`##`、`*` 等格式符号，必须完整保留
3. 每张图片必须有一个插入操作
4. 锚点文本必须在原文中存在且唯一
5. **如果原文跨行，必须在 anchor_text 中使用 \\n 保留换行符**
6. **禁止使用 replace 操作**：避免替换图片相关的说明文字，所有图片只能使用前插或后插
7. 如果找不到合适的锚点，使用段落开头文字（但仍要精确复制原文格式）
</IMPORTANT_NOTES>

<self_check>
⚠️ 返回JSON前，请逐项自检：

1. ✓ 锚点文本是否从"原始文本内容："中复制？
   - 如果你看到图片中有文字，不要直接用！
   - 必须去消息开头找对应的原文

2. ✓ 是否保留了 ** ## * 等Markdown格式？
   - 原文有 **，不要去掉
   - 原文有 ##，不要去掉
   - 原文没有，不要添加

3. ✓ 跨行文本是否使用 \\n 表示换行符？
   - JSON中换行必须写成 \\n
   - 不要合并成一行

4. ✓ 标点符号是否完全一致？
   - 中文标点（，。：）不要改成英文
   - 英文标点（,.:）不要改成中文

5. ✓ 大小写是否与原文一致？
   - Figure不要写成figure
   - TABLE不要写成Table
</self_check>

<output_format>
请仔细分析并完成上述自检后，返回JSON数组，不要有任何额外说明。
</output_format>
"""
