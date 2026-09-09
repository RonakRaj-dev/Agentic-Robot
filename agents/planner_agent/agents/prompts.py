from typing import Any


def build_planner_prompt(
    query: str,
    grade: Any,
    subject: str,
    intent: str,
) -> str:
    return (
        "You are an educational Planner Agent. Analyze the student's message and metadata to formulate a teaching plan:\n\n"
        f"Student Message: '{query}'\n"
        f"Grade Level: Class {grade}\n"
        f"Subject: {subject}\n"
        f"Explicit Intent Parameter: '{intent}'\n\n"
        "Determine the following:\n"
        "1. If the student explicitly wants a quiz, flag game, test, or MCQ, set need_quiz=true.\n"
        "2. If the query asks for a story or visual, set need_story=true and/or need_diagram=true.\n"
        "3. If the query asks for a video, set need_video=true.\n"
        "4. If the query asks for homework or handouts, set need_homework=true.\n"
        "5. If the session is wrapping up or they ask to summarize, set need_summary=true.\n"
        "6. Identify the list of agent names to execute in 'execution_plan'. Valid agent names are: TeachingAgent, RAGAgent, QuizAgent, VideoAgent, ContentGenerationAgent, AssessmentAgent, ClassroomInteractionAgent, SummaryAgent, AnalyticsAgent.\n\n"
        "Return a JSON object conforming strictly to the PlannerResponse schema:\n"
        "{\n"
        '  "need_quiz": false,\n'
        '  "need_story": false,\n'
        '  "need_diagram": false,\n'
        '  "need_video": false,\n'
        '  "need_homework": false,\n'
        '  "need_summary": false,\n'
        '  "need_revision": false,\n'
        '  "need_formula_sheet": false,\n'
        '  "need_example": false,\n'
        '  "teaching_strategy": "Explain topic X using visual/analogy style and run follow-up quiz",\n'
        '  "execution_plan": ["TeachingAgent", "AssessmentAgent"]\n'
        '}'
    )
