# Pagtive 项目创建阶段增强方案
*创建日期: 2025-09-10*

## 一、现状分析

### 1.1 当前文件处理能力

Backend 已有的文件处理服务：

1. **对象存储服务 (object_storage)**
   - `StorageManager`: 统一的文件上传/下载管理
   - 支持阿里云OSS存储
   - 文件URL生成和权限管理

2. **文档处理服务**
   
    **PDF处理服务**
    - `customized/pdf_converter/pdf_content_extractor.py`: PDF内容提取为Markdown
    - `mineru/services.py`: MinerU PDF解析服务（支持更复杂的PDF）
    - `tools/preprocessors/pdf_parser.py`: PDF解析工具接口

    **DOCX处理服务**
    - `tools/preprocessors/docx_parser.py`: DOCX解析工具接口（✅ 已创建）
    
    **Excel处理服务**
    - `tools/preprocessors/excel_parser.py`: Excel解析工具接口（✅ 已创建）
    
    **文本/代码处理服务**
    - `tools/preprocessors/text_parser.py`: 通用文本解析工具接口（✅ 已创建）

3. **处理能力状态**
   - ✅ PDF文件处理（已有多个服务）
   - ✅ DOCX文件处理（已创建 docx_parser.py - 提取为Markdown格式）
   - ✅ XLSX文件处理（已创建 excel_parser.py - 输出pandas JSON格式）
   - ✅ 文本文件处理（已创建 text_parser.py - 支持txt/md/log/csv/代码文件等）

### 1.2 当前数据保存问题

```python
# 当前views.py中的项目创建流程
def perform_create(self, serializer):
    # ⚠️ 问题1: 前端收集的数据未完整保存
    # content_type, target_audience 等信息丢失
    
    # ⚠️ 问题2: 文件只上传到OSS，内容未提取
    reference_files = []
    for uploaded_file in uploaded_files:
        storage_file = storage_manager.upload(...)
        reference_files.append({
            'file_name': uploaded_file.name,
            'file_path': storage_file.file_key,
            # ❌ 缺少: extracted_content
        })
    
    # ⚠️ 问题3: style_tags 未充分利用
    # 只保存简单的标签，未存储元数据
```

## 二、增强方案

### 2.1 完善数据保存

```python
# services/project_service.py 中增强 create_project 方法

def create_project(self, user, project_data, uploaded_files=None):
    """
    增强的项目创建方法
    """
    # 1. 提取所有前端数据
    content_type = project_data.pop('content_type', 'presentation')
    target_audience = project_data.pop('target_audience', '')
    additional_requirements = project_data.pop('additional_requirements', '')
    
    # 2. 构建完整的 style_tags 结构
    style_tags = [
        {
            "category": "project_metadata",
            "tags": {
                "content_type": content_type,
                "target_audience": target_audience,
                "additional_requirements": additional_requirements,
                "created_method": "manual",  # 或 "imported"
                "creation_time": timezone.now().isoformat()
            }
        }
    ]
    
    # 3. 合并风格要求到 project_style
    style_parts = [
        project_data.get('project_style', ''),
        f"内容类型: {content_type}" if content_type else '',
        f"目标受众: {target_audience}" if target_audience else '',
        additional_requirements
    ]
    project_data['project_style'] = '\n'.join(filter(None, style_parts))
    
    # 4. 处理上传的文件
    reference_files = []
    if uploaded_files:
        for file in uploaded_files:
            file_info = self._process_uploaded_file(user, file)
            reference_files.append(file_info)
    
    # 5. 创建项目
    project = Project.objects.create(
        user=user,
        style_tags=style_tags,
        reference_files=reference_files,
        **project_data
    )
    
    return project
```

### 2.2 文件内容提取服务

