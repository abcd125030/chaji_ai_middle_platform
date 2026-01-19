# Toolkit 应用测试

## 测试文件

### test_pdf_extractor_celery.py
测试PDF提取器的完整Celery流程。

**测试内容：**
1. 创建任务记录
2. 保存PDF文件到任务目录
3. 同步执行Celery任务
4. 验证任务状态（completed）
5. 验证输出文件结构（task.json, 页面目录, 最终markdown）
6. 生成测试报告

**测试用例：**
- `test_complete_pdf_extraction_flow` - 完整PDF提取流程测试

## 运行测试

### 运行单个测试文件
```bash
cd /Users/chagee/Repos/X/backend
source .venv/bin/activate
python manage.py test webapps.toolkit.tests.test_pdf_extractor_celery
```

### 运行单个测试方法
```bash
python manage.py test webapps.toolkit.tests.test_pdf_extractor_celery.TestPDFExtractorCeleryFlow.test_complete_pdf_extraction_flow
```

### 运行所有toolkit测试
```bash
python manage.py test webapps.toolkit.tests
```

### 详细输出模式
```bash
python manage.py test webapps.toolkit.tests.test_pdf_extractor_celery --verbosity=2
```

## 测试输出

所有测试输出保存在 `webapps/toolkit/tests/outputs/` 目录下：

### 文件命名规范
```
[文件类型]-[YYYYMMDD]-[HHMMSS]-[测试名称].[扩展名]
```

### 输出文件类型

1. **process-*.json** - 测试执行过程数据
   - 包含所有执行步骤
   - 记录初始和最终状态
   - 详细的输入输出数据

2. **log-*.log** - 测试日志
   - 详细的执行日志
   - 错误堆栈信息
   - 时间戳记录

3. **result-*.json** - 测试结果摘要
   - 任务执行结果
   - 性能数据（处理时长等）
   - 输出文件统计

### 示例
```
outputs/
├── process-20251009-152030-test_complete_pdf_extraction_flow.json
├── log-20251009-152030-test_complete_pdf_extraction_flow.log
└── result-20251009-152030-test_complete_pdf_extraction_flow.json
```

## 测试数据

### 测试PDF文件
- 位置: `webapps/toolkit/exp/CHARM- Control-point-based 3D Anime Hairstyle Auto-Regressive Modeling.pdf`
- 用途: 作为PDF提取流程的测试输入

### 任务输出目录
PDF提取任务的输出保存在：
```
media/oss-bucket/_toolkit/_extractor/{task_id}/
```

## 注意事项

1. **测试环境**
   - 使用Django TestCase的独立测试数据库
   - 每个测试方法结束后自动清理数据库
   - 不影响开发数据库

2. **Celery模式**
   - 测试中使用同步模式执行Celery任务
   - 不需要启动Celery worker
   - 直接调用任务函数进行测试

3. **环境变量**
   - 需要配置 `DASHSCOPE_API_KEY` 环境变量
   - 确保模型配置正确

4. **清理**
   - 测试数据库会自动清理
   - 任务输出目录（media/oss-bucket/_toolkit/_extractor/）需要手动清理
   - 测试输出（outputs/）目录已在.gitignore中排除

## 故障排查

### 常见错误

1. **ModuleNotFoundError: No module named 'fitz'**
   ```bash
   pip install PyMuPDF>=1.24.0
   ```

2. **DASHSCOPE_API_KEY not found**
   - 在 `.env` 文件中配置API密钥
   - 或在运行测试前设置环境变量

3. **测试PDF文件不存在**
   - 确保 `webapps/toolkit/exp/` 目录下有测试PDF文件
   - 或修改测试代码使用其他PDF文件

## 测试规范

本测试遵循 [backend/单元测试规范.md](../../../单元测试规范.md) 中的规范：

- ✅ 使用Django TestCase隔离数据库
- ✅ 调用真实的业务逻辑（禁止mock）
- ✅ 使用setUpTestData加载共享配置
- ✅ 使用setUp/tearDown管理测试生命周期
- ✅ 完整的状态捕获和记录
- ✅ 规范的输出文件命名
