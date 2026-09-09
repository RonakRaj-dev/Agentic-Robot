from typing import Any, Dict


class AgentStateManager:

    def __init__(self):
        self._model_configs = {
            "AssessmentAgent": {
                # Keep your existing model configuration here.
            }
        }

        self._system_prompts = {
            "AssessmentAgent": (
                "You are an educational "
                "Assessment Agent."
            )
        }

    def get_model_config(
        self,
        agent_name: str,
    ) -> Dict[str, Any]:

        return dict(
            self._model_configs.get(
                agent_name,
                {},
            )
        )

    def get_system_prompt(
        self,
        agent_name: str,
        query: str = "",
    ) -> str:

        return self._system_prompts.get(
            agent_name,
            "",
        )