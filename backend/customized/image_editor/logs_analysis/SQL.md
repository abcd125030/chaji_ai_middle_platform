# PostgreSQL 数据库操作指南

## 宝塔面板进入 PostgreSQL

### 方式一：通过宝塔面板终端
```bash
# 使用宝塔面板的 PostgreSQL 管理工具直接进入
# 或在宝塔终端中使用以下命令
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres
```

### 方式二：使用宝塔安装的 PostgreSQL 路径
```bash
# 宝塔面板默认安装路径
/www/server/pgsql/bin/psql -h 127.0.0.1 -p 5432 -U postgres
```

## 切换到数据库 X
```sql
\c X
```

## 查询图片编辑任务的时间差分析

```sql
SELECT      
    task_id,
    created_at,
    started_at,
    callback_occurred_at,
    EXTRACT(EPOCH FROM (callback_occurred_at - created_at)) AS time_diff_seconds,
    EXTRACT(EPOCH FROM (callback_occurred_at - created_at))/60 AS time_diff_minutes,
    image_validation_duration,
    pet_detection_duration,
    text_to_image_duration,
    consistency_check_duration,
    bg_removal_duration,
    callback_duration,
    processing_time,
    status,
    callback_status
FROM image_edit_task
WHERE callback_occurred_at IS NOT NULL
ORDER BY (callback_occurred_at - created_at) DESC
LIMIT 30;
```

### 查询 time_diff_seconds 超过180s的任务个数

```sql
SELECT 
    COUNT(*) AS count_over_180s
FROM image_edit_task
WHERE callback_occurred_at IS NOT NULL
    AND EXTRACT(EPOCH FROM (callback_occurred_at - created_at)) > 180;
```

### 查询2025年8月16日下午14时(北京时间)以后的任务 time_diff_seconds 小于180s的任务个数

```sql
SELECT 
    COUNT(*) AS count_under_180s
FROM image_edit_task
WHERE callback_occurred_at IS NOT NULL
    AND created_at >= '2025-08-16 14:00:00+08:00'::timestamptz
    AND EXTRACT(EPOCH FROM (callback_occurred_at - created_at)) < 180;
```

### 查询2025年8月16日下午14时(北京时间)以后的任务 time_diff_seconds 大于180s的任务个数

```sql
SELECT 
    COUNT(*) AS count_under_180s
FROM image_edit_task
WHERE callback_occurred_at IS NOT NULL
    AND created_at >= '2025-08-16 14:00:00+08:00'::timestamptz
    AND EXTRACT(EPOCH FROM (callback_occurred_at - created_at)) > 180;
```

### 查询2025年8月16日下午14时(北京时间)以后的任务总数

```sql
SELECT 
    COUNT(*) AS total_count
FROM image_edit_task
WHERE created_at >= '2025-08-16 14:00:00+08:00'::timestamptz;
```

### 分析2025年8月16日14时后未完成回调的任务

#### 1. 按状态分组统计没有回调的任务

```sql
SELECT 
    status,
    COUNT(*) AS count
FROM image_edit_task
WHERE created_at >= '2025-08-16 14:00:00+08:00'::timestamptz
    AND callback_occurred_at IS NULL
GROUP BY status
ORDER BY count DESC;
```

#### 2. 查看无回调任务的详细信息（最近20条）

```sql
SELECT 
    task_id,
    created_at,
    started_at,
    status,
    callback_status,
    callback_url,
    error_message,
    EXTRACT(EPOCH FROM (NOW() - created_at))/60 AS minutes_since_created
FROM image_edit_task
WHERE created_at >= '2025-08-16 14:00:00+08:00'::timestamptz
    AND callback_occurred_at IS NULL
ORDER BY created_at DESC
LIMIT 20;
```

#### 3. 统计所有任务的状态分布

```sql
SELECT 
    CASE 
        WHEN callback_occurred_at IS NOT NULL AND EXTRACT(EPOCH FROM (callback_occurred_at - created_at)) < 180 THEN '回调<180s'
        WHEN callback_occurred_at IS NOT NULL AND EXTRACT(EPOCH FROM (callback_occurred_at - created_at)) >= 180 THEN '回调>=180s'
        WHEN callback_occurred_at IS NULL THEN '无回调'
    END AS task_category,
    status,
    COUNT(*) AS count
FROM image_edit_task
WHERE created_at >= '2025-08-16 14:00:00+08:00'::timestamptz
GROUP BY task_category, status
ORDER BY task_category, count DESC;
```

#### 4. 查看无回调任务的时间分布

