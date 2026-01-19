# MinerU-API 服务器架构

## 系统架构图

```mermaid
graph TB
    subgraph "客户端层"
        Client[客户端应用]
    end
    
    subgraph "API 网关层"
        FastAPI[FastAPI 应用]
        EP1["/predict 端点"]
        EP2["/download_output_files 端点"]
    end
    
    subgraph "服务框架层"
        LitServe[LitServe 服务器]
        GPU[GPU 加速器<br/>CUDA]
    end
    
    subgraph "业务逻辑层"
        MinerUAPI[MinerUAPI 类]
        FileConv[文件转换模块<br/>cvt2pdf]
        Parse[PDF 解析模块<br/>do_parse]
        Memory[内存管理<br/>clean_memory]
    end
    
    subgraph "模型层"
        ModelManager[ModelSingleton<br/>模型管理器]
        Model1[模型实例 1]
        Model2[模型实例 2]
    end
    
    subgraph "依赖库层"
        MagicPDF[magic_pdf 库]
        PyMuPDF[PyMuPDF/fitz<br/>PDF 处理]
        Torch[PyTorch<br/>深度学习框架]
    end
    
    subgraph "存储层"
        TempDir[临时文件目录<br/>/tmp]
        OutputDir[输出目录<br/>/home/lisongming/tmp]
    end
    
    Client -->|HTTP POST<br/>Base64 文件| EP1
    EP1 --> LitServe
    LitServe --> MinerUAPI
    MinerUAPI --> FileConv
    FileConv -->|转换为 PDF| Parse
    Parse --> ModelManager
    ModelManager --> Model1
    ModelManager --> Model2
    
    MinerUAPI --> Memory
    Memory -->|清理| GPU
    
    FileConv --> PyMuPDF
    Parse --> MagicPDF
    MagicPDF --> Torch
    
    FileConv -->|临时文件| TempDir
    Parse -->|解析结果| OutputDir
    
    Client -.->|未实现| EP2
```

## 组件说明

### 1. API 层
- **FastAPI**: 提供 RESTful API 接口
- **端点**:
  - `/predict`: 接收 Base64 编码的文件，返回解析结果目录
  - `/download_output_files`: 下载输出文件（未完整实现）

### 2. 服务框架
- **LitServe**: 高性能服务框架
  - 支持 GPU 加速（CUDA）
  - 自动设备分配
  - 批处理支持（最大 32）
  - 超时控制（请求 120s，批处理 60s）

### 3. 核心处理流程

```mermaid
sequenceDiagram
    participant C as 客户端
    participant S as 服务器
    participant M as MinerUAPI
    participant P as PDF解析器
    participant F as 文件系统
    
    C->>S: POST /predict<br/>{file: base64, kwargs: {}}
    S->>M: decode_request()
    M->>M: cvt2pdf()<br/>转换文件格式
    M->>P: do_parse()<br/>解析 PDF
    P->>F: 保存解析结果
    F-->>M: 输出目录路径
    M->>M: clean_memory()<br/>清理内存
    M-->>S: encode_response()
    S-->>C: {output_dir: "路径"}
```

### 4. 文件格式支持
- **直接支持**: PDF
- **图片转换**: JPG, PNG → PDF
- **文档转换**: DOC, DOCX, PPT, PPTX → PDF

### 5. 性能优化
- **GPU 加速**: 使用 CUDA 进行模型推理
- **内存管理**: 
  - 自动清理 CUDA 缓存
  - 垃圾回收机制
  - 临时文件自动清理
- **批处理**: 支持最多 32 个请求批处理

### 6. 错误处理
- HTTP 异常处理
- 文件格式验证
- 临时目录清理保证
- 解析失败时的目录清理

## 部署配置
```python
# 服务器配置
- 端口: 8002
- GPU: 自动分配
- 每设备工作进程: 1
- 超时: 禁用全局超时
- 输出目录: /home/lisongming/tmp
```