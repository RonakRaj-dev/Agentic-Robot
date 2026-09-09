from typing import List
from loguru import logger

class ContradictionChecker:
    """Detects direct contradictions between the LLM-generated explanation and source texts."""
    def __init__(self) -> None:
        pass

    def check_contradictions(self, explanation: str, sources: List[str]) -> bool:
        if not explanation or not sources:
            return False

        negatives = {"not", "never", "no", "cannot", "doesn't", "don't", "isn't", "aren't", "neither", "nor"}
        
        # Split explanation into individual sentences
        import re
        explanation_sentences = [s.strip().lower() for s in re.split(r'[.!?]+', explanation) if s.strip()]
        
        for source in sources:
            source_lower = source.lower()
            source_sentences = [s.strip() for s in re.split(r'[.!?]+', source_lower) if s.strip()]
            
            for s_sent in source_sentences:
                s_words = set(re.findall(r'\b[a-z]{4,}\b', s_sent))
                if len(s_words) < 4:
                    continue
                
                s_has_neg = bool(set(s_sent.split()).intersection(negatives))
                
                for e_sent in explanation_sentences:
                    e_words = set(re.findall(r'\b[a-z]{4,}\b', e_sent))
                    overlap = s_words.intersection(e_words)
                    
                    # High semantic word overlap on a specific sentence (>75% matching key terms)
                    if len(overlap) >= 4 and len(overlap) / len(s_words) >= 0.75:
                        e_has_neg = bool(set(e_sent.split()).intersection(negatives))
                        if s_has_neg != e_has_neg:
                            logger.warning(f"Potential contradiction detected between source clause '{s_sent[:50]}' and explanation '{e_sent[:50]}'")
                            return True
                            
        return False
