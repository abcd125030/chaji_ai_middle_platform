# PDF处理器模块说明

## 目录结构

```
processors/
├── __init__.py                         # 模块导出
├── step1_text_extractor.py             # 步骤1: 文本提取
├── step2_page_renderer.py              # 步骤2: 页面渲染
├── step3_semantic_segmentor.py         # 步骤3: 语义分割
├── step4_markdown_reconstructor.py     # 步骤4: Markdown重构
├── processor_main.py                   # 主处理器（串联所有步骤）
└── README.md                           # 本文档
```

## 设计理念

采用**模块化**和**单一职责**原则，将PDF处理流程分解为4个独立步骤，每个步骤由专门的类负责：

1. **TextExtractor**: 提取PDF文本
2. **PageRenderer**: 渲染PDF页面为图片
3. **SemanticSegmentor**: 语义分割识别视觉元素
4. **MarkdownReconstructor**: 重构Markdown文档

主处理器 **PDFProcessor** 负责串联这4个步骤，完成完整的PDF到Markdown转换。

## 各模块详解

### 1. TextExtractor (文本提取器)

**文件**: `step1_text_extractor.py`

**职责**:
- 使用PyMuPDF提取PDF页面文本
- 清理文本格式（移除多余空行）
- 保存为markdown文件

**核心方法**:
```python
# 提取页面文本
text = extractor.extract_page_text(pdf_path, page_number)

# 保存为markdown
path = extractor.save_text_to_markdown(text, output_path, page_number)

# 一步完成
text, path = extractor.extract_and_save(pdf_path, page_number, output_dir)
```

**输出**:
- `page_N.md`: 原始提取的文本

---

### 2. PageRenderer (页面渲染器)

**文件**: `step2_page_renderer.py`

**职责**:
- 将PDF页面渲染为高质量图片（默认300 DPI）
- 支持自定义DPI
- 保存为PNG格式

**核心方法**:
```python
# 渲染页面为图像
image = renderer.render_page_to_image(pdf_path, page_number)

# 保存图像
path = renderer.save_image(image, output_path)

# 一步完成
image, path = renderer.render_and_save(pdf_path, page_number, output_dir)
```

**输出**:
- `full_page.png`: 完整页面截图

---

### 3. SemanticSegmentor (语义分割器)

**文件**: `step3_semantic_segmentor.py`

**职责**:
- 使用Qwen3-VL-Plus识别页面中的视觉元素
- 完全模仿 `qwen3vl_segmentation.py` 的提示词
- 提取并保存分割区域

**核心方法**:
```python
# 分析图像识别区域
regions = segmentor.analyze_image_regions(image)

# 提取并保存所有区域
regions, paths = segmentor.segment_and_save(image, output_dir)
```

**识别的5类视觉元素**:
1. `diagram_area` - 示意图、架构图、流程图
2. `chart_area` - 数据图表
3. `image_text_area` - 图文混合
4. `table_area` - 结构化表格
5. `formula_area` - 数学公式

**输出**:
- `image_1.png`, `image_2.png`, ... - 分割区域图片

---

### 4. MarkdownReconstructor (Markdown重构器)

**文件**: `step4_markdown_reconstructor.py`

**职责**:
- 使用Qwen3-VL理解图文排版关系
- 将分割图片插入到文本正确位置
- 生成重构后的markdown

**核心方法**:
```python
# 重构markdown
reconstructed_md = reconstructor.reconstruct_markdown(
    page_text,
    full_page_image,
    region_images,
    page_number
)

# 保存markdown
path = reconstructor.save_markdown(markdown_content, output_path)

# 一步完成
md, path = reconstructor.reconstruct_and_save(
    page_text,
    full_page_image,
    region_images,
    page_number,
    output_dir
)
```

**特点**:
- 所有图片转base64（避免本地URL访问问题）
- 明确说明图片路径对应关系
- 使用相对路径引用图片

**输出**:
- `page_N_final.md`: 重构后的markdown

---

### 5. PDFProcessor (主处理器)

**文件**: `processor_main.py`

**职责**:
- 串联所有处理步骤
- 管理任务进度
- 合并所有页面markdown

**完整流程**:

```python
# 初始化处理器
processor = PDFProcessor()

# 处理整个PDF文档
result = processor.process_pdf_document(
    pdf_path,
    task_id,
    task_dir
)
```

