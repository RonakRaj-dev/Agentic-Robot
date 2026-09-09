import uuid


def build_quiz_prompt(
    class_prompt: str,
    db_context: str,
    card_count: int,
    grade: int | None,
    topic: str,
    subject: str,
    prev_q_str: str,
) -> str:
    return (
        f"{class_prompt}\n\n"
        f"BACKGROUND TEXTBOOK CONTENT FROM NCERT MONGODB:\n{db_context}\n\n"
        f"ROLE & DIRECTIVE: You are an expert Class {grade or '7'} {subject} school teacher who just finished teaching the topic '{topic}'. "
        f"You are conducting a direct pop-quiz for your students in class.\n\n"
        f"TASK: Generate EXACTLY {card_count} brand new, unique, high-quality multiple choice questions based STRICTLY on the textbook content of '{topic}'.\n\n"
        f"STRICT QUESTION FORMATTING RULES:\n"
        f"1. PURE SUBJECT QUESTIONS ONLY: Ask direct questions testing actual mathematical calculations, geometric properties, scientific definitions, chemical/physical processes, or factual textbook concepts (e.g., 'What is the complement of an angle measuring 35°?' or 'Which organelle is known as the powerhouse of the cell?').\n"
        f"2. NO META-PEDAGOGICAL FLUFF: NEVER ask meta-questions about 'learning objectives', 'why practical examples are used', 'first steps', 'textbook guidelines', or 'how students should study'.\n"
        f"3. NO ARTIFICIAL PREFIXES OR CHAPTER CONTEXT: NEVER start questions with 'In Chapter 5...', 'According to the textbook...', 'As a student of Class 7...', or 'Disclaimer:...'. Start directly with the core question string.\n"
        f"4. REAL CLASSROOM DISTRACTORS: All 4 options (A, B, C, D) must be plausible, realistic subject answers (e.g. common miscalculations, complementary vs supplementary confusion, opposite terms). NEVER include joke choices like 'Guess an answer randomly', 'Skip to the next chapter', 'They have no purpose', or 'None of the above'.\n"
        f"5. EXP: Provide a 1-2 sentence clear step-by-step mathematical or scientific explanation for why the correct option is right.\n\n"
        f"{prev_q_str}\n"
        "You MUST return ONLY a JSON object matching this schema:\n"
        "{\n"
        '  "card_type": "flag_quiz_card_set",\n'
        f'  "topic": "{topic}",\n'
        f'  "subject": "{subject}",\n'
        f'  "class_level": {grade if grade else "null"},\n'
        '  "cards": [\n'
        '    {\n'
        '      "card_type": "flag_quiz_card",\n'
        f'      "question_id": "quiz_{uuid.uuid4().hex[:8]}",\n'
        '      "question": "direct, pure classroom subject question",\n'
        '      "options": [\n'
        '        {"key": "A", "text": "plausible option A"},\n'
        '        {"key": "B", "text": "plausible option B"},\n'
        '        {"key": "C", "text": "plausible option C"},\n'
        '        {"key": "D", "text": "plausible option D"}\n'
        '      ],\n'
        '      "correct_option": "A/B/C/D",\n'
        '      "explanation": "clear 1-2 sentence math/science explanation",\n'
        '      "difficulty": "Easy/Medium/Hard",\n'
        f'      "class_level": {grade if grade else "null"},\n'
        f'      "subject": "{subject}"\n'
        '    }\n'
        '  ]\n'
        '}'
    )
