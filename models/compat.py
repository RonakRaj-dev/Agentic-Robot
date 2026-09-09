import os
os.environ["USE_TF"] = "0"
os.environ["TRANSFORMERS_NO_TF"] = "1"

import sys
import asyncio
from typing import Any, Optional, Union, List

try:
    from agentscope.models import OpenAIChatWrapper as ModelBase
except (ImportError, ModuleNotFoundError):
    try:
        from agentscope.model import OpenAIChatModel as ModelBase
    except (ImportError, ModuleNotFoundError):
        ModelBase = object

from agentscope.message import Msg
try:
    from agentscope.agents import AgentBase
except (ImportError, ModuleNotFoundError):
    try:
        from agentscope.agent import AgentBase
    except (ImportError, ModuleNotFoundError):
        from agentscope.agent import Agent as AgentBase

# 1. Monkeypatch Msg.__init__ to support string content and default role/metadata
original_msg_init = Msg.__init__

def patched_msg_init(self, *args: Any, **kwargs: Any) -> None:
    from agentscope.message import TextBlock
    url_val = kwargs.pop("url", None)
    args_list = list(args)

    if "content" in kwargs and isinstance(kwargs["content"], str):
        kwargs["content"] = [TextBlock(text=kwargs["content"])]
    elif len(args_list) >= 2 and isinstance(args_list[1], str):
        args_list[1] = [TextBlock(text=args_list[1])]

    if "metadata" in kwargs and (kwargs["metadata"] is None or isinstance(kwargs["metadata"], str)):
        if isinstance(kwargs["metadata"], str):
            kwargs["metadata"] = {"raw": kwargs["metadata"]}
        else:
            kwargs["metadata"] = {}
    elif "metadata" not in kwargs:
        kwargs["metadata"] = {}

    if "role" not in kwargs and len(args_list) < 3:
        kwargs["role"] = "user"

    original_msg_init(self, *args_list, **kwargs)
    if url_val:
        setattr(self, "url", url_val)

Msg.__init__ = patched_msg_init


def patched_agent_new(cls: Any, *args: Any, **kwargs: Any) -> Any:
    return object.__new__(cls)

def patched_agent_init(self, *args: Any, **kwargs: Any) -> None:
    try:
        from agentscope.module._state_module import StateModule
        if isinstance(self, StateModule) and not hasattr(self, "_module_dict"):
            StateModule.__init__(self)
    except Exception:
        pass

    for hook_name in ["reply", "observe", "print"]:
        for prefix in ["_instance_pre_", "_instance_post_", "_class_pre_", "_class_post_"]:
            attr = f"{prefix}{hook_name}_hooks"
            if not hasattr(self, attr) or not isinstance(getattr(self, attr), dict):
                setattr(self, attr, {})
            if not hasattr(self.__class__, attr) or not isinstance(getattr(self.__class__, attr), dict):
                setattr(self.__class__, attr, {})

    name_val = kwargs.pop("name", None)
    if name_val:
        self.name = name_val
    elif not hasattr(self, "name"):
        self.name = "Agent"
    sys_p = kwargs.pop("system_prompt", None) or kwargs.pop("sys_prompt", None)
    if sys_p:
        self.sys_prompt = sys_p
    m_val = kwargs.pop("model", None) or kwargs.pop("model_config_name", None) or kwargs.pop("model_config", None)
    if m_val:
        self.model = m_val

AgentBase.__new__ = patched_agent_new
AgentBase.__init__ = patched_agent_init

try:
    import agentscope.agent._agent
    agentscope.agent._agent.Agent.__new__ = patched_agent_new
    agentscope.agent._agent.Agent.__init__ = patched_agent_init
except (ImportError, AttributeError):
    pass

try:
    from agentscope.agent import Agent
    Agent.__new__ = patched_agent_new
    Agent.__init__ = patched_agent_init
except (ImportError, AttributeError):
    pass



# 3. Compatibility Classes
try:
    from agentscope.model import OpenAIChatModel as NativeOpenAIModel
    Parameters = NativeOpenAIModel.Parameters
except Exception:
    class Parameters:
        def __init__(self, temperature: Optional[float] = None, max_tokens: Optional[int] = None, top_p: Optional[float] = None, **kwargs: Any) -> None:
            self.temperature = temperature
            self.max_tokens = max_tokens
            self.top_p = top_p
            self.extra_args = kwargs

from openai import AsyncOpenAI

