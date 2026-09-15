import pytest
import asyncio
import re
from unittest.mock import AsyncMock, patch
from agents.quiz_agent.agents.agent import QuizAgent

@pytest.mark.asyncio
async def test_eval_quiz_agent_quality_and_prefix_sanitization():
    """Evaluates QuizAgent for schema validity, distractor quality, and strict absence of artificial prefixes."""
    quiz_agent = QuizAgent(name="EvalQuizAgent")
    
    mock_llm_json = '''{
        "card_type": "flag_quiz_card_set",
        "topic": "Laws of Motion",
        "subject": "Physics",
        "class_level": 9,
        "cards": [
            {
                "card_type": "flag_quiz_card",
                "question_id": "quiz_001",
                "question": "In Chapter 3 of Class 9 Physics, what is Newton's First Law of Motion also known as?",
                "options": [
                    {"key": "A", "text": "Law of Inertia"},
                    {"key": "B", "text": "Law of Acceleration"},
                    {"key": "C", "text": "Law of Action-Reaction"},
                    {"key": "D", "text": "Law of Gravitation"}
                ],
                "correct_option": "A",
                "explanation": "Newton's First Law states that an object remains at rest or in uniform motion unless acted upon by a net force.",
                "difficulty": "Easy",
                "class_level": 9,
                "subject": "Physics"
            },
            {
                "card_type": "flag_quiz_card",
                "question_id": "quiz_002",
                "question": "What property of an object determines its inertia?",
                "options": [
                    {"key": "A", "text": "Mass"},
                    {"key": "B", "text": "Velocity"},
                    {"key": "C", "text": "Volume"},
                    {"key": "D", "text": "Shape"}
                ],
                "correct_option": "A",
                "explanation": "Greater mass results in greater inertia.",
                "difficulty": "Medium",
                "class_level": 9,
                "subject": "Physics"
            }
        ]
    }'''
    
    with patch.object(quiz_agent.gateway, "generate", new=AsyncMock(return_value=mock_llm_json)), \
         patch.object(quiz_agent, "_fetch_mongodb_context", new=AsyncMock(return_value="Laws of motion context")):
        
        msg = await quiz_agent.reply({
            "content": "Generate a quiz on laws of motion",
            "metadata": {"grade": 9, "subject": "Physics"}
        })
        
        agent_result = msg.metadata.get("agent_result", {})
        assert agent_result.get("success") is True, "QuizAgent execution failed"
        
        data = agent_result.get("data", {})
        cards = data.get("cards", [])
        assert len(cards) == 2, f"Expected 2 quiz cards, got {len(cards)}"
        
        # Verify prefix sanitization
        q1_text = cards[0].get("question", "")
        forbidden_prefixes = ["In Chapter", "According to", "Based on Class", "Disclaimer:"]
        for prefix in forbidden_prefixes:
            assert not q1_text.startswith(prefix), f"Question text contains artificial prefix '{prefix}': {q1_text}"
            
        assert q1_text.startswith("What is Newton's First Law"), f"Sanitization failed to clean question correctly: {q1_text}"
        
        # Verify option keys and distractors
        for card in cards:
            keys = [opt["key"] for opt in card.get("options", [])]
            assert keys == ["A", "B", "C", "D"], f"Option keys must be A, B, C, D; got {keys}"
            assert card.get("correct_option") in keys, f"Correct option {card.get('correct_option')} not in keys"
