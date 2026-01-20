# 回调队列工具（callback_queue_tools.py)

## 用途概述
回调队列工具用于在 Django 项目中维护与调度外部回调任务的队列。它既提供管理命令 callback_queue_tools 方便在命令行进行运维，也提供 Python 接口（customized.image_editor.callback_queue_tools）以便在程序内调用。

典型用例包括：查看队列状态、解除因异常导致的发送锁、将“处理中”任务恢复到“待处理”、以及在必要时重置队列。

## 关键功能
- 查看队列状态（--status / get_queue_status）
- 强制释放发送锁（--unlock / force_release_lock）
- 恢复处理中任务（--recover / clear_processing_queue）
- 完全重置队列（--reset / reset_callback_queue，危险操作，慎用）

## 工作机制
- 管理命令通过 Django 的管理命令入口调用队列维护逻辑。
- 队列状态与锁信息通常持久化在数据库或缓存中；工具会读取/更新这些记录以实现状态查询、锁释放与任务恢复。
- 重置操作会清空队列并恢复默认状态，请在确认无正在执行的任务后再使用。

## 使用方式
- 管理命令（Windows 示例）：
  - 查看状态：
    ```
    python d:\my_github\chaji_ai_middle_platform\backend\manage.py callback_queue_tools --status
    ```
  - 释放锁：
    ```
    python d:\my_github\chaji_ai_middle_platform\backend\manage.py callback_queue_tools --unlock
    ```
  - 恢复处理中任务：
    ```
    python d:\my_github\chaji_ai_middle_platform\backend\manage.py callback_queue_tools --recover
    ```
  - 重置队列（危险）：
    ```
    python d:\my_github\chaji_ai_middle_platform\backend\manage.py callback_queue_tools --reset
    ```

- 在 Django Shell 导入并调用：
  ```
  python d:\my_github\chaji_ai_middle_platform\backend\manage.py shell
  ```
  然后在交互式 Shell 中执行：
  ```
  from customized.image_editor.callback_queue_tools import (
      get_queue_status,
      force_release_lock,
      clear_processing_queue,
      reset_callback_queue,
  )

  status = get_queue_status()
  print(status)

  force_release_lock()
  clear_processing_queue()
  # reset_callback_queue()  # 慎用
  ```

- 程序化调用示例（在你的 Python 脚本或业务代码中）：
  ```
  from customized.image_editor.callback_queue_tools import get_queue_status

  def main():
      status = get_queue_status()
      print('Callback queue status:', status)

  if __name__ == '__main__':
      main()
  ```

## 总结
该工具为队列维护提供了标准化入口。建议优先使用 --status 定期巡检，遇到锁死或异常时使用 --unlock/--recover。仅当明确需要且了解影响时才使用 --reset，以避免数据丢失或中断正常任务。用途概述

- 管理 Redis 全局回调队列的维护操作，用于诊断和修复批量回调在高并发场景下的异常
- 提供锁恢复、处理中队列恢复、队列状态查看与彻底重置等工具函数
- 包含一个可作为 Django 管理命令的入口类，用于在命令行执行上述维护操作
关键功能

- force_release_lock （ customized/image_editor/callback_queue_tools.py:12–21 ）
  - 强制释放分布式发送锁（ LOCK_KEY ），用于解决因锁未释放造成的“单活调度”卡死
- clear_processing_queue （ callback_queue_tools.py:24–40 ）
  - 将 PROCESSING_KEY 中的任务逐个移回 QUEUE_KEY （待处理队列），用于恢复卡住的任务
- get_queue_status （ callback_queue_tools.py:43–63 ）
  - 读取队列与锁指标：待处理数、处理中数、锁状态、锁持有者、上次发送时间
- reset_callback_queue （ callback_queue_tools.py:66–90 ）
  - 危险操作，删除所有相关键（ QUEUE_KEY 、 PROCESSING_KEY 、 LOCK_KEY 、 LAST_SEND_KEY 及 STATS_KEY:* ），用于彻底重置队列
- Command （ callback_queue_tools.py:93–149 ）
  - Django 管理命令入口，支持参数： --status 、 --unlock 、 --recover 、 --reset
工作机制

