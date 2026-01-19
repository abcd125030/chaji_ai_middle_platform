"""
提示词配置文件示例
请复制此文件为 prompts_config.py 并根据需要修改提示词内容
注意：prompts_config.py 文件不会被提交到版本控制系统
"""

# 图片内容检测提示词
IMAGE_DETECTION_PROMPT = """<purpose>
检测图片内容是否合规。特别注意：动物的交配、生殖、繁殖行为属于不合规内容。需要检测是否存在暴力、色情内容，以及图片内容的主体是否仅为动物且不包含人类。
</purpose>

<options for false reason>
- A: 图片包含暴力内容
- B: 图片包含色情内容（特别包括但不限于：动物交配、动物生殖器官展示、动物繁殖行为、动物求偶行为等）
- C: 图片主体不是动物
- D: 图片包含人类
- E: 图片质量过低（分辨率或清晰度不足）
- F: 图片包含多个主体
</options>

<output rules>
output content must exactly be json WITHOUT ``` marks: 
{
	'object_is_only_animal': boolean,
	'reason_for_false': option-value
}
</output rules>"""

# 图片一致性检测提示词
IMAGE_CONSISTENCY_PROMPT = """<purpose>
对比两张图片，检测生成图片与原图的一致性。主要检查：
1. 主体是否为同一只宠物（品种、特征、姿态等）
2. 生成质量是否达标（清晰度、完整性）
3. 是否存在明显的生成缺陷（畸形、错位、比例失调等）
</purpose>

<evaluation_criteria>
- 主体一致性（50分）：是否为同一只宠物，品种、毛色、体型特征是否保持一致
- 姿态相似性（20分）：动作和姿态是否基本保持一致
- 生成质量（20分）：图片清晰度、完整性、无明显噪点或模糊
- 无缺陷（10分）：无畸形、错位、比例失调等明显缺陷
</evaluation_criteria>

<inconsistent_reasons>
- A: 主体不是同一只宠物（品种或特征完全不同）
- B: 生成质量过低（模糊、噪点过多、无法识别）
- C: 存在严重畸形或错位
- D: 主体姿态差异过大
- E: 生成不完整或有明显缺失部分
- F: 其他严重问题
</inconsistent_reasons>

<output_rules>
Output must be valid JSON without ``` marks:
{
    "is_consistent": boolean,
    "inconsistent_reason": option-value or null,
    "score": float (0-100)
}

判定标准：
- score >= 70: is_consistent = true
- score < 70: is_consistent = false，需要提供inconsistent_reason
</output_rules>"""

# 默认测试提示词（用于aiCallback.py）
DEFAULT_TEST_PROMPT = "测试提示词"