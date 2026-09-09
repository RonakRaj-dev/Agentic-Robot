from typing import Any


def build_summary_prompt(
    query: str,
    grade: Any,
    subject: str,
) -> str:
    return (
        "You are an educational Summary Agent. Based on the topics taught in the current session, generate a comprehensive review summary:\n\n"
        f"Taught Content / Interaction History Summary: '{query}'\n"
        f"Grade Level: Class {grade}\n"
        f"Subject: {subject}\n\n"
        "Return a JSON object conforming strictly to the EndOfClassSummaryResponse schema:\n"
        "{\n"
        '  "topics_covered": ["subtopic_A", "subtopic_B"],\n'
        '  "key_concepts": ["Concept overview 1", "Concept overview 2"],\n'
        '  "formula_revision": ["Formula 1: description = equation", "Formula 2"],\n'
        '  "interesting_fact": "An engaging hook fact related to the topic",\n'
        '  "quote_of_day": "A motivational educational quote",\n'
        '  "homework": ["Problem/exercise 1", "Problem/exercise 2"],\n'
        '  "next_topic": "Recommended next concept to study"\n'
        '}'
    )