class OpenAIChatModel(ModelBase):
    Parameters = Parameters

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        parameters: Optional[Parameters] = None,
        max_retries: int = 0,
        **kwargs: Any
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url or "https://api.groq.com/openai/v1"
        self.model = model
        self.parameters = parameters
        self.max_retries = max_retries
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def __call__(self, messages: list, **kwargs: Any) -> Any:
        from models.schemas import get_content_str
        formatted_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                formatted_messages.append(msg)
            elif hasattr(msg, "role"):
                formatted_messages.append({"role": getattr(msg, "role", "user"), "content": get_content_str(msg)})
            else:
                formatted_messages.append({"role": "user", "content": str(msg)})

        temperature = kwargs.get("temperature")
        if temperature is None and self.parameters:
            temperature = getattr(self.parameters, "temperature", None)

        max_tokens = kwargs.get("max_tokens")
        if max_tokens is None and self.parameters:
            max_tokens = getattr(self.parameters, "max_tokens", None)

        call_kwargs = {
            "model": self.model,
            "messages": formatted_messages
        }
        if temperature is not None:
            call_kwargs["temperature"] = temperature
        if max_tokens is not None:
            call_kwargs["max_tokens"] = max_tokens

        if "response_format" in kwargs and kwargs["response_format"]:
            call_kwargs["response_format"] = kwargs["response_format"]
            # Groq API requires the word 'json' in messages when response_format is json_object
            all_text = " ".join([m.get("content", "") for m in formatted_messages]).lower()
            if "json" not in all_text and formatted_messages:
                formatted_messages[-1]["content"] += "\n\nRespond strictly in valid JSON format."

        try:
            response = await self.client.chat.completions.create(**call_kwargs)
        except Exception as err:
            if "response_format" in call_kwargs and "json" in str(err).lower():
                call_kwargs.pop("response_format", None)
                response = await self.client.chat.completions.create(**call_kwargs)
            else:
                raise err

        content_text = response.choices[0].message.content or ""
        return type("ResponseCompat", (), {"text": content_text, "content": content_text})()

class UserMsg(Msg):
    def __init__(self, name: str, content: Any, url: Optional[Union[str, List[str]]] = None, metadata: Optional[Union[dict, str]] = None, **kwargs: Any) -> None:
        if isinstance(content, str):
            from agentscope.message import TextBlock
            content = [TextBlock(text=content)]
        if metadata is None or isinstance(metadata, str):
            metadata = {"raw": metadata} if isinstance(metadata, str) else {}
        super().__init__(name=name, content=content, role="user", url=url, metadata=metadata, **kwargs)

class AssistantMsg(Msg):
    def __init__(self, name: str, content: Any, url: Optional[Union[str, List[str]]] = None, metadata: Optional[Union[dict, str]] = None, **kwargs: Any) -> None:
        if isinstance(content, str):
            from agentscope.message import TextBlock
            content = [TextBlock(text=content)]
        if metadata is None or isinstance(metadata, str):
            metadata = {"raw": metadata} if isinstance(metadata, str) else {}
        super().__init__(name=name, content=content, role="assistant", url=url, metadata=metadata, **kwargs)

try:
    from agentscope.message import TextBlock
except (ImportError, ModuleNotFoundError):
    class TextBlock:
        def __init__(self, text: str) -> None:
            self.text = text
            self.type = "text"

# Monkeypatching agentscope modules to prevent import errors in other files
try:
    import agentscope.models
    agentscope.models.OpenAIChatModel = OpenAIChatModel
except (ImportError, ModuleNotFoundError):
    try:
        import agentscope.model as models_mod
        setattr(models_mod, "OpenAIChatModel", OpenAIChatModel)
        sys.modules["agentscope.models"] = models_mod
        setattr(agentscope, "models", models_mod)
    except Exception:
        pass

import agentscope.message
agentscope.message.UserMsg = UserMsg
agentscope.message.AssistantMsg = AssistantMsg
agentscope.message.TextBlock = TextBlock

try:
    import agentscope.agents
    if not hasattr(agentscope.agents, "Agent"):
        setattr(agentscope.agents, "Agent", getattr(agentscope.agents, "AgentBase", object))
except (ImportError, ModuleNotFoundError):
    try:
        import agentscope.agent as agents_mod
        setattr(agents_mod, "Agent", getattr(agents_mod, "AgentBase", object))
        sys.modules["agentscope.agents"] = agents_mod
        setattr(agentscope, "agents", agents_mod)
    except Exception:
        pass

