# PDF提取器图片插入锚点不匹配问题修复

**日期**: 2025-10-10
**问题编号**: IMAGE_INSERTION_ANCHOR_MISMATCH
**严重程度**: 高

---

## 问题描述

### 现象

在PDF提取流程中，虽然图片被成功分割并保存（如 `page_1/image_1.png`），但在生成的 `page_1_final.md` 和最终的 `{task_id}_result.md` 中，**图片引用语法（`![]()`）没有被正确插入**。

### 实际案例

**任务ID**: `d03f9244-e8c2-429f-9bc8-4b4e9f0365c2`

**文件结构**:
```
page_1/
├── page_1.md                    # step1 LLM格式化后的文本
├── page_1_raw.txt               # step1 PyMuPDF提取的原始文本
├── page_1_final.md              # step4 重构后的markdown（问题文件）
├── full_page.png                # step2 完整页面截图
├── image_1.png                  # step3 分割的图片
├── step4_model_response.json    # step4 VL模型响应
└── ...
```

**期望结果**:
```markdown
**Figure 1:** Based on a novel parametric representation...

![图1展示发型](/media/oss-bucket/_toolkit/_extractor/d03f9244-e8c2-429f-9bc8-4b4e9f0365c2/page_1/image_1.png)
```

**实际结果**:
```markdown
**Figure 1:** Based on a novel parametric representation...
（图片引用丢失）
```

---

## 根本原因分析

### 数据流追踪

1. **Step1 (文本提取)**:
   - PyMuPDF提取: `Fig. 1. Based on a novel...`
   - LLM格式化后: `**Figure 1:** Based on a novel...`
   - 返回给主流程: **格式化后的文本**

2. **Step4 (Markdown重构)**:
   - 接收: 格式化后的文本 `**Figure 1:**...`
   - VL模型分析: 同时接收文本 + 完整页面图片 + 分割图片
   - **关键问题**: VL模型从**完整页面图片的OCR识别**中看到 `Fig. 1.`，而不是从提供的文本中提取
   - VL返回锚点: `"Fig. 1. Based on a novel..."`
   - 锚点匹配: ❌ 失败（因为文本中是 `**Figure 1:**`）
   - 结果: 图片引用被跳过

### 问题核心

**VL模型的二义性行为**：
- VL模型既能读取提供的文本，也能OCR识别图片中的文字
- 在缺乏明确指引的情况下，VL模型倾向于从**图片OCR识别**中提取锚点
- 导致锚点格式与提供的文本不匹配

### 证据

