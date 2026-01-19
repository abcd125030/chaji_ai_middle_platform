from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q
import logging

from .models import PaymentOrder, PaymentCallback, PaymentConfig, PaymentLog
from .serializers import (
    PaymentOrderSerializer,
    CreatePaymentOrderSerializer,
    PaymentCallbackSerializer,
    PaymentConfigSerializer,
    PaymentLogSerializer,
    PaymentStatusSerializer,
    PaymentCallbackDataSerializer
)
from .services import get_payment_service

logger = logging.getLogger(__name__)


class PaymentOrderViewSet(viewsets.ModelViewSet):
    """支付订单视图集"""
    
    queryset = PaymentOrder.objects.all()
    serializer_class = PaymentOrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """获取当前用户的订单"""
        queryset = super().get_queryset()
        user = self.request.user
        
        # 普通用户只能看自己的订单
        if not user.is_staff:
            queryset = queryset.filter(user=user)
        
        # 支持筛选
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        payment_method = self.request.query_params.get('payment_method', 'wechat')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        
        # 搜索
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(order_id__icontains=search) |
                Q(title__icontains=search) |
                Q(trade_order_id__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def create_order(self, request):
        """创建支付订单"""
        serializer = CreatePaymentOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': '参数错误', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # 获取支付服务
            service = get_payment_service('hupijiao')
            
            # 创建订单
            result = service.create_order(
                user=request.user,
                **serializer.validated_data
            )
            
            if result['success']:
                return Response({
                    'status': 'success',
                    'data': result,
                    'message': '订单创建成功'
                })
            else:
                return Response({
                    'status': 'error',
                    'error': result.get('error', '订单创建失败'),
                    'order_id': result.get('order_id')
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"创建支付订单失败: {str(e)}")
            return Response({
                'status': 'error',
                'error': '服务暂时不可用，请稍后重试'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def query_status(self, request):
        """查询订单状态"""
        serializer = PaymentStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': '参数错误', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order_id = serializer.validated_data['order_id']
        
        try:
            # 获取支付服务
            service = get_payment_service('hupijiao')
            
            # 查询订单
            result = service.query_order(order_id)
            
            if result['success']:
                return Response({
                    'status': 'success',
                    'data': result,
                    'message': '查询成功'
                })
            else:
                return Response({
                    'status': 'error',
                    'error': result.get('error', '查询失败')
                }, status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            logger.error(f"查询订单状态失败: {str(e)}")
            return Response({
                'status': 'error',
                'error': '查询失败'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel_by_order_id(self, request):
        """通过订单号取消订单"""
        order_id = request.data.get('order_id')
        if not order_id:
            return Response({
                'status': 'error',
                'error': '订单号不能为空'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = PaymentOrder.objects.get(order_id=order_id)
        except PaymentOrder.DoesNotExist:
            return Response({
                'status': 'error',
                'error': '订单不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # 检查权限
        if order.user != request.user and not request.user.is_staff:
            return Response({
                'status': 'error',
                'error': '无权限操作此订单'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 检查订单状态
        if order.status not in ['pending', 'processing']:
            return Response({
                'status': 'error',
                'error': '订单状态不允许取消'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 取消订单
        order.status = 'cancelled'
        order.save()
        
        # 记录日志
        PaymentLog.objects.create(
            order=order,
            log_type='request',
            message=f'用户取消订单: {order_id}'
        )
        
        return Response({
            'status': 'success',
            'message': '订单已取消'
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel(self, request, pk=None):
        """取消订单（通过pk）"""
        order = self.get_object()
        
        # 检查权限
        if order.user != request.user and not request.user.is_staff:
            return Response({
                'status': 'error',
                'error': '无权限操作此订单'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 检查订单状态
        if order.status not in ['pending', 'processing']:
            return Response({
                'status': 'error',
                'error': '订单状态不允许取消'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 取消订单
        order.status = 'cancelled'
        order.save()
        
        # 记录日志
        PaymentLog.objects.create(
            order=order,
            log_type='request',
            message='用户取消订单',
            data={'user_id': str(request.user.id)}
        )
        
        return Response({
            'status': 'success',
            'message': '订单已取消'
        })


class PaymentCallbackView(viewsets.ViewSet):
    """支付回调视图"""
    
    permission_classes = []  # 回调接口不需要认证
    
    @action(detail=False, methods=['post'])
    def notify(self, request):
        """异步通知回调"""
        try:
            # 获取回调数据
            data = request.data.copy()
            
            # 添加请求信息
            data['ip_address'] = self.get_client_ip(request)
            data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
            
            logger.info(f"收到支付回调通知: {data}")
            
            # 获取支付服务
            service = get_payment_service('hupijiao')
            
            # 处理回调
            result = service.process_callback(data, callback_type='notify')
            
            if result['success']:
                # 虎皮椒要求返回success
                return Response('success', content_type='text/plain')
            else:
                logger.error(f"处理支付回调失败: {result.get('error')}")
                return Response('fail', content_type='text/plain')
                
        except Exception as e:
            logger.error(f"处理支付回调异常: {str(e)}")
            return Response('error', content_type='text/plain')
    
    @action(detail=False, methods=['get', 'post'])
    def return_url(self, request):
        """同步返回回调"""
        try:
            # 获取回调数据
            data = request.GET.dict() if request.method == 'GET' else request.data.copy()
            
            # 添加请求信息
            data['ip_address'] = self.get_client_ip(request)
            data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
            
            logger.info(f"收到支付同步返回: {data}")
            
            # 获取支付服务
            service = get_payment_service('hupijiao')
            
            # 处理回调
            result = service.process_callback(data, callback_type='return')
            
            return Response({
                'status': 'success' if result['success'] else 'error',
                'message': result.get('message', result.get('error', '处理失败'))
            })
            
        except Exception as e:
            logger.error(f"处理支付返回异常: {str(e)}")
            return Response({
                'status': 'error',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_client_ip(self, request):
        """获取客户端IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class PaymentConfigViewSet(viewsets.ModelViewSet):
    """支付配置视图集（仅管理员）"""
    
    queryset = PaymentConfig.objects.all()
    serializer_class = PaymentConfigSerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        """只有管理员可以管理配置"""
        if self.request.user and self.request.user.is_staff:
            return super().get_permissions()
        return []
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活配置"""
        config = self.get_object()
        
        # 停用同类其他配置
        PaymentConfig.objects.filter(
            provider=config.provider
        ).exclude(id=config.id).update(is_active=False)
        
        # 激活当前配置
        config.is_active = True
        config.save()
        
        return Response({
            'status': 'success',
            'message': '配置已激活'
        })


class PaymentLogViewSet(viewsets.ReadOnlyModelViewSet):
    """支付日志视图集（只读）"""
    
    queryset = PaymentLog.objects.all()
    serializer_class = PaymentLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """过滤日志"""
        queryset = super().get_queryset()
        
        # 非管理员只能看自己订单的日志
        if not self.request.user.is_staff:
            user_orders = PaymentOrder.objects.filter(user=self.request.user)
            queryset = queryset.filter(order__in=user_orders)
        
        # 按订单过滤
        order_id = self.request.query_params.get('order_id')
        if order_id:
            queryset = queryset.filter(order__order_id=order_id)
        
        # 按类型过滤
        log_type = self.request.query_params.get('log_type')
        if log_type:
            queryset = queryset.filter(log_type=log_type)
        
        return queryset.order_by('-created_at')