**单页处理流程**:

```python
def process_single_page(pdf_path, page_number, task_dir):
    # 步骤1: 提取文本
    text, _ = text_extractor.extract_and_save(...)

    # 步骤2: 生成完整截图
    full_image, _ = page_renderer.render_and_save(...)

    # 步骤3: 语义分割
    regions, paths = segmentor.segment_and_save(...)

    # 步骤4: Markdown重构
    reconstructed_md, _ = reconstructor.reconstruct_and_save(...)

    return page_result
```

**进度管理**:
- 实时更新 `task.json`
- 记录每页处理状态
- 支持错误恢复

**最终合并**:
- 将所有 `page_N_final.md` 合并
- 生成 `{task_id}_result.md`
- 添加页面分隔符

## 使用示例

### 基本使用

```python
from webapps.toolkit.services.pdf_extractor.processors import PDFProcessor

# 初始化处理器
processor = PDFProcessor()

# 处理PDF
result = processor.process_pdf_document(
    pdf_path="/path/to/document.pdf",
    task_id="550e8400-e29b-41d4-a716-446655440000",
    task_dir=Path("/path/to/output")
)

print(f"处理完成: {result['total_pages']} 页")
print(f"最终文档: {result['final_markdown']}")
```

### 自定义配置

```python
# 使用自定义DPI和模型
processor = PDFProcessor(
    api_key="your-api-key",
    base_url="https://api.example.com/v1",
    model="qwen-vl-plus",
    dpi=300
)
```

### 单独使用某个步骤

```python
from webapps.toolkit.services.pdf_extractor.processors import (
    TextExtractor,
    PageRenderer,
    SemanticSegmentor,
    MarkdownReconstructor
)

# 仅提取文本
extractor = TextExtractor()
text, path = extractor.extract_and_save(pdf_path, 1, output_dir)

# 仅渲染图片
renderer = PageRenderer(dpi=300)
image, path = renderer.render_and_save(pdf_path, 1, output_dir)

# 仅语义分割
segmentor = SemanticSegmentor(api_key, base_url)
regions, paths = segmentor.segment_and_save(image, output_dir)

# 仅重构markdown
reconstructor = MarkdownReconstructor(api_key, base_url)
md, path = reconstructor.reconstruct_and_save(
    text, full_image, region_images, 1, output_dir
)
```

## 环境变量配置

```bash
# 必需
DASHSCOPE_API_KEY=your-api-key

# 可选
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

## 输出目录结构

```
{task_id}/
├── {task_id}.pdf
├── task.json
├── {task_id}_result.md
│
├── page_1/
│   ├── page_1.md
│   ├── page_1_final.md
│   ├── full_page.png
│   ├── image_1.png
│   └── image_2.png
│
└── page_2/
    └── ...
```

## 错误处理

每个步骤都有完善的错误处理：

- **文本提取失败**: 返回空字符串，继续处理
- **页面渲染失败**: 抛出异常，停止处理该页
- **语义分割失败**: 返回空区域列表，使用原始文本
- **Markdown重构失败**: 返回原始文本

主处理器会记录所有错误到日志，并在 `task.json` 中标记失败的页面。

## 性能优化建议

1. **批处理**: 一次处理多个页面（注意API限流）
2. **缓存**: 缓存已处理的页面结果
3. **并发**: 使用Celery并发处理多个任务
4. **资源清理**: 及时关闭PDF文档，释放内存

## 测试建议

```python
# 测试单个步骤
def test_text_extraction():
    extractor = TextExtractor()
    text, _ = extractor.extract_and_save("test.pdf", 1, Path("/tmp"))
    assert len(text) > 0

# 测试完整流程
def test_full_processing():
    processor = PDFProcessor()
    result = processor.process_pdf_document(
        "test.pdf",
        "test-uuid",
        Path("/tmp/test")
    )
    assert result['status'] == 'success'
```

## 注意事项

1. **API密钥安全**: 不要将API密钥硬编码，使用环境变量
2. **文件权限**: 确保输出目录有写权限
3. **磁盘空间**: 处理大PDF时注意磁盘空间
4. **API限流**: 注意DashScope API调用频率限制
5. **提示词一致性**: 语义分割提示词必须与 `qwen3vl_segmentation.py` 保持一致
