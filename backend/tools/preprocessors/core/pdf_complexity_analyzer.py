"""
PDF复杂度分析器 - 改进版本
提供更准确的PDF复杂度评估，支持多维度分析和智能决策
"""
import os
import logging
import statistics
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PDFAnalysisResult:
    """PDF分析结果"""
    file_path: str
    file_size: int
    page_count: int
    
    # 基础指标
    is_encrypted: bool
    has_embedded_fonts: bool
    font_diversity: int
    total_text_length: int
    total_images: int
    
    # 分布指标
    avg_text_per_page: float
    text_variance: float
    text_consistency_score: float  # 0-1, 越高越一致
    image_density: float  # 有图片页面的比例
    
    # 质量指标
    likely_scanned_pages: int
    text_rich_pages: int
    mixed_content_pages: int
    
    # 决策支持
    complexity_score: float  # 0-10
    processing_recommendation: str  # 'internal', 'external', 'hybrid'
    confidence: float  # 0-1
    reasons: List[str]

class AdvancedPDFComplexityAnalyzer:
    """改进的PDF复杂度分析器"""
    
    # 配置参数
    CONFIG = {
        'max_sample_pages': 10,  # 最多采样页数（性能考虑）
        'min_sample_pages': 3,   # 最少采样页数
        'text_rich_threshold': 500,  # 富文本页面文字阈值
        'scanned_text_threshold': 50,  # 疑似扫描版文字阈值
        'large_file_threshold': 10 * 1024 * 1024,  # 10MB
        'huge_file_threshold': 50 * 1024 * 1024,   # 50MB
    }
    
    def analyze_pdf_complexity(self, file_path: str) -> PDFAnalysisResult:
        """
        综合分析PDF复杂度
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            PDFAnalysisResult: 详细的分析结果
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF文件不存在: {file_path}")
            
        file_size = os.path.getsize(file_path)
        
        try:
            import PyPDF2
            
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                
                # 基础信息提取
                page_count = len(pdf_reader.pages)
                is_encrypted = pdf_reader.is_encrypted
                
                # 如果加密，直接返回建议外部处理
                if is_encrypted:
                    return self._create_encrypted_result(file_path, file_size, page_count)
                
                # 采样策略：智能选择要分析的页面
                sample_pages = self._determine_sample_pages(page_count)
                logger.info(f"分析PDF: {page_count}页，采样{len(sample_pages)}页")
                
                # 多维度分析
                page_analysis = self._analyze_sampled_pages(pdf_reader, sample_pages)
                font_analysis = self._analyze_fonts(pdf_reader, sample_pages)
                
                # 计算统计指标
                stats = self._calculate_statistics(page_analysis, page_count)
                
                # 生成分析结果
                result = PDFAnalysisResult(
                    file_path=file_path,
                    file_size=file_size,
                    page_count=page_count,
                    is_encrypted=is_encrypted,
                    has_embedded_fonts=font_analysis['has_embedded'],
                    font_diversity=font_analysis['diversity'],
                    total_text_length=stats['total_text'],
                    total_images=stats['total_images'],
                    avg_text_per_page=stats['avg_text_per_page'],
                    text_variance=stats['text_variance'],
                    text_consistency_score=stats['consistency_score'],
                    image_density=stats['image_density'],
                    likely_scanned_pages=stats['scanned_pages'],
                    text_rich_pages=stats['rich_pages'],
                    mixed_content_pages=stats['mixed_pages'],
                    complexity_score=0.0,  # 待计算
                    processing_recommendation='',  # 待计算
                    confidence=0.0,  # 待计算
                    reasons=[]  # 待计算
                )
                
                # 智能决策
                self._make_processing_decision(result)
                
                return result
                
        except ImportError:
            logger.error("PyPDF2库未安装")
            raise ImportError("需要安装PyPDF2库: pip install PyPDF2")
        except Exception as e:
            logger.error(f"PDF分析失败: {str(e)}")
            raise RuntimeError(f"PDF分析失败: {str(e)}")
    
    def _determine_sample_pages(self, page_count: int) -> List[int]:
        """
        智能确定要采样的页面
        
        策略：
        1. 小文档：全部分析
        2. 中等文档：首页 + 中间 + 末页 + 随机采样
        3. 大文档：结构化采样
        """
        max_sample = self.CONFIG['max_sample_pages']
        min_sample = self.CONFIG['min_sample_pages']
        
        if page_count <= max_sample:
            return list(range(page_count))
        
        # 结构化采样策略
        sample_pages = set()
        
        # 必须包含的页面
        sample_pages.add(0)  # 首页
        if page_count > 1:
            sample_pages.add(page_count - 1)  # 末页
        if page_count > 2:
            sample_pages.add(page_count // 2)  # 中间页
        
        # 根据文档长度添加更多采样点
        if page_count > 10:
            # 添加四分位点
            sample_pages.add(page_count // 4)
            sample_pages.add(3 * page_count // 4)
        
        # 随机采样填补到目标数量
        import random
        remaining_pages = set(range(page_count)) - sample_pages
        additional_needed = min(max_sample - len(sample_pages), len(remaining_pages))
        
        if additional_needed > 0:
            additional_pages = random.sample(list(remaining_pages), additional_needed)
            sample_pages.update(additional_pages)
        
        return sorted(list(sample_pages))
    
    def _analyze_sampled_pages(self, pdf_reader, sample_pages: List[int]) -> List[Dict[str, Any]]:
        """分析采样页面的内容特征"""
        page_analysis = []
        
        for page_idx in sample_pages:
            try:
                page = pdf_reader.pages[page_idx]
                
                # 文本分析
                text = page.extract_text()
                text_length = len(text.strip())
                
                # 图片分析
                images_info = self._analyze_page_images(page)
                
                # 资源分析
                resources = page.get('/Resources', {})
                
                analysis = {
                    'page_idx': page_idx,
                    'text_length': text_length,
                    'images_count': images_info['count'],
                    'images_types': images_info['types'],
                    'has_xobjects': '/XObject' in resources,
                    'has_fonts': '/Font' in resources,
                    'resource_complexity': self._calculate_resource_complexity(resources),
                    'text_sample': text[:200] if text else '',  # 用于进一步分析
                }
                
                # 页面类型推断
                analysis['page_type'] = self._classify_page_type(analysis)
                
                page_analysis.append(analysis)
                
            except Exception as e:
                logger.warning(f"分析第{page_idx + 1}页失败: {str(e)}")
                continue
        
        return page_analysis
    
    def _analyze_page_images(self, page) -> Dict[str, Any]:
        """分析页面中的图片"""
        images_info = {
            'count': 0,
            'types': set(),
            'estimated_size': 0
        }
        
        try:
            xobjects = page.get('/Resources', {}).get('/XObject', {})
            
            for obj_name, obj_ref in xobjects.items():
                try:
                    obj = obj_ref.get_object()
                    if obj.get('/Subtype') == '/Image':
                        images_info['count'] += 1
                        
                        # 尝试获取图片信息
                        width = obj.get('/Width', 0)
                        height = obj.get('/Height', 0)
                        if width and height:
                            images_info['estimated_size'] += width * height
                            
                        # 获取颜色空间信息
                        colorspace = obj.get('/ColorSpace')
                        if colorspace:
                            images_info['types'].add(str(colorspace))
                            
                except Exception:
                    continue
                    
        except Exception:
            pass
        
        return images_info
    
    def _analyze_fonts(self, pdf_reader, sample_pages: List[int]) -> Dict[str, Any]:
        """分析字体信息"""
        font_analysis = {
            'diversity': 0,
            'has_embedded': False,
            'font_names': set(),
            'embedded_fonts': set()
        }
        
        for page_idx in sample_pages[:5]:  # 只分析前5个采样页面（性能考虑）
            try:
                page = pdf_reader.pages[page_idx]
                fonts = page.get('/Resources', {}).get('/Font', {})
                
                for font_name, font_ref in fonts.items():
                    font_analysis['font_names'].add(font_name)
                    
                    try:
                        font_obj = font_ref.get_object()
                        # 检查是否有嵌入字体
                        if any(key in font_obj for key in ['/FontFile', '/FontFile2', '/FontFile3']):
                            font_analysis['has_embedded'] = True
                            font_analysis['embedded_fonts'].add(font_name)
                    except Exception:
                        continue
                        
            except Exception:
                continue
        
        font_analysis['diversity'] = len(font_analysis['font_names'])
        return font_analysis
    
    def _calculate_resource_complexity(self, resources: Dict) -> int:
        """计算页面资源复杂度"""
        complexity = 0
        
        # 字体复杂度
        fonts = resources.get('/Font', {})
        complexity += len(fonts)
        
        # 图形对象复杂度
        xobjects = resources.get('/XObject', {})
        complexity += len(xobjects) * 2
        
        # 其他资源
        for key in ['/ExtGState', '/ColorSpace', '/Pattern', '/Shading']:
            if key in resources:
                complexity += len(resources[key])
        
        return complexity
    
    def _classify_page_type(self, analysis: Dict[str, Any]) -> str:
        """分类页面类型"""
        text_length = analysis['text_length']
        images_count = analysis['images_count']
        
        if text_length < self.CONFIG['scanned_text_threshold']:
            if images_count > 0:
                return 'likely_scanned'  # 可能是扫描版
            else:
                return 'minimal_content'  # 内容极少
        elif text_length > self.CONFIG['text_rich_threshold']:
            if images_count > 0:
                return 'rich_mixed'  # 图文混排
            else:
                return 'text_rich'  # 富文本
        else:
            if images_count > 0:
                return 'mixed_content'  # 混合内容
            else:
                return 'normal_text'  # 普通文本
    
    def _calculate_statistics(self, page_analysis: List[Dict], total_pages: int) -> Dict[str, Any]:
        """计算统计指标"""
        if not page_analysis:
            return self._empty_statistics()
        
        # 提取文本长度列表
        text_lengths = [p['text_length'] for p in page_analysis]
        
        # 基础统计
        total_text = sum(text_lengths)
        total_images = sum(p['images_count'] for p in page_analysis)
        avg_text_per_page = total_text / len(page_analysis) if page_analysis else 0
        
        # 文本方差和一致性
        text_variance = statistics.variance(text_lengths) if len(text_lengths) > 1 else 0
        mean_text = statistics.mean(text_lengths) if text_lengths else 0
        
        # 一致性评分：方差越小，一致性越高
        consistency_score = 0.0
        if mean_text > 0:
            cv = (text_variance ** 0.5) / mean_text  # 变异系数
            consistency_score = max(0.0, 1.0 - min(cv, 1.0))
        
        # 页面类型统计
        page_types = [p['page_type'] for p in page_analysis]
        scanned_pages = sum(1 for t in page_types if t == 'likely_scanned')
        rich_pages = sum(1 for t in page_types if t in ['text_rich', 'rich_mixed'])
        mixed_pages = sum(1 for t in page_types if 'mixed' in t)
        
        # 图片密度
        pages_with_images = sum(1 for p in page_analysis if p['images_count'] > 0)
        image_density = pages_with_images / len(page_analysis) if page_analysis else 0
        
        # 按比例推算到全文档
        sample_ratio = len(page_analysis) / total_pages
        estimated_total_text = int(total_text / sample_ratio) if sample_ratio > 0 else total_text
        estimated_total_images = int(total_images / sample_ratio) if sample_ratio > 0 else total_images
        
        return {
            'total_text': estimated_total_text,
            'total_images': estimated_total_images,
            'avg_text_per_page': avg_text_per_page,
            'text_variance': text_variance,
            'consistency_score': consistency_score,
            'image_density': image_density,
            'scanned_pages': int(scanned_pages / sample_ratio) if sample_ratio > 0 else scanned_pages,
            'rich_pages': int(rich_pages / sample_ratio) if sample_ratio > 0 else rich_pages,
            'mixed_pages': int(mixed_pages / sample_ratio) if sample_ratio > 0 else mixed_pages,
        }
    
    def _make_processing_decision(self, result: PDFAnalysisResult) -> None:
        """智能决策处理方式"""
        reasons = []
        score = 0.0  # 复杂度评分 (0-10)
        
        # 1. 文件大小因素 (0-2分)
        if result.file_size > self.CONFIG['huge_file_threshold']:
            score += 2.0
            reasons.append(f"文件很大({result.file_size/1024/1024:.1f}MB)")
        elif result.file_size > self.CONFIG['large_file_threshold']:
            score += 1.0
            reasons.append(f"文件较大({result.file_size/1024/1024:.1f}MB)")
        
        # 2. 页数因素 (0-1分)
        if result.page_count > 100:
            score += 1.0
            reasons.append(f"页数很多({result.page_count}页)")
        elif result.page_count > 50:
            score += 0.5
        
        # 3. 扫描版检测 (0-3分) - 最重要的因素
        scanned_ratio = result.likely_scanned_pages / result.page_count
        if scanned_ratio > 0.7:
            score += 3.0
            reasons.append(f"{scanned_ratio:.1%}页面疑似扫描版")
        elif scanned_ratio > 0.3:
            score += 1.5
            reasons.append(f"{scanned_ratio:.1%}页面疑似扫描版")
        elif scanned_ratio > 0.1:
            score += 0.5
        
        # 4. 图片密度 (0-1.5分)
        if result.image_density > 0.8:
            score += 1.5
            reasons.append(f"{result.image_density:.1%}页面包含图片")
        elif result.image_density > 0.5:
            score += 1.0
            reasons.append(f"{result.image_density:.1%}页面包含图片")
        elif result.image_density > 0.2:
            score += 0.5
        
        # 5. 文本一致性 (0-1分) - 低一致性可能表示复杂布局
        if result.text_consistency_score < 0.3:
            score += 1.0
            reasons.append("文本分布不一致，可能为复杂布局")
        elif result.text_consistency_score < 0.6:
            score += 0.5
        
        # 6. 字体复杂度 (0-0.5分)
        if result.font_diversity > 10:
            score += 0.5
            reasons.append(f"字体种类较多({result.font_diversity}种)")
        elif result.font_diversity > 5:
            score += 0.2
        
        # 7. 嵌入字体奖励 (-0.5分) - 有嵌入字体的文档通常更适合内部处理
        if result.has_embedded_fonts:
            score -= 0.5
            reasons.append("包含嵌入字体")
        
        # 限制评分范围
        score = max(0.0, min(10.0, score))
        
        # 决策逻辑
        if score >= 6.0:
            recommendation = 'external'
            confidence = min(1.0, score / 10.0)
        elif score >= 3.0:
            recommendation = 'hybrid'  # 建议先尝试内部，失败则外部
            confidence = 0.6
        else:
            recommendation = 'internal'
            confidence = min(1.0, (10.0 - score) / 10.0)
        
        # 特殊规则覆盖
        if result.is_encrypted:
            recommendation = 'external'
            confidence = 1.0
            reasons = ["PDF已加密"]
        
        # 更新结果
        result.complexity_score = score
        result.processing_recommendation = recommendation
        result.confidence = confidence
        result.reasons = reasons
    
    def _create_encrypted_result(self, file_path: str, file_size: int, page_count: int) -> PDFAnalysisResult:
        """为加密PDF创建结果"""
        return PDFAnalysisResult(
            file_path=file_path,
            file_size=file_size,
            page_count=page_count,
            is_encrypted=True,
            has_embedded_fonts=False,
            font_diversity=0,
            total_text_length=0,
            total_images=0,
            avg_text_per_page=0.0,
            text_variance=0.0,
            text_consistency_score=0.0,
            image_density=0.0,
            likely_scanned_pages=0,
            text_rich_pages=0,
            mixed_content_pages=0,
            complexity_score=10.0,
            processing_recommendation='external',
            confidence=1.0,
            reasons=['PDF已加密，需要专业工具处理']
        )
    
    def _empty_statistics(self) -> Dict[str, Any]:
        """空统计结果"""
        return {
            'total_text': 0,
            'total_images': 0,
            'avg_text_per_page': 0.0,
            'text_variance': 0.0,
            'consistency_score': 0.0,
            'image_density': 0.0,
            'scanned_pages': 0,
            'rich_pages': 0,
            'mixed_pages': 0,
        }

def analyze_pdf_complexity(file_path: str) -> PDFAnalysisResult:
    """便捷函数：分析PDF复杂度"""
    analyzer = AdvancedPDFComplexityAnalyzer()
    return analyzer.analyze_pdf_complexity(file_path)

def should_use_external_api(file_path: str) -> Tuple[bool, str, float]:
    """
    便捷函数：判断是否应该使用外部API
    
    Returns:
        Tuple[bool, str, float]: (是否使用外部API, 原因, 置信度)
    """
    try:
        result = analyze_pdf_complexity(file_path)
        
        use_external = result.processing_recommendation in ['external', 'hybrid']
        reason = '; '.join(result.reasons)
        
        return use_external, reason, result.confidence
        
    except Exception as e:
        logger.error(f"PDF复杂度分析失败: {str(e)}")
        return True, f"分析失败，默认使用外部API: {str(e)}", 0.5

if __name__ == "__main__":
    # 测试代码
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        try:
            result = analyze_pdf_complexity(file_path)
            print(f"文件: {result.file_path}")
            print(f"复杂度评分: {result.complexity_score:.2f}/10")
            print(f"处理建议: {result.processing_recommendation}")
            print(f"置信度: {result.confidence:.2f}")
            print(f"原因: {'; '.join(result.reasons)}")
            
        except Exception as e:
            print(f"分析失败: {str(e)}")
    else:
        print("用法: python pdf_complexity_analyzer.py <pdf_file_path>")