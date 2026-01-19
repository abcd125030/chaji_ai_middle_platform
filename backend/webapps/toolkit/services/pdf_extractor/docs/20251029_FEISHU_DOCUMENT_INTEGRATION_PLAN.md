# PDF提取器飞书文档集成技术方案

## 一、背景

### 1.1 业务需求

PDF提取工具完成文档解析后，需要将生成的Markdown文档自动同步到飞书平台，方便用户在飞书环境中查看、编辑和协作。

### 1.2 现状问题

- PDF提取结果仅提供Markdown文件下载
- 用户需手动将内容复制到飞书文档
- 图片需单独处理和上传
- 缺乏与企业协作平台的集成

### 1.3 目标

实现PDF提取完成后自动生成飞书文档，提供一键跳转能力，提升企业用户的协作体验。

## 二、方案设计

### 2.1 核心思路

采用**服务编排模式**，将Markdown转飞书文档的复杂流程拆分为多个独立组件，通过主服务类协调完成转换：

- 仅对已关联飞书账号的用户自动创建文档
- 转换失败不影响PDF提取主流程
- 自动处理图片下载和上传
- 文档所有权转移给用户

### 2.2 技术架构

**服务层设计**：
```
backend/webapps/toolkit/services/feishu_document/
├── service.py                              # 主服务类（编排器）
└── components/                              # 组件模块
    ├── feishu_token_manager.py             # 飞书令牌管理
    ├── markdown_segmentor.py               # Markdown分段器
    ├── feishu_document_creator.py          # 文档创建器
    ├── feishu_markdown_converter.py        # Markdown转Block转换器
    ├── feishu_image_processor.py           # 图片处理器
    ├── feishu_block_inserter.py            # Block批量插入器
    └── feishu_permission_manager.py        # 权限管理器
```

**集成点**：
```
Celery任务(process_pdf_extraction)
    └─ PDF提取完成
        └─ 调用 FeishuDocumentService.convert_markdown_to_feishu()
            ├─ 检查用户飞书账号（UserAccount表）
            ├─ 创建飞书文档
            ├─ 转换Markdown并上传图片
            ├─ 转移文档所有权
            └─ 保存 feishu_doc_url 到数据库
```

### 2.3 数据模型变更

**PDFExtractorTask 新增字段**：
```python
class PDFExtractorTask(models.Model):
    # ... 现有字段 ...
    feishu_doc_url = models.TextField(
        verbose_name='飞书文档链接',
        null=True,
        blank=True,
        help_text='格式: https://feishu.cn/docx/{document_id}'
    )
```

**用户认证依赖**：
```python
# 使用 UserAccount OAuth 架构
UserAccount.objects.filter(
    user=task.user,
    provider='feishu',
    is_verified=True
).first()
```

### 2.4 工作流程

```
┌─────────────────────────────────────────────────────────────┐
│  1. PDF提取任务完成                                          │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  2. 检查用户是否关联飞书账号                                 │
│     - 查询 UserAccount (provider='feishu')                  │
│     - 未关联 → 跳过飞书集成，仅返回Markdown                  │
└─────────────────┬───────────────────────────────────────────┘
                  │ 已关联
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  3. 获取飞书Tenant Access Token                             │
│     - 使用 FEISHU_APP_ID + FEISHU_APP_SECRET                │
│     - 不缓存Token，每次独立获取                              │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Markdown分段处理                                         │
│     - 200行/段（避免飞书1000块限制）                         │
│     - 识别代码块边界，避免在```内切分                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  5. 创建飞书空白文档                                         │
│     - 使用清理后的文件名作为标题                             │
│     - 文件名规则：空格→下划线，移除特殊字符                  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  6. 逐段转换并插入内容                                       │
│     For each segment:                                        │
│       - Markdown → 飞书Block JSON                           │
│       - 处理图片引用：                                       │
│         • 下载图片到临时文件                                 │
│         • 上传到飞书获取 file_token                          │
│         • 替换为飞书图片Block                                │
│       - 清理表格 merge_info 字段                             │
│       - 批量插入Block到文档                                  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  7. 文档所有权转移                                           │
│     - 将文档从应用账号转移给用户Open ID                      │
│     - 失败仅记录警告，不影响流程                             │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  8. 保存文档链接到数据库                                     │
│     - task.feishu_doc_url = 飞书文档URL                     │
│     - task.save()                                           │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  9. 前端展示飞书文档按钮                                     │
│     - 条件渲染：feishu_doc_url 存在时显示                    │
│     - 点击按钮新标签页打开飞书文档                           │
└─────────────────────────────────────────────────────────────┘
```

## 三、实施要点

### 3.1 环境配置

**必需环境变量**：
```bash
# 飞书应用凭证
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx

