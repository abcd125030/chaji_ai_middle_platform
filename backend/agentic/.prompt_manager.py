# -*- coding: utf-8 -*-
"""
prompt_manager.py - 智能体提示词管理系统
⚠️该文件目前未被使用！

====================================================================================
模块概述
====================================================================================
本模块实现了一个集中式的提示词管理系统，是12-Factor Agents框架中Factor 2（掌控你的提示词）的核心实现。
该系统提供YAML模板管理、Jinja2渲染引擎、文件热更新、模板缓存、版本管理和A/B测试等企业级功能。

====================================================================================
输入输出接口
====================================================================================

输入：
1. 提示词模板文件（YAML格式）：
   - 存储在prompts/templates/目录下，按类型分目录组织
   - 结构：{模板类型}/{段落名}.yaml
   - 支持Jinja2模板语法，可使用变量和过滤器

2. 配置文件（config.yaml）：
   - 系统配置：版本号、缓存设置、热更新间隔等
   - 位置：prompts/config.yaml

3. 渲染上下文（Dict）：
   - 包含模板渲染所需的所有变量
   - 如：task_goal, capability_map, tool_descriptions等

输出：
1. 渲染后的提示词文本（str）：
   - 完整的、可直接用于LLM的提示词
   - 支持系统提示词和用户提示词分离

2. 模板数据结构（Dict）：
   - 原始的YAML模板数据，用于进一步处理

====================================================================================
内部处理流程
====================================================================================

初始化流程：
1. 创建单例实例（线程安全）
2. 加载系统配置文件（config.yaml）
3. 初始化Jinja2环境和自定义过滤器
4. 扫描并加载所有模板文件
5. 建立文件监控机制

模板加载流程：
1. 扫描templates目录结构
2. 按类型-段落层次组织模板
3. 计算文件修改时间和校验和
4. 缓存模板对象到内存

提示词渲染流程：
1. 检查是否需要热更新（基于文件修改时间）
2. 获取指定类型和段落的模板数据
3. 递归渲染模板内容（支持嵌套结构）
4. 应用Jinja2模板引擎进行变量替换
5. 组装最终提示词文本

热更新机制：
1. 定期检查文件修改时间（可配置间隔）
2. 发现变化时重新加载对应模板
3. 更新内存缓存，确保数据一致性

====================================================================================
执行逻辑架构
====================================================================================

核心类：
- PromptManager: 主控制器，实现单例模式
- PromptTemplate: 数据类，存储模板元信息

设计模式：
- 单例模式：确保全局唯一管理器实例
- 工厂模式：动态创建和管理模板对象
- 观察者模式：文件监控和热更新机制

数据流：
YAML文件 → 模板解析 → 内存缓存 → 上下文渲染 → 最终提示词

缓存策略：
- 内存缓存：所有模板常驻内存，提供快速访问
- 懒加载：首次访问时加载，支持按需加载
- 热更新：基于文件修改时间的增量更新

====================================================================================
函数调用关系图
====================================================================================

初始化调用链：
__init__ → _load_config → _init_jinja_env → _load_all_templates
    ↓
_load_template_type → _load_single_template

核心渲染调用链：
render_prompt → _check_hot_reload → get_template_data → _render_template_data
    ↓
_render_list (处理列表) / Template.render (Jinja2渲染)

特殊方法调用链：
build_planner_prompt → render_prompt (多次调用不同section)

管理功能调用链：
update_template → 直接修改内存缓存
reload_templates → templates.clear → _load_all_templates

====================================================================================
外部依赖关系
====================================================================================

Django框架依赖：
- logging.getLogger("django"): 使用Django的日志系统
- 依赖Django项目的logging配置

文件系统依赖：
- prompts/目录结构：存储所有模板文件
- config.yaml：系统配置文件
- templates/{type}/{section}.yaml：按类型组织的模板文件

业务系统集成点：
1. agentic.planner模块：
   - 调用build_planner_prompt()生成规划器提示词
   - 传入planning context和执行历史

2. 其他智能体模块：
   - 通过render_prompt()获取特定类型提示词
   - 提供对应的context参数

3. A/B测试系统：
   - 通过update_template()动态修改模板内容
   - 实现不同版本提示词的在线切换

====================================================================================
配置和部署要求
====================================================================================

目录结构要求：
prompts/
├── config.yaml              # 系统配置
├── templates/               # 模板目录
│   ├── planner/            # 规划器模板
│   │   ├── core.yaml       # 核心定义
│   │   ├── framework.yaml  # 框架说明
│   │   ├── guides.yaml     # 执行指南
│   │   └── formats.yaml    # 输出格式
│   └── {other_types}/      # 其他类型模板
└── versions/               # 版本管理（预留）

权限要求：
- 读权限：所有模板文件和配置文件
- 写权限：支持动态模板更新时的文件写入

性能考虑：
- 内存使用：所有模板常驻内存，适合模板数量适中的场景
- 热更新开销：定期文件扫描，可通过配置调整检查频率
- 并发安全：使用线程锁保护关键资源

====================================================================================
"""