- 通过 get_redis_batcher 获取 RedisCallbackBatcher 实例（ callback_batcher_redis.py:315–320 ），直接操作其 Redis 客户端和键名
- 与批量回调主流程配合：
  - 入队与调度： tasks.py:221–249 、 callback_batcher_redis.py:74–86
  - 批量发送与分散： tasks_batch.py:13–67 、单条发送 tasks_batch.py:75–135
  - 周期检查与卡住恢复： tasks_batch.py:137–211, 213–249
使用方式

- 管理命令（前提：该文件需位于任意应用的 management/commands/ 目录下，文件名即命令名）
  - 查看状态：
    ```
    python 
    d:\my_github\chaji_ai_middle_plat
    form\backend\manage.py 
    callback_queue_tools --status
    ```
  - 释放锁：
    ```
    python 
    d:\my_github\chaji_ai_middle_plat
    form\backend\manage.py 
    callback_queue_tools --unlock
    ```
  - 恢复处理中任务：
    ```
    python 
    d:\my_github\chaji_ai_middle_plat
    form\backend\manage.py 
    callback_queue_tools --recover
    ```
  - 重置队列（危险）：
    ```
    python 
    d:\my_github\chaji_ai_middle_plat
    form\backend\manage.py 
    callback_queue_tools --reset
    ```
- 程序化调用（无需移动文件，适合在 Django Shell 或脚本中直接使用）
  - 在 Django Shell 导入并调用：
    ```
    python 
    d:\my_github\chaji_ai_middle_plat
    form\backend\manage.py shell
    ```
    ```
    from customized.image_editor.
    callback_queue_tools import (
        get_queue_status, 
        force_release_lock, 
        clear_processing_queue, 
        reset_callback_queue
    )
    status = get_queue_status()
    force_release_lock()
    clear_processing_queue()
    # reset_callback_queue()  # 慎用
    ```
适用场景

- 批量回调通道出现拥塞或死锁（锁未释放）
- 回调任务卡在 processing 队列，长时间未发送或重试失败
- 需要快速查看与修复队列状态，减少人工排障成本
风险与注意

- reset_callback_queue 会清空所有待处理与统计信息，谨慎在生产环境执行
- 强制释放锁可能导致短时间内出现并行调度，应配合查看状态与触发器运行情况
- 建议在维护窗口执行，并确保 Celery worker/beat 正常运行以恢复流水线
总体而言，这个文件是“回调队列救援工具箱”，与主流程的 Redis 批量回调实现配套，为运维/排障提供高效的手段。

结论：有被使用，但主要作为“运维工具”和“管理命令”，而不是在核心业务流程中被直接导入调用

- 该文件本身定义了一个 Django 管理命令 Command ，通过命令行参数调用内部工具函数（ force_release_lock 、 clear_processing_queue 、 get_queue_status 、 reset_callback_queue ）。这些函数在同一文件的 handle 方法内被调用，用于队列状态查看、释放分布式锁、恢复处理中队列、或重置整套回调键。
- 没有发现其他模块主动导入 callback_queue_tools 并调用其中函数；即它不作为业务逻辑的一部分在运行期被自动使用。
如何使用它（Windows，管理命令）

- 显示队列状态：
  - python d:\my_github\chaji_ai_middle_platform\backend\manage.py callback_queue_tools --status
- 强制释放发送锁（死锁恢复）：
  - python d:\my_github\chaji_ai_middle_platform\backend\manage.py callback_queue_tools --unlock
- 恢复处理中队列的任务：
  - python d:\my_github\chaji_ai_middle_platform\backend\manage.py callback_queue_tools --recover
- 完全重置队列（危险，需确认）：
  - python d:\my_github\chaji_ai_middle_platform\backend\manage.py callback_queue_tools --reset
功能关联

- 依赖 callback_batcher_redis.get_redis_batcher() ，与正在使用的 Redis 全局批量回调体系相匹配
- 管理命令提供的操作直接作用于 Redis 的键： QUEUE_KEY 、 PROCESSING_KEY 、 LOCK_KEY 、 LAST_SEND_KEY 、以及统计键 STATS_KEY:*
总结

- 文件被“使用”的形式是：提供一个可执行的 Django 管理命令与一组工具函数，供人工诊断和修复回调队列问题；不参与正常任务回调的主流程。