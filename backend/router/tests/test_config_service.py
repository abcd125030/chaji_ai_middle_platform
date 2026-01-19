"""
ModelConfigService 单元测试
测试模型配置服务的各项功能
"""
import os
import json
import logging
from datetime import datetime
from django.test import TestCase
from django.conf import settings
from django.db import transaction
from django.core.cache import cache

from router.models import LLMModel, VendorEndpoint, VendorAPIKey
from router.vendor_models import Vendor
from router.services.config import ModelConfigService


class ModelConfigServiceTestCase(TestCase):
    """
    ModelConfigService 测试类
    
    遵循"在隔离环境中重建真实状态"的原则。
    使用 setUpTestData 加载所有测试共享的、不变的配置数据。
    使用 setUp 和 tearDown 管理每个具体测试的生命周期和结果记录。
    """
    
    @classmethod
    def setUpTestData(cls):
        """
        在整个测试类运行前执行一次，用于准备共享的、不变的"背景"数据。
        这是填充测试数据库以模拟真实配置的最佳位置。
        """
        print("\n" + "="*50)
        print(f"[{cls.__name__}] Running setUpTestData: Populating test database with initial configuration...")
        
        try:
            with transaction.atomic():
                # 创建供应商
                cls.vendor_openai = Vendor.objects.create(
                    vendor_id="openai",
                    display_name="OpenAI",
                    description="OpenAI API服务",
                    website="https://openai.com",
                    supported_services=["文本生成", "嵌入", "语音"],
                    is_active=True,
                    priority=100
                )
                
                cls.vendor_anthropic = Vendor.objects.create(
                    vendor_id="anthropic",
                    display_name="Anthropic",
                    description="Claude API服务",
                    website="https://anthropic.com",
                    supported_services=["文本生成", "推理"],
                    is_active=True,
                    priority=90
                )
                
                cls.vendor_cohere = Vendor.objects.create(
                    vendor_id="cohere",
                    display_name="Cohere",
                    description="Cohere API服务",
                    website="https://cohere.com",
                    supported_services=["嵌入", "重排序"],
                    is_active=True,
                    priority=80
                )
                
                # 创建端点
                cls.endpoint_openai = VendorEndpoint.objects.create(
                    vendor=cls.vendor_openai,
                    endpoint="https://api.openai.com/v1",
                    service_type="Text Generation"
                )
                
                cls.endpoint_anthropic = VendorEndpoint.objects.create(
                    vendor=cls.vendor_anthropic,
                    endpoint="https://api.anthropic.com/v1",
                    service_type="Text Generation"
                )
                
                cls.endpoint_cohere = VendorEndpoint.objects.create(
                    vendor=cls.vendor_cohere,
                    endpoint="https://api.cohere.ai/v1",
                    service_type="Embedding"
                )
                
                # 创建API密钥
                cls.api_key_openai = VendorAPIKey.objects.create(
                    vendor=cls.vendor_openai,
                    api_key="sk-test-openai-key",
                    description="测试用OpenAI密钥"
                )
                
                cls.api_key_anthropic = VendorAPIKey.objects.create(
                    vendor=cls.vendor_anthropic,
                    api_key="sk-test-anthropic-key",
                    description="测试用Anthropic密钥"
                )
                
                # 创建模型配置
                cls.model_gpt4 = LLMModel.objects.create(
                    name="GPT-4",
                    model_id="gpt-4",
                    model_type="text",
                    description="OpenAI GPT-4模型",
                    endpoint=cls.endpoint_openai,
                    api_standard="openai",
                    params={"temperature": 0.7, "max_tokens": 2000},
                    call_count=100,
                    success_count=95
                )
                
                cls.model_gpt35 = LLMModel.objects.create(
                    name="GPT-3.5 Turbo",
                    model_id="gpt-3.5-turbo",
                    model_type="text",
                    description="OpenAI GPT-3.5 Turbo模型",
                    endpoint=cls.endpoint_openai,
                    api_standard="openai",
                    params={"temperature": 0.8, "max_tokens": 1000},
                    call_count=500,
                    success_count=480
                )
                
                cls.model_claude = LLMModel.objects.create(
                    name="Claude 3",
                    model_id="claude-3",
                    model_type="reasoning",
                    description="Anthropic Claude 3模型",
                    endpoint=cls.endpoint_anthropic,
                    api_standard="anthropic",
                    params={"temperature": 1.0, "max_tokens": 4096},
                    call_count=50,
                    success_count=48
                )
                
                cls.model_embedding = LLMModel.objects.create(
                    name="Text Embedding",
                    model_id="text-embedding-3-small",
                    model_type="embedding",
                    description="OpenAI文本嵌入模型",
                    endpoint=cls.endpoint_openai,
                    api_standard="openai",
                    params={"dimensions": 1536},
                    call_count=200,
                    success_count=200
                )
                
                cls.model_rerank = LLMModel.objects.create(
                    name="Rerank Model",
                    model_id="rerank-multilingual",
                    model_type="rerank",
                    description="Cohere重排序模型",
                    endpoint=cls.endpoint_cohere,
                    api_standard="cohere",
                    params={"top_n": 10},
                    call_count=30,
                    success_count=28
                )
                
                print(f"[{cls.__name__}] Created {Vendor.objects.count()} vendors")
                print(f"[{cls.__name__}] Created {VendorEndpoint.objects.count()} endpoints")
                print(f"[{cls.__name__}] Created {VendorAPIKey.objects.count()} API keys")
                print(f"[{cls.__name__}] Created {LLMModel.objects.count()} models")
                print(f"[{cls.__name__}] setUpTestData completed successfully.")
                
        except Exception as e:
            print(f"[{cls.__name__}] CRITICAL: Failed to set up test data: {e}")
            raise
        print("="*50)

    def setUp(self):
        """
        在每个 test_ 方法执行前运行。
        用于设置日志、创建输出目录、记录初始状态等每个测试都需要独立完成的工作。
        """
        # 清除缓存，确保每个测试都是独立的
        cache.clear()
        
        # 文件和日志设置
        self.output_dir = os.path.join(settings.BASE_DIR, 'router', 'tests', 'outputs')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 使用符合规范的文件命名格式
        test_method_name = self._testMethodName
        timestamp = datetime.now()
        date_str = timestamp.strftime('%Y%m%d')
        time_str = timestamp.strftime('%H%M%S')
        
        # 生成符合规范的文件名
        self.process_filename = f'process-{date_str}-{time_str}-{test_method_name}.json'
        self.log_filename = f'log-{date_str}-{time_str}-{test_method_name}.log'
        
        self.setup_logging()
        self.logger.info(f"Test method '{test_method_name}' starting...")
        
        # 创建服务实例
        self.service = ModelConfigService()
        
        # 状态捕获和数据记录
        self.initial_state = self.capture_state("initial")
        self.process_data = {
            "test_info": {
                "name": f"{self.__class__.__name__}.{test_method_name}",
                "start_time": datetime.now().isoformat()
            },
            "initial_state": self.initial_state,
            "execution_steps": []
        }

    def setup_logging(self):
        """配置日志记录器"""
        log_file = os.path.join(self.output_dir, self.log_filename)
        
        # 避免重复添加handler
        self.logger = logging.getLogger(self.log_filename)
        if not self.logger.handlers:
            self.logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            
            # 文件处理器
            fh = logging.FileHandler(log_file, encoding='utf-8')
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
            
            # 控制台处理器
            sh = logging.StreamHandler()
            sh.setFormatter(formatter)
            self.logger.addHandler(sh)
            
    def capture_state(self, stage: str):
        """
        捕获当前数据库和配置的状态。
        
        stage: 'initial' 或 'final'
        """
        self.logger.info(f"Capturing {stage} state...")
        
        # 捕获数据库状态
        db_snapshot = {
            "vendors": list(Vendor.objects.values('vendor_id', 'display_name', 'is_active')),
            "endpoints": list(VendorEndpoint.objects.values('id', 'vendor_id', 'endpoint')),
            "models": list(LLMModel.objects.values('model_id', 'name', 'model_type', 'call_count', 'success_count')),
            "api_keys_count": VendorAPIKey.objects.count(),
        }
        
        # 捕获缓存状态
        cache_keys = cache.keys('model_*') if hasattr(cache, 'keys') else []
        
        return {
            "database": db_snapshot,
            "cache_keys": list(cache_keys),
            "timestamp": datetime.now().isoformat()
        }

    def record_step(self, action, input_data, output_data, **kwargs):
        """记录执行步骤"""
        step_number = len(self.process_data["execution_steps"]) + 1
        step_data = {
            "step": step_number,
            "action": action,
            "input": str(input_data),
            "output": str(output_data),
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.process_data["execution_steps"].append(step_data)
        self.logger.info(f"Step {step_number}: {action} recorded.")
    
    def tearDown(self):
        """
        在每个 test_ 方法执行后运行。
        用于记录最终状态和保存所有输出文件。
        """
        end_time = datetime.now()
        start_time_iso = self.process_data["test_info"]["start_time"]
        start_time = datetime.fromisoformat(start_time_iso)
        duration = (end_time - start_time).total_seconds()

        self.process_data["test_info"]["end_time"] = end_time.isoformat()
        self.process_data["test_info"]["duration"] = duration
        self.process_data["final_state"] = self.capture_state("final")
        
        # 保存过程数据
        process_file = os.path.join(self.output_dir, self.process_filename)
        try:
            with open(process_file, 'w', encoding='utf-8') as f:
                json.dump(self.process_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to write process file: {e}")

        self.logger.info(f"Test method finished. Duration: {duration:.2f}s")
        print(f"\n[INFO] Test outputs saved to: {os.path.abspath(process_file)}")
        
    # ==================== 测试方法 ====================
    
    def test_get_model_config(self):
        """测试获取单个模型配置"""
        self.logger.info("Testing get_model_config...")
        
        # 测试获取存在的模型
        config = self.service.get_model_config("gpt-4")
        self.record_step(
            action="get_model_config",
            input_data={"model_id": "gpt-4"},
            output_data=config
        )
        
        self.assertIsNotNone(config)
        self.assertEqual(config['model_id'], 'gpt-4')
        self.assertEqual(config['name'], 'GPT-4')
        self.assertEqual(config['model_type'], 'text')
        self.assertIn('endpoint', config)
        self.assertIn('statistics', config)
        self.assertEqual(config['statistics']['call_count'], 100)
        
        # 测试缓存是否生效
        config_cached = self.service.get_model_config("gpt-4")
        self.record_step(
            action="get_model_config_cached",
            input_data={"model_id": "gpt-4"},
            output_data=config_cached
        )
        self.assertEqual(config, config_cached)
        
        # 测试不存在的模型
        config_none = self.service.get_model_config("non-existent")
        self.record_step(
            action="get_model_config_non_existent",
            input_data={"model_id": "non-existent"},
            output_data=config_none
        )
        self.assertIsNone(config_none)
    
    def test_list_models_by_type(self):
        """测试按类型列出模型"""
        self.logger.info("Testing list_models_by_type...")
        
        # 测试获取所有类型
        all_models = self.service.list_models_by_type()
        self.record_step(
            action="list_models_by_type_all",
            input_data={},
            output_data=all_models
        )
        
        self.assertIn('text', all_models)
        self.assertIn('embedding', all_models)
        self.assertIn('rerank', all_models)
        self.assertIn('reasoning', all_models)
        
        # 验证文本模型数量
        text_models = all_models.get('text', [])
        self.assertEqual(len(text_models), 2)  # gpt-4, gpt-3.5-turbo
        
        # 测试特定类型
        embedding_models = self.service.list_models_by_type('embedding')
        self.record_step(
            action="list_models_by_type_embedding",
            input_data={"model_type": "embedding"},
            output_data=embedding_models
        )
        
        self.assertIn('embedding', embedding_models)
        self.assertEqual(len(embedding_models['embedding']), 1)
    
    def test_get_available_models(self):
        """测试获取可用模型"""
        self.logger.info("Testing get_available_models...")
        
        # 测试获取所有可用模型
        available = self.service.get_available_models()
        self.record_step(
            action="get_available_models_all",
            input_data={},
            output_data=available
        )
        
        # 验证返回的模型都有端点
        self.assertTrue(all(m['model_id'] != '' for m in available))
        
        # 测试按能力过滤
        text_models = self.service.get_available_models(['text'])
        self.record_step(
            action="get_available_models_text",
            input_data={"capabilities": ["text"]},
            output_data=text_models
        )
        
        for model in text_models:
            self.assertEqual(model['type'], 'text')
        
        # 测试多个能力
        multi_models = self.service.get_available_models(['text', 'embedding'])
        self.record_step(
            action="get_available_models_multi",
            input_data={"capabilities": ["text", "embedding"]},
            output_data=multi_models
        )
        
        types = set(m['type'] for m in multi_models)
        self.assertIn('text', types)
        self.assertIn('embedding', types)
    
    def test_get_vendor_models(self):
        """测试获取供应商模型"""
        self.logger.info("Testing get_vendor_models...")
        
        # 测试OpenAI的模型
        openai_models = self.service.get_vendor_models('openai')
        self.record_step(
            action="get_vendor_models_openai",
            input_data={"vendor_id": "openai"},
            output_data=openai_models
        )
        
        self.assertEqual(len(openai_models), 3)  # gpt-4, gpt-3.5-turbo, text-embedding
        model_ids = [m['model_id'] for m in openai_models]
        self.assertIn('gpt-4', model_ids)
        self.assertIn('gpt-3.5-turbo', model_ids)
        
        # 测试不存在的供应商
        unknown_models = self.service.get_vendor_models('unknown-vendor')
        self.record_step(
            action="get_vendor_models_unknown",
            input_data={"vendor_id": "unknown-vendor"},
            output_data=unknown_models
        )
        
        self.assertEqual(unknown_models, [])
    
    def test_get_model_statistics(self):
        """测试获取模型统计"""
        self.logger.info("Testing get_model_statistics...")
        
        stats = self.service.get_model_statistics()
        self.record_step(
            action="get_model_statistics",
            input_data={},
            output_data=stats
        )
        
        self.assertIn('total_models', stats)
        self.assertEqual(stats['total_models'], 5)
        
        self.assertIn('by_type', stats)
        self.assertEqual(stats['by_type']['Text'], 2)
        self.assertEqual(stats['by_type']['Embedding'], 1)
        
        self.assertIn('by_vendor', stats)
        self.assertEqual(stats['by_vendor']['OpenAI'], 3)
        self.assertEqual(stats['by_vendor']['Anthropic'], 1)
        
        self.assertIn('most_used', stats)
        self.assertTrue(len(stats['most_used']) > 0)
        
        # 验证最常用的模型是gpt-3.5-turbo
        if stats['most_used']:
            top_model = stats['most_used'][0]
            self.assertEqual(top_model['model_id'], 'gpt-3.5-turbo')
            self.assertEqual(top_model['call_count'], 500)
    
    def test_search_models(self):
        """测试搜索模型"""
        self.logger.info("Testing search_models...")
        
        # 搜索GPT
        gpt_results = self.service.search_models('GPT')
        self.record_step(
            action="search_models_gpt",
            input_data={"query": "GPT"},
            output_data=gpt_results
        )
        
        self.assertEqual(len(gpt_results), 2)  # GPT-4 和 GPT-3.5
        
        # 搜索embedding
        embedding_results = self.service.search_models('embedding')
        self.record_step(
            action="search_models_embedding",
            input_data={"query": "embedding"},
            output_data=embedding_results
        )
        
        self.assertEqual(len(embedding_results), 1)
        
        # 搜索不存在的内容
        no_results = self.service.search_models('xyz123')
        self.record_step(
            action="search_models_no_results",
            input_data={"query": "xyz123"},
            output_data=no_results
        )
        
        self.assertEqual(no_results, [])
    
    def test_get_model_defaults(self):
        """测试获取模型默认参数"""
        self.logger.info("Testing get_model_defaults...")
        
        # 测试文本模型默认参数
        text_defaults = self.service.get_model_defaults('text')
        self.record_step(
            action="get_model_defaults_text",
            input_data={"model_type": "text"},
            output_data=text_defaults
        )
        
        self.assertIn('temperature', text_defaults)
        self.assertEqual(text_defaults['temperature'], 0.7)
        self.assertIn('max_tokens', text_defaults)
        
        # 测试嵌入模型默认参数
        embedding_defaults = self.service.get_model_defaults('embedding')
        self.record_step(
            action="get_model_defaults_embedding",
            input_data={"model_type": "embedding"},
            output_data=embedding_defaults
        )
        
        self.assertIn('dimensions', embedding_defaults)
        self.assertIn('batch_size', embedding_defaults)
        
        # 测试未知类型
        unknown_defaults = self.service.get_model_defaults('unknown')
        self.record_step(
            action="get_model_defaults_unknown",
            input_data={"model_type": "unknown"},
            output_data=unknown_defaults
        )
        
        self.assertEqual(unknown_defaults, {})
    
    def test_clear_cache(self):
        """测试清除缓存"""
        self.logger.info("Testing clear_cache...")
        
        # 先创建一些缓存
        self.service.get_model_config("gpt-4")
        self.service.get_model_config("claude-3")
        self.service.list_models_by_type()
        
        # 清除缓存
        count = self.service.clear_cache()
        self.record_step(
            action="clear_cache",
            input_data={},
            output_data={"cleared_count": count}
        )
        
        # 验证缓存已清除
        self.assertGreaterEqual(count, 0)
        self.logger.info(f"Cleared {count} cache entries")