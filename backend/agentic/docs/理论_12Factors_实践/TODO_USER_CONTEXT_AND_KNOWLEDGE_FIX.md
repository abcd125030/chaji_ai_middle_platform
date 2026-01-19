# TODO: 用户上下文和知识库修复
**创建时间**: 2025-09-08 16:35:00  
**优先级**: 高  
**预计工时**: 2-3小时

## 背景信息

### 问题发现
通过分析日志 `/backend/logs/celery/pm2_celery_worker_1_combined.log` 发现：
1. 知识库工具返回值异常，mem0.add()返回None但被标记为成功
2. Planner生成的collection_name不符合预期，应使用用户专属collection
3. RuntimeState缺少用户上下文信息，导致工具无法获取真实用户ID
4. 缺少围绕用户信息的服务层

### 当前环境
- **运行环境**: macOS开发环境
- **服务管理**: PM2进程管理器运行Django服务器和Celery worker
- **Python环境**: 使用`.venv`虚拟环境
- **数据库**: PostgreSQL (localhost:5432, 用户postgres)
- **后端路径**: `/Users/chagee/Repos/X/backend`
- **激活虚拟环境**: `cd /Users/chagee/Repos/X/backend && source .venv/bin/activate`

## 目标

### 主要目标
1. **修复mem0返回值处理**: 确保正确判断存储是否成功
2. **建立用户服务层**: 提供统一的用户信息管理
3. **增强RuntimeState**: 添加用户上下文信息
4. **规范collection命名**: 强制使用用户专属的collection

### 具体指标
- mem0返回None时正确标记为失败
- 所有工具都能获取到用户ID
- 知识库数据按用户隔离存储
- Planner能够"认识"用户

## 做事的顺序

### 第一阶段：修复知识库返回值问题 ✅
1. ✅ 修改knowledge/services.py的mem0返回值处理逻辑
2. ✅ 增强错误日志记录

### 第二阶段：创建用户服务层 ✅
3. ✅ 创建agentic/user_service.py
4. ✅ 实现获取用户详细信息的方法
5. ✅ 添加用户标签、权限等结构化数据支持

### 第三阶段：增强RuntimeState ✅
6. ✅ 修改schemas.py添加user_context字段
7. ✅ 修改executor.py在初始化时注入用户信息

### 第四阶段：修改工具支持 ✅
8. ✅ 修改所有工具的get_input_schema添加user_id参数
9. ✅ 修改executor.py的_tool_executor_node自动注入user_id
10. ✅ 修改knowledge_base.py实现collection命名规范

## 需要阅读作为上下文的文件

### 核心实现文件
- `/backend/knowledge/services.py` - 知识库服务层（重点：170-178行）
- `/backend/tools/libs/knowledge_base.py` - 知识库工具（重点：85-160行）
- `/backend/agentic/executor.py` - 执行器（重点：76-154行，317-426行）
- `/backend/agentic/schemas.py` - 数据模型定义
- `/backend/agentic/graph_nodes.py` - 图节点定义

### 日志文件（用于验证）
- `/backend/logs/celery/pm2_celery_worker_1_combined.log` - 查看实际执行日志

## 涉及到要修改的文件

### 主要修改文件

1. **`/backend/knowledge/services.py`**
   - 修改mem0返回值处理逻辑（170-178行）
   - 增强错误日志记录

2. **`/backend/authentication/user_service.py`** (新建)
   - 创建用户服务层
   - 提供获取用户详细信息的服务

3. **`/backend/agentic/schemas.py`**
   - 添加user_context字段到RuntimeState

4. **`/backend/agentic/executor.py`**
   - 初始化RuntimeState时注入用户信息（149-154行）
   - _tool_executor_node中自动注入user_id（364-376行）

5. **`/backend/agentic/graph_nodes.py`**
   - planner_node函数中添加用户信息到system prompt

6. **`/backend/tools/libs/knowledge_base.py`**
   - execute方法中处理user_id（87-88行）
   - _store_knowledge方法中强制使用用户专属collection（119行）

### 可能需要修改的文件

7. **`/backend/tools/libs/`目录下其他工具**
   - 所有工具类的get_input_schema添加user_id参数

## 危险事项 ⚠️

### 严禁操作
1. **❌ 不要修改数据库中已保存的配置**
2. **❌ 不要重启PM2服务**
3. **❌ 不要删除已有的知识库数据**

### 需要特别注意
4. **⚠️ 保持向后兼容**
   - 确保user_id参数有默认值
   - 不破坏现有的工具调用

5. **⚠️ 数据隔离安全**
   - 确保用户数据严格隔离
   - collection命名必须包含用户标识

## 验收标准

1. **mem0返回值正确处理**
   - 返回None时正确标记为失败
   - 日志清晰区分成功和失败

2. **用户上下文完整**
   - RuntimeState包含用户信息
   - Planner能够识别用户

3. **工具获取用户ID**
   - 所有工具都能获取到正确的user_id
   - 不需要Planner显式传递

4. **知识库数据隔离**
   - collection名称格式：`user_{user_id}_{collection_name}`
   - 不同用户的数据完全隔离

## 风险评估

- **低风险**: 日志增强、错误处理改进
- **中风险**: RuntimeState修改、工具参数添加
- **高风险**: 知识库collection命名规范（影响数据存储）

## 回滚方案

如果修改导致问题：
1. 使用git回滚到修改前的版本
2. 检查知识库数据完整性
3. 重新评估用户隔离方案