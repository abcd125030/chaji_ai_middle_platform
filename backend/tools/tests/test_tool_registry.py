#!/usr/bin/env python
"""测试工具注册器中的 self._tools[name] 信息"""

import os
import sys
import django
import json
import pprint

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
# 添加backend目录到sys.path (向上两级目录)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, backend_dir)
django.setup()

# 导入必要的模块
from tools.core.registry import ToolRegistry
import tools.libs  # 触发工具加载

def test_tool_registry():
    """测试并显示工具注册器中的信息"""
    
    print("=" * 80)
    print("工具注册器测试 - 检查 self._tools[name] 的内容")
    print("=" * 80)
    
    # 获取注册器实例
    registry = ToolRegistry()
    
    # 1. 显示原始的 _tools 字典内容
    print("\n1. 原始 _tools 字典内容:")
    print("-" * 40)
    
    if not registry._tools:
        print("警告: _tools 字典为空，没有工具被注册")
        return
    
    for name, info in registry._tools.items():
        print(f"\n工具名称: {name}")
        print(f"  结构: {type(info)}")
        print(f"  包含的键: {list(info.keys())}")
        
        # 显示每个字段的详细信息
        for key, value in info.items():
            if key == 'class':
                print(f"  - {key}: {value.__module__}.{value.__name__}")
            elif key == 'description':
                print(f"  - {key}: {value[:100]}..." if len(value) > 100 else f"  - {key}: {value}")
            else:
                print(f"  - {key}: {value}")
    
    # 2. 统计信息
    print("\n" + "=" * 80)
    print("2. 统计信息:")
    print("-" * 40)
    print(f"已注册工具总数: {len(registry._tools)}")
    
    # 按分类统计
    category_stats = {}
    for name, info in registry._tools.items():
        category = info.get('category', 'unknown')
        category_stats[category] = category_stats.get(category, 0) + 1
    
    print("\n按分类统计:")
    for category, count in category_stats.items():
        print(f"  - {category}: {count} 个工具")
    
    # 按类型统计
    type_stats = {}
    for name, info in registry._tools.items():
        tool_type = info.get('tool_type', 'untyped')
        type_stats[tool_type] = type_stats.get(tool_type, 0) + 1
    
    print("\n按类型统计:")
    for tool_type, count in type_stats.items():
        print(f"  - {tool_type}: {count} 个工具")
    
    # 3. 测试获取特定工具
    print("\n" + "=" * 80)
    print("3. 测试获取特定工具的信息:")
    print("-" * 40)
    
    test_tools = ["TodoGenerator", "Calculator", "GoogleSearch"]
    for tool_name in test_tools:
        if tool_name in registry._tools:
            print(f"\n测试工具: {tool_name}")
            tool_info = registry._tools[tool_name]
            print(f"  类: {tool_info['class'].__module__}.{tool_info['class'].__name__}")
            print(f"  描述: {tool_info['description'][:80]}...")
            print(f"  分类: {tool_info.get('category', 'unknown')}")
            print(f"  类型: {tool_info.get('tool_type', 'untyped')}")
            
            # 测试实例化
            try:
                tool_instance = tool_info['class']()
                print(f"  ✓ 可以成功实例化")
                
                # 测试获取输入schema
                if hasattr(tool_instance, 'get_input_schema'):
                    schema = tool_instance.get_input_schema()
                    print(f"  ✓ 输入schema已定义，包含属性: {list(schema.get('properties', {}).keys())}")
            except Exception as e:
                print(f"  ✗ 实例化失败: {e}")
        else:
            print(f"\n✗ 工具 '{tool_name}' 未注册")
    
    # 4. 测试注册器的其他方法
    print("\n" + "=" * 80)
    print("4. 测试注册器的方法:")
    print("-" * 40)
    
    # list_tools_by_category()
    categorized = registry.list_tools_by_category()
    print("\n按分类列出工具 (list_tools_by_category):")
    for category, tools in categorized.items():
        print(f"\n  {category}:")
        for tool in tools[:3]:  # 只显示前3个
            print(f"    - {tool['name']}: {tool['description'][:50]}...")
        if len(tools) > 3:
            print(f"    ... 还有 {len(tools) - 3} 个工具")
    
    # list_tools_by_type()
    typed = registry.list_tools_by_type()
    print("\n按类型列出工具 (list_tools_by_type):")
    for tool_type, tools in typed.items():
        print(f"\n  {tool_type}: {len(tools)} 个工具")
        for tool in tools[:2]:  # 只显示前2个
            print(f"    - {tool['name']}")
    
    # 5. 显示所有已注册工具的完整列表
    print("\n" + "=" * 80)
    print("5. 所有已注册工具列表:")
    print("-" * 40)
    
    all_tools = registry.list_tools()
    for i, tool_name in enumerate(sorted(all_tools), 1):
        tool_info = registry._tools[tool_name]
        print(f"{i:2d}. {tool_name}")
        print(f"    类型: {tool_info.get('tool_type', 'untyped')}")
        print(f"    分类: {tool_info.get('category', 'unknown')}")
        print(f"    模块: {tool_info['class'].__module__}")
    
    print("\n" + "=" * 80)
    print("测试完成!")

if __name__ == "__main__":
    test_tool_registry()