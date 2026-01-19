"""
后处理组件
"""
from typing import Dict, Any, List
from .base import BaseComponent


class PostprocessorComponent(BaseComponent):
    """
    后处理组件
    负责分类结果的后处理、优化、元数据添加等
    """
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        后处理分类结果
        
        Args:
            data: 分类结果数据
            
        Returns:
            处理后的数据
        """
        data = kwargs.get('data', {})
        items = data.get('items', [])
        
        # 执行后处理步骤
        processed_items = []
        for item in items:
            processed_item = self._process_item(item)
            processed_items.append(processed_item)
        
        # 添加元数据
        if self.config.include_metadata:
            processed_items = self._add_metadata(processed_items)
        
        # 优化分类结果
        processed_items = self._optimize_results(processed_items)
        
        return {
            'items': processed_items,
            'statistics': data.get('statistics', {}),
            'processing_info': {
                'metadata_added': self.config.include_metadata,
                'optimized': True,
                'total_processed': len(processed_items)
            }
        }
    
    def _process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """处理单个项目"""
        # 检查分类完整性
        if item.get('category'):
            item['is_complete'] = self._check_category_completeness(item['category'])
        
        # 调整置信度
        if item.get('confidence', 0) < self.config.min_confidence_score:
            item['is_low_confidence'] = True
        
        return item
    
    def _check_category_completeness(self, category: str) -> bool:
        """检查分类完整性"""
        if not category:
            return False
        return category.count('/') >= 2
    
    def _add_metadata(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """添加元数据"""
        # TODO: 从配置中读取并添加元数据
        for item in items:
            item['metadata'] = {
                'user_stage': '',
                'is_valid': '',
                'is_it_related': ''
            }
        return items
    
    def _optimize_results(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """优化分类结果"""
        # TODO: 实现结果优化逻辑
        # 例如：合并相似分类、修正明显错误等
        return items