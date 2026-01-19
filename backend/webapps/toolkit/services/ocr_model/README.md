# OCR Model Service - 使用文档

OCR模型服务API中转层，封装对私有化部署的DeepSeek-OCR模型的调用。

## 功能特性

- ✅ 支持批量多张图片处理
- ✅ 使用base64传输图片，避免文件传输问题
- ✅ 自动清理OCR结果中的特殊标记
- ✅ 支持从字节数据直接识别
- ✅ 完整的错误处理和日志记录

## 快速开始

### 1. 基本使用

```python
from webapps.toolkit.services import OCRModelService

# 初始化服务
ocr_service = OCRModelService()

# 健康检查
health_status = ocr_service.health_check()
print(health_status)
```

### 2. 识别单张图片（base64）

```python
import base64

# 读取图片并转换为base64
with open('test.jpg', 'rb') as f:
    image_bytes = f.read()
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

# 识别单张图片
result = ocr_service.ocr_image(
    image_base64=image_base64,
    mode='convert_to_markdown',
    max_tokens=8192,
    temperature=0.0
)

if result['success']:
    print(f"识别结果: {result['result_cleaned']}")
    print(f"图片尺寸: {result['image_size']}")
    print(f"检测到的图片标记数: {result['image_count']}")
else:
    print(f"识别失败: {result['error']}")
```

### 3. 批量识别多张图片（base64）

```python
import base64

# 准备多张图片的base64
images_base64 = []
for image_path in ['img1.jpg', 'img2.jpg', 'img3.jpg']:
    with open(image_path, 'rb') as f:
        image_base64 = base64.b64encode(f.read()).decode('utf-8')
        images_base64.append(image_base64)

# 批量识别
result = ocr_service.ocr_images(
    images_base64=images_base64,
    mode='convert_to_markdown'
)

if result['success']:
    print(f"总共: {result['total']}, 成功: {result['success_count']}")

    for i, item in enumerate(result['results'], 1):
        print(f"\n图片 {i}:")
        print(f"  尺寸: {item['image_size']}")
        print(f"  识别结果: {item['result_cleaned'][:100]}...")
else:
    print(f"批量识别失败: {result['error']}")
```

### 4. 从字节数据识别（便捷方法）

```python
# 从文件读取字节数据
with open('test.jpg', 'rb') as f:
    image_bytes = f.read()

# 直接从字节数据识别（自动转换为base64）
result = ocr_service.ocr_image_from_bytes(
    image_bytes=image_bytes,
    mode='convert_to_markdown'
)

if result['success']:
    print(f"识别结果: {result['result_cleaned']}")
```

### 5. 批量从字节数据识别

```python
# 准备多张图片的字节数据
images_bytes = []
for image_path in ['img1.jpg', 'img2.jpg', 'img3.jpg']:
    with open(image_path, 'rb') as f:
        images_bytes.append(f.read())

# 批量识别（自动转换为base64）
result = ocr_service.ocr_images_from_bytes(
    images_bytes=images_bytes,
    mode='convert_to_markdown'
)

if result['success']:
    print(f"成功识别 {result['success_count']}/{result['total']} 张图片")
```

## API参考

### OCRModelService

#### 初始化参数

```python
OCRModelService(
    api_url: Optional[str] = None,  # API地址，默认从配置读取
    timeout: int = 300              # 请求超时时间（秒）
)
```

#### 核心方法

##### `ocr_images(images_base64, mode, max_tokens, temperature)`

批量识别多张图片（核心方法）

**参数：**
- `images_base64` (List[str]): base64编码的图片列表
- `mode` (str): 处理模式，默认 'convert_to_markdown'
  - `convert_to_markdown`: 转换为Markdown格式
  - `free_ocr`: 基础OCR
  - `parse_figure`: 解析图表
  - `locate_object`: 定位对象
- `max_tokens` (int): 最大token数，默认8192
- `temperature` (float): 温度参数，默认0.0

**返回：**
```python
{
    'success': True,
    'results': [
        {
            'result': str,              # 原始识别结果
            'result_cleaned': str,      # 清理后的结果
            'image_size': [width, height],
            'mode': str,
            'image_count': int          # 检测到的图片标记数
        },
        ...
    ],
    'total': int,                       # 总图片数
    'success_count': int,               # 成功数
    'failed_count': int                 # 失败数
}
```

##### `ocr_image(image_base64, mode, max_tokens, temperature)`

识别单张图片（便捷方法）

**参数：**同上，但只接收单个base64字符串

**返回：**
```python
{
    'success': True,
    'result': str,
    'result_cleaned': str,
    'image_size': [width, height],
    'mode': str,
    'image_count': int
}
```

##### `ocr_image_from_bytes(image_bytes, mode, max_tokens, temperature)`

从字节数据识别图片

**参数：**
- `image_bytes` (bytes): 图片的字节数据
- 其他参数同上

