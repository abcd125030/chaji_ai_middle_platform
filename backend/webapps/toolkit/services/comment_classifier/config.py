"""
分类服务配置
"""
import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class ClassifierConfig:
    """分类服务配置类"""
    
    # 配置数据存储
    _config_data: Dict[str, Any] = field(default_factory=dict)
    
    # 配置文件路径
    config_file: Optional[str] = None
    
    # 当前环境
    environment: str = field(default_factory=lambda: os.getenv('ENVIRONMENT', 'development'))
    
    def __post_init__(self):
        """初始化后加载配置"""
        if self.config_file:
            self.load_from_file(self.config_file)
        else:
            # 尝试自动查找配置文件
            self._auto_load_config()
    
    def _auto_load_config(self):
        """自动查找并加载配置文件"""
        # 配置文件搜索顺序
        config_paths = [
            Path('./config.local.yml'),  # 本地配置（优先）
            Path('./config.yml'),  # 默认配置
            Path(__file__).parent / 'config.local.yml',
            Path(__file__).parent / 'config.yml',
        ]
        
        for path in config_paths:
            if path.exists():
                self.load_from_file(str(path))
                break
    
    def load_from_file(self, file_path: str):
        """
        从YAML文件加载配置
        
        Args:
            file_path: YAML配置文件路径
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在: {file_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # 替换环境变量
        config_data = self._replace_env_vars(config_data)
        
        # 合并环境特定配置
        if self.environment and 'environments' in config_data:
            env_config = config_data['environments'].get(self.environment, {})
            config_data = self._merge_configs(config_data, env_config)
        
        self._config_data = config_data
        self.config_file = file_path
    
    def _replace_env_vars(self, obj: Any) -> Any:
        """
        递归替换配置中的环境变量
        ${VAR_NAME} 格式会被替换为环境变量的值
        """
        if isinstance(obj, dict):
            return {k: self._replace_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_env_vars(item) for item in obj]
        elif isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
            var_name = obj[2:-1]
            return os.getenv(var_name, obj)
        return obj
    
    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """
        递归合并配置字典
        
        Args:
            base: 基础配置
            override: 覆盖配置
            
        Returns:
            合并后的配置
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        通过点分路径获取配置值
        
        Args:
            path: 配置路径，如 'ai.model_id' 或 'concurrency.max_concurrent'
            default: 默认值
            
        Returns:
            配置值
        """
        keys = path.split('.')
        value = self._config_data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def set(self, path: str, value: Any):
        """
        设置配置值
        
        Args:
            path: 配置路径
            value: 配置值
        """
        keys = path.split('.')
        config = self._config_data
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    # 便捷属性访问器
    @property
    def use_ai_only(self) -> bool:
        return self.get('base.use_ai_only', False)
    
    @property
    def ai_provider(self) -> str:
        return self.get('ai.provider', 'qwen')
    
    @property
    def ai_model_id(self) -> str:
        return self.get('ai.model_id', 'qwen-plus')
    
    @property
    def ai_endpoint(self) -> Optional[str]:
        return self.get('ai.endpoint')
    
    @property
    def ai_api_key(self) -> Optional[str]:
        return self.get('ai.api_key')
    
    @property
    def ai_params(self) -> Dict[str, Any]:
        return self.get('ai.params', {})
    
    @property
    def ai_custom_headers(self) -> Dict[str, Any]:
        return self.get('ai.custom_headers', {})
    
    @property
    def max_concurrent(self) -> int:
        return self.get('concurrency.max_concurrent', 20)
    
    @property
    def requests_per_second(self) -> int:
        return self.get('concurrency.requests_per_second', 4)
    
    @property
    def batch_size(self) -> int:
        return self.get('concurrency.batch_size', 100)
    
    @property
    def min_confidence_score(self) -> float:
        return self.get('classification.min_confidence_score', 0.1)
    
    @property
    def allow_incomplete_classification(self) -> bool:
        return self.get('classification.allow_incomplete', False)
    
    @property
    def auto_update_rules(self) -> bool:
        return self.get('classification.auto_update_rules', False)
    
    @property
    def output_format(self) -> str:
        return self.get('output.format', 'excel')
    
    @property
    def generate_report(self) -> bool:
        return self.get('output.generate_report', True)
    
    @property
    def include_metadata(self) -> bool:
        return self.get('output.include_metadata', True)
    
    @property
    def enable_llm_logs(self) -> bool:
        return self.get('logging.enable_llm_logs', True)
    
    @property
    def categories_config_path(self) -> str:
        return self.get('base.categories_config_path', 'categories_hierarchy.json')
    
    def get_component_config(self, component_name: str) -> Dict[str, Any]:
        """获取特定组件的配置"""
        return self.get(f'components.{component_name}', {})
    
    def get_llm_config(self) -> Dict[str, Any]:
        """
        获取适用于 core_service.call_llm 的配置
        
        Returns:
            包含 model_id, endpoint, api_key, custom_headers, params 的字典
        """
        return {
            'model_id': self.ai_model_id,
            'endpoint': self.ai_endpoint,
            'api_key': self.ai_api_key,
            'custom_headers': self.ai_custom_headers,
            'params': self.ai_params
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self._config_data.copy()
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ClassifierConfig':
        """从字典创建配置对象"""
        instance = cls()
        instance._config_data = config_dict
        return instance