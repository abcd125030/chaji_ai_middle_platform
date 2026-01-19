"""
评论分类服务主入口
"""
from typing import List, Dict, Any, Optional, Tuple
from .config import ClassifierConfig
from .components.base import BaseComponent
from .components.loader import DataLoaderComponent
from .components.preprocessor import PreprocessorComponent
from .components.classifier import ClassifierComponent
from .components.postprocessor import PostprocessorComponent
from .components.exporter import ExporterComponent


class CommentClassifierService:
    """
    评论分类服务 - 组件式架构实现
    
    组件执行流程:
    DataLoader -> Preprocessor -> Classifier -> Postprocessor -> Exporter
    """
    
    def __init__(self, config: Optional[ClassifierConfig] = None):
        """
        初始化分类服务
        
        Args:
            config: 分类服务配置
        """
        self.config = config or ClassifierConfig()
        self._components: Dict[str, BaseComponent] = {}
        self._initialize_components()
    
    def _initialize_components(self):
        """初始化所有组件"""
        # 数据加载组件
        self._components['loader'] = DataLoaderComponent(self.config)
        
        # 预处理组件
        self._components['preprocessor'] = PreprocessorComponent(self.config)
        
        # 分类组件
        self._components['classifier'] = ClassifierComponent(self.config)
        
        # 后处理组件  
        self._components['postprocessor'] = PostprocessorComponent(self.config)
        
        # 导出组件
        self._components['exporter'] = ExporterComponent(self.config)
    
    def process(self, 
                input_path: str,
                output_path: Optional[str] = None,
                **kwargs) -> Dict[str, Any]:
        """
        执行完整的分类处理流程
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（可选）
            **kwargs: 其他参数
            
        Returns:
            处理结果字典
        """
        # 1. 加载数据
        data = self._components['loader'].execute(input_path=input_path)
        
        # 2. 预处理
        preprocessed_data = self._components['preprocessor'].execute(data=data)
        
        # 3. 分类
        classified_data = self._components['classifier'].execute(data=preprocessed_data)
        
        # 4. 后处理
        processed_data = self._components['postprocessor'].execute(data=classified_data)
        
        # 5. 导出结果
        if output_path:
            export_result = self._components['exporter'].execute(
                data=processed_data,
                output_path=output_path
            )
            return export_result
        
        return processed_data
    
    def get_component(self, name: str) -> Optional[BaseComponent]:
        """获取指定组件"""
        return self._components.get(name)
    
    def register_component(self, name: str, component: BaseComponent):
        """注册自定义组件"""
        if not isinstance(component, BaseComponent):
            raise TypeError(f"Component must be instance of BaseComponent")
        self._components[name] = component