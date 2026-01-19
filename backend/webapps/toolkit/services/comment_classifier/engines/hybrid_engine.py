"""
混合分类引擎
"""
from typing import Dict, Any, List, Tuple, Optional
from .base import BaseClassifierEngine
from .ai_engine import AIClassifierEngine
from .rule_engine import RuleClassifierEngine


class HybridClassifierEngine(BaseClassifierEngine):
    """
    混合分类引擎
    结合规则和AI进行分类
    """
    
    def __init__(self, config: Any):
        super().__init__(config)
        self.rule_engine = RuleClassifierEngine(config)
        self.ai_engine = AIClassifierEngine(config)
    
    def classify(self, content: str) -> Tuple[Optional[str], float, str]:
        """
        混合分类策略
        
        Args:
            content: 待分类内容
            
        Returns:
            (分类路径, 置信度, 分类器名称)
        """
        # 首先尝试规则分类
        rule_category, rule_confidence, rule_classifier = self.rule_engine.classify(content)
        
        # 如果规则分类置信度高，直接返回
        if rule_confidence >= 0.7:
            return rule_category, rule_confidence, rule_classifier
        
        # 否则使用AI分类
        ai_category, ai_confidence, ai_classifier = self.ai_engine.classify(content)
        
        # 选择最佳结果
        if rule_confidence > ai_confidence:
            return rule_category, rule_confidence, f"混合-{rule_classifier}"
        else:
            return ai_category, ai_confidence, f"混合-{ai_classifier}"
    
    def classify_batch(self, contents: List[str]) -> List[Dict[str, Any]]:
        """
        批量分类
        
        Args:
            contents: 待分类内容列表
            
        Returns:
            分类结果列表
        """
        # 先用规则引擎批量处理
        rule_results = self.rule_engine.classify_batch(contents)
        
        # 收集需要AI处理的内容
        ai_needed = []
        ai_indices = []
        for i, result in enumerate(rule_results):
            if result.get('confidence', 0) < 0.7:
                ai_needed.append(contents[i])
                ai_indices.append(i)
        
        # AI批量处理低置信度内容
        if ai_needed:
            ai_results = self.ai_engine.classify_batch(ai_needed)
            # 合并结果
            for idx, ai_result in zip(ai_indices, ai_results):
                if ai_result['confidence'] > rule_results[idx]['confidence']:
                    rule_results[idx] = ai_result
                    rule_results[idx]['classifier'] = f"混合-{ai_result['classifier']}"
        
        return rule_results