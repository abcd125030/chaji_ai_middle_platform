import hashlib
import time
import json
import uuid
import requests
from decimal import Decimal
from urllib.parse import urlencode, unquote_plus
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging

from .models import PaymentOrder, PaymentCallback, PaymentConfig, PaymentLog

logger = logging.getLogger(__name__)  # 使用模块名作为 logger 名称


def ksort(d):
    """字典按键排序"""
    return [(k, d[k]) for k in sorted(d.keys())]


class PaymentService:
    """支付服务基类"""
    
    def create_order(self, user, payment_method, amount, title, **kwargs):
        """创建支付订单"""
        raise NotImplementedError
    
    def query_order(self, order_id):
        """查询订单状态"""
        raise NotImplementedError
    
    def process_callback(self, data, callback_type='notify'):
        """处理支付回调"""
        raise NotImplementedError
    
    def verify_signature(self, data):
        """验证签名"""
        raise NotImplementedError


class HupijiaoPaymentService(PaymentService):
    """虎皮椒支付服务"""
    
    def __init__(self):
        # 获取配置
        try:
            config = PaymentConfig.objects.get(provider='hupijiao', is_active=True)
            self.appid = config.app_id
            self.app_secret = config.app_secret
            self.api_url = config.api_url or "https://api.xunhupay.com/payment/do.html"
            self.is_test_mode = config.is_test_mode
            self.extra_config = config.extra_config or {}
        except PaymentConfig.DoesNotExist:
            logger.error("虎皮椒支付配置不存在或未激活")
            raise ValueError("支付配置未找到，请联系管理员")
    
    def sign(self, attributes):
        """生成签名"""
        attributes = ksort(attributes)
        m = hashlib.md5()
        sign_str = unquote_plus(urlencode(attributes)) + self.app_secret
        m.update(sign_str.encode('utf-8'))
        sign = m.hexdigest()
        logger.debug(f"签名字符串: {sign_str}, 签名结果: {sign}")
        return sign
    
    def verify_signature(self, data):
        """验证签名"""
        if 'hash' not in data:
            return False
        
        received_hash = data.pop('hash')
        calculated_hash = self.sign(data)
        data['hash'] = received_hash  # 恢复原始数据
        
        return received_hash == calculated_hash
    
    def create_order(self, user, payment_method, amount, title, **kwargs):
        """创建支付订单"""
        # 生成订单号
        order_id = f"PAY{int(time.time())}{uuid.uuid4().hex[:8].upper()}"
        
        # 获取前端URL（必需）
        frontend_url = kwargs.get('frontend_url')
        if not frontend_url:
            raise ValueError("frontend_url 参数是必需的")
        
        # 设置回调地址
        notify_url = kwargs.get('notify_url', f"{settings.BACKEND_API_URL}/api/payment/callback/notify/")
        return_url = kwargs.get('return_url', f"{frontend_url}/payment/success")
        callback_url = kwargs.get('callback_url', f"{frontend_url}/payment/fail")
        
        # 创建本地订单
        order = PaymentOrder.objects.create(
            order_id=order_id,
            user=user,
            payment_method=payment_method,
            amount=amount,
            title=title,
            description=kwargs.get('description', ''),
            product_id=kwargs.get('product_id', ''),
            notify_url=notify_url,
            return_url=return_url,
            expired_at=timezone.now() + timedelta(minutes=30),  # 30分钟过期
            extra_data={
                'user_id': str(user.id),
                'username': user.username,
                'frontend_url': frontend_url,
            }
        )
        
        # 记录日志
        PaymentLog.objects.create(
            order=order,
            log_type='request',
            message='创建支付订单',
            data={
                'order_id': order_id,
                'payment_method': payment_method,
                'amount': str(amount),
                'title': title
            }
        )
        
        # 调用虎皮椒接口
        try:
            # 准备请求数据
            request_data = {
                "version": "1.1",
                "lang": "zh-cn",
                "plugins": "django",
                "appid": self.appid,
                "trade_order_id": order_id,
                "payment": payment_method,
                "is_app": "Y",
                "total_fee": str(amount),
                "title": title,
                "description": kwargs.get('description', ''),
                "time": str(int(time.time())),
                "notify_url": notify_url,
                "return_url": return_url,
                "callback_url": callback_url,
                "nonce_str": str(int(time.time() * 1000)),  # 毫秒时间戳作为随机字符串
            }
            
            # 添加签名
            request_data['hash'] = self.sign(request_data)
            
            # 发送请求
            headers = {"Referer": frontend_url}
            response = requests.post(
                self.api_url,
                data=request_data,
                headers=headers,
                timeout=30
            )
            
            # 记录响应日志
            PaymentLog.objects.create(
                order=order,
                log_type='response',
                message='虎皮椒接口响应',
                data={
                    'status_code': response.status_code,
                    'response': response.text[:1000]  # 限制长度
                }
            )
            
            # 解析响应
            if response.status_code == 200:
                result = response.json()
                
                if result.get('errcode') == 0 or result.get('url'):
                    # 更新订单信息
                    order.payment_url = result.get('url', '')
                    order.qrcode_url = result.get('url_qrcode', '')
                    order.trade_order_id = result.get('transaction_id', '')
                    order.status = 'processing'
                    order.save()
                    
                    return {
                        'success': True,
                        'order_id': order_id,
                        'payment_url': order.payment_url,
                        'qrcode_url': order.qrcode_url,
                        'amount': str(amount),
                        'expire_time': order.expired_at.isoformat()
                    }
                else:
                    # 支付创建失败
                    error_msg = result.get('errmsg', '支付创建失败')
                    order.status = 'failed'
                    order.extra_data['error'] = error_msg
                    order.save()
                    
                    PaymentLog.objects.create(
                        order=order,
                        log_type='error',
                        message='支付创建失败',
                        data=result,
                        error_code=str(result.get('errcode', ''))
                    )
                    
                    return {
                        'success': False,
                        'error': error_msg,
                        'order_id': order_id
                    }
            else:
                raise Exception(f"HTTP请求失败: {response.status_code}")
                
        except Exception as e:
            logger.error(f"创建支付订单失败: {str(e)}")
            
            # 更新订单状态
            order.status = 'failed'
            order.extra_data['error'] = str(e)
            order.save()
            
            # 记录错误日志
            PaymentLog.objects.create(
                order=order,
                log_type='error',
                message='支付订单创建异常',
                data={'error': str(e)},
                error_code='SYSTEM_ERROR'
            )
            
            return {
                'success': False,
                'error': '支付服务暂时不可用，请稍后重试',
                'order_id': order_id
            }
    
    def query_order(self, order_id):
        """查询订单状态"""
        try:
            order = PaymentOrder.objects.get(order_id=order_id)
            
            return {
                'success': True,
                'order_id': order_id,
                'status': order.status,
                'amount': str(order.amount),
                'payment_method': order.payment_method,
                'title': order.title,
                'created_at': order.created_at.isoformat(),
                'paid_at': order.paid_at.isoformat() if order.paid_at else None,
                'is_expired': order.is_expired(),
                'can_pay': order.can_pay()
            }
        except PaymentOrder.DoesNotExist:
            return {
                'success': False,
                'error': '订单不存在'
            }
    
    def process_callback(self, data, callback_type='notify'):
        """处理支付回调"""
        try:
            # 获取订单号
            trade_order_id = data.get('trade_order_id')
            if not trade_order_id:
                raise ValueError("缺少订单号")
            
            # 查找订单
            order = PaymentOrder.objects.get(order_id=trade_order_id)
            
            # 创建回调记录
            callback = PaymentCallback.objects.create(
                order=order,
                callback_type=callback_type,
                raw_data=data,
                signature=data.get('hash', ''),
                ip_address=data.get('ip_address', ''),
                user_agent=data.get('user_agent', '')
            )
            
            # 验证签名
            is_valid = self.verify_signature(data.copy())
            callback.is_verified = is_valid
            callback.save()
            
            if not is_valid:
                PaymentLog.objects.create(
                    order=order,
                    log_type='error',
                    message='回调签名验证失败',
                    data=data,
                    error_code='INVALID_SIGNATURE'
                )
                return {
                    'success': False,
                    'error': '签名验证失败'
                }
            
            # 处理支付结果
            status = data.get('status')
            if status == 'complete' or status == 'success':
                # 支付成功
                if order.status != 'success':  # 避免重复处理
                    order.status = 'success'
                    order.paid_at = timezone.now()
                    order.trade_order_id = data.get('transaction_id', '')
                    order.extra_data['callback_data'] = data
                    order.save()
                    
                    PaymentLog.objects.create(
                        order=order,
                        log_type='callback',
                        message='支付成功',
                        data=data
                    )
                    
                    # TODO: 这里可以添加支付成功后的业务逻辑
                    # 例如：更新用户会员状态、发送通知等
                
                callback.is_processed = True
                callback.processed_at = timezone.now()
                callback.save()
                
                return {
                    'success': True,
                    'message': '支付成功'
                }
            else:
                # 支付失败或其他状态
                PaymentLog.objects.create(
                    order=order,
                    log_type='callback',
                    message=f'支付状态: {status}',
                    data=data
                )
                
                return {
                    'success': False,
                    'error': f'支付状态异常: {status}'
                }
                
        except PaymentOrder.DoesNotExist:
            logger.error(f"订单不存在: {data.get('trade_order_id')}")
            return {
                'success': False,
                'error': '订单不存在'
            }
        except Exception as e:
            logger.error(f"处理支付回调失败: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


def get_payment_service(provider='hupijiao'):
    """获取支付服务实例"""
    if provider == 'hupijiao':
        return HupijiaoPaymentService()
    else:
        raise ValueError(f"不支持的支付服务商: {provider}")