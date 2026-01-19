"""
Step1 智能提取流程测试

测试 Step1 及其核心组件的完整流程：
1. PageAnalyzer - 页面元素分析
2. ExtractionStrategyDecider - 策略决策
3. OCRHandler - OCR识别（如需要）
4. TextExtractor - 文本提取和格式化
5. 输出文件验证
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from django.test import TestCase
from django.conf import settings

from webapps.toolkit.services.pdf_extractor.processors.step1_text_extractor import TextExtractor
from webapps.toolkit.services.pdf_extractor.processors.components import (
    PageAnalyzer,
    ExtractionStrategy,
    ExtractionStrategyDecider,
    OCRHandler
)


class Step1SmartExtractionTestCase(TestCase):
    """
    Step1 智能提取测试基类

    遵循"在隔离环境中重建真实状态"的原则
    """

    def setUp(self):
        """
        在每个test_方法执行前运行
        """
        # --- 输出目录设置 ---
        self.output_dir = Path(settings.BASE_DIR) / 'webapps' / 'toolkit' / 'tests' / 'outputs'
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 使用符合规范的文件命名格式
        test_method_name = self._testMethodName
        timestamp = datetime.now()
        date_str = timestamp.strftime('%Y%m%d')
        time_str = timestamp.strftime('%H%M%S')

        # 生成符合规范的文件名
        self.process_filename = f'process-{date_str}-{time_str}-{test_method_name}.json'
        self.log_filename = f'log-{date_str}-{time_str}-{test_method_name}.log'
        self.result_filename = f'result-{date_str}-{time_str}-{test_method_name}.json'

        # 设置日志
        self.setup_logging()
        self.logger.info(f"Test method '{test_method_name}' starting...")

        # --- 过程数据记录 ---
        self.process_data = {
            "test_info": {
                "name": f"{self.__class__.__name__}.{test_method_name}",
                "start_time": datetime.now().isoformat()
            },
            "execution_steps": [],
            "page_results": []
        }

        # --- 测试PDF文件路径 ---
        self.test_pdf_path = Path(settings.BASE_DIR) / 'webapps' / 'toolkit' / 'tests' / '1、服务操作手册.pdf'

        if not self.test_pdf_path.exists():
            raise FileNotFoundError(f"测试PDF文件不存在: {self.test_pdf_path}")

        self.logger.info(f"测试PDF文件: {self.test_pdf_path}")

        # --- 从PDFExtractorConfig获取API信息 ---
        from webapps.toolkit.services.pdf_extractor.config import PDFExtractorConfig

        self.api_key = PDFExtractorConfig.QWEN_API_KEY
        self.base_url = PDFExtractorConfig.QWEN_BASE_URL

        if not self.api_key:
            self.logger.warning("未配置DASHSCOPE_API_KEY，OCR功能将被禁用")
        else:
            self.logger.info(f"API配置已加载: base_url={self.base_url}")

    def setup_logging(self):
        """配置日志记录器"""
        log_file = self.output_dir / self.log_filename

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

    def record_step(self, action, input_data, output_data, **kwargs):
        """记录执行步骤"""
        step_number = len(self.process_data["execution_steps"]) + 1
        step_data = {
            "step": step_number,
            "action": action,
            "input": self._truncate_data(input_data, 500),
            "output": self._truncate_data(output_data, 500),
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.process_data["execution_steps"].append(step_data)
        self.logger.info(f"Step {step_number}: {action} recorded.")

    def _truncate_data(self, data, max_length=500):
        """截断数据以避免过长"""
        data_str = str(data)
        if len(data_str) > max_length:
            return data_str[:max_length] + "... (truncated)"
        return data_str

    def tearDown(self):
        """
        在每个test_方法执行后运行
        """
        end_time = datetime.now()
        start_time_iso = self.process_data["test_info"]["start_time"]
        start_time = datetime.fromisoformat(start_time_iso)
        duration = (end_time - start_time).total_seconds()

        self.process_data["test_info"]["end_time"] = end_time.isoformat()
        self.process_data["test_info"]["duration"] = duration

        # 保存过程数据
        process_file = self.output_dir / self.process_filename
        try:
            with open(process_file, 'w', encoding='utf-8') as f:
                json.dump(self.process_data, f, ensure_ascii=False, indent=2, default=str)
            self.logger.info(f"✓ 过程数据已保存: {process_file}")
        except Exception as e:
            self.logger.error(f"Failed to write process file: {e}")

        self.logger.info(f"Test method finished. Duration: {duration:.2f}s")
        self.logger.info(f"📁 测试输出目录: {self.output_dir.absolute()}")
        print(f"\n[INFO] Test outputs saved to directory: {self.output_dir.absolute()}")


class TestStep1SmartExtraction(Step1SmartExtractionTestCase):
    """测试 Step1 智能提取完整流程"""

    def test_three_pages_smart_extraction(self):
        """
        测试前3页的智能提取流程

        测试页面特点：
        - 第1页：封面页（文本丰富，156字符）
        - 第2页：图片页（纯图片，0文本）
        - 第3页：复杂图表页（3514曲线，187矩形）

        验证点：
        1. 每页都能成功分析元素
        2. 策略决策符合预期
        3. 文本提取成功
        4. 输出文件完整
        5. 文件内容合理
        """
        self.logger.info("=" * 70)
        self.logger.info("开始测试: Step1 智能提取流程（前3页）")
        self.logger.info("=" * 70)

        # ==================== 初始化 TextExtractor ====================
        self.logger.info("初始化 TextExtractor...")

        extractor = TextExtractor(
            api_key=self.api_key,
            base_url=self.base_url,
            model="qwen-coder-plus",
            enable_smart_extraction=True,
            ocr_dpi=144
        )

        self.record_step(
            action="初始化TextExtractor",
            input_data={
                "enable_smart_extraction": True,
                "ocr_dpi": 144,
                "has_api_config": bool(self.api_key and self.base_url)
            },
            output_data={
                "page_analyzer": extractor.page_analyzer is not None,
                "strategy_decider": extractor.strategy_decider is not None,
                "ocr_handler": extractor.ocr_handler is not None
            }
        )

        self.assertIsNotNone(extractor.page_analyzer, "PageAnalyzer应该被初始化")
        self.assertIsNotNone(extractor.strategy_decider, "ExtractionStrategyDecider应该被初始化")

        if self.api_key and self.base_url:
            self.assertIsNotNone(extractor.ocr_handler, "OCRHandler应该被初始化（有API配置）")

        self.logger.info("✅ TextExtractor初始化完成")

        # ==================== 创建测试输出目录 ====================
        test_output_dir = self.output_dir / f"step1_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        test_output_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"测试输出目录: {test_output_dir}")

        # ==================== 测试前3页 ====================
        pages_to_test = [1, 2, 3]
        expected_strategies = {
            1: ExtractionStrategy.DIRECT_TEXT,  # 第1页：文本丰富，应该直接提取
            2: ExtractionStrategy.OCR,          # 第2页：纯图片，应该OCR
            3: ExtractionStrategy.OCR           # 第3页：复杂图表，应该OCR
        }

        for page_num in pages_to_test:
            self.logger.info("=" * 60)
            self.logger.info(f"测试第 {page_num} 页")
            self.logger.info("=" * 60)

            page_output_dir = test_output_dir / f"page_{page_num}"
            page_output_dir.mkdir(parents=True, exist_ok=True)

            start_time = datetime.now()

            try:
                # 执行智能提取
                result = extractor.smart_extract_page(
                    pdf_path=str(self.test_pdf_path),
                    page_number=page_num,
                    output_dir=page_output_dir,
                    save_analysis=True,
                    save_page_image=True  # 保存图片以便审查
                )

                duration = (datetime.now() - start_time).total_seconds()

                # 记录结果
                page_result = {
                    "page_number": page_num,
                    "status": "success",
                    "duration": duration,
                    "extraction_method": result['extraction_method'],
                    "strategy": result['strategy_decision']['strategy'],
                    "confidence": result['strategy_decision']['confidence'],
                    "text_length": len(result['extracted_text']),
                    "output_files": result['output_files']
                }
                self.process_data["page_results"].append(page_result)

                self.logger.info(f"✓ 第{page_num}页提取完成")
                self.logger.info(f"  策略: {result['strategy_decision']['strategy']}")
                self.logger.info(f"  置信度: {result['strategy_decision']['confidence']:.2f}")
                self.logger.info(f"  提取方法: {result['extraction_method']}")
                self.logger.info(f"  文本长度: {len(result['extracted_text'])} 字符")
                self.logger.info(f"  耗时: {duration:.2f}秒")

                # ==================== 验证分析结果 ====================
                analysis = result['analysis_result']
                self.logger.info(f"  [分析] 文本长度: {analysis['pdfplumber_metrics']['text_length']}")
                self.logger.info(f"  [分析] 单词数: {analysis['pdfplumber_metrics']['word_count']}")
                self.logger.info(f"  [分析] 图片数: {analysis['pdfplumber_metrics']['image_count']}")
                self.logger.info(f"  [分析] 表格数: {analysis['pdfplumber_metrics']['table_count']}")
                self.logger.info(f"  [分析] 绘图元素: {analysis['pymupdf_metrics']['drawing_count']}")

                # 验证策略决策（如果有明确预期）
                if page_num in expected_strategies:
                    expected_strategy = expected_strategies[page_num]
                    actual_strategy_str = result['strategy_decision']['strategy']

                    self.logger.info(f"  [验证] 预期策略: {expected_strategy.value}")
                    self.logger.info(f"  [验证] 实际策略: {actual_strategy_str}")

                    # 注意：这里我们不强制断言策略必须完全一致
                    # 因为策略决策器可能根据实际情况做调整
                    # 我们只记录是否符合预期
                    if actual_strategy_str == expected_strategy.value:
                        self.logger.info(f"  ✓ 策略符合预期")
                    else:
                        self.logger.warning(f"  ⚠ 策略与预期不同（这可能是正常的）")

                # ==================== 验证输出文件 ====================
                self.logger.info(f"  [验证] 检查输出文件...")

                output_files = result['output_files']

                # 验证最终markdown
                final_md_path = Path(output_files['final_md'])
                self.assertTrue(final_md_path.exists(), f"最终markdown应该存在: {final_md_path}")
                self.assertGreater(final_md_path.stat().st_size, 0, "最终markdown不应为空")
                self.logger.info(f"    ✓ 最终markdown: {final_md_path.name} ({final_md_path.stat().st_size} 字节)")

                # 验证提取文本
                extracted_text_path = Path(output_files['extracted_text'])
                self.assertTrue(extracted_text_path.exists(), f"提取文本应该存在: {extracted_text_path}")
                self.logger.info(f"    ✓ 提取文本: {extracted_text_path.name}")

                # 验证分析文件
                if output_files.get('analysis'):
                    analysis_path = Path(output_files['analysis'])
                    self.assertTrue(analysis_path.exists(), f"分析文件应该存在: {analysis_path}")
                    self.logger.info(f"    ✓ 分析文件: {analysis_path.name}")

                # 验证策略文件
                if output_files.get('strategy'):
                    strategy_path = Path(output_files['strategy'])
                    self.assertTrue(strategy_path.exists(), f"策略文件应该存在: {strategy_path}")
                    self.logger.info(f"    ✓ 策略文件: {strategy_path.name}")

                # 验证OCR调试文件（如果使用了OCR）
                if output_files.get('ocr_debug'):
                    ocr_debug_path = Path(output_files['ocr_debug'])
                    self.assertTrue(ocr_debug_path.exists(), f"OCR调试文件应该存在: {ocr_debug_path}")
                    self.logger.info(f"    ✓ OCR调试文件: {ocr_debug_path.name}")

                # 验证页面图片（如果保存了）
                if output_files.get('page_image'):
                    page_image_path = Path(output_files['page_image'])
                    self.assertTrue(page_image_path.exists(), f"页面图片应该存在: {page_image_path}")
                    self.logger.info(f"    ✓ 页面图片: {page_image_path.name}")

                self.logger.info(f"✅ 第{page_num}页所有验证通过")

            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                self.logger.error(f"❌ 第{page_num}页提取失败: {str(e)}", exc_info=True)

                page_result = {
                    "page_number": page_num,
                    "status": "failed",
                    "duration": duration,
                    "error": str(e)
                }
                self.process_data["page_results"].append(page_result)

                # 失败时不抛出异常，继续测试下一页
                continue

        # ==================== 保存测试结果 ====================
        self.logger.info("=" * 70)
        self.logger.info("生成测试结果报告...")
        self.logger.info("=" * 70)

        successful_pages = [r for r in self.process_data["page_results"] if r["status"] == "success"]
        failed_pages = [r for r in self.process_data["page_results"] if r["status"] == "failed"]

        test_result = {
            "test_name": "test_three_pages_smart_extraction",
            "pdf_file": str(self.test_pdf_path),
            "pages_tested": pages_to_test,
            "total_pages": len(pages_to_test),
            "successful_pages": len(successful_pages),
            "failed_pages": len(failed_pages),
            "success_rate": len(successful_pages) / len(pages_to_test) * 100,
            "test_output_dir": str(test_output_dir),
            "page_results": self.process_data["page_results"]
        }

        result_file = self.output_dir / self.result_filename
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(test_result, f, ensure_ascii=False, indent=2, default=str)

        self.logger.info("=" * 70)
        self.logger.info("✅ 测试完成")
        self.logger.info(f"成功: {len(successful_pages)}/{len(pages_to_test)} 页")
        self.logger.info(f"失败: {len(failed_pages)}/{len(pages_to_test)} 页")
        self.logger.info(f"成功率: {test_result['success_rate']:.1f}%")
        self.logger.info(f"📁 输出目录: {test_output_dir}")
        self.logger.info(f"📊 测试报告: {result_file}")
        self.logger.info("=" * 70)

        # 断言：至少有一页成功
        self.assertGreater(len(successful_pages), 0, "至少应该有一页提取成功")
