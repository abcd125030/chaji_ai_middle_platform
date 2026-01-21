# MinerU 存储适配器（StorageAdapter）

## 用途

- 提供 MinerU 的“存储适配层”，把解析相关的文件读写、缓存、上传、下载、结果保存等操作统一封装到一个类，便于服务层调用
- 当前实现使用本地文件系统模拟“OSS”行为，所有内容都落在 MEDIA_ROOT/oss-bucket/mineru 下
## 目录与路径

- 基础目录： MEDIA_ROOT/oss-bucket/mineru （ backend/mineru/services/storage_adapter.py:33–34 ）
- 临时目录：默认取 settings.MINERU_SETTINGS['TEMP_DIR'] ，若未设置则为 /tmp/mineru （ backend/mineru/services/storage_adapter.py:36–37 ）
- 缓存目录： <base_dir>/cache ，存放解析结果的缓存 JSON（ backend/mineru/services/storage_adapter.py:40–41 ）
- 结果目录： <base_dir>/results/<task_id> ，用于持久化 Markdown/JSON/图片等产物（ backend/mineru/services/storage_adapter.py:216–218 ）
## 缓存机制

- 文件哈希： generate_file_hash(file_bytes) 返回 SHA256（ backend/mineru/services/storage_adapter.py:43–53 ）
- 读缓存： check_cache(file_hash) 在 cache/ 目录查找 <hash>.json 并加载（ backend/mineru/services/storage_adapter.py:55–76 ）
- 写缓存： save_cache(file_hash, result_data) 保存解析结果，并补充 cached_at 、 file_hash 元数据（ backend/mineru/services/storage_adapter.py:78–104 ）
## 文件上传与下载

- 上传本地文件： upload_file(file_path, file_name=None, metadata=None) （ backend/mineru/services/storage_adapter.py:106–161 ）
  - 生成日期分层目录 YYYY/MM/DD ，用时间戳前缀形成唯一文件名（ backend/mineru/services/storage_adapter.py:128–139 ）
  - 返回信息包含：
    - file_key ：相对 MEDIA_ROOT 的路径，用于拼接 url （ backend/mineru/services/storage_adapter.py:146–154, 258–265 ）
    - url ：形如 "/media/<relative_path>" ，配合 Django 的 MEDIA_URL 使用（ backend/mineru/services/storage_adapter.py:150–154 ）
- 下载文件： download_file(file_key, dest_path=None) （ backend/mineru/services/storage_adapter.py:163–193 ）
  - 从 MEDIA_ROOT/<file_key> 复制到本地临时目录或指定位置
## 结果持久化

- save_result(task_id, result_type, result_data, metadata=None) （ backend/mineru/services/storage_adapter.py:195–270 ）
  - Markdown：写入 <task_id>_output.md （ backend/mineru/services/storage_adapter.py:220–226 ）
  - JSON：写入 <task_id>_result.json （ backend/mineru/services/storage_adapter.py:227–233 ）
  - 图片集：复制目录或单文件到 <task_id>_images （ backend/mineru/services/storage_adapter.py:234–244 ）
  - 其他类型：按字符串/路径直接写入或复制（ backend/mineru/services/storage_adapter.py:245–254 ）
  - 返回结构包含 file_key 、 url 、 metadata 等，便于直接对外暴露
## 临时清理

- cleanup_temp_files(task_id) 删除本地临时目录下该任务相关文件（ backend/mineru/services/storage_adapter.py:272–287 ）
## 与服务层配合

- 优化服务 OptimizedMinerUService 用到适配器的能力：
  - 生成哈希并查缓存（ backend/mineru/services/optimized_service.py:62–69 ）
  - 上传原始文件与解析结果（ backend/mineru/services/optimized_service.py:70–79, 90–107 ）
- 注意：优化服务代码中调用的是 storage.save_upload_file(...) （ backend/mineru/services/optimized_service.py:71–76 ），而适配器当前提供的是 upload_file(...) 。两者方法名不一致，属于接口不对齐的小问题，建议在适配器中增加一个 save_upload_file(file_bytes, filename, task_id) 辅助方法或在优化服务里改为调用 upload_file
## 路径与 URL 约定

- file_key 相对的是 MEDIA_ROOT （通过 relative_to(self.base_dir.parent.parent) 计算得到），URL 固定以 "/media/" 为前缀（ backend/mineru/services/storage_adapter.py:144–154, 256–265 ）
- 确保 Django 的 MEDIA_ROOT 与 MEDIA_URL="/media/" 正确配置，才能通过 URL 访问到刚保存的文件
## 使用建议

- Windows 环境请在 settings.MINERU_SETTINGS['TEMP_DIR'] 配置为如 C:\mineru\tmp ，避免默认 /tmp/mineru 路径不适配（ backend/mineru/services/storage_adapter.py:36–37 ）
- 若希望真正对接云 OSS（阿里云、S3 等），可将当前本地复制逻辑替换为云 SDK，并保持 file_key/url 返回结构不变，便于服务层和前端复用
- 建议补齐接口一致性（ save_upload_file vs upload_file ），并在异常路径统一返回可诊断信息（当前会抛异常并写日志）