# 飞书OAuth回调（已存在）
FEISHU_REDIRECT_URI=http://localhost:3000/auth/feishu/callback
```

### 3.2 关键组件设计

#### 3.2.1 Token管理器（feishu_token_manager.py）

**职责**：获取飞书Tenant Access Token

**设计原则**：
- 不缓存Token，每次请求独立获取
- 失败立即抛出异常
- 完整记录API响应

```python
class FeishuTokenManager:
    @staticmethod
    def get_tenant_access_token() -> str:
        # 从环境变量读取凭证
        # POST /auth/v3/tenant_access_token/internal
        # 返回 token 字符串
```

#### 3.2.2 Markdown分段器（markdown_segmentor.py）

**职责**：将长Markdown拆分为200行段落

**核心算法**：
```python
# 识别代码块边界
in_code_block = False
for line in lines:
    if line.strip().startswith('```'):
        in_code_block = not in_code_block

    # 避免在代码块内切分
    if len(current_segment) >= 200 and not in_code_block:
        segments.append(current_segment)
        current_segment = []
```

#### 3.2.3 图片处理器（feishu_image_processor.py）

**职责**：下载图片并上传到飞书

**流程**：
1. 解析Markdown中的图片引用：`![alt](path)`
2. 下载图片到临时文件（支持HTTP和本地路径）
3. 上传到飞书：`POST /image/v4/put/`
4. 获取 `image_key`
5. 替换为飞书图片Block

**容错设计**：
- 单张图片失败不中断流程
- 记录详细错误日志
- 下载超时10秒

#### 3.2.4 Markdown转换器（feishu_markdown_converter.py）

**职责**：Markdown语法转飞书Block JSON

**支持的Markdown元素**：
- 标题（H1-H6）
- 段落
- 列表（有序/无序）
- 代码块
- 表格
- 图片（特殊处理）

**表格清理**：
```python
# 移除 merge_info 避免飞书API报错
if 'table' in block:
    for cell in block['table']['cells']:
        if 'merge_info' in cell:
            del cell['merge_info']
```

#### 3.2.5 Block插入器（feishu_block_inserter.py）

**职责**：批量插入Block到飞书文档

**API限制**：
- 单次请求最多1000个Block
- 需分段处理

```python
def insert_blocks_batch(document_id, blocks, token):
    # POST /docx/v1/documents/{document_id}/blocks/{block_id}/children
    # 每次最多1000个Block
```

#### 3.2.6 权限管理器（feishu_permission_manager.py）

**职责**：文档所有权转移

```python
def transfer_ownership(document_id, user_open_id, token):
    # POST /drive/permission/member/transfer_owner
    # 将文档所有权从应用转给用户
    # 失败仅记录警告，不影响主流程
```

### 3.3 异常处理策略

**分级处理**：

| 异常类型 | 处理策略 | 影响 |
|---------|---------|------|
| 用户未关联飞书账号 | 跳过飞书集成 | 无，正常返回Markdown |
| Token获取失败 | 立即抛出异常 | 飞书集成失败，不影响PDF提取 |
| 单张图片下载失败 | 跳过该图片，继续 | 飞书文档部分图片缺失 |
| 文档创建失败 | 抛出异常 | 飞书集成失败 |
| 权限转移失败 | 记录警告，继续 | 文档所有者仍为应用账号 |
| 整体飞书集成失败 | 捕获异常，记录日志 | PDF提取成功，前端不显示飞书按钮 |

**Celery任务中的容错**：
```python
try:
    feishu_service = FeishuDocumentService()
    feishu_url = feishu_service.convert_markdown_to_feishu(...)
    if feishu_url:
        task.feishu_doc_url = feishu_url
        task.save()