```python
# services/document_processor.py (新建)

import logging
from typing import Dict, Any, Optional
from django.conf import settings
import base64

logger = logging.getLogger('django')

class DocumentProcessor:
    """
    文档处理服务 - 提取各种格式文件的文本内容
    """
    
    def process_file(self, file_bytes: bytes, file_name: str, 
                     file_type: str) -> Dict[str, Any]:
        """
        处理上传的文件，提取内容
        
        Returns:
            {
                'file_name': str,
                'file_type': str,
                'extracted_content': str,  # 提取的文本内容
                'metadata': {
                    'pages': int,
                    'words': int,
                    'tables': int,
                    'images': int,
                    'key_points': []  # AI提取的关键点
                }
            }
        """
        # 根据文件类型选择处理方法
        if file_type == 'application/pdf' or file_name.endswith('.pdf'):
            return self._process_pdf(file_bytes, file_name)
        
        elif file_type in ['application/msword', 
                          'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            return self._process_docx(file_bytes, file_name)
        
        elif file_type in ['application/vnd.ms-excel',
                          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
            return self._process_excel(file_bytes, file_name)
        
        elif file_type in ['text/plain', 'text/markdown']:
            return self._process_text(file_bytes, file_name)
        
        else:
            return {
                'file_name': file_name,
                'file_type': file_type,
                'extracted_content': '',
                'metadata': {'error': 'Unsupported file type'}
            }
    
    def _process_pdf(self, file_bytes: bytes, file_name: str) -> Dict[str, Any]:
        """处理PDF文件"""
        try:
            # 使用现有的 pdf_content_extractor
            from customized.pdf_converter.pdf_content_extractor import extract_pdf_content
            
            # 转换为base64
            pdf_base64 = base64.b64encode(file_bytes).decode('utf-8')
            
            # 调用PDF提取服务
            result = extract_pdf_content(pdf_base64, file_name)
            
            if result['status'] == 'success':
                content = result['content']
                
                # 统计信息
                metadata = {
                    'pages': content.count('<!-- File:') + 1,  # 简单估算页数
                    'words': len(content.split()),
                    'images': result.get('images_count', 0),
                    'processing_time': result.get('run_time', 0)
                }
                
                return {
                    'file_name': file_name,
                    'file_type': 'pdf',
                    'extracted_content': content,
                    'metadata': metadata
                }
            else:
                logger.error(f"PDF处理失败: {result.get('message')}")
                return self._fallback_pdf_processing(file_bytes, file_name)
                
        except Exception as e:
            logger.error(f"PDF处理异常: {str(e)}")
            return self._fallback_pdf_processing(file_bytes, file_name)
    
    def _fallback_pdf_processing(self, file_bytes: bytes, file_name: str) -> Dict[str, Any]:
        """PDF处理备用方案 - 使用PyPDF2"""
        try:
            import PyPDF2
            import io
            
            pdf_file = io.BytesIO(file_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text_content = []
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text_content.append(page.extract_text())
            
            content = '\n\n'.join(text_content)
            
            return {
                'file_name': file_name,
                'file_type': 'pdf',
                'extracted_content': content,
                'metadata': {
                    'pages': len(pdf_reader.pages),
                    'words': len(content.split()),
                    'method': 'PyPDF2'
                }
            }
            
        except Exception as e:
            logger.error(f"PDF备用处理失败: {str(e)}")
            return {
                'file_name': file_name,
                'file_type': 'pdf',
                'extracted_content': '',
                'metadata': {'error': str(e)}
            }
    
    def _process_docx(self, file_bytes: bytes, file_name: str) -> Dict[str, Any]:
        """处理DOCX文件 - 使用已创建的DOCXParserTool"""
        try:
            from tools.preprocessors.docx_parser import DOCXParserTool
            import tempfile
            import os
            
            # 保存为临时文件
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
                tmp_file.write(file_bytes)
                tmp_path = tmp_file.name
            
            try:
                # 使用DOCXParserTool
                parser = DOCXParserTool()
                result = parser.execute({
                    "file_path": tmp_path,
                    "extract_images": False,  # 不提取图片以节省空间
                    "include_metadata": True,
                    "preserve_formatting": True
                })
                
                if result["status"] == "success":
                    return {
                        'file_name': file_name,
                        'file_type': 'docx',
                        'extracted_content': result.get('content', ''),
                        'metadata': {
                            **result.get('statistics', {}),
                            **result.get('metadata', {}),
                            'tables_data': result.get('tables', [])
                        }
                    }
                else:
                    logger.error(f"DOCX解析失败: {result.get('message')}")
                    return {
                        'file_name': file_name,
                        'file_type': 'docx',
                        'extracted_content': '',
                        'metadata': {'error': result.get('message')}
                    }
                    
            finally:
                # 清理临时文件
                os.unlink(tmp_path)
                
        except ImportError:
            logger.error("需要安装python-docx: pip install python-docx")
            return {
                'file_name': file_name,
                'file_type': 'docx',
                'extracted_content': '',
                'metadata': {'error': 'python-docx not installed'}
            }
        except Exception as e:
            logger.error(f"DOCX处理失败: {str(e)}")
            return {
                'file_name': file_name,
                'file_type': 'docx',
                'extracted_content': '',
                'metadata': {'error': str(e)}
            }
    
    def _process_excel(self, file_bytes: bytes, file_name: str) -> Dict[str, Any]:
        """处理Excel文件 - 使用已创建的ExcelParserTool"""
        try:
            from tools.preprocessors.excel_parser import ExcelParserTool
            import tempfile
            import os
            import json
            
            # 保存为临时文件
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
                tmp_file.write(file_bytes)
                tmp_path = tmp_file.name
            
            try:
                # 使用ExcelParserTool
                parser = ExcelParserTool()
                result = parser.execute({
                    "file_path": tmp_path,
                    "sheet_name": None,  # 读取所有工作表
                    "orient": "records",  # 使用records格式，便于理解
                    "include_summary": True
                })
                
                if result["status"] == "success":
                    # 提取数据为JSON字符串形式存储
                    if 'sheets' in result:
                        # 多个工作表
                        extracted_content = json.dumps(result['sheets'], ensure_ascii=False)
                        metadata = result.get('summary', {})
                        metadata['file_summary'] = result.get('file_summary', {})
                    else:
                        # 单个工作表
                        extracted_content = json.dumps(result['data'], ensure_ascii=False)
                        metadata = result.get('summary', {})
                    
                    return {
                        'file_name': file_name,
                        'file_type': 'excel',
                        'extracted_content': extracted_content,  # JSON格式的数据
                        'metadata': metadata
                    }
                else:
                    logger.error(f"Excel解析失败: {result.get('message')}")
                    return {
                        'file_name': file_name,
                        'file_type': 'excel',
                        'extracted_content': '',
                        'metadata': {'error': result.get('message')}
                    }
                    
            finally:
                # 清理临时文件
                os.unlink(tmp_path)
                
        except ImportError:
            logger.error("需要安装pandas和openpyxl: pip install pandas openpyxl")
            return {
                'file_name': file_name,
                'file_type': 'excel',
                'extracted_content': '',
                'metadata': {'error': 'pandas/openpyxl not installed'}
            }
        except Exception as e:
            logger.error(f"Excel处理失败: {str(e)}")
            return {
                'file_name': file_name,
                'file_type': 'excel',
                'extracted_content': '',
                'metadata': {'error': str(e)}
            }
    
    def _process_text(self, file_bytes: bytes, file_name: str) -> Dict[str, Any]:
        """处理文本文件 - 使用已创建的TextParserTool"""
        try:
            from tools.preprocessors.text_parser import TextParserTool
            from pathlib import Path
            import tempfile
            import os
            
            # 确定文件后缀
            suffix = Path(file_name).suffix or '.txt'
            
            # 保存为临时文件
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
                tmp_file.write(file_bytes)
                tmp_path = tmp_file.name
            
            try:
                # 使用TextParserTool
                parser = TextParserTool()
                result = parser.execute({
                    "file_path": tmp_path,
                    "extract_structure": True,
                    "detect_patterns": True
                })
                
                if result["status"] == "success":
                    return {
                        'file_name': file_name,
                        'file_type': result.get('file_type', 'text'),
                        'extracted_content': result.get('content', ''),
                        'metadata': {
                            **result.get('statistics', {}),
                            **result.get('metadata', {}),
                            'structured_content': result.get('structured_content')
                        }
                    }
                else:
                    logger.error(f"文本解析失败: {result.get('message')}")
                    return {
                        'file_name': file_name,
                        'file_type': 'text',
                        'extracted_content': '',
                        'metadata': {'error': result.get('message')}
                    }
                    
            finally:
                # 清理临时文件
                os.unlink(tmp_path)
                
        except Exception as e:
            logger.error(f"文本文件处理失败: {str(e)}")
            return {
                'file_name': file_name,
                'file_type': 'text',
                'extracted_content': '',
                'metadata': {'error': str(e)}
            }
    
    def extract_key_points(self, content: str, max_points: int = 5) -> list:
        """
        使用AI提取文档关键点（可选功能）
        """
        # TODO: 调用LLM服务提取关键点
        # 这里可以集成现有的LLM服务
        return []
```

