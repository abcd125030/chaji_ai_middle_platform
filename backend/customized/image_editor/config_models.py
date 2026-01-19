from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.cache import cache


class ImageEditorConfig(models.Model):
    """图片编辑器全局配置模型"""
    
    name = models.CharField(
        max_length=100, 
        unique=True, 
        default='default',
        verbose_name='配置名称',
        help_text='配置标识符，默认使用default'
    )
    
    # 提示词配置
    default_prompt = models.TextField(
        default="完全参考图片内容, 调整图片风格变为油画刮刀风格，刮刀笔触适中，色彩饱满偏暖，姿态鲜活自然，必须使用纯白色背景#ffffff",
        verbose_name='默认提示词',
        help_text='当用户未提供提示词时使用的默认值'
    )
    
    # Seed配置
    use_random_seed = models.BooleanField(
        default=True,
        verbose_name='使用随机Seed',
        help_text='是否使用随机seed值，如果为False则使用fixed_seed'
    )
    
    fixed_seed = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(2147483647)],
        verbose_name='固定Seed值',
        help_text='当use_random_seed为False时使用的固定seed值'
    )
    
    seed_min = models.IntegerField(
        default=100000000,
        validators=[MinValueValidator(1)],
        verbose_name='随机Seed最小值',
        help_text='生成随机seed的最小值'
    )
    
    seed_max = models.IntegerField(
        default=999999999,
        validators=[MaxValueValidator(2147483647)],
        verbose_name='随机Seed最大值',
        help_text='生成随机seed的最大值'
    )
    
    # 生成参数配置
    guidance_scale = models.FloatField(
        default=10.0,
        validators=[MinValueValidator(0.1), MaxValueValidator(30.0)],
        verbose_name='引导系数',
        help_text='图像生成的引导强度，值越大越接近提示词描述'
    )
    
    generation_model = models.CharField(
        max_length=100,
        default='doubao-seededit-3-0-i2i-250628',
        verbose_name='生成模型',
        help_text='用于图像生成的模型名称'
    )
    
    detection_model = models.CharField(
        max_length=100,
        default='doubao-1.5-vision-pro-250328',
        verbose_name='检测模型',
        help_text='用于宠物检测的模型名称'
    )
    
    detection_prompt = models.TextField(
        default="""你必须分析图片并输出JSON格式的结果。

<purpose>
检测图片内容是否合规。特别注意：动物的交配、生殖、繁殖行为属于不合规内容。需要检测是否存在暴力、色情内容，以及图片内容的主体是否仅为动物（宠物）且不包含人类。
如果图片合规，你必须生成极其详细和精确的宠物描述，用于文生图模型重建。
</purpose>

<options_for_false_reason>
- A: 图片包含暴力内容
- B: 图片包含色情内容（特别包括但不限于：动物交配、动物生殖器官展示、动物繁殖行为、动物求偶行为等）
- C: 图片主体不是动物
- D: 图片包含完整的人类面部或上半身躯干肢体
- E: 图片质量过低（分辨率或清晰度不足）
- F: 图片包含多个主体
</options_for_false_reason>

<pet_description_requirements>
如果图片合规，你必须提供一个极其详细、精确的宠物描述，包含以下所有方面：

1. **品种与体型**：准确的品种名称、体型大小、身材比例
2. **毛发特征**：
   - 毛发长度（短毛/中长毛/长毛）
   - 毛发质地（直毛/卷毛/波浪毛、粗糙/柔软/丝滑）
   - 毛发密度和蓬松程度
3. **颜色与花纹**：
   - 主色调和次要色调的精确描述
   - 特殊花纹或斑点的位置、形状、大小
   - 渐变色或混色区域的描述
4. **面部特征**：
   - 眼睛：颜色、大小、形状、神态
   - 鼻子：颜色、湿润度
   - 嘴巴：是否张开、舌头位置
   - 耳朵：形状、位置、朝向（立耳/垂耳/半立）
5. **姿态与动作**：
   - 身体姿势（站立/坐姿/卧姿/奔跑/跳跃等）
   - 头部朝向和角度
   - 四肢位置和动作
   - 尾巴位置和状态（上翘/下垂/摇摆等）
6. **特殊细节**：
   - 任何独特的标记或特征（如额头的星形斑、脚掌的白袜等）
   - 配饰（项圈、铃铛、衣服等）的颜色、材质、样式
   - 表情和情绪状态（警觉/放松/兴奋/好奇等）

描述要求：
- 使用精确、具体的词汇
- 按照从整体到局部、从主要到次要的顺序
- 包含所有可见的细节特征
- 描述长度：150-250字
</pet_description_requirements>

<output_rules>
你的输出必须是一个有效的JSON对象。不要输出任何其他内容，只输出JSON。
JSON必须包含以下三个字段（缺一不可）：
1. "object_is_only_animal": boolean类型 - 是否仅包含动物（宠物）且合规
2. "reason_for_false": string类型或null - 如果不合规，必须提供原因代码（A-F）；如果合规，必须为null
3. "pet_description": string类型或null - 如果合规，必须提供150-250字的极其详细的宠物描述；如果不合规，必须为null

重要：当object_is_only_animal为true时，pet_description字段必须包含详细的宠物描述，不能为null或空字符串！

示例输出（合规情况，注意pet_description必须有内容）：
{
    "object_is_only_animal": true,
    "reason_for_false": null,
    "pet_description": "一只成年雄性金毛寻回犬，体型中大，身材匀称健壮。拥有中长度的金棕色直毛，毛发浓密蓬松，呈现出温暖的蜂蜜色光泽。面部特征鲜明：深棕色的大眼睛流露出温和友善的神情，黑色湿润的鼻子，粉红色的舌头微微外露。耳朵呈三角形自然下垂，紧贴头部两侧。此刻正以坐姿端正，前腿笔直支撑，后腿自然弯曲，尾巴自然下垂，尾尖的毛发略长呈羽毛状。颈部佩戴一条深蓝色的尼龙项圈，项圈上有银色的金属扣环。整体表情放松愉悦，嘴角微微上扬呈现微笑状。"
}

示例输出（不合规情况）：
{
    "object_is_only_animal": false,
    "reason_for_false": "D",
    "pet_description": null
}
</output_rules>

现在请分析图片，并严格按照上述要求输出JSON。记住：如果图片是合规的宠物图片，你必须在pet_description字段中提供150-300字的详细描述，不能返回null！""",
        verbose_name='宠物检测提示词',
        help_text='用于宠物检测的提示词，必须包含pet_description字段的要求'
    )
    
    style_prompt = models.TextField(
        default="油画刮刀风格，刮刀笔触适中，色彩饱满偏暖，姿态鲜活自然，纯白色背景#ffffff",
        verbose_name='风格化提示词',
        help_text='用于文生图的风格化要求，会与宠物描述结合使用'
    )
    
    t2i_model = models.CharField(
        max_length=100,
        default='doubao-seedream-3-0-t2i-250415',
        verbose_name='文生图模型',
        help_text='用于文本生成图像的模型名称'
    )
    
    t2i_size = models.CharField(
        max_length=50,
        default='1024x1024',
        verbose_name='文生图尺寸',
        help_text='文生图输出尺寸，支持：1024x1024, 1024x768, 768x1024等'
    )
    
    t2i_guidance_scale = models.FloatField(
        default=7.5,
        validators=[MinValueValidator(1.0), MaxValueValidator(20.0)],
        verbose_name='文生图引导系数',
        help_text='文生图的引导强度，值越大越接近文本描述'
    )
    
    # 图像参数配置
    image_size = models.CharField(
        max_length=50,
        default='adaptive',
        verbose_name='图像尺寸',
        help_text='生成图像的尺寸，如1024x1024或adaptive'
    )
    
    add_watermark = models.BooleanField(
        default=False,
        verbose_name='添加水印',
        help_text='是否在生成的图像上添加水印'
    )
    
    response_format = models.CharField(
        max_length=20,
        default='url',
        choices=[('url', 'URL'), ('b64_json', 'Base64')],
        verbose_name='响应格式',
        help_text='API返回的图像格式'
    )
    
    # 超时和重试配置
    api_timeout = models.IntegerField(
        default=60,
        validators=[MinValueValidator(10), MaxValueValidator(300)],
        verbose_name='API超时时间',
        help_text='API调用的超时时间（秒）'
    )
    
    max_retries = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        verbose_name='最大重试次数',
        help_text='API调用失败时的最大重试次数'
    )
    
    # 背景移除配置
    enable_bg_removal = models.BooleanField(
        default=True,
        verbose_name='启用背景移除',
        help_text='是否启用背景移除功能'
    )
    
    bg_removal_max_retries = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        verbose_name='背景移除最大重试次数',
        help_text='背景移除失败时的最大重试次数'
    )
    
    # 其他配置
    is_active = models.BooleanField(
        default=True,
        verbose_name='配置是否激活',
        help_text='只有激活的配置才会被使用'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'image_editor_config'
        verbose_name = '图片编辑器配置'
        verbose_name_plural = '图片编辑器配置'
    
    def save(self, *args, **kwargs):
        """保存配置并清除缓存"""
        # 如果当前配置设为激活，确保其他配置都设为非激活
        if self.is_active:
            ImageEditorConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        
        # 先保存
        super().save(*args, **kwargs)
        
        # 保存后清除配置缓存，让下次请求重新加载
        from .config_manager import ConfigManager
        ConfigManager.clear_cache()
    
    def __str__(self):
        return f"Config: {self.name} ({'Active' if self.is_active else 'Inactive'})"
    
    @classmethod
    def get_active_config(cls):
        """获取当前激活的配置，优先从缓存读取"""
        # 尝试从缓存获取
        config = cache.get('image_editor_config')
        if config:
            return config
        
        # 从数据库获取
        try:
            config = cls.objects.filter(is_active=True, name='default').first()
            if not config:
                # 如果没有默认配置，获取任意激活的配置
                config = cls.objects.filter(is_active=True).first()
            
            if not config:
                # 如果没有任何配置，创建默认配置
                config = cls.objects.create(name='default')
            
            # 缓存配置，5分钟过期
            cache.set('image_editor_config', config, 300)
            return config
        except Exception:
            # 如果数据库访问失败，返回None，让调用方使用默认值
            return None
    
    @classmethod
    def reload_config(cls):
        """强制重新加载配置"""
        cache.delete('image_editor_config')
        return cls.get_active_config()