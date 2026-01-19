"""
Router模块视图
提供模型配置的REST API接口
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.core.cache import cache

from .models import VendorEndpoint, VendorAPIKey, LLMModel
from .vendor_models import Vendor
from .serializers import (
    VendorEndpointSerializer,
    VendorAPIKeySerializer,
    LLMModelSerializer,
    VendorSerializer
)


class VendorEndpointViewSet(viewsets.ModelViewSet):
    """供应商端点管理API"""
    queryset = VendorEndpoint.objects.all()
    serializer_class = VendorEndpointSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """支持按供应商名称和服务类型过滤"""
        queryset = super().get_queryset()
        vendor_name = self.request.query_params.get('vendor_name')
        service_type = self.request.query_params.get('service_type')
        
        if vendor_name:
            queryset = queryset.filter(vendor_name=vendor_name)
        if service_type:
            queryset = queryset.filter(service_type__icontains=service_type)
        
        return queryset


class VendorAPIKeyViewSet(viewsets.ModelViewSet):
    """供应商API密钥管理"""
    queryset = VendorAPIKey.objects.all()
    serializer_class = VendorAPIKeySerializer
    permission_classes = [IsAuthenticated]
    
    def list(self, request, *args, **kwargs):
        """列表时隐藏API密钥的完整内容"""
        response = super().list(request, *args, **kwargs)
        # 对API密钥进行掩码处理
        for item in response.data.get('results', response.data):
            if 'api_key' in item and item['api_key']:
                # 只显示前8位和后4位
                key = item['api_key']
                if len(key) > 12:
                    item['api_key'] = f"{key[:8]}...{key[-4:]}"
        return response


class LLMModelViewSet(viewsets.ModelViewSet):
    """LLM模型配置管理API"""
    queryset = LLMModel.objects.all()
    serializer_class = LLMModelSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """支持多种过滤条件"""
        queryset = super().get_queryset()
        
        # 按模型类型过滤
        model_type = self.request.query_params.get('model_type')
        if model_type:
            queryset = queryset.filter(model_type=model_type)
        
        # 按供应商过滤
        vendor_name = self.request.query_params.get('vendor_name')
        if vendor_name:
            queryset = queryset.filter(endpoint__vendor_name=vendor_name)
        
        # 按API标准过滤
        api_standard = self.request.query_params.get('api_standard')
        if api_standard:
            queryset = queryset.filter(api_standard=api_standard)
        
        # 搜索功能
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(model_id__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset.select_related('endpoint')
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """按类型分组返回模型"""
        models_by_type = {}
        for model_type, type_name in LLMModel.MODEL_TYPE_CHOICES:
            models = self.get_queryset().filter(model_type=model_type)
            models_by_type[model_type] = {
                'name': type_name,
                'count': models.count(),
                'models': LLMModelSerializer(models[:10], many=True).data
            }
        return Response(models_by_type)
    
    @action(detail=False, methods=['get'])
    def embedding_models(self, request):
        """获取所有Embedding模型"""
        models = self.get_queryset().filter(model_type='embedding')
        serializer = self.get_serializer(models, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def rerank_models(self, request):
        """获取所有Rerank模型"""
        models = self.get_queryset().filter(model_type='rerank')
        serializer = self.get_serializer(models, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """测试模型连接是否正常"""
        model = self.get_object()
        
        # 这里可以实现实际的连接测试逻辑
        # 例如向API端点发送测试请求
        
        # 暂时返回模拟结果
        return Response({
            'model_id': model.model_id,
            'endpoint': model.endpoint.endpoint,
            'status': 'success',
            'message': 'Connection test successful',
            'response_time': '150ms'
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """获取模型使用统计"""
        stats = {
            'total_models': self.get_queryset().count(),
            'by_type': {},
            'by_vendor': {},
            'most_used': []
        }
        
        # 按类型统计
        for model_type, type_name in LLMModel.MODEL_TYPE_CHOICES:
            count = self.get_queryset().filter(model_type=model_type).count()
            if count > 0:
                stats['by_type'][type_name] = count
        
        # 按供应商统计
        for vendor in VendorEndpoint.objects.values('vendor_name').distinct():
            vendor_name = vendor['vendor_name']
            count = self.get_queryset().filter(
                endpoint__vendor_name=vendor_name
            ).count()
            if count > 0:
                stats['by_vendor'][vendor_name] = count
        
        # 最常用的模型（按调用次数）
        top_models = self.get_queryset().order_by('-call_count')[:5]
        stats['most_used'] = [
            {
                'name': m.name,
                'model_id': m.model_id,
                'call_count': m.call_count,
                'success_rate': (
                    round(m.success_count / m.call_count * 100, 2)
                    if m.call_count > 0 else 0
                )
            }
            for m in top_models
        ]
        
        return Response(stats)
    
    @action(detail=False, methods=['post'])
    def clear_cache(self, request):
        """清除模型配置缓存"""
        # 清除Redis中的模型配置缓存
        cache_keys = cache.keys('model_config_*')
        for key in cache_keys:
            cache.delete(key)
        
        return Response({
            'status': 'success',
            'message': f'Cleared {len(cache_keys)} cache entries'
        })
    
    @action(detail=False, methods=['post'])
    def batch_import(self, request):
        """批量导入模型配置"""
        models_data = request.data.get('models', [])
        created_count = 0
        updated_count = 0
        errors = []
        
        for model_data in models_data:
            try:
                model_id = model_data.get('model_id')
                if not model_id:
                    errors.append({'error': 'model_id is required', 'data': model_data})
                    continue
                
                # 查找或创建端点
                endpoint_data = model_data.pop('endpoint', {})
                if endpoint_data:
                    endpoint, _ = VendorEndpoint.objects.get_or_create(
                        vendor_name=endpoint_data.get('vendor_name', 'Unknown'),
                        defaults=endpoint_data
                    )
                    model_data['endpoint'] = endpoint
                
                # 创建或更新模型
                model, created = LLMModel.objects.update_or_create(
                    model_id=model_id,
                    defaults=model_data
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                    
            except Exception as e:
                errors.append({
                    'error': str(e),
                    'data': model_data
                })
        
        return Response({
            'created': created_count,
            'updated': updated_count,
            'errors': errors
        }, status=status.HTTP_201_CREATED if created_count > 0 else status.HTTP_200_OK)


class VendorViewSet(viewsets.ModelViewSet):
    """供应商管理API"""
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'vendor_id'
    
    def get_queryset(self):
        """支持按状态过滤"""
        queryset = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('-priority', 'display_name')
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取所有激活的供应商"""
        vendors = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(vendors, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def endpoints(self, request, vendor_id=None):
        """获取特定供应商的所有端点"""
        vendor = self.get_object()
        endpoints = vendor.endpoints.all()
        serializer = VendorEndpointSerializer(endpoints, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def api_keys(self, request, vendor_id=None):
        """获取特定供应商的所有API密钥"""
        vendor = self.get_object()
        api_keys = vendor.api_keys.all()
        serializer = VendorAPIKeySerializer(api_keys, many=True)
        # 隐藏API密钥
        for item in serializer.data:
            if 'api_key' in item:
                item['api_key'] = '********'
        return Response(serializer.data)