### 2.3 整合到项目创建流程

```python
# services/project_service.py 增强

def _process_uploaded_file(self, user, uploaded_file) -> Dict[str, Any]:
    """
    处理单个上传文件
    """
    # 1. 上传到OSS
    storage_service = StorageService(user=user)
    storage_info = storage_service.upload_document(
        document=uploaded_file,
        metadata={'source': 'project_creation'}
    )
    
    # 2. 提取文件内容
    processor = DocumentProcessor()
    file_bytes = uploaded_file.read()
    uploaded_file.seek(0)  # 重置文件指针
    
    process_result = processor.process_file(
        file_bytes=file_bytes,
        file_name=uploaded_file.name,
        file_type=uploaded_file.content_type
    )
    
    # 3. 组合文件信息
    file_info = {
        'file_name': uploaded_file.name,
        'file_path': storage_info['file_key'],
        'file_url': storage_info['url'],
        'file_type': process_result.get('file_type', 'unknown'),
        'file_size': uploaded_file.size,
        'extracted_content': process_result.get('extracted_content', ''),
        'metadata': {
            **process_result.get('metadata', {}),
            'upload_time': timezone.now().isoformat(),
            'storage_id': storage_info['id']
        }
    }
    
    # 4. 如果内容提取失败，记录但不阻塞
    if not file_info['extracted_content']:
        logger.warning(f"文件内容提取失败: {uploaded_file.name}")
        file_info['metadata']['extraction_failed'] = True
    
    return file_info
```

