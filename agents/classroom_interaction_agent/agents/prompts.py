def build_interaction_prompt(
    game_mode: str,
    current_score: int,
    query: str,
    student_id: str,
) -> str:
    return (
        "You are an engaging Classroom Interaction Agent. You manage gamified learning experiences.\n"
        f"GAME MODE: {game_mode}\n"
        f"CURRENT SCORE: {current_score}\n"
        f"STUDENT QUERY / RESPONSE: '{query}'\n\n"
        "Formulate a response. If the student answers correctly, increment the score. Otherwise, keep it same and suggest hints.\n"
        "Return a JSON object conforming strictly to the InteractiveClassroomResponse schema:\n"
        "{\n"
        f'  "game_mode": "{game_mode}",\n'
        '  "timer_seconds": 20,\n'
        f'  "score": {current_score},\n'
        '  "leaderboard": [\n'
        f'     {{"name": "{student_id}", "score": {current_score}}},\n'
        '     {"name": "Bot_Assistant", "score": 2}\n'
        '  ],\n'
        '  "hints": ["Try to recall primary factors", "Hint 2"],\n'
        '  "game_payload": {\n'
        '     "question": "Next educational riddle/challenge here",\n'
        '     "previous_was_correct": true,\n'
        '     "points_earned": 1\n'
        '  }\n'
        '}'
    )
