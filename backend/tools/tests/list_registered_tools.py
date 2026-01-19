#!/usr/bin/env python
"""
列出所有已注册的工具
"""
import os
import sys
import django
from pathlib import Path

# 添加backend到Python路径
backend_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(backend_dir))

# 设置Django配置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

# 现在导入工具相关模块
from tools.core.registry import ToolRegistry
import tools.libs  # 这会自动加载所有工具

def main():
    """列出所有已注册的工具"""
    registry = ToolRegistry()
    
    print("=" * 80)
    print("所有已注册的工具")
    print("=" * 80)
    
    # 按分类列出工具（基于目录结构）
    tools_by_dir = {
        'data_analysis': [],
        'general': [],
        'generator': [],
        'retrieval': []
    }
    
    for name in registry.list_tools():
        tool_data = registry._tools[name]
        module_path = tool_data['class'].__module__
        
        # 从模块路径推断分类
        if 'data_analysis' in module_path:
            category = 'data_analysis'
        elif 'general' in module_path:
            category = 'general'
        elif 'generator' in module_path:
            category = 'generator'
        elif 'retrieval' in module_path:
            category = 'retrieval'
        else:
            category = 'unknown'
        
        if category in tools_by_dir:
            tools_by_dir[category].append({
                'name': name,
                'description': tool_data['description'],
                'tool_type': tool_data.get('tool_type')
            })
    
    for category, tools in tools_by_dir.items():
        if tools:
            print(f"\n## {category.upper()} 类别的工具:")
            print("-" * 40)
            
            for tool in tools:
                print(f"\n### {tool['name']}")
                print(f"类型: {tool.get('tool_type', '未指定')}")
                print(f"描述: {tool['description']}")
    
    # 按类型列出工具
    print("\n" + "=" * 80)
    print("按工具类型分组")
    print("=" * 80)
    
    typed_tools = registry.list_tools_by_type()
    
    for tool_type, tools in typed_tools.items():
        print(f"\n## {tool_type.upper()} 类型:")
        print("-" * 40)
        
        for tool in tools:
            print(f"  - {tool['name']} ({tool.get('category', 'unknown')})")
    
    # 列出所有工具的简单列表
    print("\n" + "=" * 80)
    print("工具注册名称列表（用于调用）")
    print("=" * 80)
    
    all_tools = registry.list_tools()
    for name in sorted(all_tools):
        print(f"  - {name}")
    
    print(f"\n总计: {len(all_tools)} 个工具已注册")

if __name__ == "__main__":
    main()