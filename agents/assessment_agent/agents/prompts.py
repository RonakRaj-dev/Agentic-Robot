import json


def generation_prompt(
    topic: str,
    grade: int,
    subject: str,
    curriculum: str,
    question_ids: dict,
) -> str:

    return f"""
You are an educational Assessment Generation Agent.

Generate exactly 4 brand-new assessment questions based strictly
on the provided curriculum context.

CURRICULUM:
{curriculum}

TOPIC:
{topic}

GRADE:
Class {grade}

SUBJECT:
{subject}

GENERATE:
1. One MCQ
2. One Subjective question
3. One HOTS question
4. One Case-based question

REQUIREMENTS:
- Match the grade level.
- Stay relevant to the topic.
- Do not duplicate questions.
- Return ONLY valid JSON.

QUESTION IDS:
MCQ: {question_ids["mcq"]}
Subjective: {question_ids["subjective"]}
HOTS: {question_ids["hots"]}
Case: {question_ids["case"]}

OUTPUT:
{{
  "questions": [
    {{
      "question_id": "id",
      "type": "mcq",
      "question_text": "Question",
      "options": [
        {{"key": "A", "text": "Option A"}},
        {{"key": "B", "text": "Option B"}},
        {{"key": "C", "text": "Option C"}},
        {{"key": "D", "text": "Option D"}}
      ],
      "correct_answer": "A",
      "explanation": "Explanation",
      "difficulty": "Easy"
    }}
  ]
}}
"""


def evaluation_prompt(
    topic: str,
    questions: list,
    answers: dict,
) -> str:

    return f"""
You are an educational Assessment Evaluation Agent.

Evaluate the student's answers against the original questions.

TOPIC:
{topic}

ORIGINAL QUESTIONS:
{json.dumps(questions, indent=2)}

STUDENT ANSWERS:
{json.dumps(answers, indent=2)}

REQUIREMENTS:
- Evaluate every response.
- Evaluate MCQs for correctness.
- Evaluate subjective answers for understanding.
- Evaluate HOTS answers for reasoning.
- Evaluate case answers for analysis.
- Calculate the score.
- Identify weak topics.
- Suggest remedial reading.
- Create a revision plan.
- Return ONLY valid JSON.

SCORING:
Use 1 point per question.

OUTPUT:
{{
  "questions": [],
  "score": 0,
  "weak_topics": [],
  "suggested_reading": [],
  "revision_plan": ""
}}
"""