**文件**: `page_1/step4_model_response.json`
```json
{
  "response": "```json\n[\n  {\n    \"anchor_text\": \"Fig. 1. Based on a novel parametric representation...\"\n  }\n]\n```"
}
```

**对比**:
- VL模型返回: `Fig. 1.` (OCR识别结果)
- 实际文本包含: `**Figure 1:**` (LLM格式化结果)
- 差异: `Fig.` vs `Figure`，`.` vs `:`，缺少粗体标记 `**`

---

## 解决方案

### 修改内容

**文件**: [step4_markdown_reconstructor.py:151-274](backend/webapps/toolkit/services/pdf_extractor/processors/step4_markdown_reconstructor.py#L151-L274)

**修改类型**: 提示词工程优化

### 关键改进

1. **明确禁止OCR提取**:
   ```
   核心原则：锚点文本必须从消息开头提供的"原始文本内容："部分中精确提取，
   不要从图片OCR识别！
   ```

2. **增加对比示例**:
   ```
   场景：图片OCR识别为 "Fig. 1."，但原始文本是 "**Figure 1:**"

   ❌ 错误做法：使用 "Fig. 1. Based on..."
   ✅ 正确做法：使用 "**Figure 1:** Based on..."
   ```

3. **强调Markdown格式保留**:
   ```
   - 精确匹配原文格式：包括Markdown格式符号（如 **、##、* 等）
   - 示例中的锚点都包含了Markdown格式符号
   ```

4. **多处强调**:
   - 在"锚点文本提取规则"标题中添加"极其重要！必须严格遵守"
   - 在"注意事项"第1条强调"最重要"
   - 在返回格式示例后添加注意事项说明

### 完整提示词结构

```
1. 图片索引说明
2. 分析任务
3. 锚点文本提取规则（极其重要！必须严格遵守）
   3.1 从原始文本内容中精确复制
   3.2 锚点提取实例对比 ← 新增
   3.3 换行符处理示例
   3.4 锚点长度建议
   3.5 锚点类型推荐
4. 返回格式
   + 注意说明 ← 新增
5. 字段说明
6. 注意事项（必读！）← 增强
```

---

## 技术细节

### 为什么会产生OCR识别？

VL模型（如Qwen3-VL-Plus）具有**多模态能力**：
- **文本理解**: 读取消息中的文本内容
- **视觉理解**: OCR识别图片中的文字
- **图文匹配**: 将图片内容与文本关联

在Step4中，VL模型同时接收：
1. 文本: `"原始文本内容：\n\n**Figure 1:** Based on..."`
2. 图片1: 完整页面截图（包含 `Fig. 1.`）
3. 图片2: 分割的区域图片

**如果提示词不够明确**，VL模型可能优先使用图片OCR识别结果作为锚点。

### 数据流图

```
┌─────────────────┐
│  PyMuPDF提取    │ → "Fig. 1. Based on..."
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM格式化      │ → "**Figure 1:** Based on..."
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Step4输入      │ ← page_text: "**Figure 1:**..."
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  VL模型分析                          │
│  - 接收文本: "**Figure 1:**..."      │
│  - 接收图片: OCR识别 "Fig. 1."       │
│  - 旧提示词: 不够明确                 │
│  - 结果: 使用OCR结果 "Fig. 1."  ❌   │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  锚点匹配失败   │ ← "Fig. 1." 在 "**Figure 1:**" 中找不到
└─────────────────┘
```

**修复后**:
```
┌─────────────────────────────────────┐
│  VL模型分析                          │
│  - 接收文本: "**Figure 1:**..."      │
│  - 接收图片: OCR识别 "Fig. 1."       │
│  - 新提示词: 明确禁止OCR，必须从文本提取│
│  - 结果: 使用文本格式 "**Figure 1:**" ✅│
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  锚点匹配成功   │ ← "**Figure 1:**" 精确匹配
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  图片引用插入   │ → ![...](image_1.png)
└─────────────────┘
```

---

## 验证方法

### 测试步骤

1. **准备测试PDF**:
   - 选择包含 `Fig.`、`Figure`、`Table` 等标记的学术论文
   - 确保PDF中有可分割的图表

2. **运行PDF提取器**:
   ```bash
   cd /Users/chagee/Repos/X/backend
   source .venv/bin/activate
   python manage.py shell
   ```

   ```python
   from webapps.toolkit.services.pdf_extractor.processors import PDFProcessor
   from pathlib import Path

   processor = PDFProcessor(
       dashscope_api_key="your_key",
       dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
   )

   result = processor.process_pdf(
       pdf_path="path/to/test.pdf",
       task_dir=Path("/path/to/output"),
       task_id="test-001"
   )
   ```

3. **检查输出**:
   ```bash
   # 检查VL模型响应
   cat page_1/step4_model_response.json

   # 检查锚点是否包含Markdown格式
   grep -o '"anchor_text": ".*"' page_1/step4_model_response.json

   # 检查最终markdown是否包含图片引用
   grep "!\[" page_1/page_1_final.md
   ```

### 预期结果

**step4_model_response.json**:
```json
{
  "response": "```json\n[\n  {\n    \"anchor_text\": \"**Figure 1:** Based on a novel parametric representation\"\n  }\n]\n```"
}
```
✅ 包含 `**` 粗体标记
✅ 包含 `:` 而不是 `.`

**page_1_final.md**:
```markdown
**Figure 1:** Based on a novel parametric representation...

![图1展示发型](/media/oss-bucket/_toolkit/_extractor/test-001/page_1/image_1.png)
```
✅ 图片引用成功插入

---

## 相关文件

### 修改文件
- [step4_markdown_reconstructor.py](backend/webapps/toolkit/services/pdf_extractor/processors/step4_markdown_reconstructor.py)

### 相关文档
- [PDF提取器架构文档](backend/webapps/toolkit/services/pdf_extractor/processors/README.md)
- [Step4优化说明](backend/webapps/toolkit/services/pdf_extractor/processors/STEP4_OPTIMIZATION.md)

### 问题案例
- 任务ID: `d03f9244-e8c2-429f-9bc8-4b4e9f0365c2`
- 位置: `backend/media/oss-bucket/_toolkit/_extractor/d03f9244-e8c2-429f-9bc8-4b4e9f0365c2/`

---

## 未来改进建议

### 1. 增加调试日志

在 `_apply_insertions` 方法中增加详细日志：
```python
logger.info(f"尝试匹配锚点: '{anchor[:50]}...'")
logger.info(f"在文本中搜索: '{page_text[:200]}...'")
if pos < 0:
    logger.warning(f"锚点匹配失败，可能原因：")
    logger.warning(f"  1. 锚点包含OCR识别文本而非原文")
    logger.warning(f"  2. 锚点缺少Markdown格式符号")
```

### 2. 自动格式对齐

如果锚点匹配失败，尝试自动修复：
```python
# 策略4: 智能格式修复
# 尝试将"Fig."替换为"Figure"，"."替换为":"等
alternative_anchor = anchor.replace("Fig.", "**Figure").replace(". ", ":** ")
pos = text.find(alternative_anchor)
```

### 3. 提示词模板化

将提示词拆分为可配置的模板：
```python
ANCHOR_EXTRACTION_RULES = """
1. 从原始文本中精确提取
2. 保留Markdown格式符号
3. 禁止使用OCR识别结果
"""
```

### 4. 单元测试覆盖

添加针对锚点匹配的单元测试：
```python
def test_anchor_extraction_with_markdown():
    """测试包含Markdown格式的锚点提取"""
    text = "**Figure 1:** Test content"
    anchor = "**Figure 1:**"  # 正确格式
    pos = reconstructor._find_anchor_position(text, anchor, 1)
    assert pos == 0

    wrong_anchor = "Fig. 1."  # 错误格式（OCR识别）
    pos = reconstructor._find_anchor_position(text, wrong_anchor, 1)
    assert pos == -1  # 应该匹配失败
```

---

## 总结

### 问题根源
VL模型在缺乏明确指引时，倾向于使用图片OCR识别结果而非提供的文本内容作为锚点。

### 解决方案
通过**提示词工程优化**，明确要求VL模型从原始文本中提取锚点，并保留所有Markdown格式符号。

### 影响范围
- 所有包含格式化文本的PDF（特别是学术论文）
- 提高图片引用插入成功率

### 风险评估
- **低风险**: 仅修改提示词，不改变代码逻辑
- **高收益**: 显著提高图片插入准确率

---

**修复状态**: ✅ 已完成
**需要测试**: 是
**向后兼容**: 是