## 三、实施步骤

### 第一步：创建文档处理服务（立即可做）

1. 创建 `services/document_processor.py`
2. 实现基本的文件处理方法
3. 集成现有的PDF处理服务

### 第二步：增强项目创建服务

1. 修改 `services/project_service.py` 的 `create_project` 方法
2. 添加 `_process_uploaded_file` 方法
3. 确保所有前端数据都被保存

### 第三步：更新视图层

```python
# views.py 修改

def perform_create(self, serializer):
    """创建项目时保存完整信息"""
    
    # 收集所有数据（包括未在serializer中的）
    extra_data = {
        'content_type': self.request.data.get('content_type'),
        'target_audience': self.request.data.get('target_audience'),
        'additional_requirements': self.request.data.get('additional_requirements'),
    }
    
    # 合并数据
    project_data = {**serializer.validated_data, **extra_data}
    
    # 获取上传的文件
    uploaded_files = self.request.FILES.getlist('files')
    
    # 调用服务创建项目
    project = self.project_service.create_project(
        user=self.request.user,
        project_data=project_data,
        uploaded_files=uploaded_files
    )
    
    # 返回创建的项目
    serializer.instance = project
```

## 四、数据存储示例

### 完整的项目数据结构

```json
{
  "project_name": "企业年度报告",
  "project_description": "2024年度公司业绩总结与展望",
  "project_style": "现代科技风格，蓝色主题\n内容类型: presentation\n目标受众: 公司股东、投资者\n需要包含数据图表和时间线",
  
  "style_tags": [
    {
      "category": "project_metadata",
      "tags": {
        "content_type": "presentation",
        "target_audience": "公司股东、投资者、高级管理层",
        "additional_requirements": "需要包含数据图表和时间线",
        "created_method": "manual",
        "creation_time": "2025-09-10T10:00:00Z"
      }
    }
  ],
  
  "reference_files": [
    {
      "file_name": "2023年度报告.pdf",
      "file_path": "oss://pagtive/2025/09/uuid/file.pdf",
      "file_url": "https://oss.example.com/signed-url",
      "file_type": "pdf",
      "file_size": 2548576,
      "extracted_content": "# 2023年度报告\n\n## 业绩概览\n公司在2023年实现营收增长25%...",
      "metadata": {
        "pages": 45,
        "words": 12500,
        "images": 23,
        "tables": 8,
        "upload_time": "2025-09-10T10:00:00Z",
        "storage_id": "storage-uuid",
        "processing_time": 5.2
      }
    },
    {
      "file_name": "财务数据.xlsx",
      "file_path": "oss://pagtive/2025/09/uuid/data.xlsx",
      "file_url": "https://oss.example.com/signed-url",
      "file_type": "excel",
      "file_size": 156432,
      "extracted_content": "## 营收数据\n\n| 季度 | 营收(万) | 同比增长 |\n|------|---------|----------|\n| Q1 | 2500 | 15% |...",
      "metadata": {
        "sheets": 5,
        "tables": 5,
        "total_rows": 248,
        "upload_time": "2025-09-10T10:00:00Z",
        "storage_id": "storage-uuid2"
      }
    }
  ],
  
  "pages": []  // 初始为空，在规划阶段生成
}
```

