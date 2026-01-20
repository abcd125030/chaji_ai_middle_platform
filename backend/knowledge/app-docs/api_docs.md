# 知识库系统 API 文档

本文档详细说明了知识库系统的 RESTful API 接口规范和使用方法。

## 基础信息

**基础 URL**: `/api/knowledge/`

**版本**: v1.0.1

**更新日期**: 2026-01-20

## 通用约定

*   **数据格式**: 所有请求体和响应体均为 JSON 格式
*   **请求头**: 必须包含 `Content-Type: application/json`
*   **认证方式**:
    - 当前 API 端点未强制要求用户认证
    - 敏感操作建议在网关层添加认证
*   **配置管理**:
    - 使用 `KnowledgeConfig` 在 Admin 中管理向量库与模型配置
    - LLM 配置通过路由器与 `knowledge_config_bridge` 获取，支持 OpenAI 兼容端点
    - `app_id`/`secret` 可用于扩展，当前不参与鉴权
*   **错误处理**:
    - 4xx 错误表示客户端问题
    - 5xx 错误表示服务端问题
    - 所有错误响应包含 `error` 字段说明原因

---

## 1. 添加知识数据

**典型使用场景**:
- 上传产品文档内容
- 添加FAQ知识条目
- 存储用户手册章节

**端点**: `POST /api/knowledge/data/add/`

**描述**: 服务层对文本进行向量化并写入 Qdrant（LangChain `QdrantVectorStore`），不依赖 mem0。

**方法**: `POST`

**性能考虑**:
- 单次请求建议内容不超过 10KB
- 批量添加建议分多次请求

### 请求体 (JSON)

| 参数              | 类型     | 是否必需 | 描述                                                                 |
| ----------------- | -------- | -------- | -------------------------------------------------------------------- |
| `user_id`         | String   | 是       | 用户唯一标识符，用于 `mem0ai` 内部的数据隔离。                         |
| `collection_name` | String   | 是       | 目标知识集合的名称。如果该集合不存在，系统会尝试创建它。 |
| `app_id`          | String   | 否       | （可选）用于获取 LLM API 密钥的客户端应用 ID。如果提供，将通过内部认证服务获取 JWT token 作为该请求的 LLM API 密钥，覆盖通过 Admin 配置的默认 LLM API 密钥。 |
| `secret`          | String   | 否       | （可选）用于获取 LLM API 密钥的客户端应用密钥。与 `app_id` 一同提供。       |
| `content`         | String   | 是       | 要添加的文本内容。                                                     |
| `metadata`        | Object   | 否       | 一个 JSON 对象，包含与此内容相关的附加元数据。例如: `{"source": "doc_id_123", "tags": ["faq"]}` |

**请求示例**:
```json
{
    "user_id": "user_alpha_001",
    "collection_name": "product_manuals_v2",
    "content": "最新的用户手册章节内容，详细介绍了如何配置高级设置。",
    "metadata": {
        "source_document_id": "manual_v2_chap5_rev3",
        "author": "tech_writer_jane",
        "version": "2.3"
    }
}
```
**带可选 app_id/secret 的请求示例 (用于特定 LLM 认证)**:
```json
{
    "user_id": "user_beta_002",
    "collection_name": "project_docs",
    "app_id": "client_app_xyz",
    "secret": "client_secret_123",
    "content": "项目特定文档内容。",
    "metadata": { "project_id": "p789" }
}
```

### 响应

#### 成功响应 (Status Code: `200 OK`)

| 参数      | 类型   | 描述                                     |
| --------- | ------ | ---------------------------------------- |
| `message` | String | 操作成功的消息，例如 "Data added successfully." |
| `details` | Object | `mem0ai` 的 `add()` 方法返回的详细信息。   |

**响应示例**:
```json
{
    "message": "Data added successfully.",
    "details": {
        // mem0.add() 的具体返回内容，可能包含处理状态或ID等
        "result": "Successfully added memory chunk." 
    }
}
```

#### 错误响应

*   **Status Code: `400 Bad Request`**
    *   原因: 请求参数缺失 (如 `user_id`, `collection_name`, 或 `content`)。
    *   响应体: `{"error": "Missing user_id, collection_name, or content."}`
*   **Status Code: `500 Internal Server Error`**
    *   原因: 后端处理错误，例如 `mem0ai` 初始化失败（如未配置激活的 `KnowledgeConfig`）、数据库操作失败等。
    *   响应体: `{"error": "具体错误信息描述"}`
*   **Status Code: `503 Service Unavailable` (可能)**
    *   原因: 如果提供了 `app_id`/`secret` 但内部认证服务不可用或配置错误。
    *   响应体: `{"error": "Failed to fetch JWT token from authentication service: ..."}`

---

## 2. 查询知识数据并获取答案

**典型使用场景**:
- 智能客服问答
- 产品文档检索
- 知识库搜索

**端点**: `POST /api/knowledge/data/query/`

**描述**: 服务层从 Qdrant 检索相关片段，并在有召回时使用配置的 LLM 生成答案。

**方法**: `POST`

**性能考虑**:
- 查询响应时间通常在 1-3 秒
- 复杂查询建议设置较低 limit 值
- 高频查询建议使用缓存

### 请求体 (JSON)

