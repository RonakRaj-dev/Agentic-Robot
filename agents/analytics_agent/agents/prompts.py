import json
from typing import Any, Dict, List


def build_analytics_prompt(
    query: str,
    student_id: str,
    grade: Any,
    subject: str,
    records: List[Dict[str, Any]],
    statistics: Dict[str, Any],
) -> str:
    records_str = format_records(records)

    return (
        "You are an educational Analytics Agent.\n"
        "Analyze the student's learning history and current request "
        "to produce a reliable educational analytics report.\n\n"
        "CURRENT REQUEST:\n"
        f"{query}\n\n"
        "STUDENT INFORMATION:\n"
        f"Student ID: {student_id}\n"
        f"Grade: {grade}\n"
        f"Subject: {subject}\n\n"
        "CALCULATED STATISTICS:\n"
        f"Questions Asked: {statistics['questions_asked']}\n"
        f"Weak Topics: {json.dumps(statistics['weak_topics'])}\n"
        f"Topic Statistics: {json.dumps(statistics['topic_statistics'])}\n\n"
        "LEARNING HISTORY:\n"
        f"{records_str}\n\n"
        "TASK:\n"
        "Use the provided learning history and calculated statistics to synthesize educational insights.\n\n"
        "IMPORTANT:\n"
        "- Do not invent student performance data.\n"
        "- Base conceptual gaps on the provided records.\n"
        "- Keep recommendations actionable.\n"
        "- Return ONLY valid JSON.\n\n"
        "OUTPUT SCHEMA:\n"
        "{\n"
        f'  "subject": "{subject}",\n'
        f'  "grade": {grade},\n'
        f'  "questions_asked": {statistics["questions_asked"]},\n'
        '  "average_difficulty": "Easy | Medium | Hard",\n'
        f'  "weak_topics": {json.dumps(statistics["weak_topics"])},\n'
        f'  "topic_statistics": {json.dumps(statistics["topic_statistics"])},\n'
        '  "student_analytics": {\n'
        '    "learning_trend": "Improving | Stable | Struggling",\n'
        '    "conceptual_gaps": "Brief overview of what the student is missing",\n'
        '    "recommended_next_steps": "Actionable feedback"\n'
        '  }\n'
        '}'
    )


def format_records(records: List[Dict[str, Any]]) -> str:
    if not records:
        return "No learning history available."

    formatted_records = []
    for record in records:
        formatted_records.append(
            f"Topic: {record.get('topic', 'Unknown')}, "
            f"Mastery: {record.get('mastery_score', 'Unknown')}, "
            f"Questions Asked: {record.get('questions_asked', 0)}, "
            f"Mistakes: {record.get('mistakes_logged', [])}"
        )
    return "\n".join(formatted_records)
