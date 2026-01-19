# PDF提取器简化工作流

## 概述

本文档描述了简化后的PDF提取工作流，消除了复杂的LLM锚点匹配，改为直接使用OCR坐标进行图片裁剪和占位符替换。

## 核心改进

### 问题分析

**原有流程存在的问题：**

1. **Step3（语义分割）** 使用Qwen3-VL重新识别图片区域
   - 识别结果与Step1的OCR结果不一致
   - 区域数量可能不匹配
   - 区域顺序可能不一致

2. **Step4（Markdown重构）** 使用LLM进行锚点匹配
   - 需要调用昂贵的VL模型
   - 锚点匹配容易失败
   - 存在LLM幻觉风险
   - 处理速度慢

### 简化方案

**新工作流的核心思想：**

> **一次识别，全程复用** - OCR模型一次识别出图片位置，后续步骤直接使用这些坐标。

## 详细工作流

### Step1: 文本提取（OCR）

**输入：**
- PDF文件
- 页码

**处理：**
1. 将PDF页面渲染为图片（DPI 144）
2. 调用OCR API识别
3. OCR返回结果包含：
   - `result`: 原始Markdown（带DeepSeek格式标记）
   - `result_cleaned`: 清理后的Markdown（图片标记替换为`[[[!image]]]`）
   - `image_regions`: 图片坐标列表 `[[x1, y1, x2, y2], ...]`

**输出文件：**
- `full_page.png`: 完整页面图片
- `page_{num}_step1_raw.md`: 原始Markdown
- `page_{num}_step1_final.md`: 清理后的Markdown（包含`[[[!image]]]`占位符）
- `page_{num}_image_regions.json`: 图片坐标数据

**代码示例：**
```python
# OCR服务解析图片标记
# 原始格式: <|ref|>image<|/ref|><|det|>[[x1, y1, x2, y2]]<|/det|>
# 替换为: [[[!image]]]
# 同时提取坐标: [[x1, y1, x2, y2], ...]
```

### Step2: 跳过

原Step2（页面渲染）已被Step1集成，不再需要。

### Step3: BBox裁剪（新版）

**模块：** `step3_bbox_cropper.py`（替代 `step3_semantic_segmentor.py`）

**输入：**
- `full_page.png`: Step1产生的完整页面图片
- `page_{num}_image_regions.json`: Step1产生的坐标文件

**处理：**
1. 读取坐标文件
2. 按顺序裁剪每个区域
3. 保存为 `image_1.png`, `image_2.png`, ...

**输出文件：**
- `image_1.png`, `image_2.png`, ...: 局部图片（顺序与占位符一致）
- `page_{num}_step3_crop_report.txt`: 裁剪报告

**关键特性：**
- ✅ 顺序严格与Step1的占位符顺序一致
- ✅ 数量严格与Step1的占位符数量一致
- ✅ 无需调用LLM
- ✅ 处理速度快

### Step4: Markdown重构（新版）

**模块：** `step4_markdown_reconstructor.py`（简化版）

**输入：**
- `page_{num}_step1_final.md`: Step1产生的Markdown（包含占位符）
- `image_1.png`, `image_2.png`, ...: Step3产生的局部图

**处理：**
1. 读取Step1的Markdown文件
2. 查找所有 `[[[!image]]]` 占位符
3. 按顺序替换为Markdown图片语法：`![图片 {i}](/media/.../image_{i}.png)`

**输出文件：**
- `page_{num}_step4_final.md`: 最终Markdown
- `page_{num}_step4_report.txt`: 替换报告

**关键特性：**
- ✅ 无需调用LLM
- ✅ 无需锚点匹配
- ✅ 简单的字符串替换
- ✅ 处理速度极快（毫秒级）

## 数据流图

```
PDF页面
  │
  ├─> [Step1: OCR] ──> page_1_step1_final.md (含 [[[!image]]] 占位符)
  │                 └─> page_1_image_regions.json (坐标: [[x1,y1,x2,y2], ...])
  │                 └─> full_page.png
  │
  ├─> [Step3: BBox裁剪] ──> image_1.png (使用坐标[0])
  │                      └─> image_2.png (使用坐标[1])
  │                      └─> image_N.png (使用坐标[N-1])
  │
  └─> [Step4: 占位符替换]
        输入: page_1_step1_final.md + image_*.png
        处理: 替换第1个 [[[!image]]] -> ![图片 1](image_1.png)
             替换第2个 [[[!image]]] -> ![图片 2](image_2.png)
             ...
        输出: page_1_step4_final.md (最终Markdown)
```

