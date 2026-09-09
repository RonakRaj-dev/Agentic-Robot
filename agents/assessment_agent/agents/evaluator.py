from models.schemas import AssessmentResponse

from .prompts import evaluation_prompt


class AssessmentEvaluator:

    def __init__(
        self,
        gateway,
        state_manager,
        assessment_repo,
    ):
        self.gateway = gateway
        self.state_manager = state_manager
        self.assessment_repo = assessment_repo

    async def evaluate(
        self,
        topic: str,
        questions: list,
        answers: dict,
    ) -> AssessmentResponse:

        prompt = evaluation_prompt(
            topic=topic,
            questions=questions,
            answers=answers,
        )

        response = await self._call_llm(prompt)

        return response

    async def _call_llm(
        self,
        prompt: str,
    ) -> AssessmentResponse:

        config = dict(
            self.state_manager.get_model_config(
                "AssessmentAgent"
            )
        )

        config["response_format"] = {
            "type": "json_object"
        }

        raw = await self.gateway.generate(
            prompt,
            **config,
        )

        return AssessmentResponse(
            **self._parse_json(raw)
        )

    @staticmethod
    def _parse_json(raw: str):

        import json

        raw = raw.strip()

        if raw.startswith("```json"):
            raw = raw[7:]

        elif raw.startswith("```"):
            raw = raw[3:]

        if raw.endswith("```"):
            raw = raw[:-3]

        return json.loads(raw.strip())

    async def persist(
        self,
        session_id: str,
        student_id: str,
        topic: str,
        questions: list,
        response: AssessmentResponse,
    ):

        await self.assessment_repo.log_assessment(
            session_id=session_id,
            student_id=student_id,
            topic=topic,
            questions=[
                q.model_dump()
                for q in response.questions
            ],
            score=response.score or 0.0,
            max_score=float(len(questions or [1])),
            weak_topics=response.weak_topics or [],
            revision_plan=response.revision_plan or "",
        )