#!/usr/bin/env python
"""
真实的视觉模型调用测试
测试 CoreLLMService.call_vision_llm 方法的完整功能
遵循测试规范，使用真实的模型配置和 LLM 调用
"""

import os
import sys
import json
import logging
import base64
from datetime import datetime
from pathlib import Path
from io import BytesIO
from PIL import Image

# 设置 Django 环境
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from llm.llm_service import LLMService
from llm.config_manager import ModelConfigManager
from router.models import LLMModel
from authentication.models import User


class TestVisionModelReal:
    """真实的视觉模型测试"""
    
    def __init__(self):
        """初始化测试环境"""
        # 创建输出目录
        self.output_dir = os.path.join(os.path.dirname(__file__), 'outputs')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 生成文件名时间戳
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.test_name = 'vision_model'
        
        # 设置日志
        self.setup_logging()
        
        # 初始化服务
        self.llm_service = LLMService()
        self.config_manager = ModelConfigManager()
        
        # 记录初始状态
        self.initial_state = self.capture_state()
        self.process_data = {
            "test_info": {
                "name": self.test_name,
                "start_time": datetime.now().isoformat(),
                "description": "测试视觉模型调用功能"
            },
            "initial_state": self.initial_state,
            "execution_steps": []
        }
        
        # 测试结果
        self.test_results = {
            "success": True,
            "test_cases": [],
            "metrics": {
                "total_llm_tokens": 0,
                "total_llm_cost": 0,
                "total_execution_time": 0,
                "database_operations": 0
            }
        }
    
    def setup_logging(self):
        """配置日志记录"""
        log_file = os.path.join(
            self.output_dir,
            f'test_{self.test_name}_{self.timestamp}.log'
        )
        
        # 配置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # 配置logger
        self.logger = logging.getLogger(self.test_name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.info(f"{'='*60}")
        self.logger.info(f"测试开始: {self.test_name}")
        self.logger.info(f"时间: {datetime.now().isoformat()}")
        self.logger.info(f"{'='*60}")
    
    def capture_state(self):
        """捕获当前状态"""
        state = {}
        
        try:
            # 获取vision类型的模型配置
            vision_models = LLMModel.objects.filter(model_type='vision')
            state['vision_models'] = [
                {
                    'name': m.name,
                    'model_id': m.model_id,
                    'endpoint': m.endpoint.endpoint if m.endpoint else None
                }
                for m in vision_models
            ]
            self.logger.info(f"找到 {len(vision_models)} 个活跃的视觉模型")
            
            # 记录配置信息
            from router.models import Config
            vision_config = Config.objects.filter(key__contains='vision')
            state['vision_configs'] = {
                c.key: c.value for c in vision_config
            }
            
        except Exception as e:
            self.logger.error(f"捕获状态失败: {str(e)}")
            state['error'] = str(e)
        
        return state
    
    def create_test_image(self):
        """创建测试用的图片"""
        # 创建一个简单的测试图片
        img = Image.new('RGB', (200, 200), color='blue')
        
        # 在图片上添加文字（需要PIL的ImageDraw）
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 150, 150], fill='red', outline='white', width=3)
        draw.text((70, 90), "TEST", fill='white')
        
        # 保存到内存并转换为base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_bytes = buffer.getvalue()
        
        # 转换为base64
        base64_str = base64.b64encode(img_bytes).decode('utf-8')
        
        # 保存图片到文件（供参考）
        img_path = os.path.join(self.output_dir, f'test_image_{self.timestamp}.png')
        img.save(img_path)
        self.logger.info(f"测试图片已保存到: {img_path}")
        
        return f"data:image/png;base64,{base64_str}", img_path
    
    def record_step(self, action, input_data, output_data, **kwargs):
        """记录执行步骤"""
        step = {
            "step": len(self.process_data["execution_steps"]) + 1,
            "action": action,
            "input": input_data,
            "output": output_data,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.process_data["execution_steps"].append(step)
        self.logger.info(f"步骤 {step['step']}: {action}")
    
    def test_vision_model_with_base64(self):
        """测试使用base64图片调用视觉模型"""
        test_case = {
            "name": "test_vision_model_with_base64",
            "description": "使用base64格式图片调用视觉模型",
            "passed": False,
            "actual_result": None,
            "expected_result": "模型成功返回图片描述",
            "error": None
        }
        
        try:
            self.logger.info("\n" + "="*40)
            self.logger.info("测试用例: base64图片调用")
            self.logger.info("="*40)
            
            # 获取可用的vision模型
            vision_models = LLMModel.objects.filter(model_type='vision').first()
            
            if not vision_models:
                self.logger.warning("没有找到可用的vision模型，跳过测试")
                test_case["error"] = "No vision model available"
                self.test_results["test_cases"].append(test_case)
                return
            
            model_name = vision_models.name
            self.logger.info(f"使用模型: {model_name}")
            
            # 创建测试图片
            base64_image, img_path = self.create_test_image()
            
            # 准备调用参数
            text_prompt = "请描述这张图片的内容，包括颜色、形状和文字。"
            
            # 记录调用前的状态
            self.record_step(
                action="准备调用视觉模型",
                input_data={
                    "model": model_name,
                    "text_prompt": text_prompt,
                    "image_format": "base64",
                    "image_size": len(base64_image)
                },
                output_data=None
            )
            
            # 调用视觉模型
            start_time = datetime.now()
            try:
                response = self.llm_service.call_vision_model(
                    model_name=model_name,
                    text_prompt=text_prompt,
                    images=[base64_image],
                    temperature=0.7,
                    max_tokens=500
                )
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # 解析响应
                if response and 'choices' in response:
                    content = response['choices'][0]['message']['content']
                    usage = response.get('usage', {})
                    
                    self.logger.info(f"模型响应成功")
                    self.logger.info(f"响应内容: {content[:200]}...")
                    self.logger.info(f"Token使用: {usage}")
                    
                    # 记录成功的调用
                    self.record_step(
                        action="视觉模型调用成功",
                        input_data={
                            "model": model_name,
                            "text_prompt": text_prompt
                        },
                        output_data={
                            "response": content,
                            "usage": usage,
                            "duration": duration
                        },
                        llm_calls={
                            "model": model_name,
                            "endpoint": vision_models.endpoint.endpoint if vision_models.endpoint else None,
                            "tokens": usage.get('total_tokens', 0),
                            "duration": duration
                        }
                    )
                    
                    # 更新测试结果
                    test_case["passed"] = True
                    test_case["actual_result"] = content
                    
                    # 更新指标
                    self.test_results["metrics"]["total_llm_tokens"] += usage.get('total_tokens', 0)
                    self.test_results["metrics"]["total_execution_time"] += duration
                    
                else:
                    self.logger.error(f"响应格式错误: {response}")
                    test_case["error"] = "Invalid response format"
                    
            except Exception as e:
                self.logger.error(f"调用失败: {str(e)}")
                test_case["error"] = str(e)
                
                # 记录失败的调用
                self.record_step(
                    action="视觉模型调用失败",
                    input_data={
                        "model": model_name,
                        "text_prompt": text_prompt
                    },
                    output_data={
                        "error": str(e)
                    }
                )
                
        except Exception as e:
            self.logger.error(f"测试用例执行失败: {str(e)}")
            test_case["error"] = str(e)
        
        self.test_results["test_cases"].append(test_case)
    
    def test_vision_model_with_file_path(self):
        """测试使用文件路径调用视觉模型"""
        test_case = {
            "name": "test_vision_model_with_file_path",
            "description": "使用本地文件路径调用视觉模型",
            "passed": False,
            "actual_result": None,
            "expected_result": "模型成功返回图片描述",
            "error": None
        }
        
        try:
            self.logger.info("\n" + "="*40)
            self.logger.info("测试用例: 文件路径调用")
            self.logger.info("="*40)
            
            # 获取可用的vision模型
            vision_models = LLMModel.objects.filter(model_type='vision').first()
            
            if not vision_models:
                self.logger.warning("没有找到可用的vision模型，跳过测试")
                test_case["error"] = "No vision model available"
                self.test_results["test_cases"].append(test_case)
                return
            
            model_name = vision_models.name
            
            # 创建测试图片并获取路径
            _, img_path = self.create_test_image()
            
            # 准备调用参数
            text_prompt = "这是什么图片？请详细描述。"
            
            # 记录调用前的状态
            self.record_step(
                action="准备使用文件路径调用视觉模型",
                input_data={
                    "model": model_name,
                    "text_prompt": text_prompt,
                    "image_path": img_path
                },
                output_data=None
            )
            
            # 调用视觉模型
            start_time = datetime.now()
            try:
                response = self.llm_service.call_vision_model(
                    model_name=model_name,
                    text_prompt=text_prompt,
                    images=[img_path],
                    temperature=0.7,
                    max_tokens=500
                )
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # 解析响应
                if response and 'choices' in response:
                    content = response['choices'][0]['message']['content']
                    usage = response.get('usage', {})
                    
                    self.logger.info(f"文件路径调用成功")
                    self.logger.info(f"响应内容: {content[:200]}...")
                    
                    # 记录成功的调用
                    self.record_step(
                        action="文件路径视觉模型调用成功",
                        input_data={
                            "model": model_name,
                            "image_path": img_path
                        },
                        output_data={
                            "response": content,
                            "usage": usage,
                            "duration": duration
                        }
                    )
                    
                    # 更新测试结果
                    test_case["passed"] = True
                    test_case["actual_result"] = content
                    
                    # 更新指标
                    self.test_results["metrics"]["total_llm_tokens"] += usage.get('total_tokens', 0)
                    self.test_results["metrics"]["total_execution_time"] += duration
                    
                else:
                    self.logger.error(f"响应格式错误: {response}")
                    test_case["error"] = "Invalid response format"
                    
            except Exception as e:
                self.logger.error(f"文件路径调用失败: {str(e)}")
                test_case["error"] = str(e)
                
        except Exception as e:
            self.logger.error(f"测试用例执行失败: {str(e)}")
            test_case["error"] = str(e)
        
        self.test_results["test_cases"].append(test_case)
    
    def run_all_tests(self):
        """运行所有测试用例"""
        self.logger.info("\n开始执行测试用例...")
        
        # 执行测试用例
        self.test_vision_model_with_base64()
        self.test_vision_model_with_file_path()
        
        # 判断整体测试是否成功
        self.test_results["success"] = all(
            tc["passed"] for tc in self.test_results["test_cases"]
        )
    
    def save_results(self):
        """保存测试结果"""
        # 记录最终状态
        self.process_data["test_info"]["end_time"] = datetime.now().isoformat()
        self.process_data["final_state"] = self.capture_state()
        
        # 计算总时长
        start = datetime.fromisoformat(self.process_data["test_info"]["start_time"])
        end = datetime.fromisoformat(self.process_data["test_info"]["end_time"])
        self.process_data["test_info"]["duration"] = (end - start).total_seconds()
        
        # 保存过程数据文件
        process_file = os.path.join(
            self.output_dir,
            f'test_{self.test_name}_{self.timestamp}_process.json'
        )
        with open(process_file, 'w', encoding='utf-8') as f:
            json.dump(self.process_data, f, ensure_ascii=False, indent=2)
        
        # 保存测试结果文件
        result_file = os.path.join(
            self.output_dir,
            f'test_{self.test_name}_{self.timestamp}_result.json'
        )
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)
        
        # 打印结果摘要
        self.logger.info("\n" + "="*60)
        self.logger.info("测试完成！")
        self.logger.info("="*60)
        self.logger.info(f"测试结果: {'成功' if self.test_results['success'] else '失败'}")
        self.logger.info(f"测试用例: {len(self.test_results['test_cases'])} 个")
        self.logger.info(f"成功: {sum(1 for tc in self.test_results['test_cases'] if tc['passed'])} 个")
        self.logger.info(f"失败: {sum(1 for tc in self.test_results['test_cases'] if not tc['passed'])} 个")
        self.logger.info(f"总Token使用: {self.test_results['metrics']['total_llm_tokens']}")
        self.logger.info(f"总执行时间: {self.test_results['metrics']['total_execution_time']:.2f} 秒")
        self.logger.info("\n结果文件已保存到:")
        self.logger.info(f"  日志: {os.path.abspath(process_file).replace('_process.json', '.log')}")
        self.logger.info(f"  过程: {os.path.abspath(process_file)}")
        self.logger.info(f"  结果: {os.path.abspath(result_file)}")


def main():
    """主函数"""
    print("开始测试视觉模型调用功能...")
    print("="*60)
    
    # 创建测试实例
    test = TestVisionModelReal()
    
    try:
        # 运行所有测试
        test.run_all_tests()
        
        # 保存结果
        test.save_results()
        
        # 返回状态码
        return 0 if test.test_results["success"] else 1
        
    except Exception as e:
        print(f"\n测试执行异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())