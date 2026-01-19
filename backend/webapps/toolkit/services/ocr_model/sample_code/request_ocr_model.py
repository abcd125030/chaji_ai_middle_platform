import requests
import re

API_URL = "http://172.22.217.66:9123"

# 健康检查
print("=" * 60)
print("健康检查")
print("=" * 60)
response = requests.get(f"{API_URL}/health")
print(response.json())

# OCR 测试 - Convert to Markdown 模式
print("\n" + "=" * 60)
print("OCR 测试 - Convert to Markdown 模式")
print("=" * 60)

files = {"image": open("/mnt/models/test-2.jpeg", "rb")}
data = {
    "mode": "convert_to_markdown",
    "max_tokens": 8192,
    "temperature": 0.0
}

response = requests.post(f"{API_URL}/ocr", files=files, data=data)

if response.status_code == 200:
    result_data = response.json()
    raw_result = result_data["result"]
    
    print(f"\n文件名: {result_data['filename']}")
    print(f"图片尺寸: {result_data['image_size']}")
    print(f"模式: {result_data['mode']}")
    
    # 解析并替换图片标记
    # 原始格式: <|ref|>image<|/ref|><|det|>[[x1, y1, x2, y2]]<|/det|>
    # 替换为: [[[!image]]]
    
    def parse_and_replace_images(text):
        """解析 DeepSeek-OCR 的标记格式，将图片标记替换为 [[[!image]]]"""
        
        # 匹配图片标记: <|ref|>image<|/ref|><|det|>[[...]]<|/det|>
        image_pattern = r'<\|ref\|>image<\|/ref\|><\|det\|>\[\[(\d+,\s*\d+,\s*\d+,\s*\d+)\]\]<\|/det\|>'
        
        # 提取所有图片位置信息
        images = re.findall(image_pattern, text)
        print(f"\n检测到 {len(images)} 个图片")
        for i, coords in enumerate(images, 1):
            print(f"  图片 {i} 坐标: [{coords}]")
        
        # 替换为 [[[!image]]]
        text = re.sub(image_pattern, '[[[!image]]]', text)
        
        # 清理其他标记
        # 移除 <|ref|>...<|/ref|> 和 <|det|>...<|/det|>
        text = re.sub(r'<\|ref\|>.*?<\|/ref\|>', '', text)
        text = re.sub(r'<\|det\|>\[\[.*?\]\]<\|/det\|>', '', text)
        
        # 清理多余的空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text
    
    # 处理结果
    cleaned_result = parse_and_replace_images(raw_result)
    
    print("\n" + "=" * 60)
    print("清理后的结果（图片标记为 [[[!image]]]）")
    print("=" * 60)
    print(cleaned_result)
    
    # 保存原始结果
    with open("./ocr_raw.txt", "w") as f:
        f.write(raw_result)
    print("\n原始结果已保存到: ./ocr_raw.txt")
    
    # 保存清理后的结果
    with open("./ocr_cleaned.txt", "w") as f:
        f.write(cleaned_result)
    print("清理后结果已保存到: ./ocr_cleaned.txt")
    
else:
    print(f"错误: {response.status_code}")
    print(response.json())