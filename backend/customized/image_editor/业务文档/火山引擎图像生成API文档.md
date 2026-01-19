# 火山引擎文生图API技术文档

## API概述

本文档描述文生图服务接口，该接口支持根据文本描述生成图像。

本次请求使用模型的 Model ID 或推理接入点 (Endpoint ID)，目前仅支持 doubao-seedream-3-0-t2i-250415。

## 请求参数

### 请求格式

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| prompt | String | 是 | 用于生成图像的文本描述，最多支持... |
| model | String | 是 | 本次请求使用模型的 Model ID 或推理接入点 (Endpoint ID)，目前仅支持 doubao-seedream-3-0-t2i-250415 |
| response_format | String | 否 | 返回格式，可选值：`url`、`b64_json` |
| size | String | 否 | 生成图像的分辨率，支持以下尺寸：<br>• 1024x1024 (默认)<br>• 1024x768<br>• 768x1024<br>• 1024x576<br>• 576x1024<br>• 768x768<br>• 768x512<br>• 512x768<br>• 768x432<br>• 432x768<br>• 512x512 |
| seed | Integer | 否 | 随机种子，用于固定随机化生成的图像内容。相同种子在相同条件下会生成相同的图像。取值范围0~2147483647，如不指定则使用随机种子 |
| guidance_scale | Float | 否 | 引导尺度，控制生成图像与文本提示的匹配程度。建议值：指导权重，数值越高生成的图片内容与提示词的相关性越强。取值范围1.0~20.0，默认值7.5 |
| watermark | Boolean | 否 | 是否添加水印，默认为true |


## 请求示例

### cURL示例

```bash
curl -X POST 'https://ark.cn-beijing.volces.com/api/v3/images/generations' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -d '{
    "model": "doubao-seedream-3-0-t2i-250415",
    "prompt": "一只可爱的小猫在花园里玩耍",
    "response_format": "url",
    "size": "1024x1024",
    "guidance_scale": 7.5,
    "seed": 123456
  }'
```

## 响应参数

### 响应格式

| 参数名 | 类型 | 描述 |
|--------|------|------|
| model | String | 本次使用的模型名称（如doubao_seedream_3_0_t2i_250415） |
| created | Integer | 生成时间戳（Unix时间戳，例如：1677） |
| data | Array | 生成的图像数据数组 |
| usage | Object | 计费相关信息 |

#### data数组元素

| 参数名 | 类型 | 描述 |
|--------|------|------|
| url | String | 当response_format为"url"时，返回图像的URL地址 |
| b64_json | String | 当response_format为"b64_json"时，返回Base64编码的图像数据 |

### 响应示例

```json
{
  "model": "doubao_seedream_3_0_t2i_250415",
  "created": 1677,
  "data": [
    {
      "url": "https://ark.cn-beijing.volces.com/generated/xxxxx.png"
    }
  ],
  "usage": {
    "total_tokens": 1
  }
}
```

## Python SDK使用示例

```python
from volcenginesdkarkruntime import Ark

# 初始化客户端
client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key="YOUR_API_KEY"
)

# 发送请求
completion = client.images.generate(
    model="doubao-seedream-3-0-t2i-250415",
    prompt="一只可爱的小猫在花园里玩耍",
    size="1024x1024",
    response_format="url",
    guidance_scale=7.5,
    seed=123456
)

# 获取结果
image_url = completion.data[0].url
print(f"生成的图像URL: {image_url}")
```

## 相关参数

### model参数
本次请求使用模型的 Model ID 或推理接入点 (Endpoint ID)，目前仅支持 doubao-seedream-3-0-t2i-250415。

### created参数
生成时间戳（Unix时间戳），例如：1677

### size参数
支持的图像尺寸（像素）：
- 1024x1024 (默认)
- 1024x768
- 768x1024
- 1024x576
- 576x1024
- 768x768
- 768x512
- 512x768
- 768x432
- 432x768
- 512x512

### usage参数
计费相关信息，包含：
- 消耗

### watermark参数
是否在生成的图像中添加水印：
- true: 添加水印（默认）
- false: 不添加水印

## 注意事项

1. 图像生成速度取决于所选尺寸和服务负载
2. 生成的图像URL有效期为24小时，建议及时保存
3. 相同的prompt和seed在相同条件下会生成相同的图像
4. guidance_scale值越高，生成的图像越贴近文本描述，但过高可能导致图像质量下降

---

*本文档基于火山引擎官方API文档整理，版本：2025-08-14*