import os
import yaml
import time
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from jinja2 import Template, Environment, FileSystemLoader, TemplateNotFound
from dataclasses import dataclass
from threading import Lock
import hashlib

logger = logging.getLogger("django")


@dataclass
class PromptTemplate:
    """提示词模板数据类"""
    name: str
    content: str
    version: str = "1.0"
    last_modified: float = 0
    checksum: str = ""


class PromptManager:
    """
    提示词管理器，集中管理所有提示词模板
    
    特性：
    - YAML配置文件管理提示词
    - Jinja2模板引擎渲染
    - 文件监控和热更新
    - 模板缓存
    - 版本管理
    - A/B测试支持
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, prompts_dir: Optional[str] = None):
        # 避免重复初始化
        if hasattr(self, '_initialized'):
            return
            
        self.prompts_dir = Path(prompts_dir) if prompts_dir else Path(__file__).parent / "prompts"
        self.templates_dir = self.prompts_dir / "templates"
        self.versions_dir = self.prompts_dir / "versions"
        self.config_file = self.prompts_dir / "config.yaml"
        
        # 内部状态
        self.config: Dict[str, Any] = {}
        self.templates: Dict[str, PromptTemplate] = {}
        self.jinja_env: Optional[Environment] = None
        self.last_check_time: float = 0
        self._file_locks: Dict[str, Lock] = {}
        
        # 初始化
        self._load_config()
        self._init_jinja_env()
        self._load_all_templates()
        
        self._initialized = True
        logger.info(f"[PromptManager] 初始化完成，提示词目录：{self.prompts_dir}")
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f) or {}
            else:
                # 默认配置
                self.config = {
                    'version': '1.0',
                    'default_template_dir': 'templates',
                    'cache': {'enabled': True, 'ttl': 3600},
                    'hot_reload': {'enabled': True, 'watch_interval': 5}
                }
                logger.warning(f"[PromptManager] 配置文件不存在：{self.config_file}，使用默认配置")
        except Exception as e:
            logger.error(f"[PromptManager] 加载配置文件失败：{e}")
            self.config = {}
    
    def _init_jinja_env(self):
        """初始化Jinja2环境"""
        try:
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                autoescape=False,
                trim_blocks=True,
                lstrip_blocks=True
            )
            # 添加自定义过滤器
            self.jinja_env.filters['truncate_text'] = self._truncate_text
            self.jinja_env.filters['format_list'] = self._format_list
        except Exception as e:
            logger.error(f"[PromptManager] 初始化Jinja2环境失败：{e}")
    
    def _truncate_text(self, text: str, max_length: int = 200) -> str:
        """文本截断过滤器"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."
    
    def _format_list(self, items: List[str], prefix: str = "- ") -> str:
        """列表格式化过滤器"""
        if not items:
            return ""
        return "\n".join(f"{prefix}{item}" for item in items)
    
    def _load_all_templates(self):
        """加载所有模板"""
        if not self.templates_dir.exists():
            logger.warning(f"[PromptManager] 模板目录不存在：{self.templates_dir}")
            return
        
        for template_type in self.templates_dir.iterdir():
            if template_type.is_dir():
                self._load_template_type(template_type.name)
    
    def _load_template_type(self, template_type: str):
        """加载特定类型的模板"""
        type_dir = self.templates_dir / template_type
        if not type_dir.exists():
            return
        
        for yaml_file in type_dir.glob("*.yaml"):
            template_key = f"{template_type}_{yaml_file.stem}"
            self._load_single_template(template_key, yaml_file)
    
    def _load_single_template(self, template_key: str, file_path: Path):
        """加载单个模板文件"""
        try:
            stat = file_path.stat()
            last_modified = stat.st_mtime
            
            # 检查是否需要重新加载
            if template_key in self.templates:
                if self.templates[template_key].last_modified >= last_modified:
                    return  # 文件未修改，跳过
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
            
            # 计算文件校验和
            checksum = hashlib.md5(str(content).encode()).hexdigest()
            
            self.templates[template_key] = PromptTemplate(
                name=template_key,
                content=content,
                last_modified=last_modified,
                checksum=checksum
            )
            
            logger.debug(f"[PromptManager] 加载模板：{template_key}")
            
        except Exception as e:
            logger.error(f"[PromptManager] 加载模板失败 {file_path}：{e}")
    
    def get_template_data(self, template_type: str, section: str = None) -> Dict[str, Any]:
        """
        获取模板数据
        
        Args:
            template_type: 模板类型（如 planner）
            section: 具体段落（如 core, framework）
            
        Returns:
            模板数据字典
        """
        if section:
            template_key = f"{template_type}_{section}"
        else:
            # 获取该类型的所有模板并合并
            merged_data = {}
            for key, template in self.templates.items():
                if key.startswith(f"{template_type}_"):
                    if isinstance(template.content, dict):
                        merged_data.update(template.content)
            return merged_data
        
        if template_key not in self.templates:
            logger.warning(f"[PromptManager] 模板不存在：{template_key}")
            return {}
        
        return self.templates[template_key].content
    
    def render_prompt(self, 
                     template_type: str, 
                     context: Dict[str, Any], 
                     section: Optional[str] = None,
                     version: Optional[str] = None) -> str:
        """
        渲染提示词
        
        Args:
            template_type: 模板类型
            context: 渲染上下文
            section: 特定段落
            version: 版本号
            
        Returns:
            渲染后的提示词文本
        """
        try:
            # 检查是否需要热更新
            self._check_hot_reload()
            
            # 获取模板数据
            template_data = self.get_template_data(template_type, section)
            if not template_data:
                return ""
            
            # 渲染模板
            return self._render_template_data(template_data, context)
            
        except Exception as e:
            logger.error(f"[PromptManager] 渲染提示词失败 {template_type}.{section}：{e}")
            return ""
    
    def _render_template_data(self, template_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """递归渲染模板数据"""
        if isinstance(template_data, dict):
            rendered_parts = []
            
            for key, value in template_data.items():
                if key == 'title':
                    rendered_parts.append(f"## {value}")
                elif key == 'description':
                    rendered_parts.append(value)
                elif isinstance(value, dict):
                    rendered_parts.append(self._render_template_data(value, context))
                elif isinstance(value, list):
                    rendered_parts.append(self._render_list(value, context))
                elif isinstance(value, str):
                    # 使用Jinja2渲染字符串
                    template = Template(value)
                    rendered_parts.append(template.render(**context))
            
            return "\n\n".join(filter(None, rendered_parts))
        
        elif isinstance(template_data, str):
            template = Template(template_data)
            return template.render(**context)
        
        return str(template_data)
    
    def _render_list(self, items: List[Any], context: Dict[str, Any]) -> str:
        """渲染列表项"""
        rendered_items = []
        
        for item in items:
            if isinstance(item, dict):
                if 'name' in item and 'description' in item:
                    rendered_items.append(f"**{item['name']}**: {item['description']}")
                elif 'key' in item and 'description' in item:
                    rendered_items.append(f"**{item['key']}**: {item['description']}")
                else:
                    rendered_items.append(self._render_template_data(item, context))
            elif isinstance(item, str):
                template = Template(item)
                rendered_items.append(template.render(**context))
            else:
                rendered_items.append(str(item))
        
        return "\n".join(f"- {item}" for item in rendered_items if item)
    
    def build_planner_prompt(self, context: Dict[str, Any]) -> tuple[str, str]:
        """
        构建planner提示词，返回(系统提示词, 用户提示词)
        
        这是为了兼容现有代码的便利方法
        """
        try:
            # 渲染各个部分
            core_section = self.render_prompt('planner', context, 'core')
            framework_section = self.render_prompt('planner', context, 'framework') 
            guides_section = self.render_prompt('planner', context, 'guides')
            formats_section = self.render_prompt('planner', context, 'formats')
            
            # 组装系统提示词
            system_parts = [
                f"# {context.get('identity_title', '智能任务规划器')}",
                "",
                core_section,
                "",
                framework_section, 
                "",
                f"## 可用能力\n{context.get('capability_map', '')}",
                "",
                f"## 工具详细参数\n{context.get('tool_descriptions', '')}",
                "",
                guides_section,
                "",
                formats_section
            ]
            
            # 组装用户提示词
            user_parts = [
                "## 当前状态信息",
                "",
                f"### 原始任务\n{context.get('task_goal', '')}",
                ""
            ]
            
            # 添加TODO部分（如果存在）
            if context.get('todo_section'):
                user_parts.append(context['todo_section'])
                user_parts.append("")
            
            # 添加执行历史
            user_parts.extend([
                f"### 执行进展概览\n{context.get('history_summary', '')}",
                "",
                context.get('detailed_history', ''),
                "",
                f"{context.get('data_summary', '')}",
                "",
                "请基于以上信息和你的能力，决定下一步最合适的行动。",
                "",
                "**注意**: 执行历史中包含了每个步骤的reflection评价，请参考这些评价来判断哪些结果是充分的，哪些需要补充。"
            ])
            
            # 添加任务指导（如果有）
            if context.get('task_guidance'):
                user_parts.append(f"\n{context['task_guidance']}")
            
            return "\n".join(system_parts), "\n".join(user_parts)
            
        except Exception as e:
            logger.error(f"[PromptManager] 构建planner提示词失败：{e}")
            # 返回空提示词而不是抛出异常
            return "", ""
    
    def _check_hot_reload(self):
        """检查是否需要热更新"""
        if not self.config.get('hot_reload', {}).get('enabled', False):
            return
        
        now = time.time()
        interval = self.config.get('hot_reload', {}).get('watch_interval', 5)
        
        if now - self.last_check_time < interval:
            return
        
        self.last_check_time = now
        
        # 重新加载所有模板
        self._load_all_templates()
    
    def update_template(self, template_type: str, section: str, new_content: Dict[str, Any]):
        """
        动态更新模板（用于A/B测试）
        
        Args:
            template_type: 模板类型
            section: 模板段落
            new_content: 新的模板内容
        """
        template_key = f"{template_type}_{section}"
        
        if template_key in self.templates:
            # 更新内容但保持其他元数据
            self.templates[template_key].content = new_content
            self.templates[template_key].last_modified = time.time()
            logger.info(f"[PromptManager] 动态更新模板：{template_key}")
        else:
            # 创建新模板
            self.templates[template_key] = PromptTemplate(
                name=template_key,
                content=new_content,
                last_modified=time.time()
            )
            logger.info(f"[PromptManager] 创建新模板：{template_key}")
    
    def list_templates(self) -> List[str]:
        """列出所有可用模板"""
        return list(self.templates.keys())
    
    def get_template_info(self, template_key: str) -> Optional[PromptTemplate]:
        """获取模板信息"""
        return self.templates.get(template_key)
    
    def reload_templates(self):
        """手动重新加载所有模板"""
        self.templates.clear()
        self._load_all_templates()
        logger.info("[PromptManager] 手动重新加载所有模板完成")


# 创建全局单例
prompt_manager = PromptManager()


def get_prompt_manager() -> PromptManager:
    """获取提示词管理器实例"""
    return prompt_manager