# 任务
- [x] admin视图缺少 "生图成功失败"的筛选器。（已完成 2025-08-14）
- [x] 获取新的接口文档然后在 notebook/volcengine_test 下修改测试脚本实验，目标是测试返回url的方式。基于测试用例1修改。文档：https://www.volcengine.com/docs/6793/1472219
- [x] 《同步转异步接口使用说明》接口文档内容保存为md文件放在 backend/customized/image_editor/业务文档 下，与 backend/customized/image_editor/业务文档/火山引擎主体分割API文档.md 相对应。
- [x] 测试脚本缺陷检查：return_url的这个能力,在"同步转异步"方法里是否有什么前置配置要求? 你的脚本是否按照"同步转异步"方法实现？并通过查询来获得结果?（已完成检查 2025-08-14）
	- 发现问题：原脚本test_return_url.py使用的是同步接口CVProcess，return_url不生效
	- 解决方案：创建了test_async_return_url.py，正确实现了同步转异步方法
	- 关键发现：return_url必须在CVSync2AsyncGetResult查询接口的req_json中设置才生效
- [ ] 2025-08-14 13:31:53 整理 image editor 下业务实现所涉及的以下知识，保存目录backend/customized/image_editor/新知识：
	- Redis队列 
	- Celery工作原理/机制/流程
	- 任务流转的过程和关键信息和关键动作
	- pgbouncer的用途和面向多数据库的用法
	- 接口返回较大数据值时的优化方法

- [ ] base64存储不能按照原尺寸，得缩小到最大720px(宽高取优先)
- [ ] redis 队列如果崩溃，从持久化恢复？
- [ ] redis 队列超时时间，

- [x] 服务器配置问题：修改ecosystem配置把daphne改成gunicorn

- [x] 迭代预检流程输出结构化内容。（已完成 2025-08-14）
	- 添加 response_format: json_object 强制结构化输出
	- 升级为极其详细的宠物描述（150-300字，覆盖7个维度）
	- 新增 pet_description 字段存储详细描述
	- 从图生图（Seededit I2I）切换到文生图（Seedream T2I）
	- 实现提示词组合策略：宠物描述 + 风格化要求
	- 跳过一致性检查（文生图不需要原图对比）
	- 完善配置系统，支持Django Admin在线调整
	- 创建3个数据库迁移文件
	- 详见：《迭代说明_从图生图到文生图.md》


- [ ] **Celery 假死问题修复**（2025-08-15 添加）
	- **问题描述**：prod_check_and_start.sh 启动的 Celery workers 可能运行一段时间后假死
	- **原因分析**：
		1. 使用 nohup 直接启动，缺少进程监控和自动重启机制
		2. Gevent 协程池配置过高（400协程×10 workers = 4000并发），可能导致协程泄漏
		3. 禁用了心跳检测（--without-heartbeat），无法及时发现 worker 失活
		4. 内存限制在 gevent 模式下可能不生效
		5. 日志文件无轮转机制，可能导致磁盘满
		6. PgBouncer 连接池只有 200，可能被 4000 并发耗尽
	- **改进方案**：
		1. 使用 Supervisor 或 systemd 管理 Celery 进程，实现自动重启
		2. 移除 --without-heartbeat 参数，启用心跳检测
		3. 降低并发数或增加 PgBouncer 连接池大小
		4. 配置日志轮转（logrotate）
		5. 添加健康检查脚本，定期监控 worker 状态
		6. 考虑使用 prefork 池替代 gevent，或降低协程数
	- **相关文件**：
		- prod_check_and_start.sh (line 393-411)
		- prod_start_celery_gevent.sh