```sql
SELECT 
    DATE_TRUNC('hour', created_at AT TIME ZONE 'Asia/Shanghai') AS hour,
    COUNT(*) AS total_tasks,
    SUM(CASE WHEN callback_occurred_at IS NULL THEN 1 ELSE 0 END) AS no_callback_count,
    ROUND(100.0 * SUM(CASE WHEN callback_occurred_at IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS no_callback_percentage
FROM image_edit_task
WHERE created_at >= '2025-08-16 14:00:00+08:00'::timestamptz
GROUP BY hour
ORDER BY hour DESC;
```

#### 5. 检查是否有任务卡在某个处理阶段

```sql
SELECT 
    CASE
        WHEN started_at IS NULL THEN '未开始'
        WHEN started_at IS NOT NULL AND callback_occurred_at IS NULL THEN '处理中/失败'
        ELSE '已完成'
    END AS task_stage,
    status,
    COUNT(*) AS count,
    AVG(EXTRACT(EPOCH FROM (NOW() - created_at))/60)::INT AS avg_minutes_since_created
FROM image_edit_task
WHERE created_at >= '2025-08-16 14:00:00+08:00'::timestamptz
GROUP BY task_stage, status
ORDER BY task_stage, count DESC;
```

## 日志时间段（2025-08-16 13:29-16:22）任务统计

### 统计日志时间段内的任务总数和状态分布
```sql
-- 任务总数
SELECT 
    COUNT(*) AS total_tasks
FROM image_edit_task
WHERE created_at >= '2025-08-16 13:29:00+08:00'::timestamptz
    AND created_at <= '2025-08-16 16:22:00+08:00'::timestamptz;

-- 任务状态分布
SELECT 
    status,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) AS percentage
FROM image_edit_task
WHERE created_at >= '2025-08-16 13:29:00+08:00'::timestamptz
    AND created_at <= '2025-08-16 16:22:00+08:00'::timestamptz
GROUP BY status
ORDER BY count DESC;
```

### 统计任务成功和失败情况
```sql
SELECT 
    CASE 
        WHEN status = 'success' THEN '任务成功'
        WHEN status = 'failed' THEN '任务失败'
        WHEN status = 'pending' THEN '任务待处理'
        WHEN status = 'processing' THEN '任务处理中'
        ELSE '其他状态'
    END AS task_result,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) AS percentage
FROM image_edit_task
WHERE created_at >= '2025-08-16 13:29:00+08:00'::timestamptz
    AND created_at <= '2025-08-16 16:22:00+08:00'::timestamptz
GROUP BY task_result
ORDER BY count DESC;
```

### 统计回调成功和失败情况
```sql
SELECT 
    CASE 
        WHEN callback_status = 'success' THEN '回调成功'
        WHEN callback_status = 'failed' THEN '回调失败'
        WHEN callback_status IS NULL AND callback_occurred_at IS NOT NULL THEN '回调状态未知'
        WHEN callback_occurred_at IS NULL THEN '未回调'
        ELSE '其他'
    END AS callback_result,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) AS percentage
FROM image_edit_task
WHERE created_at >= '2025-08-16 13:29:00+08:00'::timestamptz
    AND created_at <= '2025-08-16 16:22:00+08:00'::timestamptz
GROUP BY callback_result
ORDER BY count DESC;
```

### 综合统计：任务和回调成功率
```sql
WITH task_stats AS (
    SELECT 
        COUNT(*) AS total_tasks,
        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS task_success,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS task_failed,
        SUM(CASE WHEN callback_status = 'success' THEN 1 ELSE 0 END) AS callback_success,
        SUM(CASE WHEN callback_status = 'failed' THEN 1 ELSE 0 END) AS callback_failed,
        SUM(CASE WHEN callback_occurred_at IS NOT NULL THEN 1 ELSE 0 END) AS has_callback,
        SUM(CASE WHEN callback_occurred_at IS NULL THEN 1 ELSE 0 END) AS no_callback
    FROM image_edit_task
    WHERE created_at >= '2025-08-16 13:29:00+08:00'::timestamptz
        AND created_at <= '2025-08-16 16:22:00+08:00'::timestamptz
)
SELECT 
    total_tasks AS "总任务数",
    task_success AS "任务成功数",
    task_failed AS "任务失败数",
    ROUND(100.0 * task_success / NULLIF(total_tasks, 0), 2) AS "任务成功率(%)",
    callback_success AS "回调成功数",
    callback_failed AS "回调失败数",
    ROUND(100.0 * callback_success / NULLIF(has_callback, 0), 2) AS "回调成功率(%)",
    has_callback AS "已回调数",
    no_callback AS "未回调数",
    ROUND(100.0 * has_callback / NULLIF(total_tasks, 0), 2) AS "回调率(%)"
FROM task_stats;
```

