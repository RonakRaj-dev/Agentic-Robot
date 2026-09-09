import os
import json
import threading
from typing import Any, Dict
from loguru import logger

class AgentStateManager:
    """
    Manages metadata, dynamic prompts, and model configuration parameters for individual agents.
    Caches configurations loaded from JSON files under prompts/.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(AgentStateManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, prompts_dir: str = "prompts") -> None:
        if self._initialized:
            return
        self.prompts_dir = prompts_dir
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._initialized = True

    AGENT_DIR_MAP = {
        "planneragent": "planning",
        "planner": "planning",
        "planning": "planning",
        "retrievalplanneragent": "retrievalplanner",
        "retrievalplanner": "retrievalplanner",
        "adaptivelearningagent": "adaptive_learning",
        "adaptivelearning": "adaptive_learning",
        "adaptive_learning": "adaptive_learning",
        "contentgenerationagent": "content_generation",
        "contentgeneration": "content_generation",
        "content_generation": "content_generation",
        "classroominteractionagent": "interaction",
        "classroominteraction": "interaction",
        "interactionagent": "interaction",
        "interaction": "interaction",
        "curriculumragagent": "curriculumrag",
        "curriculumrag": "curriculumrag",
        "ragagent": "curriculumrag",
        "factverificationagent": "factverification",
        "factverification": "factverification",
        "verificationagent": "factverification",
        "validationagent": "validation",
        "validation": "validation",
        "safetyagent": "safety",
        "safety": "safety",
        "teachingagent": "teaching",
        "teaching": "teaching",
        "responseagent": "response",
        "response": "response",
        "quizagent": "quiz",
        "quiz": "quiz",
        "videoagent": "video",
        "video": "video",
        "memoryagent": "memory",
        "memory": "memory",
        "assessmentagent": "assessment",
        "assessment": "assessment",
        "summaryagent": "summary",
        "summary": "summary",
        "analyticsagent": "analytics",
        "analytics": "analytics"
    }

    def load_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """Loads and returns the configuration file for the specified agent."""
        agent_key = agent_name.lower().strip()
        agent_dir_name = self.AGENT_DIR_MAP.get(agent_key, agent_key.replace("agent", ""))
        config_path = os.path.join(self.prompts_dir, agent_dir_name, "config.json")

        with self._lock:
            if agent_name in self._configs:
                return self._configs[agent_name]

            if not os.path.exists(config_path):
                logger.warning(f"Configuration file not found for agent '{agent_name}' at path: {config_path}. Using default configuration.")
                default_config = {
                    "prompt_template": f"You are a helpful education assistant ({agent_name}). Input: {{query}}",
                    "model_config": {
                        "temperature": 0.2,
                        "max_tokens": 500
                    }
                }
                self._configs[agent_name] = default_config
                return default_config

            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self._configs[agent_name] = config
                    logger.info(f"Loaded config for agent '{agent_name}' successfully.")
                    return config
            except Exception as e:
                logger.error(f"Error loading configuration for agent '{agent_name}': {e}")
                raise

    def get_system_prompt(self, agent_name: str, **kwargs: Any) -> str:
        """Retrieves and formats the system prompt template for the agent."""
        config = self.load_agent_config(agent_name)
        template = config.get("prompt_template", "")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Template formatting key error for agent '{agent_name}': {e}. Returning raw template.")
            return template

    def get_model_config(self, agent_name: str) -> Dict[str, Any]:
        """Retrieves model-specific hyper-parameters (temperature, max_tokens, etc.) for the agent."""
        config = self.load_agent_config(agent_name)
        return config.get("model_config", {})

    def get_class_subject_prompt(self, class_no: Any, subject: str) -> str:
        """
        Retrieves the class and subject system prompt from prompts/class_subject/Class_<N>/<Subject>.md.
        Falls back to a default structured prompt if specific file is missing.
        """
        if not class_no:
            class_str = "General"
        else:
            import re
            match = re.search(r'\d+', str(class_no))
            class_str = f"Class_{match.group(0)}" if match else f"Class_{class_no}"

        # Normalize subject filename (e.g. social_studies -> Social_Studies)
        norm_subj = subject.strip().replace(" ", "_").title() if subject else "General"
        
        md_path = os.path.join(self.prompts_dir, "class_subject", class_str, f"{norm_subj}.md")
        if not os.path.exists(md_path):
            # Try matching case-insensitively in directory if exists
            class_dir = os.path.join(self.prompts_dir, "class_subject", class_str)
            if os.path.exists(class_dir):
                for filename in os.listdir(class_dir):
                    if filename.lower() == f"{norm_subj.lower()}.md":
                        md_path = os.path.join(class_dir, filename)
                        break

        if os.path.exists(md_path):
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    logger.info(f"Loaded class/subject prompt from: {md_path}")
                    return content
            except Exception as e:
                logger.error(f"Error reading markdown prompt file '{md_path}': {e}")

        logger.info(f"Class/subject prompt file not found at '{md_path}'. Using dynamic fallback.")
        return f"System Prompt for {class_str} - {subject}:\nProvide clear, engaging, and grade-appropriate instruction tailored for {class_str} students in {subject}."

