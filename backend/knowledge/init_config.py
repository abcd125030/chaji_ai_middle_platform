"""
初始化知识库配置
"""
import os
import sys
import django

# 设置Django环境
sys.path.insert(0, '/Users/chagee/Repos/X/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from knowledge.models import KnowledgeConfig


def create_default_config():
    """创建默认的知识库配置"""
    
    # 检查是否已有配置
    existing_configs = KnowledgeConfig.objects.all()
    if existing_configs.exists():
        print(f"已存在 {existing_configs.count()} 个配置")
        for config in existing_configs:
            print(f"  - {config.name} ({'激活' if config.is_active else '未激活'})")
        
        # 如果没有激活的配置，激活第一个
        if not existing_configs.filter(is_active=True).exists():
            first_config = existing_configs.first()
            first_config.is_active = True
            first_config.save()
            print(f"✅ 已激活配置: {first_config.name}")
        return
    
    # 创建新配置
    config = KnowledgeConfig.objects.create(
        name="默认配置 - Qdrant本地",
        is_active=True,
        
        # LLM配置
        llm_provider="groq",
        llm_model_name="llama-3.1-70b-versatile",
        llm_api_key="test_api_key",  # 需要替换为实际的API密钥
        openai_base_url="https://api.groq.com/openai/v1",
        llm_temperature=0.7,
        
        # Embedder配置
        embedder_provider="openai",
        embedder_model_name="text-embedding-v3",
        embedder_api_key="test_embedder_key",  # 需要替换为实际的API密钥
        embedder_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        embedder_dimensions=1024,
        
        # 向量存储配置
        vector_store_provider="qdrant",
        qdrant_host="localhost",
        qdrant_port=6333,
        qdrant_api_key=""  # 本地Qdrant不需要API密钥
    )
    
    print(f"✅ 创建并激活了默认配置: {config.name}")
    print("\n⚠️  注意：请在Django Admin中更新以下配置：")
    print("  1. LLM API密钥 (llm_api_key)")
    print("  2. Embedder API密钥 (embedder_api_key)")
    print("\n访问 http://localhost:8000/admin/knowledge/knowledgeconfig/ 进行配置")


if __name__ == "__main__":
    create_default_config()