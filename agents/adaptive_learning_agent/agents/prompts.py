ADAPTIVE_LEARNING_PROMPT_TEMPLATE = """{system_prompt}

STUDENT HISTORICAL PERFORMANCE:
{history}

CURRENT CONTEXT:
Grade: {grade}
Subject: {subject}
Student Message: {query}

TASK:
Analyze the student's current query and historical performance to determine the appropriate learning strategy.

OUTPUT REQUIREMENTS:
Return ONLY a valid JSON object matching this schema:
{{
  "difficulty_level": "Beginner | Intermediate | Advanced",
  "teaching_style": "Visual | Conceptual | Analogy-based | Active Learning",
  "recommended_learning_path": ["subtopic_1", "subtopic_2", "subtopic_3"]
}}"""
