import asyncio
import time
from typing import Any, Dict, List, Tuple
from loguru import logger
from agentscope.message import Msg
from models.schemas import AgentResult


class ConcurrentExecutor:
    """
    ConcurrentExecutor: Handles Fan-Out / Fan-In parallel agent execution.
    Executes multiple agent calls asynchronously via asyncio.gather with 
    timeout protection, exception isolation, and timing telemetry.
    """

    def __init__(self, default_timeout_seconds: float = 20.0) -> None:
        self.default_timeout = default_timeout_seconds

    async def execute_parallel(
        self,
        tasks_map: Dict[str, Any],
        timeout_seconds: float = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Executes a dict of {branch_name: coroutine} concurrently.
        
        Returns a dict of {branch_name: {"success": bool, "data": Any, "error": str, "execution_time": float}}.
        """
        timeout = timeout_seconds or self.default_timeout
        start_time = time.perf_counter()
        
        branch_names = list(tasks_map.keys())
        coroutines = list(tasks_map.values())
        
        logger.info(f"ConcurrentExecutor: Fanning out {len(branch_names)} parallel tasks ({branch_names})")
        
        results: Dict[str, Dict[str, Any]] = {}

        try:
            raw_results = await asyncio.wait_for(
                asyncio.gather(*coroutines, return_exceptions=True),
                timeout=timeout,
            )

            for name, res in zip(branch_names, raw_results):
                if isinstance(res, Exception):
                    logger.error(f"ConcurrentExecutor: Branch '{name}' raised exception: {res}")
                    results[name] = {
                        "success": False,
                        "data": None,
                        "error": str(res),
                        "execution_time": time.perf_counter() - start_time,
                    }
                else:
                    res_data = {}
                    if hasattr(res, "metadata") and isinstance(res.metadata, dict):
                        agent_res = res.metadata.get("agent_result", {})
                        if isinstance(agent_res, dict):
                            res_data = agent_res
                        else:
                            res_data = {"success": True, "data": res.content}
                    elif isinstance(res, dict):
                        res_data = res
                    else:
                        res_data = {"success": True, "data": getattr(res, "content", str(res))}

                    results[name] = {
                        "success": res_data.get("success", True),
                        "data": res_data.get("data"),
                        "error": res_data.get("error"),
                        "execution_time": res_data.get("execution_time", time.perf_counter() - start_time),
                    }

        except asyncio.TimeoutError:
            logger.warning(f"ConcurrentExecutor: Parallel tasks timed out after {timeout}s")
            for name in branch_names:
                if name not in results:
                    results[name] = {
                        "success": False,
                        "data": None,
                        "error": f"Concurrent task timed out after {timeout} seconds",
                        "execution_time": timeout,
                    }

        total_time = time.perf_counter() - start_time
        logger.info(f"ConcurrentExecutor: Fan-in complete for {len(branch_names)} tasks in {total_time:.3f}s")
        return results
