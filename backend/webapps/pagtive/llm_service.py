"""
Pagtive LLM服务封装
处理Pagtive特定的LLM调用逻辑
"""

import json
import logging
import time
from typing import Dict, List, Optional, Any
from django.conf import settings
from llm.llm_service import LLMService
from router.models import LLMModel
from .prompts import get_generate_page_prompts, get_edit_page_prompts, parse_llm_response, SYSTEM_PROMPTS

logger = logging.getLogger(__name__)


class PagtiveLLMService:
    """
    Pagtive专用的LLM服务封装
    """
    
    def __init__(self):
        self.llm_service = LLMService()
    
    def _extract_provider_from_endpoint(self, endpoint: str) -> str:
        """从endpoint URL中提取provider名称"""
        if 'openai.com' in endpoint or 'openai.azure.com' in endpoint:
            return 'openai'
        elif 'anthropic.com' in endpoint:
            return 'anthropic'
        elif 'dashscope.aliyuncs.com' in endpoint:
            return 'qwen'
        elif 'aip.baidubce.com' in endpoint:
            return 'baidu'
        elif 'googleapis.com' in endpoint:
            return 'google'
        else:
            # 尝试从路径中提取
            import re
            match = re.search(r'/v1/([^/]+)/', endpoint)
            if match:
                return match.group(1)
            return 'unknown'
        
    def get_pagtive_llm_config(self, scenario: str = 'generatePageCode') -> Dict[str, Any]:
        """
        获取Pagtive专用的LLM配置
        优先使用激活的PagtiveConfig配置，如果没有则使用默认配置
        
        Args:
            scenario: 场景类型，'generatePageCode' 或 'editPageCode'
            
        Returns:
            包含model_name, endpoint, api_key, prompts等配置的字典
        """
        from .models import PagtiveConfig
        
        try:
            # 获取激活的Pagtive配置
            active_config = PagtiveConfig.objects.filter(is_active=True).first()
            
            if active_config:
                # 根据场景选择不同的模型
                if scenario == 'editPageCode' and active_config.llm_model_for_edit:
                    llm_model = active_config.llm_model_for_edit
                else:
                    llm_model = active_config.llm_model
                
                if llm_model:
                    # 构建参数
                    params = {
                        'temperature': active_config.temperature,
                        'stream': active_config.enable_stream
                    }
                    
                    # 只有在配置了max_tokens时才添加
                    if active_config.max_tokens is not None:
                        params['max_tokens'] = active_config.max_tokens
                    
                    # 合并额外配置
                    if active_config.extra_config:
                        params.update(active_config.extra_config)
                    
                    # 如果模型本身有参数，也合并进来
                    if llm_model.params:
                        params.update(llm_model.params)
                    
                    config = {
                        'model_name': llm_model.name,
                        'model_id': llm_model.model_id,
                        'params': params,
                        # 添加提示词覆盖配置
                        'custom_prompts': {
                            'system_prompt': active_config.system_prompt if active_config.system_prompt else None,
                            'generate_template': active_config.generate_template if active_config.generate_template else None,
                            'edit_template': active_config.edit_template if active_config.edit_template else None,
                        },
                        # 添加模板配置
                        'prompt_templates': list(active_config.prompt_templates.filter(
                            is_active=True
                        ).order_by('template_type', 'order').values(
                            'name', 'template_type', 'template_content', 'variables'
                        )) if active_config else []
                    }
                    
                    logger.info(f"[Pagtive配置] 使用激活配置: {active_config.name}, 模型: {llm_model.name}")
                    return config
            
            # 如果没有激活的配置，尝试使用通用LLM模型
            llm_models = LLMModel.objects.filter(
                description__icontains='pagtive'
            ).first()
            
            if not llm_models:
                # 如果没有Pagtive专用模型，查找通用模型
                llm_models = LLMModel.objects.filter(
                    model_type='text'
                ).first()
            
            if llm_models:
                logger.info(f"[Pagtive配置] 使用通用LLM模型: {llm_models.name}")
                return {
                    'model_name': llm_models.name,
                    'model_id': llm_models.model_id,
                    'endpoint': llm_models.endpoint.endpoint,
                    'api_key': llm_models.endpoint.vendorapikey_set.first().api_key if llm_models.endpoint.vendorapikey_set.exists() else '',
                    'custom_headers': llm_models.custom_headers or {},
                    'params': llm_models.params or {},
                    'custom_prompts': {},
                    'prompt_templates': []
                }
            
        except Exception as e:
            logger.warning(f"从数据库获取Pagtive配置失败: {e}")
        
        # 使用默认配置 - 与旧系统兼容
        logger.info("[Pagtive配置] 使用默认配置")
        return {
            'model_name': 'gpt-4',
            'model_id': 'gpt-4',
            'endpoint': getattr(settings, 'DEFAULT_LLM_ENDPOINT', 'https://api.openai.com/v1/chat/completions'),
            'api_key': getattr(settings, 'DEFAULT_LLM_API_KEY', ''),
            'custom_headers': {},
            'params': {
                'temperature': 0.7,
                # 默认不设置max_tokens，让模型自行决定
                'stream': False
            },
            'custom_prompts': {},
            'prompt_templates': []
        }
    
    def generate_page_content(self, 
        project_data: Dict[str, Any],
        prompt: str,
        template: str,
        references: List[Dict[str, Any]] = None,
        images: List[Dict[str, Any]] = None,
        current: Dict[str, Any] = None,
        user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        生成或编辑页面内容
        
        Args:
            project_data: 项目数据，包含project_name, project_description等
            prompt: 用户输入的需求描述
            template: 'generatePageCode' 或 'editPageCode'
            references: 参考页面列表
            images: 图片列表
            current: 当前页面内容（编辑模式时使用）
            
        Returns:
            包含html, styles, script, mermaidContent的字典
        """
        logger.info("=" * 80 + "\n" +
                   "[Pagtive LLM] 开始生成页面内容\n" +
                   f"[Pagtive LLM] 场景类型: {template}\n" +
                   f"[Pagtive LLM] 用户输入提示词: {prompt}\n" +
                   f"[Pagtive LLM] 项目数据: {project_data}\n" +
                   f"[Pagtive LLM] 参考页面数量: {len(references) if references else 0}\n" +
                   f"[Pagtive LLM] 图片数量: {len(images) if images else 0}")
        if current:
            logger.info(f"[Pagtive LLM] 当前页面内容 - HTML: {len(current.get('html', ''))}字符, CSS: {len(current.get('styles', ''))}字符, JS: {len(current.get('script', ''))}字符")
        
        try:
            # 获取LLM配置
            llm_config = self.get_pagtive_llm_config(scenario=template)
            logger.info(f"[Pagtive LLM] 获取到配置: 模型={llm_config.get('model_name')}, 温度={llm_config.get('params', {}).get('temperature')}, max_tokens={llm_config.get('params', {}).get('max_tokens', '无限制')}")
            
            # 处理参考页面内容
            aggregated_reference_html = ''
            aggregated_reference_css = ''
            aggregated_reference_js = ''
            
            if references:
                for ref in references:
                    page_name = ref.get('pageName', ref.get('pageId', ''))
                    if ref.get('html'):
                        aggregated_reference_html += f"\n\n/* 参考页面 {page_name} 的 HTML: */\n{ref['html']}"
                    if ref.get('styles'):
                        aggregated_reference_css += f"\n\n/* 参考页面 {page_name} 的 CSS: */\n{ref['styles']}"
                    if ref.get('script'):
                        aggregated_reference_js += f"\n\n/* 参考页面 {page_name} 的 JS: */\n{ref['script']}"
            
            # 处理图片信息 - 与旧系统保持一致
            if images:
                # 分离参考图片和插入图片
                insert_images = [img for img in images if not img.get('isReference')]
                
                # 将插入图片添加到提示词
                if insert_images:
                    image_refs = '\n'.join([
                        f"图片 {img['alias']} 的URL是 {img.get('url', '')}"
                        for img in insert_images
                    ])
                    prompt = f"{prompt}\n\n可用的图片资源：\n{image_refs}"
            
            # 构建提示词
            logger.info("[Pagtive LLM] 开始构建提示词...")
            # 首先检查是否有自定义提示词
            custom_prompts = llm_config.get('custom_prompts', {})
            
            if template == 'editPageCode':
                # 检查是否有自定义编辑模板
                if custom_prompts.get('edit_template'):
                    # 使用自定义模板，进行变量替换
                    user_prompt = custom_prompts['edit_template']
                    # 替换变量
                    replacements = {
                        'projectStyle': project_data.get('project_style', ''),
                        'globalStyleCode': project_data.get('global_style_code', ''),
                        'projectDescription': project_data.get('project_description', ''),
                        'currentHtml': current.get('html', '') if current else '',
                        'currentCss': current.get('styles', '') if current else '',
                        'currentJs': current.get('script', '') if current else '',
                        'currentMermaid': current.get('currentMermaid', '') if current else '',
                        'referenceHtml': aggregated_reference_html,
                        'referenceCss': aggregated_reference_css,
                        'referenceJs': aggregated_reference_js,
                        'requirement': prompt
                    }
                    for key, value in replacements.items():
                        user_prompt = user_prompt.replace(f'{{{{{key}}}}}', str(value))
                    
                    # 构建提示词列表
                    prompts = [
                        {
                            'role': 'system',
                            'content': custom_prompts.get('system_prompt') or SYSTEM_PROMPTS['defaultAssistant']
                        },
                        {
                            'role': 'user',
                            'content': user_prompt
                        }
                    ]
                else:
                    # 使用默认模板
                    prompts = get_edit_page_prompts(
                        project_style=project_data.get('project_style', ''),
                        global_style_code=project_data.get('global_style_code', ''),
                        project_description=project_data.get('project_description', ''),
                        current_html=current.get('html', '') if current else '',
                        current_css=current.get('styles', '') if current else '',
                        current_js=current.get('script', '') if current else '',
                        current_mermaid=current.get('currentMermaid', '') if current else '',
                        reference_html=aggregated_reference_html,
                        reference_css=aggregated_reference_css,
                        reference_js=aggregated_reference_js,
                        requirement=prompt
                    )
            else:
                # 检查是否有自定义生成模板
                if custom_prompts.get('generate_template'):
                    # 使用自定义模板，进行变量替换
                    user_prompt = custom_prompts['generate_template']
                    # 替换变量
                    replacements = {
                        'projectStyle': project_data.get('project_style', ''),
                        'globalStyleCode': project_data.get('global_style_code', ''),
                        'projectDescription': project_data.get('project_description', ''),
                        'referenceHtml': aggregated_reference_html,
                        'referenceCss': aggregated_reference_css,
                        'referenceJs': aggregated_reference_js,
                        'requirement': prompt
                    }
                    for key, value in replacements.items():
                        user_prompt = user_prompt.replace(f'{{{{{key}}}}}', str(value))
                    
                    # 构建提示词列表
                    prompts = [
                        {
                            'role': 'system',
                            'content': custom_prompts.get('system_prompt') or SYSTEM_PROMPTS['defaultAssistant']
                        },
                        {
                            'role': 'user',
                            'content': user_prompt
                        }
                    ]
                else:
                    # 使用默认模板
                    prompts = get_generate_page_prompts(
                        project_style=project_data.get('project_style', ''),
                        global_style_code=project_data.get('global_style_code', ''),
                        project_description=project_data.get('project_description', ''),
                        reference_html=aggregated_reference_html,
                        reference_css=aggregated_reference_css,
                        reference_js=aggregated_reference_js,
                        requirement=prompt
                    )
            
            # 调用LLM
            logger.info(f"[Pagtive LLM] 开始调用LLM - 模板: {template}\n" +
                       f"[Pagtive LLM] 构建的提示词消息:")
            for i, msg in enumerate(prompts):
                logger.info(f"  消息{i+1} - role: {msg.get('role')}, content长度: {len(msg.get('content', ''))}字符\n" +
                           f"  消息{i+1}内容: {msg.get('content', '')}")
            
            start_time = time.time()
            
            # 构建请求payload
            payload = {
                'messages': prompts,
                'model': llm_config['model_id'],
                **llm_config.get('params', {})
            }
            logger.info(f"[Pagtive LLM] 请求payload参数: {json.dumps({k: v for k, v in payload.items() if k != 'messages'}, ensure_ascii=False)}")
            
            # 调用LLM服务 - 使用内部LLM服务，它会自动处理API密钥查找
            from llm.llm_service import LLMService
            from authentication.models import User
            
            llm = LLMService()
            
            # 获取用户对象（如果传入了user_id）
            user = None
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    logger.warning(f"用户不存在: user_id={user_id}")
            
            # 先获取模型配置，无论哪个分支都需要
            from llm.config_manager import ModelConfigManager
            config_manager = ModelConfigManager()
            model_config = config_manager.get_model_config(llm_config['model_name'])
            
            if user:
                # 使用内部服务调用LLM（需要用户对象）
                response = llm.internal.call_llm(
                    model_name=llm_config['model_name'],
                    messages=prompts,
                    user=user,
                    record_qa=False,  # Pagtive有自己的日志记录，不需要记录到QA
                    **llm_config.get('params', {})
                )
            else:
                # 直接使用核心服务（不需要用户对象）
                from llm.core_service import CoreLLMService
                
                core_service = CoreLLMService()
                
                # 调用核心服务
                response = core_service.call_llm(
                    model_id=model_config['model_id'],
                    endpoint=model_config['endpoint'],
                    api_key=model_config['api_key'],
                    messages=prompts,
                    custom_headers=model_config.get('custom_headers', {}),
                    params={**model_config.get('params', {}), **llm_config.get('params', {})}
                )
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[Pagtive LLM] LLM调用完成 - 耗时: {duration_ms}ms\n" +
                       f"[Pagtive LLM] 响应数据: {json.dumps({k: v for k, v in response.items() if k not in ['choices', 'content']}, ensure_ascii=False)}")
            
            # 检查错误
            if 'error' in response:
                logger.error(f"[Pagtive LLM] LLM调用失败: {response['error']}")
                raise Exception(f"LLM调用失败: {response['error']}")
            
            # 解析响应
            response_content = response.get('content', '')
            if not response_content and 'choices' in response:
                # 标准OpenAI格式响应
                choices = response.get('choices', [])
                if choices:
                    response_content = choices[0].get('message', {}).get('content', '')
            
            logger.info(f"[Pagtive LLM] 收到LLM响应，长度: {len(response_content)}字符\n" +
                       f"[Pagtive LLM] 响应内容: {response_content}")
            
            # 解析代码块
            logger.info("[Pagtive LLM] 开始解析响应中的代码块...")
            parsed_content = parse_llm_response(response_content)
            
            # 添加额外信息
            parsed_content['raw_response'] = response_content
            parsed_content['duration_ms'] = duration_ms
            parsed_content['usage'] = response.get('usage', {})
            
            # 添加模型信息，供日志记录使用
            parsed_content['model_info'] = {
                'model_name': llm_config.get('model_name', 'unknown'),
                'model_id': model_config.get('model_id', llm_config.get('model_id', 'unknown')),
                'provider': self._extract_provider_from_endpoint(model_config.get('endpoint', '')),
                'endpoint': model_config.get('endpoint', '')
            }
            
            logger.info(f"[Pagtive LLM] 解析结果:\n" +
                       f"  - HTML: {len(parsed_content.get('html', ''))}字符\n" +
                       f"  - CSS: {len(parsed_content.get('styles', ''))}字符\n" +
                       f"  - JavaScript: {len(parsed_content.get('script', ''))}字符\n" +
                       f"  - Mermaid: {len(parsed_content.get('mermaidContent', ''))}字符\n" +
                       f"  - 使用模型: {parsed_content['model_info']['model_name']}\n" +
                       f"[Pagtive LLM] 生成完成，总耗时: {duration_ms}ms\n" +
                       "=" * 80)
            
            return parsed_content
            
        except Exception as e:
            # 获取友好的错误描述
            from llm.retry_utils import LLMRetryHandler
            error_desc, is_retryable = LLMRetryHandler.get_error_description(e)
            
            # 使用info级别记录，避免过多ERROR日志
            logger.info(f"[Pagtive LLM] 页面内容生成遇到问题: {error_desc}")
            
            # 如果是API限流或临时故障，提供降级建议
            if 'rate limit' in str(e).lower() or 'quota' in str(e).lower():
                logger.info("[Pagtive LLM] 建议：当前API调用频率过高，请稍后重试或考虑使用备用模型")
                raise Exception(f"{error_desc}。建议稍后重试或联系管理员切换备用模型")
            elif '401' in str(e) or 'unauthorized' in str(e).lower():
                logger.info("[Pagtive LLM] 建议：API密钥可能已失效，请联系管理员更新配置")
                raise Exception(f"{error_desc}。请联系管理员检查API配置")
            elif is_retryable:
                logger.info("[Pagtive LLM] 建议：这是临时性网络问题，已自动重试但仍未成功")
                raise Exception(f"{error_desc}。这可能是临时性问题，请稍后重试")
            else:
                # 不可重试的错误，直接传递
                raise Exception(error_desc)
    
    def generate_outline(self, project_name: str, project_description: str, 
                        project_style: str = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        生成项目大纲
        
        Args:
            project_name: 项目名称
            project_description: 项目描述
            project_style: 项目风格
            user_id: 用户ID
            
        Returns:
            包含pages列表的字典
        """
        logger.info("=" * 80 + "\n" +
                   "[Pagtive LLM] 开始生成项目大纲\n" +
                   f"[Pagtive LLM] 项目名称: {project_name}\n" +
                   f"[Pagtive LLM] 项目描述: {project_description}\n" +
                   f"[Pagtive LLM] 项目风格: {project_style}")
        
        try:
            # 获取LLM配置
            llm_config = self.get_pagtive_llm_config(scenario='generateOutline')
            logger.info(f"[Pagtive LLM] 使用模型: {llm_config.get('model_name')}")
            
            # 构建大纲生成的提示词
            system_prompt = """你是一位专业的网页项目规划师。你的任务是根据用户提供的项目描述，生成一个结构清晰、逻辑合理的项目页面大纲。

要求：
1. 根据项目描述生成合适的页面列表
2. 每个页面都应该有明确的目的和内容定位
3. 页面数量要适中（通常3-8个页面）
4. 页面名称要简洁明了
5. 考虑用户体验和信息架构
6. 为每个页面提供3-5个关键要点

请以JSON格式返回，格式如下：
```json
{
  "pages": [
    {
      "id": "1",
      "title": "页面标题", 
      "description": "页面描述",
      "keyPoints": ["要点1", "要点2", "要点3"],
      "order": 1
    },
    {
      "id": "2",
      "title": "页面标题",
      "description": "页面描述", 
      "keyPoints": ["要点1", "要点2", "要点3"],
      "order": 2
    }
  ]
}
```"""
            
            user_prompt = f"""请为以下项目生成页面大纲：

项目名称：{project_name}
项目描述：{project_description}
"""
            
            if project_style:
                user_prompt += f"项目风格：{project_style}\n"
            
            user_prompt += """
请根据项目的特点，生成合适的页面结构。确保页面之间有良好的逻辑关系，能够完整地展现项目内容。
"""
            
            prompts = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ]
            
            logger.info("[Pagtive LLM] 开始调用LLM生成大纲")
            start_time = time.time()
            
            # 获取模型配置
            from llm.config_manager import ModelConfigManager
            config_manager = ModelConfigManager()
            model_config = config_manager.get_model_config(llm_config['model_name'])
            
            # 获取用户对象
            user = None
            if user_id:
                try:
                    from authentication.models import User
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    logger.warning(f"用户不存在: user_id={user_id}")
            
            # 调用LLM
            if user:
                # 使用内部服务
                # 合并参数，避免重复的temperature
                call_params = {'temperature': 0.7}
                call_params.update(llm_config.get('params', {}))
                
                response = self.llm_service.internal.call_llm(
                    model_name=llm_config['model_name'],
                    messages=prompts,
                    user=user,
                    record_qa=False,
                    **call_params
                )
            else:
                # 使用核心服务
                from llm.core_service import CoreLLMService
                core_service = CoreLLMService()
                
                response = core_service.call_llm(
                    model_id=model_config['model_id'],
                    endpoint=model_config['endpoint'],
                    api_key=model_config['api_key'],
                    messages=prompts,
                    custom_headers=model_config.get('custom_headers', {}),
                    params={'temperature': 0.7, **model_config.get('params', {}), **llm_config.get('params', {})}
                )
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[Pagtive LLM] 大纲生成完成 - 耗时: {duration_ms}ms")
            
            # 提取响应内容
            response_content = response.get('content', '')
            if not response_content and 'choices' in response:
                choices = response.get('choices', [])
                if choices:
                    response_content = choices[0].get('message', {}).get('content', '')
            
            logger.info(f"[Pagtive LLM] 收到响应: {response_content}")
            
            # 解析JSON响应
            import re
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_content)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response_content
            
            try:
                outline_data = json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning("[Pagtive LLM] 无法解析JSON响应，使用默认大纲")
                # 生成默认大纲
                outline_data = {
                    'pages': [
                        {'id': '1', 'title': '首页', 'description': '项目介绍和概览', 'keyPoints': ['项目简介', '核心价值', '快速开始'], 'order': 1},
                        {'id': '2', 'title': '详情', 'description': '详细内容展示', 'keyPoints': ['功能特性', '技术优势', '应用场景'], 'order': 2},
                        {'id': '3', 'title': '关于', 'description': '相关信息', 'keyPoints': ['团队介绍', '联系方式', '更多资源'], 'order': 3}
                    ]
                }
            
            # 确保pages字段存在
            if 'pages' not in outline_data:
                outline_data = {'pages': outline_data} if isinstance(outline_data, list) else {'pages': []}
            
            # 为每个页面添加必要的字段
            for i, page in enumerate(outline_data['pages']):
                if 'order' not in page:
                    page['order'] = (i + 1) * 100
                if 'description' not in page:
                    page['description'] = ''
                # 添加ID字段
                if 'id' not in page:
                    page['id'] = str(i + 1)
                # 确保有keyPoints字段
                if 'keyPoints' not in page:
                    page['keyPoints'] = ['要点1', '要点2', '要点3']
            
            logger.info(f"[Pagtive LLM] 生成大纲包含 {len(outline_data['pages'])} 个页面\n" +
                       "=" * 80)
            
            return outline_data
            
        except Exception as e:
            logger.error(f"[Pagtive LLM] 生成大纲失败: {str(e)}")
            # 返回默认大纲
            return {
                'pages': [
                    {'id': '1', 'title': '首页', 'description': '项目主页', 'keyPoints': ['项目介绍', '核心功能', '快速导航'], 'order': 100},
                    {'id': '2', 'title': '内容', 'description': '主要内容', 'keyPoints': ['详细说明', '功能展示', '案例分析'], 'order': 200}
                ]
            }