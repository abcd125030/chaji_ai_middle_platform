# Step4 Markdown重构器优化说明

## 优化内容

### 1. 返回格式优化：从完整Markdown到JSON指令

**原方案**：VL模型返回完整重构后的Markdown文本
- 问题：生成完整文档慢，耗时长
- 问题：难以精确控制插入位置

**新方案**：VL模型只返回JSON格式的插入指令
```json
[
  {
    "image_index": 1,
    "image_type": "table",
    "description": "性能对比表格",
    "anchor_text": "Table 1. Performance comparison",
    "operation": "replace",
    "reason": "表格内容需要用图片替换文本"
  }
]
```

**优势**：
- ✅ VL模型只需分析语义关系，返回简洁指令
- ✅ 文本重构在本地执行，速度更快
- ✅ 更易调试和优化插入逻辑
- ✅ 支持3种操作：replace（替换）、insert_before（前插）、insert_after（后插）

### 2. 完整页面图像缩放优化

**问题**：原始PDF页面图像（300 DPI）尺寸过大，影响API请求速度

**解决方案**：
- 在发送给VL模型前，将完整页面图像等比例缩放到最大边不超过1000px
- 使用高质量LANCZOS插值算法保持图像清晰度
- 缩放后的图像保存为 `full_page_resized.png`，便于调试查看

**缩放示例**：
```
原尺寸 2400x3000 -> 缩放后 800x1000 (缩放比例: 0.333)
原尺寸 1200x900  -> 缩放后 1000x750 (缩放比例: 0.833)
原尺寸 800x600   -> 保持原尺寸（无需缩放）
```

**注意**：
- 仅缩放发送给VL的完整页面图像
- 分割图片保持原始尺寸（精度优先）
- 缩放不影响最终输出的图片文件

## 代码位置

- 主文件：`step4_markdown_reconstructor.py`
- 关键方法：
  - `_resize_image_for_vl()`: 图像缩放
  - `_save_resized_image()`: 保存缩放图像
  - `_get_insertion_instructions()`: 获取JSON指令
  - `_apply_insertions()`: 应用插入指令

## 性能提升

- **VL响应时间**：预计减少50-70%（不需要生成完整文档）
- **API请求大小**：完整页面图像base64大小减少约50-70%
- **可控性**：本地文本操作，调试更方便

## 使用方式

无需改变调用方式，`reconstruct_and_save()` 自动处理：
```python
md, path = reconstructor.reconstruct_and_save(
    page_text,
    full_page_image,
    region_images,
    page_number,
    output_dir  # 缩放后的图像会保存在这里
)
```

输出文件：
- `page_N/full_page_resized.png` - 缩放后的完整页面图像
- `page_N/page_N_final.md` - 重构后的Markdown文件
