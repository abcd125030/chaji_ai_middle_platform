# cache_manager.py 模块说明

## 作用概述
- 提供基于 `django.core.cache` 的任务状态缓存管理，减少数据库读写，优化高并发下的查询性能（`d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\cache_manager.py`:1–4）
- 提供用户级按秒限流工具（滑动窗口），保障接口 QPS 在可控范围内（`cache_manager.py`:295–311）

## 核心组件
- TaskCacheManager（`cache_manager.py`:15）
  - 键前缀：`image_task`（`cache_manager.py`:19）
  - TTL 策略：`processing=300s`、`success=3600s`、`failed=1800s`、`batch=600s`（`cache_manager.py`:22–27）
  - 状态驱动 TTL 使用点：`ttl = cls.CACHE_TTL.get(status, cls.CACHE_TTL['processing'])`（`cache_manager.py`:53）
- UserRateLimiter（`cache_manager.py`:295）
  - 按秒限流键格式：`rate_limit:{user_id}:{current_second}`（`cache_manager.py`:318–321）
  - 原子自增与过期控制：`cache.incr` + 首次 `cache.set(..., window)`（`cache_manager.py`:334–347）

## 典型流程
- 写入任务缓存
  - `set_task(task_id, task_data, status)`：序列化为 JSON，按状态设置 TTL；记录热点统计（`cache_manager.py`:40–70）
- 查询任务缓存
  - `get_task(task_id)`：命中则反序列化返回，同时更新热点统计（`cache_manager.py`:76–108）
- 更新任务状态
  - `update_task_status(task_id, status, additional_data)`：合并数据后按新状态 TTL 重设（`cache_manager.py`:111–141）
- 批量操作
  - 批量读：`batch_get_tasks(task_ids)` 通过 `cache.get_many` 提升效率（`cache_manager.py`:167–200）
  - 批量写：`batch_set_tasks(tasks_data)` 遍历设置，提高入缓存吞吐（`cache_manager.py`:203–234）
- 监控与维护
  - 热点统计：`_update_hot_data_stats(task_id)` 记录短期访问次数与热点提示（`cache_manager.py`:237–252）
  - 缓存统计：`get_cache_stats()` 读取 Redis INFO 指标（`cache_manager.py`:264–293）
  - 过期清理日志：`clear_expired_cache()`（`cache_manager.py`:254–262）

## 与视图集成
- 提交任务后写缓存：`TaskCacheManager.set_task(...)`（`d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\views.py`:94–95）
- 查询任务优先读缓存：`TaskCacheManager.get_task(task_id)`（`views.py`:151）
- 查询数据库后刷新缓存：`TaskCacheManager.set_task(...)`（`views.py`:323）
- 用户限流检查：
  - 单任务提交：`UserRateLimiter.check_rate_limit(...)` 配合 `RATE_LIMIT_CONFIG`（`views.py`:45–49）
  - 批量提交：`UserRateLimiter.check_rate_limit(...)`（`views.py`:363–367）

## 实现细节
- 键命名
  - 单任务键：`image_task:{task_id}`（`cache_manager.py`:32–37）
  - 限流键：按窗口粒度加入时间戳，1 秒窗口用当前秒（`cache_manager.py`:318–324）
- 原子性与健壮性
  - 限流计数：`cache.incr` 保证原子自增，首次用 `cache.set(..., window)` 设置过期（`cache_manager.py`:334–347）
  - 反序列化异常自动清理损坏缓存（`cache_manager.py`:101–106）
- TTL 策略
  - 状态驱动 TTL：成功结果保留更久、处理中短保留，兼顾查询体验与内存占用（`cache_manager.py`:22–27, 53）

## 注意事项
- 重置限流只删除 `rate_limit:{user_id}`（`cache_manager.py`:369–375），但按秒限流实际键为 `rate_limit:{user_id}:{timestamp}`；若需彻底重置当前窗口限流，需要删除带时间戳的键集合或改造为统一计数键策略
- 依赖 `django.core.cache` 的后端配置（通常为 Redis）；`redis` 与 `RedisError` 的导入为兼容或扩展用途（`cache_manager.py`:8–12）
- 缓存中的任务数据为 JSON 字符串，字段需可序列化；复杂类型应转换为字符串或基本类型（`cache_manager.py`:56）

## 小结
- `cache_manager.py` 是图片编辑服务的“缓存与限流基础设施”，通过状态化 TTL、批量操作和热点统计，支撑高并发任务查询与接口 QPS 控制
- 与 `views.py` 的提交流程和查询流程紧密耦合：优先命中缓存、回退数据库、再刷新缓存，降低数据库压力、提升响应速度