| 参数              | 类型     | 是否必需 | 描述                                                                 |
| ----------------- | -------- | -------- | -------------------------------------------------------------------- |
| `user_id`         | String   | 是       | 用户唯一标识符，用于集合命名或服务层数据隔离。                         |
| `collection_name` | String   | 是       | 要查询的目标知识集合的名称。                                           |
| `app_id`          | String   | 否       | （可选）用于获取 LLM API 密钥的客户端应用 ID。若提供，将通过路由器配置覆盖默认 LLM 配置。 |
| `secret`          | String   | 否       | （可选）用于获取 LLM API 密钥的客户端应用密钥。与 `app_id` 一同提供。       |
| `query`           | String   | 是       | 用户提出的问题或查询语句。                                             |
| `limit`           | Integer  | 否       | （可选）希望从向量数据库召回的最大记忆片段数量。默认为 `5`。             |

**请求示例**:
```json
{
    "user_id": "user_alpha_001",
    "collection_name": "product_manuals_v2",
    "query": "如何重置设备到出厂设置？",
    "limit": 3
}
```

## 4. 更新知识数据
- 端点: `POST /api/knowledge/data/update/`
- 请求体:
  - `item_id` (必需)
  - `content` (可选)
  - `metadata` (可选)
  - `user_id` (可选，默认 `system`)
- 成功响应 (200): `message`, `item_id`, `updated_fields`

## 5. 删除知识数据
- 端点: `POST /api/knowledge/data/delete/`
- 请求体:
  - `item_id` (必需)
  - `user_id` (可选，默认 `system`)
- 成功响应 (200): `message`, `item_id`

## 6. 列出知识数据
- 端点: `GET /api/knowledge/data/list/`
- 查询参数: `collection_name` (可选), `page`, `page_size`, `status`
- 成功响应 (200): `items`, `total_count`, `page`, `page_size`

## 7. 批量添加知识
- 端点: `POST /api/knowledge/data/batch_add/`
- 请求体:
  - `items` (必需，列表)
  - `collection_name` (可选，默认 `default`)
  - `user_id` (可选，默认 `system`)
- 成功响应 (200): `success_count`, `failed_items`

## 8. 批量删除知识
- 端点: `POST /api/knowledge/data/batch_delete/`
- 请求体:
  - `item_ids` (必需，列表)
  - `user_id` (可选，默认 `system`)
- 成功响应 (200): `deleted_count`, `failed_items`

### 响应

#### 成功响应 (Status Code: `200 OK`)

| 参数                 | 类型          | 描述                                                                 |
| -------------------- | ------------- | -------------------------------------------------------------------- |
| `answer`             | String        | LLM 基于召回的上下文生成的最终答案。如果未找到相关信息或LLM处理失败，可能包含提示信息。 |
| `recalled_context_count` | Integer    | 从向量数据库召回并用于生成答案的记忆文本片段的数量。                       |
| `raw_search_results` | Object        | （可选）向量检索返回的原始结果，结构可能随版本调整。 |


**响应示例**:
```json
{
    "answer": "要重置设备到出厂设置，请导航到系统设置菜单，选择“恢复”选项，然后确认恢复出厂设置。请注意，这将清除所有用户数据。",
    "recalled_context_count": 2,
    "raw_search_results": { // 内容可能精简或移除
        "results": [
            {
                "id": "mem_chunk_id_abc",
                "memory": "手册第5.3节：设备重置流程。导航至设置 > 系统 > 恢复 > 恢复出厂设置。此操作不可逆，会清除所有数据。",
                "score": 0.895
            },
            {
                "id": "mem_chunk_id_def",
                "memory": "常见问题解答#12：问：如何恢复出厂默认值？答：请参阅用户手册第5.3节的详细步骤。",
                "score": 0.852
            }
        ]
    }
}
```

#### 错误响应

*   **Status Code: `400 Bad Request`**
    *   原因: 请求参数缺失 (如 `user_id`, `collection_name`, 或 `query`)。
    *   响应体: `{"error": "Missing user_id, collection_name, or query."}`
*   **Status Code: `500 Internal Server Error`**
    *   原因: 后端处理错误，例如 `mem0ai` 初始化失败（如未配置激活的 `KnowledgeConfig`）、向量检索失败、LLM 调用失败等。
    *   响应体: `{"error": "具体错误信息描述"}`
*   **Status Code: `503 Service Unavailable` (可能)**
    *   原因: 如果提供了 `app_id`/`secret` 但内部认证服务不可用或配置错误。
    *   响应体: `{"error": "Failed to fetch JWT token from authentication service: ..."}`

---

## 3. 仅检索知识数据

**典型使用场景**:
- 调试向量检索的准确性
- 在前端展示原始的相关文档列表
- 需要低延迟、低成本的纯搜索功能

**端点**: `POST /api/knowledge/data/search/`

**描述**: 服务层从 Qdrant 检索相关片段并直接返回原始结果，**不经过 LLM 处理**。

**方法**: `POST`

### 请求体 (JSON)

| 参数              | 类型     | 是否必需 | 描述                                                                 |
| ----------------- | -------- | -------- | -------------------------------------------------------------------- |
| `user_id`         | String   | 是       | 用户唯一标识符，用于集合命名或服务层数据隔离。                         |
| `collection_name` | String   | 是       | 要查询的目标知识集合的名称。                                           |
| `app_id`          | String   | 否       | （可选）用于获取 LLM API 密钥的客户端应用 ID。尽管此接口不直接调用 LLM，初始化配置仍可能通过路由器获取。 |
| `secret`          | String   | 否       | （可选）用于获取 LLM API 密钥的客户端应用密钥。与 `app_id` 一同提供。       |
| `query`           | String   | 是       | 用户提出的问题或查询语句。                                             |
| `limit`           | Integer  | 否       | （可选）希望从向量数据库召回的最大记忆片段数量。默认为 `5`。             |

**请求示例**:
```json
{
    "user_id": "user_alpha_001",
    "collection_name": "product_manuals_v2",
    "query": "如何重置设备到出厂设置？",
    "limit": 3
}
```