"""
LLM 调用日志记录服务
负责记录每次 LLM 调用的详细信息，包括请求、响应、Token使用量等
"""

import logging
import uuid
from typing import Dict, Optional, List
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum
from django.db import OperationalError
from .models import LLMCallLog, LLMTokenUsage, LLMModelPrice
from backend.utils.db_connection import ensure_db_connection_safe

logger = logging.getLogger(__name__)


class LLMLogService:
    """LLM 日志记录服务"""
    
    @staticmethod
    def create_call_log(
        model_name: str,
        model_id: str = None,
        endpoint: str = None,
        messages: List[Dict] = None,
        params: Dict = None,
        headers: Dict = None,
        user=None,
        session_id: str = None,
        call_type: str = 'chat',
        source_app: str = None,
        source_function: str = None,
        vendor_name: str = None,
        vendor_id: str = None,
        is_stream: bool = False,
        metadata: Dict = None,
        request=None
    ) -> LLMCallLog:
        """
        创建 LLM 调用日志记录
        
        Args:
            model_name: 模型名称
            model_id: 模型标识符
            endpoint: API 端点
            messages: 请求消息列表
            params: 请求参数
            headers: 请求头
            user: 用户对象
            session_id: 会话ID
            call_type: 调用类型
            source_app: 来源应用
            source_function: 来源函数
            vendor_name: 供应商名称
            vendor_id: 供应商标识符
            is_stream: 是否流式
            metadata: 元数据
            request: HTTP 请求对象（用于获取IP和UA）
        
        Returns:
            LLMCallLog 实例
        """
        try:
            # 生成请求ID
            request_id = str(uuid.uuid4())
            
            # 获取供应商信息（如果未提供）
            if not vendor_name and endpoint:
                vendor_name, vendor_id = LLMLogService._detect_vendor(endpoint)
            
            # 获取IP和User Agent
            ip_address = None
            user_agent = None
            if request:
                ip_address = LLMLogService._get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            
            # 创建日志记录
            log_entry = LLMCallLog.objects.create(
                request_id=request_id,
                user=user,
                session_id=session_id,
                call_type=call_type,
                model_name=model_name,
                model_id=model_id or model_name,
                vendor_name=vendor_name or '',
                vendor_id=vendor_id or '',
                endpoint=endpoint or '',
                request_messages=messages or [],
                request_params=params or {},
                request_headers=headers or {},
                request_timestamp=timezone.now(),
                status='processing',
                is_stream=is_stream,
                source_app=source_app or '',
                source_function=source_function or '',
                metadata=metadata or {},
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            # logger.info(f"创建 LLM 调用日志: {request_id} - {model_name}")
            return log_entry
            
        except Exception as e:
            logger.error(f"创建 LLM 调用日志失败: {e}")
            return None
    
    @staticmethod
    def update_success(
        log_entry: LLMCallLog,
        response_content: str = None,
        response_raw: Dict = None,
        prompt_tokens: int = None,
        completion_tokens: int = None,
        total_tokens: int = None,
        usage_data: Dict = None
    ):
        """
        更新日志记录为成功状态
        
        Args:
            log_entry: 日志记录实例
            response_content: 响应内容
            response_raw: 原始响应数据
            prompt_tokens: 输入 Token 数
            completion_tokens: 输出 Token 数
            total_tokens: 总 Token 数
            usage_data: 使用数据字典（包含 token 信息）
        """
        if not log_entry:
            return
        
        try:
            # 更新响应信息
            log_entry.response_timestamp = timezone.now()
            log_entry.response_content = response_content or ''
            log_entry.response_raw = response_raw or {}
            log_entry.status = 'success'
            
            # 更新 Token 信息
            if usage_data:
                log_entry.prompt_tokens = usage_data.get('prompt_tokens') or usage_data.get('input_tokens')
                log_entry.completion_tokens = usage_data.get('completion_tokens') or usage_data.get('output_tokens')
                log_entry.total_tokens = usage_data.get('total_tokens')
            else:
                if prompt_tokens is not None:
                    log_entry.prompt_tokens = prompt_tokens
                if completion_tokens is not None:
                    log_entry.completion_tokens = completion_tokens
                if total_tokens is not None:
                    log_entry.total_tokens = total_tokens
            
            # 计算成本
            if log_entry.prompt_tokens and log_entry.completion_tokens:
                log_entry.estimated_cost = LLMLogService._calculate_cost(
                    log_entry.model_name,
                    log_entry.prompt_tokens,
                    log_entry.completion_tokens
                )
            
            log_entry.save()
            
            # 更新统计数据
            if log_entry.user:
                LLMLogService._update_token_usage(log_entry, success=True)
            
            # 更新 router.LLMModel 的调用计数
            LLMLogService._update_model_counters(log_entry.model_name, success=True)
            
            # logger.info(f"更新 LLM 调用成功: {log_entry.request_id} - Tokens: {log_entry.total_tokens}")
            
        except OperationalError as e:
            if 'client_idle_timeout' in str(e) or 'connection already closed' in str(e):
                logger.warning(f"数据库连接超时，尝试重新连接: {e}")
                # 使用强力的连接恢复函数
                ensure_db_connection_safe()
                try:
                    log_entry.save()
                    if log_entry.user:
                        LLMLogService._update_token_usage(log_entry, success=True)
                    LLMLogService._update_model_counters(log_entry.model_name, success=True)
                    logger.info(f"重试成功: {log_entry.request_id}")
                except Exception as retry_e:
                    logger.error(f"重试失败: {retry_e}")
            else:
                logger.error(f"更新 LLM 调用日志失败: {e}")
        except Exception as e:
            logger.error(f"更新 LLM 调用日志失败: {e}")
    
    @staticmethod
    def update_failure(
        log_entry: LLMCallLog,
        error_message: str,
        error_code: str = None
    ):
        """
        更新日志记录为失败状态
        
        Args:
            log_entry: 日志记录实例
            error_message: 错误信息
            error_code: 错误代码
        """
        if not log_entry:
            return
        
        try:
            log_entry.response_timestamp = timezone.now()
            log_entry.status = 'failed'
            log_entry.error_message = error_message
            log_entry.error_code = error_code or ''
            log_entry.save()
            
            # 更新统计数据
            if log_entry.user:
                LLMLogService._update_token_usage(log_entry, success=False)
            
            # 更新 router.LLMModel 的调用计数（失败也计入总调用次数）
            LLMLogService._update_model_counters(log_entry.model_name, success=False)
            
            logger.info(f"更新 LLM 调用失败: {log_entry.request_id} - {error_message}")
            
        except Exception as e:
            logger.error(f"更新 LLM 失败日志失败: {e}")
    
    @staticmethod
    def update_timeout(log_entry: LLMCallLog):
        """更新日志记录为超时状态"""
        if not log_entry:
            return
        
        try:
            log_entry.response_timestamp = timezone.now()
            log_entry.status = 'timeout'
            log_entry.error_message = '请求超时'
            log_entry.save()
            
            # 更新统计数据
            if log_entry.user:
                LLMLogService._update_token_usage(log_entry, success=False)
            
            # 更新 router.LLMModel 的调用计数（超时也计入总调用次数）
            LLMLogService._update_model_counters(log_entry.model_name, success=False)
            
            logger.info(f"更新 LLM 调用超时: {log_entry.request_id}")
            
        except Exception as e:
            logger.error(f"更新 LLM 超时日志失败: {e}")
    
    @staticmethod
    def update_retry(log_entry: LLMCallLog, attempt: int):
        """更新重试次数"""
        if not log_entry:
            return
        
        try:
            log_entry.retry_count = attempt
            log_entry.save(update_fields=['retry_count'])
        except Exception as e:
            logger.error(f"更新重试次数失败: {e}")
    
    @staticmethod
    def _detect_vendor(endpoint: str) -> tuple:
        """
        根据端点检测供应商
        
        Returns:
            (vendor_name, vendor_id) 元组
        """
        endpoint_lower = endpoint.lower()
        
        vendor_map = {
            'openai.com': ('OpenAI', 'openai'),
            'anthropic.com': ('Anthropic', 'anthropic'),
            'openrouter.ai': ('OpenRouter', 'openrouter'),
            'dashscope.aliyuncs.com': ('阿里云百炼大模型', 'aliyun'),
            'baidu.com': ('Baidu', 'baidu'),
            'moonshot.cn': ('Moonshot', 'moonshot'),
            'zhipuai.cn': ('Zhipu', 'zhipu'),
            'deepseek.com': ('DeepSeek', 'deepseek'),
        }
        
        for domain, vendor_info in vendor_map.items():
            if domain in endpoint_lower:
                return vendor_info
        
        return ('', '')
    
    @staticmethod
    def _get_client_ip(request) -> Optional[str]:
        """获取客户端真实IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def _calculate_cost(
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> Optional[float]:
        """
        计算调用成本
        
        Args:
            model_name: 模型名称
            prompt_tokens: 输入 Token 数
            completion_tokens: 输出 Token 数
        
        Returns:
            成本（USD）或 None
        """
        try:
            # 使用强力的连接恢复函数确保连接可用
            ensure_db_connection_safe()
            
            # 查找有效的定价配置
            price_config = LLMModelPrice.objects.filter(
                model_name=model_name,
                is_active=True
            ).first()
            
            if not price_config:
                # 尝试模糊匹配
                for price in LLMModelPrice.objects.filter(is_active=True):
                    if price.model_name.lower() in model_name.lower() or \
                       model_name.lower() in price.model_name.lower():
                        price_config = price
                        break
            
            if price_config:
                input_cost = (prompt_tokens / 1000) * float(price_config.input_price_per_1k)
                output_cost = (completion_tokens / 1000) * float(price_config.output_price_per_1k)
                total_cost = input_cost + output_cost
                return total_cost
            
        except OperationalError as e:
            if 'client_idle_timeout' in str(e) or 'connection already closed' in str(e):
                logger.warning(f"计算成本时数据库连接超时，尝试重连: {e}")
                # 使用强力的连接恢复函数
                ensure_db_connection_safe()
                try:
                    # 重试查询
                    price_config = LLMModelPrice.objects.filter(
                        model_name=model_name,
                        is_active=True
                    ).first()
                    
                    if not price_config:
                        for price in LLMModelPrice.objects.filter(is_active=True):
                            if price.model_name.lower() in model_name.lower() or \
                               model_name.lower() in price.model_name.lower():
                                price_config = price
                                break
                    
                    if price_config:
                        input_cost = (prompt_tokens / 1000) * float(price_config.input_price_per_1k)
                        output_cost = (completion_tokens / 1000) * float(price_config.output_price_per_1k)
                        total_cost = input_cost + output_cost
                        logger.info(f"成本计算重试成功: {model_name}")
                        return total_cost
                except Exception as retry_e:
                    logger.error(f"成本计算重试失败: {retry_e}")
            else:
                logger.error(f"计算成本失败: {e}")
        except Exception as e:
            logger.error(f"计算成本失败: {e}")
        
        return None
    
    @staticmethod
    def _update_token_usage(log_entry: LLMCallLog, success: bool = True):
        """
        更新 Token 使用统计
        
        Args:
            log_entry: 日志记录实例
            success: 是否成功
        """
        try:
            # 在长时间LLM调用后，主动关闭可能超时的连接
            ensure_db_connection_safe()
            now = timezone.now()
            today = now.date()
            current_hour = now.hour
            
            # 更新每日统计
            daily_usage, created = LLMTokenUsage.objects.get_or_create(
                user=log_entry.user,
                model_name=log_entry.model_name,
                date=today,
                period='daily',
                defaults={
                    'vendor_name': log_entry.vendor_name,
                    'hour': None
                }
            )
            
            daily_usage.call_count += 1
            if success:
                daily_usage.success_count += 1
            else:
                daily_usage.failed_count += 1
            
            if log_entry.prompt_tokens:
                daily_usage.total_prompt_tokens += log_entry.prompt_tokens
            if log_entry.completion_tokens:
                daily_usage.total_completion_tokens += log_entry.completion_tokens
            if log_entry.total_tokens:
                daily_usage.total_tokens += log_entry.total_tokens
            if log_entry.estimated_cost:
                daily_usage.total_cost += log_entry.estimated_cost
            
            # 更新平均耗时
            if log_entry.duration_ms and success:
                if daily_usage.avg_duration_ms:
                    # 增量平均
                    daily_usage.avg_duration_ms = int(
                        (daily_usage.avg_duration_ms * (daily_usage.success_count - 1) + 
                         log_entry.duration_ms) / daily_usage.success_count
                    )
                else:
                    daily_usage.avg_duration_ms = log_entry.duration_ms
            
            daily_usage.save()
            
            # 更新小时统计
            hourly_usage, created = LLMTokenUsage.objects.get_or_create(
                user=log_entry.user,
                model_name=log_entry.model_name,
                date=today,
                hour=current_hour,
                period='hourly',
                defaults={
                    'vendor_name': log_entry.vendor_name
                }
            )
            
            hourly_usage.call_count += 1
            if success:
                hourly_usage.success_count += 1
            else:
                hourly_usage.failed_count += 1
            
            if log_entry.prompt_tokens:
                hourly_usage.total_prompt_tokens += log_entry.prompt_tokens
            if log_entry.completion_tokens:
                hourly_usage.total_completion_tokens += log_entry.completion_tokens
            if log_entry.total_tokens:
                hourly_usage.total_tokens += log_entry.total_tokens
            if log_entry.estimated_cost:
                hourly_usage.total_cost += log_entry.estimated_cost
            
            hourly_usage.save()
            
        except Exception as e:
            logger.error(f"更新 Token 使用统计失败: {e}")
    
    @staticmethod
    def _update_model_counters(model_name: str, success: bool = True):
        """
        更新 router.LLMModel 表中的调用计数
        
        Args:
            model_name: 模型名称
            success: 是否成功
        """
        from router.models import LLMModel
        from django.db.models import F
        
        try:
            # 在长时间LLM调用后，主动关闭可能超时的连接
            ensure_db_connection_safe()
            # 尝试通过 name 字段查找模型
            try:
                model = LLMModel.objects.get(name=model_name)
            except LLMModel.DoesNotExist:
                # 如果通过 name 找不到，尝试通过 model_id 查找
                try:
                    model = LLMModel.objects.get(model_id=model_name)
                except LLMModel.DoesNotExist:
                    logger.warning(f"找不到模型 '{model_name}' 来更新计数")
                    return
            
            # 更新调用次数
            model.call_count = F('call_count') + 1
            if success:
                model.success_count = F('success_count') + 1
            
            model.save(update_fields=['call_count', 'success_count'])
            # logger.debug(f"更新模型 '{model_name}' 的调用计数")
            
        except Exception as e:
            logger.error(f"更新模型 '{model_name}' 调用计数失败: {e}")
    
    @staticmethod
    def get_user_usage_summary(user, days: int = 30) -> Dict:
        """
        获取用户使用摘要
        
        Args:
            user: 用户对象
            days: 统计天数
        
        Returns:
            使用摘要字典
        """
        try:
            start_date = timezone.now().date() - timedelta(days=days)
            
            # 获取汇总数据
            summary = LLMTokenUsage.objects.filter(
                user=user,
                date__gte=start_date,
                period='daily'
            ).aggregate(
                total_calls=Sum('call_count'),
                total_success=Sum('success_count'),
                total_failed=Sum('failed_count'),
                total_tokens=Sum('total_tokens'),
                total_cost=Sum('total_cost')
            )
            
            # 获取模型分组数据
            model_stats = LLMTokenUsage.objects.filter(
                user=user,
                date__gte=start_date,
                period='daily'
            ).values('model_name').annotate(
                calls=Sum('call_count'),
                tokens=Sum('total_tokens'),
                cost=Sum('total_cost')
            ).order_by('-calls')[:10]
            
            return {
                'total_calls': summary['total_calls'] or 0,
                'total_success': summary['total_success'] or 0,
                'total_failed': summary['total_failed'] or 0,
                'total_tokens': summary['total_tokens'] or 0,
                'total_cost': float(summary['total_cost'] or 0),
                'success_rate': (summary['total_success'] or 0) / (summary['total_calls'] or 1) * 100,
                'top_models': list(model_stats)
            }
            
        except Exception as e:
            logger.error(f"获取用户使用摘要失败: {e}")
            return {}