import os
import importlib
import pkgutil
import logging

logger = logging.getLogger('django')

# 定义所有工具模块的路径
TOOL_MODULES = [
    # Analysis tools
    'analysis.calculator',
    'analysis.table_analyzer', 
    'analysis.pandas_data_calculator',
    
    # General tools
    'general.todo_generator',
    
    # Generator tools
    'generator.report_generator',
    'generator.text_generator',
    'generator.image_generator',
    'generator.translator',
    
    # Retrieval tools
    'retrieval.web_search',
    'retrieval.knowledge_base',

]

def load_tools():
    """
    加载所有工具模块，确保它们被正确注册。
    按照目录结构递归加载所有子模块。
    """
    package_path = os.path.dirname(__file__)
    
    # 递归函数来加载包及其子包中的所有模块
    def load_package_recursively(package_name):
        try:
            # 导入包本身
            package = importlib.import_module(package_name)
            package_path = os.path.dirname(package.__file__)
            
            # 遍历包中的所有模块和子包
            for _, module_name, is_pkg in pkgutil.iter_modules([package_path]):
                if module_name.startswith('_'):
                    continue
                    
                full_module_name = f"{package_name}.{module_name}"
                
                try:
                    if is_pkg:
                        # 如果是子包，递归加载
                        load_package_recursively(full_module_name)
                    else:
                        # 如果是模块，直接导入
                        importlib.import_module(full_module_name)
                        logger.debug(f"Successfully loaded tool module: {full_module_name}")
                except Exception as e:
                    logger.warning(f"Failed to load module {full_module_name}: {e}")
                    
        except Exception as e:
            logger.warning(f"Failed to load package {package_name}: {e}")
    
    # 从当前包开始递归加载
    load_package_recursively(__name__)
    
# 自动加载所有工具
load_tools()