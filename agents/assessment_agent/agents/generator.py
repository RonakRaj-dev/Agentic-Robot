import uuid

from models.schemas import AssessmentResponse

from .prompts import generation_prompt


class AssessmentGenerator:

    def __init__(
        self,
        gateway,
        state_manager,
        curriculum_repo,
    ):
        self.gateway = gateway
        self.state_manager = state_manager
        self.curriculum_repo = curriculum_repo

    async def generate(
        self,
        topic: str,
        grade: int,
        subject: str,
    ) -> AssessmentResponse:

        curriculum = await self.curriculum_repo.get_context(
            topic=topic,
            grade=grade,
            subject=subject,
        )

        ids = self._generate_ids()

        prompt = generation_prompt(
            topic=topic,
            grade=grade,
            subject=subject,
            curriculum=curriculum,
            question_ids=ids,
        )

        return await self._call_llm(prompt)

    async def _call_llm(self, prompt: str) -> AssessmentResponse:

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
    def _generate_ids():

        return {
            key: f"assess_{uuid.uuid4().hex[:6]}"
            for key in (
                "mcq",
                "subjective",
                "hots",
                "case",
            )
        }

    @staticmethod
    def _parse_json(raw: str):

        raw = raw.strip()

        if raw.startswith("```json"):
            raw = raw[7:]

        elif raw.startswith("```"):
            raw = raw[3:]

        if raw.endswith("```"):
            raw = raw[:-3]

        import json

        return json.loads(raw.strip())