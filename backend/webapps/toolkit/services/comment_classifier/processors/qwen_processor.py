"""
Qwen AI处理器
使用 backend.llm.core_service 进行LLM调用
"""
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from .base_processor import BaseAIProcessor

logger = logging.getLogger(__name__)


class QwenProcessor(BaseAIProcessor):
    """
    阿里Qwen模型处理器
    通过 core_service 调用 LLM
    """
    
    def __init__(self, config: Any):
        super().__init__(config)
        
        # 从配置获取LLM相关参数
        self.llm_config = config.get_llm_config()
        
        # 初始化 core_service
        from backend.llm.core_service import CoreLLMService
        self.core_service = CoreLLMService()
        
        # 并发控制
        self.max_concurrent = config.max_concurrent
        self.requests_per_second = config.requests_per_second
        self.rate_limiter = asyncio.Semaphore(self.max_concurrent)
        
        # 日志配置
        self.enable_logging = config.enable_llm_logs
        
        logger.info(f"QwenProcessor 初始化完成: 模型={self.llm_config['model_id']}, 并发={self.max_concurrent}")
    
    async def process_single(self, content: str) -> Dict[str, Any]:
        """
        处理单条内容
        
        Args:
            content: 待分类的内容
            
        Returns:
            处理结果，包含分类路径和相关信息
        """
        try:
            # 构建分类提示词
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(content)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # 调用 core_service（同步方法，需要在线程中运行）
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self._call_llm_sync,
                messages
            )
            
            # 解析响应
            result = self._parse_response(response, content)
            return result
            
        except Exception as e:
            logger.error(f"处理单条内容失败: {str(e)}")
            return {
                'content': content,
                'category_path': None,
                'keywords': [],
                'reason': f'处理失败: {str(e)}',
                'ai_steps': {}
            }
    
    def _call_llm_sync(self, messages: List[Dict]) -> Dict:
        """
        同步调用 LLM（供异步方法使用）
        """
        return self.core_service.call_llm(
            messages=messages,
            enable_logging=self.enable_logging,
            source_app='toolkit',
            source_function='comment_classifier.qwen_processor',
            **self.llm_config
        )
    
    async def process_batch(self, contents: List[str]) -> List[Dict[str, Any]]:
        """
        批量处理内容
        
        Args:
            contents: 待处理内容列表
            
        Returns:
            处理结果列表
        """
        logger.info(f"开始批量处理 {len(contents)} 条内容")
        
        tasks = []
        for i, content in enumerate(contents):
            task = self._process_with_rate_limit(content, i)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        logger.info(f"批量处理完成，成功分类 {sum(1 for r in results if r.get('category_path'))} 条")
        return results
    
    async def _process_with_rate_limit(self, content: str, index: int) -> Dict[str, Any]:
        """带速率限制的处理"""
        async with self.rate_limiter:
            # 添加处理进度日志
            if (index + 1) % 10 == 0:
                logger.info(f"处理进度: {index + 1}")
            
            result = await self.process_single(content)
            result['index'] = index  # 保留原始索引
            return result
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        # 这里可以从配置文件加载分类体系
        return """你是一个专业的评论分类助手。请根据给定的评论内容，分析并返回最合适的分类。

分类体系：
1. 产品问题
   - 饮品相关
     - 口味问题
     - 温度问题
     - 配料问题
   - 食品相关
     - 新鲜度问题
     - 口感问题
2. 服务问题
   - 员工态度
   - 等待时间
   - 订单错误
3. 环境问题
   - 卫生状况
   - 座位安排
   - 噪音问题

请返回JSON格式的分类结果，包含以下字段：
{
    "category_path": "一级分类/二级分类/三级分类",
    "keywords": ["关键词1", "关键词2"],
    "reason": "分类理由",
    "confidence": 0.9,
    "analysis_steps": {
        "scenario": "场景分析",
        "level1_candidates": ["候选一级分类"],
        "level2_candidates": ["候选二级分类"],
        "level3_candidates": ["候选三级分类"]
    }
}

重要：
1. category_path 必须是完整的三级分类路径
2. 只返回JSON，不要包含其他解释文字
3. 如果无法明确分类，选择最可能的分类"""
    
    def _build_user_prompt(self, content: str) -> str:
        """构建用户提示词"""
        return f"请对以下评论进行分类：\n\n{content}"
    
    def _parse_response(self, response: Dict, original_content: str) -> Dict[str, Any]:
        """
        解析LLM响应
        
        Args:
            response: LLM响应
            original_content: 原始内容
            
        Returns:
            解析后的结果
        """
        try:
            # 提取响应内容
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            # 解析JSON
            result_data = self._extract_json(content)
            
            return {
                'content': original_content,
                'category_path': result_data.get('category_path'),
                'keywords': result_data.get('keywords', []),
                'reason': result_data.get('reason', ''),
                'confidence': result_data.get('confidence', 0.5),
                'ai_steps': result_data.get('analysis_steps', {})
            }
            
        except Exception as e:
            logger.error(f"解析响应失败: {str(e)}")
            return {
                'content': original_content,
                'category_path': None,
                'keywords': [],
                'reason': f'响应解析失败: {str(e)}',
                'ai_steps': {}
            }
    
    def _extract_json(self, text: str) -> Dict:
        """
        从文本中提取JSON
        
        Args:
            text: 包含JSON的文本
            
        Returns:
            解析后的字典
        """
        # 尝试直接解析
        try:
            return json.loads(text)
        except:
            pass
        
        # 尝试提取JSON块
        import re
        
        # 查找JSON对象
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                return json.loads(match)
            except:
                continue
        
        # 如果都失败，返回空字典
        logger.warning(f"无法从响应中提取JSON: {text[:200]}...")
        return {}
    
    def process_file_sync(self, input_file: str, output_file: str):
        """
        同步处理文件（供兼容旧代码使用）
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径
        """
        import json
        
        # 读取输入文件
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 提取内容
        contents = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    content = item.get('content', '')
                else:
                    content = str(item)
                contents.append(content)
        else:
            contents = [str(data)]
        
        # 异步处理
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(self.process_batch(contents))
        loop.close()
        
        # 合并原始数据和结果
        output_data = []
        for i, item in enumerate(data if isinstance(data, list) else [data]):
            if i < len(results):
                result = results[i]
                if isinstance(item, dict):
                    item.update(result)
                    output_data.append(item)
                else:
                    output_data.append(result)
        
        # 保存结果
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"处理完成，结果已保存到: {output_file}")
    
    # 兼容旧接口
    def process_unclassified_file(self, input_file: str, output_file: str):
        """兼容旧的文件处理接口"""
        self.process_file_sync(input_file, output_file)
    
    def analyze_single_content_sync(self, content: str):
        """兼容旧的单条内容处理接口"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.process_single(content))
        loop.close()
        
        # 返回旧格式的元组
        return (
            result.get('category_path'),
            result.get('keywords', []),
            result.get('reason', ''),
            result.get('ai_steps', {})
        )