## 五、依赖和配置

### 需要的Python包

```python
# requirements.txt 添加
python-docx>=0.8.11  # DOCX文件处理
pandas>=1.5.0        # Excel文件处理
openpyxl>=3.0.0      # Excel文件读写
PyPDF2>=3.0.0        # PDF备用处理
tabulate>=0.9.0      # Markdown表格生成
```

### 配置项

```python
# settings.py 添加

PAGTIVE_FILE_PROCESSING = {
    'MAX_FILE_SIZE': 50 * 1024 * 1024,  # 50MB
    'SUPPORTED_FORMATS': {
        'pdf': ['application/pdf'],
        'docx': ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
        'excel': ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
        'text': ['text/plain', 'text/markdown', 'text/csv']
    },
    'PDF_SERVICE_URL': 'http://127.0.0.1:8002/predict',  # PDF处理服务地址
    'EXTRACTION_TIMEOUT': 30,  # 文件处理超时时间（秒）
}
```

## 六、错误处理

```python
# 文件处理的错误处理策略

def handle_file_processing_error(file_name: str, error: Exception) -> Dict[str, Any]:
    """
    文件处理错误时的降级策略
    """
    logger.error(f"文件处理失败 {file_name}: {str(error)}")
    
    return {
        'file_name': file_name,
        'file_type': 'unknown',
        'extracted_content': '',  # 空内容但不阻塞项目创建
        'metadata': {
            'error': str(error),
            'extraction_failed': True,
            'fallback_used': True
        }
    }

# 在项目创建时
try:
    file_info = self._process_uploaded_file(user, file)
except Exception as e:
    # 错误不阻塞项目创建
    file_info = handle_file_processing_error(file.name, e)

reference_files.append(file_info)
```

## 七、测试建议

### 单元测试

```python
# tests/test_document_processor.py

class DocumentProcessorTest(TestCase):
    def setUp(self):
        self.processor = DocumentProcessor()
    
    def test_process_pdf(self):
        with open('test_files/sample.pdf', 'rb') as f:
            result = self.processor.process_file(
                file_bytes=f.read(),
                file_name='sample.pdf',
                file_type='application/pdf'
            )
        
        self.assertIn('extracted_content', result)
        self.assertGreater(len(result['extracted_content']), 0)
    
    def test_process_docx(self):
        # 类似测试DOCX处理
        pass
    
    def test_process_excel(self):
        # 类似测试Excel处理
        pass
```

## 八、总结

通过以上增强方案，可以实现：

1. ✅ **完整保存前端数据**：content_type、target_audience等不再丢失
2. ✅ **文件内容提取**：支持PDF、DOCX、Excel、文本文件的内容提取
3. ✅ **结构化存储**：利用现有JSON字段存储所有元数据
4. ✅ **容错处理**：文件处理失败不影响项目创建
5. ✅ **可扩展性**：易于添加新的文件格式支持

这些改进可以为后续的页面生成提供丰富的上下文信息，显著提升生成质量。