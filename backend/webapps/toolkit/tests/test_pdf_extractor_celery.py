"""
PDF提取器Celery任务流程测试

测试完整的PDF提取流程：
1. 创建任务记录
2. 保存PDF文件
3. 提交Celery任务
4. 等待任务完成
5. 验证输出结果
"""
import os
import json
import shutil
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from django.test import TestCase
from django.conf import settings
from django.db import transaction

from webapps.toolkit.models import PDFExtractorTask
from webapps.toolkit.tasks import process_pdf_extraction
from webapps.toolkit.utils import FileManager


class PDFExtractorCeleryFlowTestCase(TestCase):
    """
    PDF提取器Celery流程测试基类

    遵循"在隔离环境中重建真实状态"的原则
    """

    @classmethod
    def setUpTestData(cls):
        """
        在整个测试类运行前执行一次
        准备测试所需的配置数据
        """
        print("\n" + "="*70)
        print(f"[{cls.__name__}] Running setUpTestData: Preparing test environment...")

        try:
            with transaction.atomic():
                # 这里可以添加需要的配置项
                # 例如：从真实数据库读取必要配置并创建到测试数据库
                pass

            print(f"[{cls.__name__}] setUpTestData completed successfully.")
        except Exception as e:
            print(f"[{cls.__name__}] CRITICAL: Failed to set up test data: {e}")
            raise
        print("="*70)

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

        # --- 状态捕获和数据记录 ---
        self.initial_state = self.capture_state("initial")
        self.process_data = {
            "test_info": {
                "name": f"{self.__class__.__name__}.{test_method_name}",
                "start_time": datetime.now().isoformat()
            },
            "initial_state": self.initial_state,
            "execution_steps": []
        }

        # --- 测试文件路径 ---
        self.test_pdf_path = Path(settings.BASE_DIR) / 'webapps' / 'toolkit' / 'exp' / 'Agentic-Context-Engineering-Evolving-Contexts-for-Self-Improving-Language-Models.pdf'

        if not self.test_pdf_path.exists():
            raise FileNotFoundError(f"测试PDF文件不存在: {self.test_pdf_path}")

        self.logger.info(f"测试PDF文件: {self.test_pdf_path}")

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

    def capture_state(self, stage: str):
        """
        捕获当前数据库状态

        Args:
            stage: 'initial' 或 'final'
        """
        self.logger.info(f"Capturing {stage} state...")

        # 捕获PDFExtractorTask表状态
        tasks_snapshot = list(PDFExtractorTask.objects.values(
            'id', 'original_filename', 'status', 'total_pages', 'processed_pages'
        ))

        return {
            "database": {
                "PDFExtractorTask_count": PDFExtractorTask.objects.count(),
                "PDFExtractorTask_records": tasks_snapshot
            }
        }

    def record_step(self, action, input_data, output_data, **kwargs):
        """记录执行步骤"""
        step_number = len(self.process_data["execution_steps"]) + 1
        step_data = {
            "step": step_number,
            "action": action,
            "input": str(input_data)[:500],  # 限制长度
            "output": str(output_data)[:500],  # 限制长度
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.process_data["execution_steps"].append(step_data)
        self.logger.info(f"Step {step_number}: {action} recorded.")

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
        self.process_data["final_state"] = self.capture_state("final")

        # 保存过程数据
        process_file = self.output_dir / self.process_filename
        try:
            with open(process_file, 'w', encoding='utf-8') as f:
                json.dump(self.process_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to write process file: {e}")

        self.logger.info(f"Test method finished. Duration: {duration:.2f}s")
        print(f"\n[INFO] Test outputs saved to directory: {self.output_dir.absolute()}")


class TestPDFExtractorCeleryFlow(PDFExtractorCeleryFlowTestCase):
    """测试PDF提取器完整Celery流程"""

    def test_complete_pdf_extraction_flow(self):
        """
        测试完整的PDF提取流程

        步骤：
        1. 创建任务UUID和目录
        2. 复制测试PDF到任务目录
        3. 创建数据库任务记录
        4. 同步调用Celery任务（测试环境）
        5. 验证任务状态
        6. 验证输出文件
        7. 验证结果内容
        """
        self.logger.info("="*70)
        self.logger.info("开始测试: 完整PDF提取流程")
        self.logger.info("="*70)

        # ==================== 步骤1: 创建任务UUID和目录 ====================
        task_id = str(uuid.uuid4())
        task_dir = FileManager.create_task_directory(task_id)

        self.record_step(
            action="创建任务目录",
            input_data={"task_id": task_id},
            output_data={"task_dir": str(task_dir)}
        )
        self.logger.info(f"✅ 步骤1完成: 任务ID={task_id}, 目录={task_dir}")

        # ==================== 步骤2: 复制测试PDF到任务目录 ====================
        pdf_filename = f"{task_id}.pdf"
        pdf_path = task_dir / pdf_filename
        shutil.copy(self.test_pdf_path, pdf_path)

        self.record_step(
            action="复制PDF文件",
            input_data={"source": str(self.test_pdf_path)},
            output_data={"destination": str(pdf_path), "size_mb": pdf_path.stat().st_size / 1024 / 1024}
        )
        self.logger.info(f"✅ 步骤2完成: PDF已复制到 {pdf_path}")

        # ==================== 步骤3: 创建数据库任务记录 ====================
        task = PDFExtractorTask.objects.create(
            id=task_id,
            original_filename=self.test_pdf_path.name,
            file_path=str(pdf_path),
            status='pending'
        )

        self.record_step(
            action="创建任务记录",
            input_data={
                "task_id": str(task_id),
                "original_filename": self.test_pdf_path.name,
                "file_path": str(pdf_path)
            },
            output_data={"task_status": task.status}
        )
        self.logger.info(f"✅ 步骤3完成: 任务记录已创建, 状态={task.status}")

        # ==================== 步骤4: 同步调用Celery任务 ====================
        self.logger.info("开始执行Celery任务（同步模式）...")
        start_processing_time = datetime.now()

        try:
            # 在测试环境中同步调用任务
            result = process_pdf_extraction(str(task.id), str(pdf_path))

            processing_duration = (datetime.now() - start_processing_time).total_seconds()

            self.record_step(
                action="执行Celery任务",
                input_data={"task_id": str(task_id), "pdf_path": str(pdf_path)},
                output_data={"result": result, "duration": processing_duration}
            )
            self.logger.info(f"✅ 步骤4完成: Celery任务执行完成, 耗时={processing_duration:.2f}秒")

        except Exception as e:
            self.logger.error(f"❌ Celery任务执行失败: {str(e)}", exc_info=True)
            self.record_step(
                action="执行Celery任务",
                input_data={"task_id": str(task_id)},
                output_data={"error": str(e)},
                status="failed"
            )
            raise

        # ==================== 步骤5: 验证任务状态 ====================
        task.refresh_from_db()

        self.logger.info(f"任务状态: {task.status}")
        self.logger.info(f"总页数: {task.total_pages}")
        self.logger.info(f"已处理页数: {task.processed_pages}")

        self.record_step(
            action="验证任务状态",
            input_data={"task_id": str(task_id)},
            output_data={
                "status": task.status,
                "total_pages": task.total_pages,
                "processed_pages": task.processed_pages
            }
        )

        # 断言任务完成
        self.assertIn(task.status, ['completed', 'completed_with_errors'],
                     f"任务状态应为completed或completed_with_errors，实际为: {task.status}")
        self.assertGreater(task.total_pages, 0, "总页数应大于0")
        self.assertEqual(task.processed_pages, task.total_pages,
                        f"已处理页数({task.processed_pages})应等于总页数({task.total_pages})")

        self.logger.info("✅ 步骤5完成: 任务状态验证通过")

        # ==================== 步骤6: 验证输出文件结构 ====================
        self.logger.info("检查输出文件结构...")

        expected_files = []

        # 检查task.json
        task_json_path = task_dir / 'task.json'
        if task_json_path.exists():
            expected_files.append(str(task_json_path))
            with open(task_json_path, 'r', encoding='utf-8') as f:
                task_json_data = json.load(f)
            self.logger.info(f"  ✓ task.json存在: {task_json_data.get('status')}")

        # 检查最终markdown
        final_md_path = task_dir / f"{task_id}_result.md"
        if final_md_path.exists():
            expected_files.append(str(final_md_path))
            md_size = final_md_path.stat().st_size
            self.logger.info(f"  ✓ 最终markdown存在: {final_md_path.name}, 大小={md_size}字节")

        # 检查页面目录
        page_dirs = sorted(task_dir.glob('page_*'))
        for page_dir in page_dirs:
            if page_dir.is_dir():
                self.logger.info(f"  ✓ 页面目录: {page_dir.name}")

                # 检查页面文件
                page_files = list(page_dir.glob('*'))
                for page_file in page_files:
                    expected_files.append(str(page_file))
                    self.logger.info(f"    - {page_file.name}")

        self.record_step(
            action="验证输出文件",
            input_data={"task_dir": str(task_dir)},
            output_data={
                "total_files": len(expected_files),
                "page_dirs": len(page_dirs),
                "files": expected_files[:20]  # 限制记录数量
            }
        )

        # 断言关键文件存在
        self.assertTrue(task_json_path.exists(), "task.json应该存在")
        self.assertTrue(final_md_path.exists(), "最终markdown文件应该存在")
        self.assertGreater(len(page_dirs), 0, "应该至少有一个页面目录")

        self.logger.info(f"✅ 步骤6完成: 输出文件结构验证通过, 共{len(expected_files)}个文件")

        # ==================== 步骤7: 保存测试结果 ====================
        test_result = {
            "test_name": "test_complete_pdf_extraction_flow",
            "task_id": str(task_id),
            "status": "success",
            "task_status": task.status,
            "total_pages": task.total_pages,
            "processed_pages": task.processed_pages,
            "processing_duration": processing_duration,
            "output_files_count": len(expected_files),
            "task_dir": str(task_dir),
            "final_markdown": str(final_md_path) if final_md_path.exists() else None
        }

        result_file = self.output_dir / self.result_filename
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(test_result, f, ensure_ascii=False, indent=2, default=str)

        self.logger.info("="*70)
        self.logger.info("✅ 测试完成: 所有验证通过")
        self.logger.info(f"📁 任务目录: {task_dir}")
        self.logger.info(f"📄 最终结果: {final_md_path}")
        self.logger.info(f"📊 测试报告: {result_file}")
        self.logger.info("="*70)