except Exception as e:
    logger.warning(f"飞书文档转换失败，不影响PDF提取结果: {str(e)}", exc_info=True)
    # 继续执行，返回成功状态
```

### 3.4 文件名清理规则

**安全处理**：
```python
@staticmethod
def sanitize_filename(filename: str) -> str:
    # 移除扩展名
    # 空格 → 下划线
    # 保留中文、英文、数字、下划线、连字符
    # 压缩连续下划线
    # 移除首尾下划线
    # 空名称 → 'untitled'
```

**示例**：
- `My Document (2024).pdf` → `My_Document_2024`
- `产品说明书 v1.0.pdf` → `产品说明书_v1_0`
- `...pdf` → `untitled`

## 四、前端集成

### 4.1 类型定义

```typescript
interface TaskContent {
  // ... 现有字段 ...
  feishu_doc_url: string | null;  // 新增
}
```

### 4.2 UI组件

```tsx
{content.feishu_doc_url && (
  <button
    onClick={() => window.open(content.feishu_doc_url!, '_blank')}
    className="flex items-center gap-2 px-4 py-2 bg-[#0A0A0A] text-[#EDEDED] rounded-lg border border-[#1A1A1A] hover:border-[#EDEDED] transition-colors"
  >
    <DocumentTextIcon className="w-4 h-4" />
    查看飞书文档
  </button>
)}
```

**显示逻辑**：
- `feishu_doc_url` 存在 → 显示按钮
- `feishu_doc_url` 为 null → 不显示（用户未关联或转换失败）

## 五、预期收益

### 5.1 用户体验提升

- **一键跳转**：PDF提取完成后直接打开飞书文档
- **免手动操作**：无需复制粘贴Markdown内容
- **图片自动处理**：图片自动上传，无需单独处理
- **协作友好**：文档直接在飞书环境中，便于分享和协作

### 5.2 技术优势

- **模块化设计**：7个独立组件，职责清晰，易于维护
- **容错能力强**：飞书集成失败不影响PDF提取主流程
- **可扩展性好**：易于添加其他协作平台（钉钉、企微等）
- **OAuth集成**：复用现有UserAccount架构，无需额外认证

### 5.3 性能指标

- **转换速度**：<30秒（不含大量图片）
- **完整流程**：<2分钟（PDF提取 + 飞书同步）
- **并发支持**：多任务独立处理，无状态共享

## 六、风险评估

### 6.1 技术风险

| 风险 | 等级 | 应对措施 |
|------|------|----------|
| 飞书API限制 | 中 | 200行分段，避免1000块限制 |
| 图片下载失败 | 低 | 跳过失败图片，不中断流程 |
| Token获取失败 | 中 | 完整日志记录，便于问题定位 |
| 网络波动 | 低 | 无自动重试，失败即返回 |

### 6.2 业务风险

| 风险 | 等级 | 应对措施 |
|------|------|----------|
| 用户未关联账号 | 低 | 跳过飞书集成，仅提供Markdown |
| 权限转移失败 | 低 | 文档仍可用，仅所有者为应用 |
| 飞书服务不可用 | 中 | 不影响PDF提取，静默失败 |

### 6.3 兼容性

- 依赖现有 UserAccount OAuth 架构
- 不影响未关联飞书的用户
- 前向兼容：已有任务无 feishu_doc_url 字段

## 七、实施过程

### 7.1 开发阶段（2025-10-29）

**单次提交完成**：
- 提交哈希：`391eafa`
- 代码量：+998行
- 文件变更：15个文件

**核心文件**：
1. **数据模型迁移**：
   - `migrations/0003_pdfextractortask_feishu_doc_url.py`

2. **服务层实现**：
   - `services/feishu_document/service.py`（178行）
   - 7个组件模块（共约700行）

3. **Celery任务集成**：
   - `tasks.py`：新增飞书转换调用（15行）

4. **API响应更新**：
   - `views.py`：返回 feishu_doc_url 字段（1行）

5. **前端UI**：
   - `web/src/app/tools/pdf2md/content/[taskId]/page.tsx`（10行）

### 7.2 文档完善（2025-10-29）

**规格文档提交**：
- 提交哈希：`0d27602`
- 文档量：+3264行
- 包含规格：8个文档

**文档结构**：
```
specs/005-pdf-md-backend/
├── spec.md                              # 功能规格（需求、用户故事）
├── plan.md                              # 实现计划（架构设计）
├── tasks.md                             # 任务清单（24个任务）
├── data-model.md                        # 数据模型设计
├── research.md                          # 技术调研
├── quickstart.md                        # 快速开始指南
├── checklists/requirements.md           # 需求检查清单
└── contracts/feishu-integration-api.yaml # API接口契约
```

### 7.3 后续优化（2025-11-05）

**图片处理增强**：
- 提交哈希：`0f625ae`
- 支持多种路径格式下载图片
- 优化日志信息

## 八、关键代码位置

| 模块 | 文件路径 | 行数 | 说明 |
|------|---------|------|------|
| 主服务类 | services/feishu_document/service.py | 178 | 编排器 |
| Token管理 | components/feishu_token_manager.py | 70 | 获取Token |
| Markdown分段 | components/markdown_segmentor.py | 157 | 200行分段 |
| 文档创建 | components/feishu_document_creator.py | 65 | 创建文档 |
| MD转换 | components/feishu_markdown_converter.py | 73 | MD→Block |
| 图片处理 | components/feishu_image_processor.py | 208 | 下载上传 |
| Block插入 | components/feishu_block_inserter.py | 122 | 批量插入 |
| 权限管理 | components/feishu_permission_manager.py | 67 | 所有权转移 |
| Celery集成 | tasks.py | +15 | 任务触发 |
| 数据模型 | models.py | +6 | 新增字段 |
| API响应 | views.py | +1 | 返回URL |
| 前端UI | page.tsx | +10 | 条件渲染 |

## 九、验收标准

### 9.1 功能验收

- [ ] 用户完成PDF提取后，已关联飞书账号的自动创建飞书文档
- [ ] 未关联飞书账号的用户，前端不显示飞书文档按钮
- [ ] 飞书文档包含完整的文本、标题、列表、代码块、表格
- [ ] 飞书文档中的图片正确显示
- [ ] 点击"查看飞书文档"按钮能在新标签页打开
- [ ] 飞书文档所有者为当前用户（非应用账号）

### 9.2 异常验收

- [ ] 飞书集成失败时，PDF提取仍然成功
- [ ] 飞书集成失败时，前端不显示飞书文档按钮
- [ ] 单张图片下载失败时，其他内容正常转换
- [ ] 权限转移失败时，文档仍可访问
- [ ] 完整的错误日志记录

### 9.3 性能验收

- [ ] 单页文档转换 <5秒
- [ ] 50页文档转换 <30秒（不含大量图片）
- [ ] 支持并发转换多个任务

## 十、总结

本次飞书文档集成采用**模块化服务编排**架构，通过7个独立组件协作完成Markdown到飞书文档的自动转换。核心设计原则：

1. **职责分离**：每个组件专注单一功能
2. **容错优先**：飞书集成失败不影响PDF提取
3. **OAuth集成**：复用现有UserAccount架构
4. **用户优先**：仅对已关联用户启用，文档所有权自动转移
5. **可维护性**：模块化设计，易于扩展和调试

技术亮点：
- 一次性提交完成（998行代码）
- 完整的组件化设计
- 健壮的异常处理机制
- 详尽的规格文档支撑（3264行）

---

**文档版本**：v1.0
**创建日期**：2025-10-29
**最后更新**：2025-11-11
**相关提交**：391eafa, 0d27602, 0f625ae
**规格文档**：specs/005-pdf-md-backend/