##### `ocr_images_from_bytes(images_bytes, mode, max_tokens, temperature)`

批量从字节数据识别图片

**参数：**
- `images_bytes` (List[bytes]): 图片字节数据列表
- 其他参数同上

##### `health_check()`

检查API服务健康状态

**返回：**
```python
{
    'success': True,
    'status': 'ok',
    'data': {...}
}
```

##### `get_api_info()`

获取API服务信息

## 配置说明

配置文件位于：`ocr_model/config.py`

### 环境变量配置

在 `.env` 文件中配置：

```bash
# OCR API地址
OCR_API_URL=http://172.22.217.66:9123

# 请求超时时间（秒）
OCR_API_TIMEOUT=300
```

### 配置类说明

```python
from webapps.toolkit.services.ocr_model.config import OCRModelConfig

# 获取完整配置
config = OCRModelConfig.get_config()

# 验证图片格式
is_valid = OCRModelConfig.validate_image_format('test.jpg')

# 验证OCR模式
is_valid = OCRModelConfig.validate_mode('convert_to_markdown')
```

## 图片标记处理

OCR模型会在识别结果中标记图片位置，格式如下：

**原始标记：**
```
<|ref|>image<|/ref|><|det|>[[x1, y1, x2, y2]]<|/det|>
```

**清理后：**
```
[[[!image]]]
```

服务会自动：
1. 识别所有图片标记
2. 提取图片坐标信息（记录到日志）
3. 替换为统一的 `[[[!image]]]` 标记
4. 清理其他特殊标记
5. 清理多余空行

## 使用场景

### PDF解析

```python
import fitz  # PyMuPDF
from webapps.toolkit.services import OCRModelService

ocr_service = OCRModelService()

# 打开PDF
pdf_document = fitz.open('document.pdf')

# 提取每页为图片并识别
images_bytes = []
for page_num in range(len(pdf_document)):
    page = pdf_document[page_num]
    pix = page.get_pixmap(dpi=200)
    images_bytes.append(pix.tobytes('jpg'))

# 批量识别所有页面
result = ocr_service.ocr_images_from_bytes(
    images_bytes=images_bytes,
    mode='convert_to_markdown'
)

# 合并所有页面的结果
if result['success']:
    full_text = '\n\n'.join([
        r['result_cleaned'] for r in result['results']
    ])
    print(full_text)
```

### Django视图中使用

```python
from django.http import JsonResponse
from webapps.toolkit.services import OCRModelService

def ocr_upload_view(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('image')

        if not uploaded_file:
            return JsonResponse({'error': '未上传图片'}, status=400)

        # 读取上传的图片
        image_bytes = uploaded_file.read()

        # OCR识别
        ocr_service = OCRModelService()
        result = ocr_service.ocr_image_from_bytes(image_bytes)

        return JsonResponse(result)
```

## 错误处理

服务提供完整的错误处理：

```python
result = ocr_service.ocr_image(image_base64)

if not result['success']:
    error_msg = result.get('error', '未知错误')

    if 'timeout' in error_msg.lower():
        print("请求超时，请检查网络或增加timeout参数")
    elif 'connection' in error_msg.lower():
        print("无法连接到OCR API服务")
    else:
        print(f"识别失败: {error_msg}")
```

## 性能优化建议

1. **批量处理优先**：尽量使用 `ocr_images()` 批量处理，而不是循环调用单张识别
2. **适当的超时设置**：根据图片数量调整timeout参数
3. **图片预处理**：适当压缩图片可以加快传输和识别速度
4. **异步处理**：对于大量图片，建议使用Celery等异步任务队列

## 日志记录

服务使用Django日志系统，可以在日志中看到：

- API请求和响应
- 图片处理进度
- 图片标记检测信息
- 错误堆栈信息

日志级别：
- `INFO`: 主要流程信息
- `DEBUG`: 详细的图片标记坐标信息
- `ERROR`: 错误信息和堆栈跟踪

## 常见问题

### Q: 如何处理大批量图片？

A: 建议分批处理，每批不超过10张图片，避免单次请求时间过长。

### Q: 识别结果中的图片标记是什么？

A: 这是OCR模型在文档中检测到的图片区域标记，服务会自动替换为 `[[[!image]]]`。

### Q: 支持哪些图片格式？

A: 支持 JPG、JPEG、PNG、BMP、TIFF、PDF等常见格式。

### Q: 如何调整识别质量？

A: 可以通过调整 `temperature` 参数（0.0-2.0）来控制输出的随机性。通常保持0.0即可获得最稳定的结果。

## 更新日志

### v2.0.0
- ✅ 支持批量base64图片处理
- ✅ 新增从字节数据识别的便捷方法
- ✅ 优化图片标记清理逻辑
- ✅ 完善错误处理和日志记录

### v1.0.0
- ✅ 初始版本
- ✅ 基础OCR识别功能
