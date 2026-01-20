作用概述

- 提供一个“基于 Redis 的全局批量回调管理器”，统一管理所有 worker 的回调入队、批次提取与并发限流，避免多进程/多主机竞争导致重复或过载
- 通过队列键与分布式锁实现“单调度器”模式：只有持有锁的执行者才能进行批次发送，从而实现全局带宽流控
核心键与配置

- 队列与状态键： QUEUE_KEY 、 PROCESSING_KEY 、 LOCK_KEY 、 LAST_SEND_KEY 、 STATS_KEY 定义在 d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:22-27
- 配置来源： BATCH_CALLBACK_CONFIG 中的 BATCH_SIZE 、 MAX_DELAY 、 MIN_INTERVAL 读取于 d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:43-47
入队与触发

- 入队方法： add_callback 将回调序列化为 JSON，追加到 QUEUE_KEY ，并累计统计 d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:49-69
- 触发策略：当队列长度达到 batch_size 或最早入队任务等待时间超过 max_delay 时，投递一个 Celery 任务 customized.image_editor.tasks_batch.trigger_batch_send 到 celery 队列 d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:70-88
- 时间判断： _should_flush_by_time 取队首元素 _queued_at 计算等待时长，与 max_delay 对比 d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:155-175
批次获取

- 原子提取： get_batch 使用 Lua 脚本把最多 batch_size 个元素从 pending 队列 lpop 并同时 rpush 到 processing ，保证提取与迁移是一个原子操作 d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:96-134
- 反序列化：按条解析 JSON，返回 Python 字典列表 d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:140-149
并发控制

- 分布式锁： acquire_send_lock 通过 SET NX EX 获取 LOCK_KEY ，避免多个 worker 同时执行发送； release_send_lock 释放锁 d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:177-207、208-215
- 发送间隔： check_send_interval 读取 LAST_SEND_KEY ，若距离上次发送小于 MIN_INTERVAL ，返回需要等待的秒数； update_last_send_time 更新该时间（TTL 60s） d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:216-237、239-249
统计与监控

- 事件计数： _update_stats(action) 对 queued/sent/failed 分别进行自增，键有效期 1 天 d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:250-261
- 状态聚合： get_queue_stats 返回待处理/处理中数量与累计指标，并附带当前配置项 d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:262-293
故障恢复

- 处理中回退： clear_processing_queue 将 processing 队列的任务全部回退到 pending ，用于异常或死锁后的快速恢复 d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:295-308
全局实例

- 单例访问： get_redis_batcher 返回全局批量器实例，避免重复连接与配置读取 d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:315-320
与 Celery 的集成

- 入队侧触发： add_callback 在达到数量或时间阈值时，通过 current_app.send_task('customized.image_editor.tasks_batch.trigger_batch_send', queue='celery') 发起异步触发 d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\callback_batcher_redis.py:74-86
- 执行侧配合：通常由 tasks_batch.trigger_batch_send 获取锁、检查间隔、拉取批次并执行实际回调发送；本文件侧重队列/并发与节流，发送实现位于任务模块
典型工作流程

- 入队：业务将回调数据调用 add_callback 入队并打点统计
- 触发：达到 BATCH_SIZE 或超过 MAX_DELAY ，投递触发任务
- 执行：触发任务获取锁 → 检查 MIN_INTERVAL → get_batch 原子迁移到 processing → 执行对接回调 → 更新统计与最后发送时间 → 释放锁
- 恢复：异常时使用管理工具或 clear_processing_queue 将卡住项回退到 pending 再次处理
使用建议与注意

- 锁超时与任务耗时： acquire_send_lock 默认 30 秒过期，若批次发送可能超时，需配合任务侧续期或延长锁 TTL
- 发送间隔控制： MIN_INTERVAL 为全局节流阈值，过小会导致拥塞，过大则延迟增大
- Celery 队列名：默认使用 queue='celery' ，需与实际 Celery 路由配置一致
- 处理队列回退： clear_processing_queue 仅做队列层面的回退，任务侧应确保幂等，避免重复发送带来的副作用
- 统计键 TTL：统计键 1 天过期，适合近实时监控而非长期审计，如需长期报表需另行聚合