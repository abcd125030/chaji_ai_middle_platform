"""
配置管理器 - 用于在Celery中管理图片编辑器配置
"""
import logging
import random
from django.core.cache import cache

logger = logging.getLogger(__name__)

# 缓存配置
CACHE_KEY = 'image_editor_active_config'
CACHE_TIMEOUT = 300  # 5分钟，配置更新时也会主动清除


class ConfigManager:
    """配置管理器单例"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
    
    def get_config(self):
        """获取配置，优先从缓存读取"""
        # 尝试从缓存获取
        config_data = cache.get(CACHE_KEY)
        
        if config_data is None:
            # 缓存未命中，从数据库加载
            logger.debug("配置缓存未命中，从数据库加载")
            from .config_models import ImageEditorConfig
            
            try:
                config = ImageEditorConfig.get_active_config()
                if config:
                    # 将配置数据存入缓存（序列化为字典）
                    config_data = {
                        'name': config.name,
                        'default_prompt': config.default_prompt,
                        'style_prompt': config.style_prompt,
                        'detection_prompt': config.detection_prompt,
                        'use_random_seed': config.use_random_seed,
                        'fixed_seed': config.fixed_seed,
                        'seed_min': config.seed_min,
                        'seed_max': config.seed_max,
                        'guidance_scale': config.guidance_scale,
                        'generation_model': config.generation_model,
                        'detection_model': config.detection_model,
                        't2i_model': config.t2i_model,
                        't2i_size': config.t2i_size,
                        't2i_guidance_scale': config.t2i_guidance_scale,
                        'image_size': config.image_size,
                        'add_watermark': config.add_watermark,
                        'response_format': config.response_format,
                        'api_timeout': config.api_timeout,
                        'max_retries': config.max_retries,
                        'enable_bg_removal': config.enable_bg_removal,
                        'bg_removal_max_retries': config.bg_removal_max_retries,
                    }
                    cache.set(CACHE_KEY, config_data, CACHE_TIMEOUT)
                    logger.info(f"配置已缓存: {config.name}")
                else:
                    logger.warning("未找到激活的配置")
                    return None
            except Exception as e:
                logger.error(f"加载配置失败: {e}")
                return None
        else:
            logger.debug(f"使用缓存的配置: {config_data.get('name', 'unknown')}")
        
        return config_data
    
    @classmethod
    def clear_cache(cls):
        """清除配置缓存"""
        cache.delete(CACHE_KEY)
        logger.info("配置缓存已清除")
    
    def reload(self):
        """重新加载配置（清除缓存后重新获取）"""
        self.clear_cache()
        config = self.get_config()
        if config:
            logger.info(f"配置已重新加载: {config.get('name', 'unknown')}")
        else:
            logger.warning("重新加载配置失败")
        return config
    
    def get_default_prompt(self) -> str:
        """获取默认提示词"""
        config = self.get_config()
        if config:
            return config.get('default_prompt', "完全参考图片内容, 调整图片风格变为油画刮刀风格，刮刀笔触适中，色彩饱满偏暖，姿态鲜活自然，必须使用纯白色背景#ffffff")
        return "完全参考图片内容, 调整图片风格变为油画刮刀风格，刮刀笔触适中，色彩饱满偏暖，姿态鲜活自然，必须使用纯白色背景#ffffff"
    
    def get_seed(self) -> int:
        """获取seed值"""
        config = self.get_config()
        if config:
            if not config.get('use_random_seed') and config.get('fixed_seed'):
                return config.get('fixed_seed')
            return random.randint(
                config.get('seed_min', 100000000),
                config.get('seed_max', 999999999)
            )
        # 默认值
        return random.randint(100000000, 999999999)
    
    def get_guidance_scale(self) -> float:
        """获取引导系数"""
        config = self.get_config()
        if config:
            return config.get('guidance_scale', 10.0)
        return 10.0
    
    def get_generation_model(self) -> str:
        """获取生成模型名称"""
        config = self.get_config()
        if config:
            return config.get('generation_model', 'doubao-seededit-3-0-i2i-250628')
        return 'doubao-seededit-3-0-i2i-250628'
    
    def get_detection_model(self) -> str:
        """获取检测模型名称"""
        config = self.get_config()
        if config:
            return config.get('detection_model', 'doubao-1.5-vision-pro-250328')
        return 'doubao-1.5-vision-pro-250328'
    
    def get_detection_prompt(self) -> str:
        """获取宠物检测提示词"""
        config = self.get_config()
        if config:
            return config.get('detection_prompt')
        return None
    
    def get_image_size(self) -> str:
        """获取图像尺寸"""
        config = self.get_config()
        if config:
            return config.get('image_size', 'adaptive')
        return 'adaptive'
    
    def should_add_watermark(self) -> bool:
        """是否添加水印"""
        config = self.get_config()
        if config:
            return config.get('add_watermark', False)
        return False
    
    def get_response_format(self) -> str:
        """获取响应格式"""
        config = self.get_config()
        if config:
            return config.get('response_format', 'url')
        return 'url'
    
    def get_api_timeout(self) -> int:
        """获取API超时时间"""
        config = self.get_config()
        if config:
            return config.get('api_timeout', 60)
        return 60
    
    def get_max_retries(self) -> int:
        """获取最大重试次数"""
        config = self.get_config()
        if config:
            return config.get('max_retries', 3)
        return 3
    
    def is_bg_removal_enabled(self) -> bool:
        """是否启用背景移除"""
        config = self.get_config()
        if config:
            return config.get('enable_bg_removal', True)
        return True
    
    def get_bg_removal_max_retries(self) -> int:
        """获取背景移除最大重试次数"""
        config = self.get_config()
        if config:
            return config.get('bg_removal_max_retries', 3)
        return 3
    
    def get_style_prompt(self) -> str:
        """获取风格化提示词"""
        config = self.get_config()
        if config:
            return config.get('style_prompt', "油画刮刀风格，刮刀笔触适中，色彩饱满偏暖，姿态鲜活自然，纯白色背景#ffffff")
        return "油画刮刀风格，刮刀笔触适中，色彩饱满偏暖，姿态鲜活自然，纯白色背景#ffffff"
    
    def get_t2i_model(self) -> str:
        """获取文生图模型名称"""
        config = self.get_config()
        if config:
            return config.get('t2i_model', 'doubao-seedream-3-0-t2i-250415')
        return 'doubao-seedream-3-0-t2i-250415'
    
    def get_t2i_size(self) -> str:
        """获取文生图尺寸"""
        config = self.get_config()
        if config:
            return config.get('t2i_size', '1024x1024')
        return '1024x1024'
    
    def get_t2i_guidance_scale(self) -> float:
        """获取文生图引导系数"""
        config = self.get_config()
        if config:
            return config.get('t2i_guidance_scale', 7.5)
        return 7.5


# 全局配置管理器实例
config_manager = ConfigManager()