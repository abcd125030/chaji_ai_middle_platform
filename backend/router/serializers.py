from rest_framework import serializers
from .models import LLMModel, VendorEndpoint, VendorAPIKey
from .vendor_models import Vendor


class VendorEndpointSerializer(serializers.ModelSerializer):
    """供应商端点序列化器"""
    vendor_display = serializers.CharField(source='get_vendor_display', read_only=True)
    vendor_identifier = serializers.CharField(source='get_vendor_identifier', read_only=True)
    
    class Meta:
        model = VendorEndpoint
        fields = '__all__'


class VendorAPIKeySerializer(serializers.ModelSerializer):
    """供应商API密钥序列化器"""
    vendor_display = serializers.CharField(source='get_vendor_display', read_only=True)
    vendor_identifier = serializers.CharField(source='get_vendor_identifier', read_only=True)
    
    class Meta:
        model = VendorAPIKey
        fields = '__all__'
        extra_kwargs = {
            'api_key': {'write_only': True}  # API密钥只写不读
        }


class LLMModelSerializer(serializers.ModelSerializer):
    """LLM模型序列化器"""
    endpoint_detail = VendorEndpointSerializer(source='endpoint', read_only=True)
    vendor_name = serializers.CharField(source='endpoint.vendor_name', read_only=True)
    
    class Meta:
        model = LLMModel
        fields = '__all__'
    
    def to_representation(self, instance):
        """自定义序列化输出"""
        data = super().to_representation(instance)
        # 添加成功率计算
        if instance.call_count > 0:
            data['success_rate'] = round(
                instance.success_count / instance.call_count * 100, 2
            )
        else:
            data['success_rate'] = 0
        return data


class VendorSerializer(serializers.ModelSerializer):
    """供应商序列化器"""
    endpoints_count = serializers.IntegerField(source='endpoints.count', read_only=True)
    api_keys_count = serializers.IntegerField(source='api_keys.count', read_only=True)
    
    class Meta:
        model = Vendor
        fields = '__all__'