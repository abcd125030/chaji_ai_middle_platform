# MinerU v2.2.2 升级文档

## 升级日期
2025-09-10

## 版本信息
- **旧版本**: 2.1.0
- **新版本**: 2.2.2

## 主要升级内容

### 1. 新功能特性

#### v2.2.0 主要更新
- **新增表格识别模型**: 提高表格解析准确率
- **跨页表格合并支持**: 自动识别并合并跨页的表格
- **改进的表格解析精度**: 更准确的表格结构识别
- **新增语言支持**: 添加泰语(th)和希腊语(el)的OCR支持
- **JSON输出增强**: 输出JSON中新增`bbox`字段

#### v2.2.1 更新
- 添加新模型到下载列表

#### v2.2.2 更新
- 修复表格识别模型影响解析任务的问题

### 2. 代码更改

#### 2.1 依赖更新
**文件**: `backend/requirements.txt`
```diff
- mineru==2.1.0
+ mineru==2.2.2
```

#### 2.2 服务层更新
**文件**: `backend/mineru/services.py`
- 新增参数支持:
  - `enable_table_merge`: 启用跨页表格合并（默认True）
  - `use_new_table_model`: 使用新的表格识别模型（默认True）
- 新增统计字段: `cross_page_tables` 跨页表格计数

#### 2.3 配置更新
**文件**: `backend/backend/settings.py`
```python
MINERU_SETTINGS = {
    # ... 原有配置
    # MinerU v2.2 新特性
    'ENABLE_TABLE_MERGE': True,  # 启用跨页表格合并
    'USE_NEW_TABLE_MODEL': True,  # 使用新的表格识别模型
    'SUPPORT_LANGUAGES': ['en', 'zh', 'th', 'el'],  # 新增泰语和希腊语支持
}
```

#### 2.4 数据模型更新
**文件**: `backend/mineru/models.py`

新增字段:
- `PDFParseTask`:
  - `enable_table_merge`: BooleanField - 启用跨页表格合并
  - `use_new_table_model`: BooleanField - 使用新表格识别模型
- `ParseResult`:
  - `cross_page_tables`: IntegerField - 跨页表格数统计

#### 2.5 任务处理更新
**文件**: `backend/mineru/tasks.py`
- 从配置读取v2.2特性设置
- 传递新参数给MinerUService
- 保存cross_page_tables统计信息

### 3. 数据库迁移

已创建迁移文件: `mineru/migrations/0002_add_mineru_v2_2_features.py`

执行迁移:
```bash
cd /Users/chagee/Repos/X/backend
source .venv/bin/activate
python manage.py migrate mineru
```

### 4. 升级步骤

1. **更新依赖包**
```bash
cd /Users/chagee/Repos/X/backend
source .venv/bin/activate
pip install -U mineru==2.2.2
```

2. **执行数据库迁移**
```bash
python manage.py migrate mineru
```

3. **重启服务**
```bash
pm2 restart backend-django
pm2 restart backend-celery
```

### 5. 测试要点

1. **基础功能测试**
   - PDF文件上传和解析
   - 检查解析结果的准确性

2. **新功能测试**
   - 测试包含跨页表格的PDF文档
   - 验证跨页表格是否正确合并
   - 测试泰语和希腊语文档的OCR识别
   - 检查JSON输出中的bbox字段

3. **性能测试**
   - 对比v2.1.0和v2.2.2的解析速度
   - 检查内存使用情况

### 6. 回滚方案

如需回滚到v2.1.0:

1. **恢复代码**
```bash
git checkout HEAD~1 -- backend/requirements.txt backend/mineru/
```

2. **回滚迁移**
```bash
python manage.py migrate mineru 0001_initial
```

3. **降级包**
```bash
pip install mineru==2.1.0
```

4. **重启服务**
```bash
pm2 restart backend-django
pm2 restart backend-celery
```

### 7. 注意事项

1. **命令行参数变化**: v2.2版本的命令行工具可能有新的参数，如`--table-merge`和`--table-model`，这些已在代码中适配
2. **模型下载**: 首次使用新的表格识别模型时，MinerU可能需要下载新的模型文件
3. **兼容性**: v2.2保持了向后兼容，不会影响现有功能

### 8. 参考资源

- [MinerU GitHub仓库](https://github.com/opendatalab/MinerU)
- [MinerU PyPI页面](https://pypi.org/project/mineru/)
- [MinerU v2.2.0 Release Notes](https://github.com/opendatalab/MinerU/releases/tag/mineru-2.2.0-released)

## 更新记录

| 日期 | 版本 | 更新内容 | 更新者 |
|------|------|----------|--------|
| 2025-09-10 | 2.1.0 → 2.2.2 | 升级MinerU支持跨页表格合并和新表格识别模型 | Claude Code |