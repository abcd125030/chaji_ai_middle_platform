# 配置刷新机制说明

## 自动刷新机制

配置加载器支持两种刷新机制：

### 1. 缓存过期刷新（默认开启）
- **刷新间隔**：5分钟（300秒）
- **工作原理**：每次请求配置时，检查缓存是否超过5分钟，如果是则重新加载

### 2. 文件修改检测（默认开启）
- **检测方式**：检查文件的修改时间戳
- **工作原理**：每次访问配置时，如果检测到文件被修改，立即重新加载

## 配置参数

在 Django settings 中可以配置：

```python
# settings.py

# 缓存过期时间（秒）
CONFIG_CACHE_TTL = 300  # 默认5分钟

# 是否开启文件修改自动重载
CONFIG_AUTO_RELOAD = True  # 默认开启

# 生产环境建议配置
# CONFIG_CACHE_TTL = 3600  # 1小时
# CONFIG_AUTO_RELOAD = False  # 关闭自动重载，提高性能
```

## 刷新时机

配置会在以下情况下刷新：

1. **自动刷新**：
   - 缓存超过5分钟自动刷新
   - 检测到YAML文件被修改立即刷新

2. **手动刷新**：
   ```python
   from authentication.config_loader import get_config_loader
   
   loader = get_config_loader()
   loader.reload_configs()  # 强制刷新所有配置
   ```

3. **服务重启**：
   - 重启Django服务器会重新加载所有配置

## 实际效果

- **开发环境**：修改YAML文件后，最多5分钟内生效（如果开启文件检测则立即生效）
- **生产环境**：建议设置较长的缓存时间（如1小时），通过服务重启或手动刷新更新配置

## 性能考虑

- 文件修改检测会有轻微的I/O开销
- 建议生产环境关闭 `CONFIG_AUTO_RELOAD`，使用较长的 `CONFIG_CACHE_TTL`
- 可以通过API端点触发手动刷新：

```python
# views.py
from django.http import JsonResponse
from authentication.config_loader import get_config_loader

def reload_configs(request):
    """管理员端点：重新加载配置"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    loader = get_config_loader()
    loader.reload_configs()
    
    return JsonResponse({'status': 'Configurations reloaded'})
```

## 监控日志

配置加载器会记录以下日志：

- `INFO`: 检测到文件修改，重新加载
- `DEBUG`: 缓存过期，重新加载
- `ERROR`: 加载配置失败

查看日志：
```bash
tail -f logs/django.log | grep "config_loader"
```