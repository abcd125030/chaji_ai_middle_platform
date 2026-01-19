"""
配置管理服务
============

管理 Pagtive 的配置，包括 LLM 模型配置、提示词模板等。
所有配置从数据库读取，不使用硬编码。
"""

import logging
from typing import Optional, Dict, Any, List
from django.core.cache import cache
from django.db.models import Q

from ..models import PagtiveConfig, PagtivePromptTemplate
from router.models import LLMModel

logger = logging.getLogger(__name__)


class ConfigurationService:
    """配置管理服务类"""
    
    # 缓存键前缀
    CACHE_PREFIX = 'pagtive_config'
    # 缓存时间（秒）
    CACHE_TIMEOUT = 300  # 5分钟
    
    def get_active_config(self) -> Optional[PagtiveConfig]:
        """
        获取当前激活的配置
        
        Returns:
            激活的配置对象，如果没有则返回None
        """
        cache_key = f"{self.CACHE_PREFIX}:active"
        
        # 尝试从缓存获取
        config = cache.get(cache_key)
        if config is not None:
            return config
        
        # 从数据库获取
        try:
            config = PagtiveConfig.objects.filter(is_active=True).first()
            if config:
                # 预加载关联的模板
                config.templates = list(config.prompt_templates.all())
                # 存入缓存
                cache.set(cache_key, config, self.CACHE_TIMEOUT)
            return config
        except Exception as e:
            logger.error(f"获取激活配置失败: {str(e)}")
            return None
    
    def get_llm_config(
        self,
        scenario: str = 'generate',
        config: Optional[PagtiveConfig] = None
    ) -> Dict[str, Any]:
        """
        获取 LLM 配置信息
        
        Args:
            scenario: 场景类型 (generate/edit/outline)
            config: 配置对象（可选，不提供则获取激活配置）
            
        Returns:
            包含 model_id、provider、params 等的配置字典
        """
        if config is None:
            config = self.get_active_config()
        
        # 默认配置
        default_config = {
            'model_id': 'gpt-4',
            'provider': 'openai',
            'params': {
                'temperature': 0.7,
                'max_tokens': 4000
            },
            'enable_stream': False
        }
        
        if not config:
            # 尝试从 LLMModel 获取默认配置
            try:
                # 获取第一个可用的模型作为默认
                llm_model = LLMModel.objects.first()
                if llm_model:
                    default_config['model_id'] = llm_model.model_id
                    # 从 endpoint 获取 vendor 信息
                    if hasattr(llm_model, 'endpoint') and llm_model.endpoint:
                        default_config['provider'] = llm_model.endpoint.get_vendor_identifier() or 'openai'
                    if llm_model.params:
                        default_config['params'].update(llm_model.params)
            except Exception as e:
                logger.error(f"获取默认LLM配置失败: {str(e)}")
            
            return default_config
        
        # 根据场景选择模型
        llm_model = None
        if scenario == 'edit' and config.llm_model_for_edit:
            llm_model = config.llm_model_for_edit
        elif config.llm_model:
            llm_model = config.llm_model
        
        if not llm_model:
            return default_config
        
        # 构建配置
        result = {
            'model_id': llm_model.model_id,
            'model_name': llm_model.name,
            'provider': llm_model.endpoint.get_vendor_identifier() if llm_model.endpoint else 'openai',
            'params': {},
            'enable_stream': config.enable_stream
        }
        
        # 合并参数
        if llm_model.params:
            result['params'].update(llm_model.params)
        
        # 覆盖配置中的参数
        if config.temperature is not None:
            result['params']['temperature'] = config.temperature
        if config.max_tokens:
            result['params']['max_tokens'] = config.max_tokens
        
        # 从 extra_config 中获取其他参数
        if config.extra_config:
            # 提取特定的 LLM 参数
            if 'top_p' in config.extra_config:
                result['params']['top_p'] = config.extra_config['top_p']
            if 'frequency_penalty' in config.extra_config:
                result['params']['frequency_penalty'] = config.extra_config['frequency_penalty']
            if 'presence_penalty' in config.extra_config:
                result['params']['presence_penalty'] = config.extra_config['presence_penalty']
            
            # 添加其他额外配置
            for key, value in config.extra_config.items():
                if key not in ['top_p', 'frequency_penalty', 'presence_penalty']:
                    result['params'][key] = value
        
        return result
    
    def get_prompt_template(
        self,
        config: PagtiveConfig,
        template_type: str
    ) -> Optional[str]:
        """
        获取提示词模板
        
        Args:
            config: 配置对象
            template_type: 模板类型 (system/generate/edit/outline等)
            
        Returns:
            模板内容字符串，如果没有则返回None
        """
        # 先从配置的直接字段获取
        field_mapping = {
            'system': 'system_prompt',
            'generate': 'generate_template',
            'edit': 'edit_template'
        }
        
        if template_type in field_mapping:
            field_name = field_mapping[template_type]
            template_content = getattr(config, field_name, None)
            # 只有当字段不为None且不为空字符串时才使用它
            if template_content and template_content.strip():
                return template_content
        
        # 从关联的模板表获取
        try:
            # 如果已预加载
            if hasattr(config, 'templates'):
                for template in config.templates:
                    if template.template_type == template_type and template.is_active:
                        return template.template_content
            else:
                # 从数据库查询
                template = PagtivePromptTemplate.objects.filter(
                    config=config,
                    template_type=template_type,
                    is_active=True
                ).first()
                if template:
                    return template.template_content
        except Exception as e:
            logger.error(f"获取提示词模板失败: {str(e)}")
        
        return None
    
    def list_configs(
        self,
        include_inactive: bool = False
    ) -> List[PagtiveConfig]:
        """
        列出所有配置
        
        Args:
            include_inactive: 是否包含未激活的配置
            
        Returns:
            配置列表
        """
        query = PagtiveConfig.objects.all()
        if not include_inactive:
            query = query.filter(is_active=True)
        
        return list(query.order_by('-is_active', '-updated_at'))
    
    def activate_config(self, config_id: int) -> bool:
        """
        激活指定配置（会自动停用其他配置）
        
        Args:
            config_id: 配置ID
            
        Returns:
            是否激活成功
        """
        try:
            # 先停用所有配置
            PagtiveConfig.objects.update(is_active=False)
            
            # 激活指定配置
            config = PagtiveConfig.objects.get(id=config_id)
            config.is_active = True
            config.save()
            
            # 清除缓存
            self.clear_cache()
            
            return True
        except PagtiveConfig.DoesNotExist:
            logger.error(f"配置不存在: {config_id}")
            return False
        except Exception as e:
            logger.error(f"激活配置失败: {str(e)}")
            return False
    
    def create_config(
        self,
        name: str,
        description: str = "",
        llm_model_id: Optional[int] = None,
        **kwargs
    ) -> Optional[PagtiveConfig]:
        """
        创建新配置
        
        Args:
            name: 配置名称
            description: 配置描述
            llm_model_id: LLM模型ID
            **kwargs: 其他配置字段
            
        Returns:
            创建的配置对象
        """
        try:
            config_data = {
                'name': name,
                'description': description
            }
            
            # 设置LLM模型
            if llm_model_id:
                try:
                    llm_model = LLMModel.objects.get(id=llm_model_id)
                    config_data['llm_model'] = llm_model
                except LLMModel.DoesNotExist:
                    logger.warning(f"LLM模型不存在: {llm_model_id}")
            
            # 添加其他字段
            allowed_fields = [
                'system_prompt', 'generate_template', 'edit_template',
                'temperature', 'max_tokens', 'top_p',
                'frequency_penalty', 'presence_penalty',
                'enable_stream', 'extra_config'
            ]
            
            for field in allowed_fields:
                if field in kwargs:
                    config_data[field] = kwargs[field]
            
            # 如果要设为激活，先停用其他配置
            if kwargs.get('is_active', False):
                PagtiveConfig.objects.update(is_active=False)
                config_data['is_active'] = True
            
            config = PagtiveConfig.objects.create(**config_data)
            
            # 清除缓存
            if config.is_active:
                self.clear_cache()
            
            return config
            
        except Exception as e:
            logger.error(f"创建配置失败: {str(e)}")
            return None
    
    def update_config(
        self,
        config_id: int,
        **kwargs
    ) -> Optional[PagtiveConfig]:
        """
        更新配置
        
        Args:
            config_id: 配置ID
            **kwargs: 要更新的字段
            
        Returns:
            更新后的配置对象
        """
        try:
            config = PagtiveConfig.objects.get(id=config_id)
            
            # 更新允许的字段
            allowed_fields = [
                'name', 'description', 'system_prompt',
                'generate_template', 'edit_template',
                'temperature', 'max_tokens', 'top_p',
                'frequency_penalty', 'presence_penalty',
                'enable_stream', 'extra_config'
            ]
            
            for field in allowed_fields:
                if field in kwargs:
                    setattr(config, field, kwargs[field])
            
            # 更新LLM模型
            if 'llm_model_id' in kwargs:
                if kwargs['llm_model_id']:
                    try:
                        llm_model = LLMModel.objects.get(
                            id=kwargs['llm_model_id']
                        )
                        config.llm_model = llm_model
                    except LLMModel.DoesNotExist:
                        logger.warning(f"LLM模型不存在: {kwargs['llm_model_id']}")
                else:
                    config.llm_model = None
            
            # 处理激活状态
            if kwargs.get('is_active', False) and not config.is_active:
                # 停用其他配置
                PagtiveConfig.objects.exclude(id=config_id).update(is_active=False)
                config.is_active = True
            
            config.save()
            
            # 清除缓存
            if config.is_active:
                self.clear_cache()
            
            return config
            
        except PagtiveConfig.DoesNotExist:
            logger.error(f"配置不存在: {config_id}")
            return None
        except Exception as e:
            logger.error(f"更新配置失败: {str(e)}")
            return None
    
    def delete_config(self, config_id: int) -> bool:
        """
        删除配置
        
        Args:
            config_id: 配置ID
            
        Returns:
            是否删除成功
        """
        try:
            config = PagtiveConfig.objects.get(id=config_id)
            
            # 不允许删除激活的配置
            if config.is_active:
                logger.warning("不能删除激活的配置")
                return False
            
            config.delete()
            return True
            
        except PagtiveConfig.DoesNotExist:
            logger.error(f"配置不存在: {config_id}")
            return False
        except Exception as e:
            logger.error(f"删除配置失败: {str(e)}")
            return False
    
    def create_prompt_template(
        self,
        config: PagtiveConfig,
        template_type: str,
        template_content: str,
        description: str = "",
        variables: Optional[List[str]] = None,
        is_active: bool = True
    ) -> Optional[PagtivePromptTemplate]:
        """
        创建提示词模板
        
        Args:
            config: 所属配置
            template_type: 模板类型
            template_content: 模板内容
            description: 模板描述
            variables: 使用的变量列表
            is_active: 是否激活
            
        Returns:
            创建的模板对象
        """
        try:
            # 如果要激活，先停用同类型的其他模板
            if is_active:
                PagtivePromptTemplate.objects.filter(
                    config=config,
                    template_type=template_type
                ).update(is_active=False)
            
            template = PagtivePromptTemplate.objects.create(
                config=config,
                template_type=template_type,
                template_content=template_content,
                description=description,
                variables=variables or [],
                is_active=is_active
            )
            
            # 清除缓存
            if config.is_active:
                self.clear_cache()
            
            return template
            
        except Exception as e:
            logger.error(f"创建提示词模板失败: {str(e)}")
            return None
    
    def clear_cache(self):
        """清除所有配置缓存"""
        cache_pattern = f"{self.CACHE_PREFIX}:*"
        cache.delete_pattern(cache_pattern)
        logger.info("已清除Pagtive配置缓存")