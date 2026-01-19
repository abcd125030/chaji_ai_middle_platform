"""
页面生成服务

负责使用 LLM 生成页面内容、编辑页面、生成项目大纲等 AI 相关功能。
所有 LLM 调用都通过配置管理，不使用硬编码。
"""

import json
import logging
from typing import Optional, Dict, Any, List
from uuid import uuid4
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import transaction

from llm.llm_service import LLMService
from ..models import Project, ProjectDetail, ProjectLLMLog, PagtiveConfig
from .configuration_service import ConfigurationService

logger = logging.getLogger(__name__)


class PageGenerationService:
    """页面生成服务类"""
    
    def __init__(self):
        self.config_service = ConfigurationService()
        self.llm_service = LLMService()
    
    def generate_project_outline(
        self,
        project_name: str,
        project_description: str = "",
        project_style: str = ""
    ) -> List[Dict[str, Any]]:
        """
        生成项目大纲（页面列表）
        
        Args:
            project_name: 项目名称
            project_description: 项目描述
            project_style: 项目风格
            
        Returns:
            页面列表
        """
        try:
            # 获取配置
            config = self.config_service.get_active_config()
            llm_config = self.config_service.get_llm_config(scenario='outline')
            
            # 详细记录大纲生成的配置
            logger.info(f"""
[Pagtive大纲服务] 大纲配置详情:
    [大纲配置] 场景: outline
    [大纲配置] 项目名称: {project_name}
    [大纲配置] 项目描述: {project_description}
    [大纲配置] 项目风格: {project_style}
    [LLM配置] 模型ID: {llm_config['model_id']}
    [LLM配置] 模型名称: {llm_config.get('model_name', 'N/A')}
    [LLM配置] 提供商: {llm_config.get('provider', 'unknown')}
    [LLM配置] 完整参数: {json.dumps(llm_config['params'], ensure_ascii=False)}""")
            
            # 构建提示词
            prompt = self._build_outline_prompt(
                config=config,
                project_name=project_name,
                project_description=project_description,
                project_style=project_style
            )
            
            # 调用 LLM
            messages = [{'role': 'user', 'content': prompt}]
            response = self.llm_service.internal.call_llm(
                model_name=llm_config.get('model_name', llm_config['model_id']),
                messages=messages,
                **llm_config['params']
            )
            
            # 提取响应内容
            if isinstance(response, dict) and 'choices' in response:
                response = response['choices'][0]['message']['content']
            elif isinstance(response, dict) and 'content' in response:
                response = response['content']
            
            # 解析响应
            pages = self._parse_outline_response(response)
            
            # 添加默认顺序和时间戳
            for i, page in enumerate(pages):
                if 'order' not in page:
                    page['order'] = (i + 1) * 100
                if 'created_at' not in page:
                    page['created_at'] = datetime.now().isoformat()
            
            return pages
            
        except Exception as e:
            logger.error(f"生成项目大纲失败: {str(e)}")
            # 返回默认页面列表
            return self._get_default_pages()
    
    @transaction.atomic
    def generate_page_content(
        self,
        project: Project,
        user: Any,
        prompt: str,
        scenario: Optional[str] = None,
        template: Optional[str] = None,
        references: Optional[List[Dict]] = None,
        images: Optional[List[Dict]] = None,
        page_id: Optional[int] = None,
        current_content: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        统一的页面内容生成/编辑方法
        
        Args:
            project: 项目对象
            user: 用户对象
            prompt: 用户提示词（生成模式）或编辑指令（编辑模式）
            scenario: 场景类型 ('generatePageCode' 或 'editPageCode')
            template: 模板类型（保留用于兼容）
            references: 参考内容列表
            images: 图片列表
            page_id: 页面ID（可选，编辑模式必需）
            current_content: 当前页面内容（编辑模式必需）
            
        Returns:
            生成/编辑的页面内容和元信息
        """
        # 判断实际场景
        is_edit_mode = (scenario == 'editPageCode' or template == 'editPageCode') and page_id and current_content
        actual_scenario = 'edit' if is_edit_mode else 'generate'
        log_scenario = 'editPageCode' if is_edit_mode else 'generatePageCode'
        # 生成临时页面ID
        temp_page_id = str(uuid4())
        
        # 创建 LLM 日志（先用占位符，稍后更新实际配置）
        llm_log = ProjectLLMLog.objects.create(
            user=user,
            project=project,
            page_id=page_id or 0,
            scenario=log_scenario,
            request_prompts=prompt,
            request_config={},  # 稍后在获取 llm_config 后更新
            status='pending',
            temporary_page_id=temp_page_id
        )
        
        try:
            # 获取配置
            config = self.config_service.get_active_config()
            llm_config = self.config_service.get_llm_config(scenario=actual_scenario)
            
            # 详细记录Pagtive配置信息
            if config:
                logger.info(f"""[Pagtive生成服务] 配置详情:
            [Pagtive配置] 配置名称: {config.name}
            [Pagtive配置] 配置ID: {config.id}
            [Pagtive配置] 描述: {config.description}
            [Pagtive配置] 是否激活: {config.is_active}
            [Pagtive配置] LLM模型: {config.llm_model.name if config.llm_model else '未设置'}
            [Pagtive配置] 编辑模型: {config.llm_model_for_edit.name if config.llm_model_for_edit else '未设置'}
            [Pagtive配置] Temperature: {config.temperature}
            [Pagtive配置] Max Tokens: {config.max_tokens}
            [Pagtive配置] 流式输出: {config.enable_stream}
            [Pagtive配置] 额外配置: {config.extra_config}""")
                
                # 打印提示词模板（如果不太长）
                if config.system_prompt and len(config.system_prompt) <= 500:
                    logger.info(f"[Pagtive配置] 系统提示词: {config.system_prompt}")
                elif config.system_prompt:
                    logger.info(f"[Pagtive配置] 系统提示词长度: {len(config.system_prompt)} 字符")
                
                if config.generate_template and len(config.generate_template) <= 500:
                    logger.info(f"[Pagtive配置] 生成模板: {config.generate_template}")
                elif config.generate_template:
                    logger.info(f"[Pagtive配置] 生成模板长度: {len(config.generate_template)} 字符")
            else:
                logger.warning(f"[Pagtive配置] 未找到激活的配置，使用默认设置")
            
            # 详细记录LLM配置信息
            logger.info(f"""[LLM配置] LLM配置详情:
            [LLM配置] 场景: {actual_scenario}
            [LLM配置] 模型ID: {llm_config['model_id']}
            [LLM配置] 模型名称: {llm_config.get('model_name', 'N/A')}
            [LLM配置] 提供商: {llm_config.get('provider', 'unknown')}
            [LLM配置] 启用流式: {llm_config.get('enable_stream', False)}
            [LLM配置] 完整参数: {json.dumps(llm_config['params'], ensure_ascii=False)}""")
            
            # 构建完整提示词
            if is_edit_mode:
                # 编辑模式：使用编辑提示词构建器
                full_prompt = self._build_edit_prompt(
                    config=config,
                    edit_instruction=prompt,
                    current_content=current_content,
                    project=project,
                    references=references  # 编辑模式也支持参考内容
                )
            else:
                # 生成模式：使用生成提示词构建器
                full_prompt = self._build_generation_prompt(
                    config=config,
                    project=project,
                    user_prompt=prompt,
                    template=template,
                    references=references,
                    images=images
                )
            
            # 详细记录提示词信息
            logger.info(f"""[Pagtive生成服务] 提示词详情:
            [提示词] 用户输入: {prompt}
            [提示词] 用户输入长度: {len(prompt)} 字符
            [提示词] 模板类型: {template}
            [提示词] 参考内容数: {len(references)}
            [提示词] 图片数: {len(images)}
            [提示词] 项目名称: {project.project_name}
            [提示词] 项目风格: {project.project_style}
            [提示词] 完整提示词长度: {len(full_prompt)} 字符""")
            
            # 打印完整提示词（不截取）
            logger.info(f"[提示词] 完整内容:\n{full_prompt}")
            
            # 更新日志，包含实际使用的 LLM 配置
            llm_log.provider = llm_config.get('provider', 'openai')
            llm_log.model = llm_config['model_id']
            # 存储实际的 LLM 配置参数
            llm_log.request_config = {
                'model': llm_config['model_id'],
                'temperature': llm_config['params'].get('temperature', 0.7),
                'max_tokens': llm_config['params'].get('max_tokens'),
                'topP': llm_config['params'].get('top_p'),  # 注意这里使用 topP 而不是 top_p
                'frequencyPenalty': llm_config['params'].get('frequency_penalty'),
                'presencePenalty': llm_config['params'].get('presence_penalty')
            }
            # 移除 None 值
            llm_log.request_config = {k: v for k, v in llm_log.request_config.items() if v is not None}
            llm_log.status = 'processing'
            llm_log.save()
            
            # 调用 LLM
            messages = [{'role': 'user', 'content': full_prompt}]
            
            # 准备LLM调用参数，避免参数冲突
            llm_params = llm_config['params'].copy()
            
            if llm_config.get('enable_stream', False):
                # 流式生成 - 确保stream参数为True
                llm_params['stream'] = True
                response_content = ""
                
                logger.info(f"[Pagtive生成服务] 开始调用LLM（流式模式）\n" +
                           f"[Pagtive生成服务] 实际调用参数: model_name={llm_config.get('model_name', llm_config['model_id'])}, params={llm_params}")
                
                response = self.llm_service.internal.call_llm(
                    model_name=llm_config.get('model_name', llm_config['model_id']),
                    messages=messages,
                    **llm_params
                )
                # 处理流式响应（SSE格式）
                for chunk in response:
                    if isinstance(chunk, str):
                        # 处理SSE格式的流式响应
                        if chunk.startswith('data: '):
                            chunk_data = chunk[6:]  # 移除'data: '前缀
                            if chunk_data.strip() == '[DONE]':
                                continue
                            try:
                                chunk_json = json.loads(chunk_data)
                                if 'choices' in chunk_json:
                                    delta = chunk_json['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        response_content += delta['content']
                            except json.JSONDecodeError:
                                logger.debug(f"无法解析流式响应块: {chunk}")
                    elif isinstance(chunk, dict) and 'choices' in chunk:
                        # 处理已解析的字典格式
                        delta = chunk['choices'][0].get('delta', {})
                        if 'content' in delta:
                            response_content += delta['content']
            else:
                # 非流式生成 - 确保stream参数为False或不存在
                llm_params.pop('stream', None)  # 移除stream参数，让默认值生效
                
                logger.info(f"[Pagtive生成服务] 开始调用LLM（非流式模式）\n" +
                           f"[Pagtive生成服务] 实际调用参数: model_name={llm_config.get('model_name', llm_config['model_id'])}, params={llm_params}")
                
                response = self.llm_service.internal.call_llm(
                    model_name=llm_config.get('model_name', llm_config['model_id']),
                    messages=messages,
                    **llm_params
                )
                
                # 检查是否返回了生成器（即使我们没有请求流式）
                if hasattr(response, '__iter__') and not isinstance(response, (str, dict)):
                    # 如果是生成器，消费所有内容
                    logger.warning("LLM服务返回了流式响应，即使未请求流式输出")
                    response_content = ""
                    for chunk in response:
                        if isinstance(chunk, str):
                            # 如果是SSE格式，提取实际内容
                            if chunk.startswith('data: '):
                                chunk = chunk[6:]  # 移除'data: '前缀
                                if chunk.strip() == '[DONE]':
                                    continue
                                try:
                                    chunk_data = json.loads(chunk)
                                    if 'choices' in chunk_data:
                                        delta = chunk_data['choices'][0].get('delta', {})
                                        if 'content' in delta:
                                            response_content += delta['content']
                                except json.JSONDecodeError:
                                    pass
                            else:
                                response_content += chunk
                        elif isinstance(chunk, dict) and 'choices' in chunk:
                            delta = chunk['choices'][0].get('delta', {})
                            if 'content' in delta:
                                response_content += delta['content']
                else:
                    # 提取响应内容
                    if isinstance(response, dict) and 'choices' in response:
                        response_content = response['choices'][0]['message']['content']
                    elif isinstance(response, dict) and 'content' in response:
                        response_content = response['content']
                    else:
                        response_content = str(response)
            
            # 解析响应内容
            logger.info(f"[Pagtive生成服务] LLM响应长度: {len(response_content)} 字符\n" +
                       f"[Pagtive生成服务] 完整LLM响应内容:\n{response_content}")
            page_content = self._parse_page_content(response_content)
            
            # 确定页面ID（但不保存）
            if page_id is None:
                page_id = self._get_next_page_id(project)
            
            # 注释掉自动保存功能，只返回生成的内容供预览
            # 用户需要手动点击保存按钮才会真正保存到数据库
            # detail = self._save_page_content(
            #     project=project,
            #     page_id=page_id,
            #     content=page_content,
            #     temp_page_id=temp_page_id
            # )
            detail = None  # 不自动保存，返回None
            
            # 更新 LLM 日志
            llm_log.response_content = response_content
            llm_log.status = 'success'
            # 注意：page_id 是预计的ID，实际页面尚未保存
            # 保存时前端会使用 tempPageId 来关联
            llm_log.page_id = None  # 不设置 page_id，因为页面尚未真正创建
            
            # 获取 token 使用量（如果响应中包含）
            if isinstance(response, dict) and 'usage' in response:
                usage = response['usage']
                llm_log.usage_prompt_tokens = usage.get('prompt_tokens', 0)
                llm_log.usage_completion_tokens = usage.get('completion_tokens', 0)
                llm_log.usage_total_tokens = usage.get('total_tokens', 0)
            
            llm_log.save()
            
            return {
                'status': 'success',
                'data': {
                    'id': str(detail.id) if detail else None,  # 由于未保存，id 为 None
                    'content': page_content,
                    'pageId': page_id,  # 返回预计的页面ID，但实际未保存
                    'tempPageId': temp_page_id
                }
            }
            
        except Exception as e:
            logger.error(f"生成页面内容失败: {str(e)}", exc_info=True)
            
            # 更新日志状态，保存详细的错误信息
            llm_log.status = 'failed'
            llm_log.response_error = str(e)  # 使用正确的字段名
            llm_log.save()
            
            return {
                'status': 'error',
                'message': f'生成页面失败: {str(e)}',
                'tempPageId': temp_page_id
            }
    
    def generate_page_metadata(
        self,
        html_content: str,
        project_name: Optional[str] = None,
        page_title: Optional[str] = None
    ) -> Dict[str, str]:
        """
        基于页面HTML内容生成SEO metadata
        
        Args:
            html_content: 页面的HTML内容
            project_name: 项目名称（可选）
            page_title: 页面标题（可选）
            
        Returns:
            包含metadata的字典：
            - title: 页面标题
            - description: 页面描述
            - keywords: 关键词（逗号分隔）
        """
        try:
            # 获取配置
            config = self.config_service.get_active_config()
            if not config:
                logger.warning("[Pagtive元数据] 未找到激活的配置，使用默认方式")
                return self._generate_default_metadata(html_content, project_name, page_title)
            
            # 获取LLM配置（使用edit场景的配置，因为这是编辑相关的操作）
            llm_config = self.config_service.get_llm_config(scenario='edit')
            
            logger.info(f"""[Pagtive元数据] 开始生成页面元数据
            [元数据] HTML内容长度: {len(html_content)} 字符
            [元数据] 项目名称: {project_name}
            [元数据] 页面标题: {page_title}
            [LLM配置] 模型: {llm_config.get('model_name', llm_config['model_id'])}""")
            
            # 构建提示词
            prompt = self._build_metadata_prompt(
                config=config,
                html_content=html_content,
                project_name=project_name,
                page_title=page_title
            )
            
            # 调用LLM
            messages = [{'role': 'user', 'content': prompt}]
            
            logger.info(f"[Pagtive元数据] 调用LLM生成metadata")
            response = self.llm_service.internal.call_llm(
                model_name=llm_config.get('model_name', llm_config['model_id']),
                messages=messages,
                temperature=0.3,  # 使用较低的temperature以获得更稳定的输出
                **{k: v for k, v in llm_config['params'].items() if k != 'temperature'}
            )
            
            # 提取响应内容
            if isinstance(response, dict) and 'choices' in response:
                response_content = response['choices'][0]['message']['content']
            elif isinstance(response, dict) and 'content' in response:
                response_content = response['content']
            else:
                response_content = str(response)
            
            # 解析响应
            metadata = self._parse_metadata_response(response_content)
            
            logger.info(f"""[Pagtive元数据] 成功生成metadata
            [元数据] 标题: {metadata.get('title', 'N/A')}
            [元数据] 描述长度: {len(metadata.get('description', ''))} 字符
            [元数据] 关键词数: {len(metadata.get('keywords', '').split(','))} 个""")
            
            return metadata
            
        except Exception as e:
            logger.error(f"[Pagtive元数据] 生成metadata失败: {str(e)}", exc_info=True)
            return self._generate_default_metadata(html_content, project_name, page_title)
    
    # 私有方法
    
    def _build_outline_prompt(
        self,
        config: Optional[PagtiveConfig],
        project_name: str,
        project_description: str,
        project_style: str
    ) -> str:
        """构建生成大纲的提示词"""
        if config:
            template = self.config_service.get_prompt_template(
                config, 'outline'
            )
            if template:
                # 使用安全的字符串替换而不是format()，以避免CSS大括号冲突
                return template.replace(
                    '{project_name}', project_name
                ).replace(
                    '{project_description}', project_description
                ).replace(
                    '{project_style}', project_style
                )
        
        # 默认提示词
        return f"""请为以下项目生成一个页面列表大纲：

项目名称：{project_name}
项目描述：{project_description}
项目风格：{project_style}

请返回一个JSON数组，每个页面包含以下字段：
- id: 页面ID（数字）
- title: 页面标题
- description: 页面简要描述（可选）

示例格式：
[
    {{"id": "1", "title": "首页", "description": "项目主页"}},
    {{"id": "2", "title": "关于我们", "description": "团队介绍"}}
]"""
    
    def _build_generation_prompt(
        self,
        config: Optional[PagtiveConfig],
        project: Project,
        user_prompt: str,
        template: Optional[str],
        references: Optional[List[Dict]],
        images: Optional[List[Dict]]
    ) -> str:
        """构建生成页面的提示词"""
        # 获取系统提示词
        system_prompt = ""
        if config:
            system_template = self.config_service.get_prompt_template(
                config, 'system'
            )
            if system_template:
                # 使用安全的字符串替换而不是format()，以避免CSS大括号冲突
                system_prompt = system_template.replace(
                    '{project_name}', project.project_name or ''
                ).replace(
                    '{project_style}', project.project_style or ''
                )
        
        # 获取生成模板
        generation_template = ""
        if config:
            gen_template = self.config_service.get_prompt_template(
                config, 'generate'
            )
            if gen_template:
                # 构建参考内容字符串
                ref_content = ""
                if references:
                    ref_content = "\n\n参考内容：\n"
                    for ref in references:
                        ref_content += f"- {ref.get('title', '未命名')}: {ref.get('content', '')}\n"
                
                # 处理参考内容（分离HTML、CSS、JS，为每个页面生成独立的代码块）
                ref_html_blocks = []
                ref_css_blocks = []
                ref_js_blocks = []
                
                if references:
                    # references 已经在 views_generate.py 中处理过
                    # 格式为 [{'title': '...', 'content': 'HTML:\n...\n\nCSS:\n...\n\nJavaScript:\n...'}]
                    for idx, ref in enumerate(references, 1):
                        content = ref.get('content', '')
                        title = ref.get('title', f'参考页面 {idx}')
                        
                        # 按标记分割内容
                        if 'HTML:' in content:
                            parts = content.split('HTML:')
                            if len(parts) > 1:
                                html_part = parts[1].split('\n\nCSS:')[0] if '\n\nCSS:' in parts[1] else parts[1].split('\n\nJavaScript:')[0] if '\n\nJavaScript:' in parts[1] else parts[1]
                                html_content = html_part.strip()
                                if html_content:
                                    # 为每个页面创建独立的HTML代码块
                                    ref_html_blocks.append(f"<!-- {title} -->\n```html\n{html_content}\n```")
                        
                        if 'CSS:' in content:
                            parts = content.split('CSS:')
                            if len(parts) > 1:
                                css_part = parts[1].split('\n\nJavaScript:')[0] if '\n\nJavaScript:' in parts[1] else parts[1]
                                css_content = css_part.strip()
                                if css_content:
                                    # 为每个页面创建独立的CSS代码块
                                    ref_css_blocks.append(f"/* {title} */\n```css\n{css_content}\n```")
                        
                        if 'JavaScript:' in content:
                            parts = content.split('JavaScript:')
                            if len(parts) > 1:
                                js_content = parts[1].strip()
                                if js_content:
                                    # 为每个页面创建独立的JavaScript代码块
                                    ref_js_blocks.append(f"// {title}\n```javascript\n{js_content}\n```")
                
                # 合并所有代码块，每个页面的代码块之间用换行分隔
                ref_html = "\n\n".join(ref_html_blocks) if ref_html_blocks else ""
                ref_css = "\n\n".join(ref_css_blocks) if ref_css_blocks else ""
                ref_js = "\n\n".join(ref_js_blocks) if ref_js_blocks else ""
                
                # 构建图片描述
                img_desc = ""
                if images:
                    img_desc = "\n\n相关图片：\n"
                    for img in images:
                        img_desc += f"- {img.get('name', '图片')}: {img.get('url', '')}\n"
                
                # 使用安全的字符串替换而不是format()，以避免CSS大括号冲突
                generation_template = gen_template.replace(
                    '{user_prompt}', user_prompt
                ).replace(
                    '{template}', template or ""
                ).replace(
                    '{references}', ref_content
                ).replace(
                    '{images}', img_desc
                ).replace(
                    '{global_styles}', project.global_style_code or ""
                ).replace(
                    '{{projectDescription}}', project.project_description or ''
                ).replace(
                    '{{requirement}}', user_prompt
                ).replace(
                    '{{referenceHtml}}', ref_html
                ).replace(
                    '{{referenceCss}}', ref_css
                ).replace(
                    '{{referenceJs}}', ref_js
                ).replace(
                    '{{projectStyle}}', project.project_style or ''
                ).replace(
                    '{{globalStyleCode}}', project.global_style_code or ''
                )
        
        if not generation_template:
            # 使用默认模板
            generation_template = f"""请根据以下需求生成网页代码：

需求：{user_prompt}

项目信息：
- 名称：{project.project_name}
- 风格：{project.project_style}
- 全局样式：{project.global_style_code or '无'}

请返回一个JSON对象，包含以下字段：
- html: HTML代码
- styles: CSS样式代码
- script: JavaScript代码（可选）
- mermaidContent: Mermaid图表代码（可选）"""
        
        # 组合提示词
        if system_prompt:
            return f"{system_prompt}\n\n{generation_template}"
        return generation_template
    
    def _build_edit_prompt(
        self,
        config: Optional[PagtiveConfig],
        edit_instruction: str,
        current_content: Dict[str, str],
        project: Project,
        references: Optional[List[Dict]] = None
    ) -> str:
        """构建编辑页面的提示词"""
        if config:
            template = self.config_service.get_prompt_template(
                config, 'edit'
            )
            if template:
                # 处理参考内容（为每个页面生成独立的代码块）
                ref_html_blocks = []
                ref_css_blocks = []
                ref_js_blocks = []
                
                if references:
                    # references 已经在 views_generate.py 中处理过
                    # 格式为 [{'title': '...', 'content': 'HTML:\n...\n\nCSS:\n...\n\nJavaScript:\n...'}]
                    for idx, ref in enumerate(references, 1):
                        content = ref.get('content', '')
                        title = ref.get('title', f'参考页面 {idx}')
                        
                        # 按标记分割内容
                        if 'HTML:' in content:
                            parts = content.split('HTML:')
                            if len(parts) > 1:
                                html_part = parts[1].split('\n\nCSS:')[0] if '\n\nCSS:' in parts[1] else parts[1].split('\n\nJavaScript:')[0] if '\n\nJavaScript:' in parts[1] else parts[1]
                                html_content = html_part.strip()
                                if html_content:
                                    # 为每个页面创建独立的HTML代码块
                                    ref_html_blocks.append(f"<!-- {title} -->\n```html\n{html_content}\n```")
                        
                        if 'CSS:' in content:
                            parts = content.split('CSS:')
                            if len(parts) > 1:
                                css_part = parts[1].split('\n\nJavaScript:')[0] if '\n\nJavaScript:' in parts[1] else parts[1]
                                css_content = css_part.strip()
                                if css_content:
                                    # 为每个页面创建独立的CSS代码块
                                    ref_css_blocks.append(f"/* {title} */\n```css\n{css_content}\n```")
                        
                        if 'JavaScript:' in content:
                            parts = content.split('JavaScript:')
                            if len(parts) > 1:
                                js_content = parts[1].strip()
                                if js_content:
                                    # 为每个页面创建独立的JavaScript代码块
                                    ref_js_blocks.append(f"// {title}\n```javascript\n{js_content}\n```")
                
                # 合并所有代码块，每个页面的代码块之间用换行分隔
                ref_html = "\n\n".join(ref_html_blocks) if ref_html_blocks else ""
                ref_css = "\n\n".join(ref_css_blocks) if ref_css_blocks else ""
                ref_js = "\n\n".join(ref_js_blocks) if ref_js_blocks else ""
                
                # 使用安全的字符串替换，处理数据库中的{{}}格式占位符
                result = template.replace(
                    '{{requirement}}', edit_instruction
                ).replace(
                    '{{currentHtml}}', current_content.get('html', '')
                ).replace(
                    '{{currentCss}}', current_content.get('styles', '')
                ).replace(
                    '{{currentJs}}', current_content.get('script', '')
                ).replace(
                    '{{currentMermaid}}', current_content.get('mermaidContent', '')
                ).replace(
                    '{{projectStyle}}', project.project_style or ''
                ).replace(
                    '{{projectDescription}}', project.project_description or ''
                ).replace(
                    '{{globalStyleCode}}', project.global_style_code or ''
                ).replace(
                    '{{referenceHtml}}', ref_html
                ).replace(
                    '{{referenceCss}}', ref_css
                ).replace(
                    '{{referenceJs}}', ref_js
                )
                return result
        
        # 默认编辑提示词
        return f"""请根据以下指令修改网页代码：

修改指令：{edit_instruction}

当前代码：
HTML:
{current_content.get('html', '')}

CSS:
{current_content.get('styles', '')}

JavaScript:
{current_content.get('script', '')}

项目信息：
- 名称：{project.project_name}
- 风格：{project.project_style}

请返回修改后的完整代码，格式为JSON对象：
- html: 修改后的HTML代码
- styles: 修改后的CSS样式
- script: 修改后的JavaScript代码
- mermaidContent: Mermaid图表代码（如果有）"""
    
    def _parse_outline_response(self, response: str) -> List[Dict[str, Any]]:
        """解析大纲生成响应"""
        try:
            # 尝试提取JSON
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                pages = json.loads(json_match.group())
                # 确保每个页面都有必要的字段
                for page in pages:
                    if 'id' not in page:
                        page['id'] = str(pages.index(page) + 1)
                    else:
                        page['id'] = str(page['id'])
                return pages
        except Exception as e:
            logger.error(f"解析大纲响应失败: {str(e)}")
        
        return self._get_default_pages()
    
    def _parse_page_content(self, response: str) -> Dict[str, str]:
        """解析页面内容响应 - 兼容旧项目的解析逻辑"""
        import re
        
        # 定义解析结果的默认结构
        result = {
            'html': '',
            'styles': '',
            'script': '',
            'mermaidContent': ''
        }
        
        try:
            # 1. 首先尝试直接解析为JSON
            try:
                content = json.loads(response)
                if isinstance(content, dict):
                    result['html'] = content.get('html', '')
                    result['styles'] = content.get('styles', '') or content.get('css', '')
                    result['script'] = content.get('script', '') or content.get('javascript', '') or content.get('js', '')
                    result['mermaidContent'] = content.get('mermaidContent', '') or content.get('mermaid', '')
                    logger.info(f"[Pagtive生成服务] 成功解析为JSON格式")
                    return result
            except json.JSONDecodeError:
                pass
            
            # 2. 检查是否有HTML代码块 (```html...```)
            html_block_match = re.search(r'```html\s*\n(.*?)\n```', response, re.DOTALL)
            css_block_match = re.search(r'```(?:css|styles?)\s*\n(.*?)\n```', response, re.DOTALL)
            js_block_match = re.search(r'```(?:javascript|js|script)\s*\n(.*?)\n```', response, re.DOTALL)
            mermaid_block_match = re.search(r'```mermaid\s*\n(.*?)\n```', response, re.DOTALL)
            
            if html_block_match:
                result['html'] = html_block_match.group(1).strip()
                logger.info(f"[Pagtive生成服务] 提取到HTML代码块，长度: {len(result['html'])} 字符")
            
            if css_block_match:
                result['styles'] = css_block_match.group(1).strip()
                logger.info(f"[Pagtive生成服务] 提取到CSS代码块，长度: {len(result['styles'])} 字符")
            
            if js_block_match:
                result['script'] = js_block_match.group(1).strip()
                logger.info(f"[Pagtive生成服务] 提取到JavaScript代码块，长度: {len(result['script'])} 字符")
            
            if mermaid_block_match:
                result['mermaidContent'] = mermaid_block_match.group(1).strip()
                logger.info(f"[Pagtive生成服务] 提取到Mermaid代码块，长度: {len(result['mermaidContent'])} 字符")
            
            # 如果找到了HTML内容，认为解析成功
            if result['html']:
                logger.info(f"[Pagtive生成服务] 成功从代码块中提取内容")
                return result
            
            # 3. 尝试提取JSON代码块
            json_block_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response, re.DOTALL)
            if json_block_match:
                try:
                    content = json.loads(json_block_match.group(1))
                    if isinstance(content, dict):
                        result['html'] = content.get('html', '')
                        result['styles'] = content.get('styles', '') or content.get('css', '')
                        result['script'] = content.get('script', '') or content.get('javascript', '') or content.get('js', '')
                        result['mermaidContent'] = content.get('mermaidContent', '') or content.get('mermaid', '')
                        logger.info(f"[Pagtive生成服务] 成功解析JSON代码块")
                        return result
                except json.JSONDecodeError:
                    pass
            
            # 4. 如果响应本身就是HTML（没有包装在代码块或JSON中）
            # 检查是否包含HTML标签
            if re.search(r'<[^>]+>', response):
                # 如果响应看起来像HTML，直接作为HTML内容
                result['html'] = response.strip()
                logger.info(f"[Pagtive生成服务] 将整个响应作为HTML内容，长度: {len(result['html'])} 字符")
                return result
            
            # 5. 最后的尝试：查找嵌入的JSON对象
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            for match in re.finditer(json_pattern, response):
                json_str = match.group()
                try:
                    content = json.loads(json_str)
                    if isinstance(content, dict) and any(key in content for key in ['html', 'styles', 'css', 'script', 'javascript', 'js']):
                        result['html'] = content.get('html', '')
                        result['styles'] = content.get('styles', '') or content.get('css', '')
                        result['script'] = content.get('script', '') or content.get('javascript', '') or content.get('js', '')
                        result['mermaidContent'] = content.get('mermaidContent', '') or content.get('mermaid', '')
                        logger.info(f"[Pagtive生成服务] 成功提取嵌入的JSON对象")
                        return result
                except json.JSONDecodeError:
                    continue
            
        except Exception as e:
            logger.error(f"[Pagtive生成服务] 解析页面内容异常: {str(e)}", exc_info=True)
        
        # 如果所有解析尝试都失败，将整个响应作为HTML
        if not result['html'] and response.strip():
            result['html'] = response.strip()
            logger.warning(f"[Pagtive生成服务] 所有解析尝试失败，将整个响应作为HTML内容")
        
        return result
    
    def _get_default_pages(self) -> List[Dict[str, Any]]:
        """获取默认页面列表"""
        return [
            {
                'id': '1',
                'title': '首页',
                'order': 100,
                'created_at': datetime.now().isoformat()
            }
        ]
    
    def _get_next_page_id(self, project: Project) -> int:
        """获取下一个可用的页面ID"""
        # 确保 pages 是一个列表
        if not project.pages or not isinstance(project.pages, list):
            return 1
        
        existing_ids = [int(p.get('id', 0)) for p in project.pages if p.get('id')]
        return max(existing_ids) + 1 if existing_ids else 1
    
    def _save_page_content(
        self,
        project: Project,
        page_id: int,
        content: Dict[str, str],
        temp_page_id: Optional[str] = None
    ) -> ProjectDetail:
        """保存页面内容到数据库"""
        # 生成新的版本ID
        new_version_id = uuid4()
        
        detail, created = ProjectDetail.objects.update_or_create(
            project=project,
            page_id=page_id,
            defaults={
                'html': content.get('html', ''),
                'styles': content.get('styles', ''),
                'script': content.get('script', ''),
                'mermaid_content': content.get('mermaidContent', ''),
                'version_id': new_version_id
            }
        )
        
        # 如果有临时页面ID，更新对应的LLM日志的version_id
        if temp_page_id:
            ProjectLLMLog.objects.filter(
                temporary_page_id=temp_page_id
            ).update(version_id=new_version_id)
        
        # 如果是新页面，更新项目的pages列表
        if created:
            # 确保 pages 是一个列表
            if project.pages is None:
                project.pages = []
            elif not isinstance(project.pages, list):
                project.pages = []
            
            page_exists = any(
                str(p.get('id')) == str(page_id) 
                for p in project.pages
            )
            if not page_exists:
                new_page = {
                    'id': str(page_id),
                    'title': f'页面 {page_id}',
                    'order': len(project.pages) * 100 + 100,
                    'created_at': datetime.now().isoformat()
                }
                if temp_page_id:
                    new_page['tempPageId'] = temp_page_id
                
                # 创建新的列表来避免直接修改
                pages_list = list(project.pages)
                pages_list.append(new_page)
                project.pages = pages_list
                project.save()
        
        return detail
    
    def _build_metadata_prompt(
        self,
        config: Optional[PagtiveConfig],
        html_content: str,
        project_name: Optional[str],
        page_title: Optional[str]
    ) -> str:
        """构建生成metadata的提示词"""
        # 尝试从配置获取metadata模板
        if config:
            template = self.config_service.get_prompt_template(config, 'metadata')
            if template:
                # 使用安全的字符串替换 - 注意模板中使用的是 {{html_content}} 变量
                return template.replace(
                    '{{html_content}}', html_content[:5000]  # 限制HTML长度避免token超限
                )
        
        # 默认的metadata生成提示词 - 如果数据库中没有配置
        return f"""请基于以下HTML内容生成SEO优化的页面元数据。

项目名称：{project_name or '未知'}
页面标题：{page_title or '未知'}

HTML内容（前3000字符）：
{html_content[:3000]}

请分析HTML内容，提取关键信息，生成以下两个字段：
1. title - 页面标题（不超过20字）
2. description - 页面描述（不超过100字）

请以JSON格式返回，例如：
{{
    "title": "页面标题",
    "description": "页面描述"
}}

重要：
- title应该简洁有力，包含页面核心主题
- description应该准确概括页面内容
- 请直接返回JSON，不要包含其他解释文字"""
    
    def _parse_metadata_response(self, response: str) -> Dict[str, str]:
        """解析LLM返回的metadata响应"""
        try:
            # 尝试提取JSON内容
            import re
            json_pattern = r'\{[^}]*\}'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            if matches:
                # 尝试解析最后一个匹配的JSON（通常是最完整的）
                for match in reversed(matches):
                    try:
                        metadata = json.loads(match)
                        # 验证必需字段 - 现在只需要 title 和 description
                        if all(k in metadata for k in ['title', 'description']):
                            return {
                                'title': str(metadata['title'])[:100],  # 限制长度
                                'description': str(metadata['description'])[:200],
                                'keywords': metadata.get('keywords', '')[:200]  # keywords 是可选的
                            }
                    except json.JSONDecodeError:
                        continue
            
            # 如果无法解析JSON，尝试从文本中提取
            lines = response.strip().split('\n')
            metadata = {}
            
            for line in lines:
                if 'title' in line.lower() and ':' in line:
                    metadata['title'] = line.split(':', 1)[1].strip()[:100]
                elif 'description' in line.lower() and ':' in line:
                    metadata['description'] = line.split(':', 1)[1].strip()[:200]
                elif 'keyword' in line.lower() and ':' in line:
                    metadata['keywords'] = line.split(':', 1)[1].strip()[:200]
            
            # 确保所有字段都存在
            return {
                'title': metadata.get('title', '未命名页面'),
                'description': metadata.get('description', ''),
                'keywords': metadata.get('keywords', '')
            }
            
        except Exception as e:
            logger.error(f"[Pagtive元数据] 解析metadata响应失败: {str(e)}")
            return {
                'title': '未命名页面',
                'description': '',
                'keywords': ''
            }
    
    def _generate_default_metadata(
        self,
        html_content: str,
        project_name: Optional[str],
        page_title: Optional[str]
    ) -> Dict[str, str]:
        """生成默认的metadata（不使用LLM）"""
        try:
            # 尝试从HTML中提取文本内容
            import re
            
            # 移除HTML标签
            text = re.sub(r'<[^>]+>', ' ', html_content)
            # 移除多余空格
            text = ' '.join(text.split())
            
            # 生成标题
            if page_title:
                title = page_title
            elif project_name:
                title = f"{project_name} - 页面"
            else:
                # 尝试从文本中提取第一句话作为标题
                sentences = text.split('.')
                title = sentences[0][:50] if sentences else '未命名页面'
            
            # 生成描述（取前150个字符）
            description = text[:150] + '...' if len(text) > 150 else text
            
            # 提取关键词（简单的基于频率的提取）
            words = re.findall(r'\b[a-zA-Z\u4e00-\u9fa5]{2,}\b', text.lower())
            word_freq = {}
            for word in words:
                if len(word) > 2:  # 只统计长度大于2的词
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # 取频率最高的10个词作为关键词
            keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            keywords_str = ','.join([k[0] for k in keywords])
            
            return {
                'title': title[:100],
                'description': description[:200],
                'keywords': keywords_str[:200]
            }
            
        except Exception as e:
            logger.error(f"[Pagtive元数据] 生成默认metadata失败: {str(e)}")
            return {
                'title': page_title or '未命名页面',
                'description': '',
                'keywords': ''
            }