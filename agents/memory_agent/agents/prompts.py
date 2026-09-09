def build_memory_prompt(
    session_mem_str: str,
    lt_mem_str: str,
) -> str:
    return (
        "You are an educational Memory Agent. Aggregate the following information into a structured summary of what the student knows and what they struggled with:\n\n"
        f"SESSION CONVERSATION LOGS:\n{session_mem_str}\n\n"
        f"LONG-TERM CONCEPT MASTERIES:\n{lt_mem_str}\n\n"
        "Return a JSON object conforming strictly to this format:\n"
        "{\n"
        '  "working_memory": "Immediate concepts being asked: (e.g. Gravity, Newton Laws)",\n'
        '  "session_memory": "Key points of the current session so far",\n'
        '  "long_term_memory": "Summary of student strength areas, weak topics, and recurring mistakes",\n'
        '  "curriculum_memory": "Curriculum-level recommendations based on NCERT goals"\n'
        "}"
    )