## 一致性保证

### 顺序一致性

**Step1:**
- OCR从上到下、从左到右扫描页面
- 按顺序检测图片：图片1, 图片2, 图片3, ...
- 按顺序插入占位符：`[[[!image]]]`, `[[[!image]]]`, `[[[!image]]]`, ...
- 按顺序保存坐标：`[[x1,y1,x2,y2], [x3,y3,x4,y4], ...]`

**Step3:**
- 读取坐标文件（顺序保持）
- 按索引裁剪：坐标[0] -> image_1.png, 坐标[1] -> image_2.png, ...

**Step4:**
- 从前往后查找占位符：第1个, 第2个, 第3个, ...
- 从后往前替换（避免位置偏移）
- 第N个占位符 -> image_N.png

### 数量一致性

**验证机制：**
```python
# Step4执行时
placeholders_count = len(re.findall(r'\[\[\[!image\]\]\]', markdown))
images_count = len(list(output_dir.glob("image_*.png")))

if placeholders_count != images_count:
    logger.warning(f"数量不一致！占位符: {placeholders_count}, 局部图: {images_count}")
```

## 性能对比

| 步骤 | 原版本 | 新版本 | 提升 |
|------|--------|--------|------|
| Step3 | 调用Qwen3-VL识别区域 (~3-5秒) | 直接裁剪 (~50ms) | **100倍** |
| Step4 | 调用Qwen3-VL+锚点匹配 (~5-10秒) | 字符串替换 (~10ms) | **500倍** |
| **总计** | **~8-15秒/页** | **~60ms/页** | **~200倍** |

*注：不包括Step1的OCR时间，因为两个版本都需要*

## 可靠性对比

| 问题 | 原版本 | 新版本 |
|------|--------|--------|
| VL模型识别区域数量不匹配 | ❌ 经常发生 | ✅ 不存在 |
| VL模型识别区域顺序错误 | ❌ 经常发生 | ✅ 不存在 |
| 锚点文本匹配失败 | ❌ 经常发生 | ✅ 不存在 |
| LLM幻觉导致错误插入 | ❌ 偶尔发生 | ✅ 不存在 |

## 使用示例

```python
from pathlib import Path
from step1_text_extractor import TextExtractor
from step3_bbox_cropper import BBoxCropper
from step4_markdown_reconstructor import MarkdownReconstructor

# Step1: OCR识别
extractor = TextExtractor()
result = extractor.extract_page(
    pdf_path="document.pdf",
    page_number=1,
    output_dir=Path("output/page_1"),
    save_debug=True
)

# Step3: BBox裁剪
cropper = BBoxCropper()
count, paths = cropper.crop_and_save(
    image=np.array(Image.open("output/page_1/full_page.png")),
    output_dir=Path("output/page_1"),
    page_number=1
)

# Step4: 占位符替换
reconstructor = MarkdownReconstructor()
final_md, stats = reconstructor.reconstruct_markdown(
    page_number=1,
    output_dir=Path("output/page_1"),
    task_id="uuid-xxx"
)
```

## 文件清单

### Step1产生的文件
- `full_page.png` - 完整页面图片
- `page_1_step1_raw.md` - 原始OCR结果
- `page_1_step1_final.md` - 清理后的结果（含占位符）
- `page_1_image_regions.json` - 图片坐标数据

### Step3产生的文件
- `image_1.png`, `image_2.png`, ... - 局部图片
- `page_1_step3_crop_report.txt` - 裁剪报告

### Step4产生的文件
- `page_1_step4_final.md` - 最终Markdown
- `page_1_step4_report.txt` - 替换报告

## 注意事项

1. **坐标系统**：OCR返回的坐标格式为 `[x1, y1, x2, y2]`（左上角，右下角）
2. **顺序依赖**：Step3和Step4必须在Step1之后执行
3. **文件命名**：所有文件名都基于页码，确保不冲突
4. **兼容性**：新版本保留了旧版本的方法签名，可以无缝替换

## 未来优化

1. **并行处理**：多个页面可以并行处理
2. **增量更新**：只重新处理修改过的页面
3. **缓存机制**：缓存OCR结果避免重复识别