### 按小时统计任务和回调情况
```sql
SELECT 
    DATE_TRUNC('hour', created_at AT TIME ZONE 'Asia/Shanghai') AS hour,
    COUNT(*) AS total_tasks,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS task_success,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS task_failed,
    SUM(CASE WHEN callback_status = 'success' THEN 1 ELSE 0 END) AS callback_success,
    SUM(CASE WHEN callback_status = 'failed' THEN 1 ELSE 0 END) AS callback_failed,
    ROUND(100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) AS task_success_rate,
    ROUND(100.0 * SUM(CASE WHEN callback_status = 'success' THEN 1 ELSE 0 END) / 
          NULLIF(SUM(CASE WHEN callback_occurred_at IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS callback_success_rate
FROM image_edit_task
WHERE created_at >= '2025-08-20 00:00:00+08:00'::timestamptz
    AND created_at <= '2025-08-31 23:59:00+08:00'::timestamptz
GROUP BY hour
ORDER BY hour;
```

## 删除特定时间后的任务

### 删除2025年8月16日下午16:30(北京时间)以后的任务
```sql
-- 先查看将要删除的任务数量
SELECT COUNT(*) AS tasks_to_delete
FROM image_edit_task
WHERE created_at >= '2025-08-16 16:30:00+08:00'::timestamptz;

-- 执行删除操作
DELETE FROM image_edit_task
WHERE created_at >= '2025-08-16 16:30:00+08:00'::timestamptz;
```

## 2025年8月20日凌晨任务统计

### 查询2025年8月20日凌晨0:00~1:30之间的任务数量分布（按分钟）

```sql
-- 按分钟统计任务数量
SELECT 
    TO_CHAR(created_at AT TIME ZONE 'Asia/Shanghai', 'HH24:MI') AS minute,
    COUNT(*) AS task_count
FROM image_edit_task
WHERE created_at >= '2025-08-20 00:00:00+08:00'::timestamptz
    AND created_at <= '2025-08-20 01:30:00+08:00'::timestamptz
GROUP BY TO_CHAR(created_at AT TIME ZONE 'Asia/Shanghai', 'HH24:MI')
ORDER BY minute;

-- 按分钟和状态统计
SELECT 
    TO_CHAR(created_at AT TIME ZONE 'Asia/Shanghai', 'HH24:MI') AS minute,
    status,
    COUNT(*) AS count
FROM image_edit_task
WHERE created_at >= '2025-08-20 00:00:00+08:00'::timestamptz
    AND created_at <= '2025-08-20 01:30:00+08:00'::timestamptz
GROUP BY TO_CHAR(created_at AT TIME ZONE 'Asia/Shanghai', 'HH24:MI'), status
ORDER BY minute, status;

-- 汇总统计
SELECT 
    COUNT(*) AS "总任务数",
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS "成功数",
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS "失败数",
    SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) AS "处理中"
FROM image_edit_task
WHERE created_at >= '2025-08-20 00:00:00+08:00'::timestamptz
    AND created_at <= '2025-08-20 01:30:00+08:00'::timestamptz;
```

### 一条命令执行（宝塔环境）
```bash
/www/server/pgsql/bin/psql -h 127.0.0.1 -p 5432 -U postgres -d X -c "SELECT TO_CHAR(created_at AT TIME ZONE 'Asia/Shanghai', 'HH24:MI') AS minute, COUNT(*) AS tasks FROM image_edit_task WHERE created_at >= '2025-08-20 00:00:00+08:00'::timestamptz AND created_at <= '2025-08-20 01:30:00+08:00'::timestamptz GROUP BY TO_CHAR(created_at AT TIME ZONE 'Asia/Shanghai', 'HH24:MI') ORDER BY minute;"
```

## 其他常用查询

### 查看最近失败的任务
```sql
SELECT 
    task_id,
    created_at,
    status,
    callback_status,
    error_message
FROM image_edit_task
WHERE status = 'failed' OR callback_status != 'success'
ORDER BY created_at DESC
LIMIT 20;
```

### 统计任务处理性能
```sql
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_tasks,
    AVG(EXTRACT(EPOCH FROM (callback_occurred_at - created_at))) as avg_processing_seconds,
    MAX(EXTRACT(EPOCH FROM (callback_occurred_at - created_at))) as max_processing_seconds,
    MIN(EXTRACT(EPOCH FROM (callback_occurred_at - created_at))) as min_processing_seconds
FROM image_edit_task
WHERE callback_occurred_at IS NOT NULL
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 7;
```