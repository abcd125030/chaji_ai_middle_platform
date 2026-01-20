用途概述

- 删除所有图片编辑相关任务记录（ ImageEditTask 与 BatchTask ）及其生成文件
- 支持直连 PostgreSQL 或通过 PgBouncer 连接，带双重确认以防误删
- 可选清理 Redis 中以 task:* 为前缀的缓存键
关键流程

- 连接模式选择与环境初始化：根据参数或环境变量启用 PgBouncer，端口 6432 （ d:\my_github\chaji_ai_middle_platform\backend\customized\image_editor\delete_all_tasks.py :15–22）；设置并初始化 Django（ :24–28 ）
- 任务数量统计与双重确认：统计任务与批量任务数量并进行两次人工确认（ yes 与 DELETE ALL ）（ :37–39, 48–59 ）
- 文件删除：删除 MEDIA_ROOT/image_editor 目录及其内容，打印文件数量与结果（ :64–76, 68–72 ）
- 数据库删除：删除所有 ImageEditTask 与 BatchTask 记录并输出删除计数（ :81–86 ）
- 缓存清理（可选）：若使用 django-redis ，删除匹配 task:* 的键；缺失或异常时给出提示（ :93–117 ）
- 完成与状态汇总：打印完成提示与删除后剩余任务数（ :121–127 ）
适用场景

- 开发/测试环境需要彻底清空图片编辑任务及其产出
- 数据异常或迁移前的重置操作
- 批量清理，确保数据库与文件系统、缓存一致性
运行方式（Windows）

- 直连数据库：
  ```
  python 
  d:\my_github\chaji_ai_middle_plat
  form\backend\customized\image_edi
  tor\delete_all_tasks.py
  ```
- 使用 PgBouncer（命令行参数）：
  ```
  python 
  d:\my_github\chaji_ai_middle_plat
  form\backend\customized\image_edi
  tor\delete_all_tasks.py 
  --pgbouncer
  ```
- 使用 PgBouncer（环境变量）：
  ```
  set USE_PGBOUNCER=true
  python 
  d:\my_github\chaji_ai_middle_plat
  form\backend\customized\image_edi
  tor\delete_all_tasks.py
  ```
安全提醒

- 操作不可逆，会删除数据库记录与磁盘文件，请务必确认两次提示（ yes 与 DELETE ALL ）
- 建议在开发/测试环境或维护窗口执行，并做好数据库与文件系统备份
- Redis键的通配删除可能较重，谨慎在生产执行
配置注意

- 文件路径来源为 settings.MEDIA_ROOT ，当前代码包含默认回退 /Users/chagee/Repos/X/backend/media （ :64–66 ），请确保你在目标环境中设置了正确的 MEDIA_ROOT
- 仅当安装并配置了 django-redis 且默认连接为 "default" 时才会执行键清理（ :105–114 ）