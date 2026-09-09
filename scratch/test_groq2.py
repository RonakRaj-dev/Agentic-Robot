import os
import asyncio
import time
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
api_key = os.environ.get("GROQ_API_KEY")
base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

client = AsyncOpenAI(api_key=api_key, base_url=base_url)

async def test_model(model_name):
    start = time.time()
    try:
        res = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a JSON assistant."},
                {"role": "user", "content": "Return a JSON object with key 'answer' and a 5-word sentence."}
            ],
            response_format={"type": "json_object"},
            max_tokens=100
        )
        duration = time.time() - start
        print(f"[{model_name}] SUCCESS in {duration:.3f}s -> {res.choices[0].message.content}")
    except Exception as e:
        duration = time.time() - start
        print(f"[{model_name}] FAILED in {duration:.3f}s -> {type(e).__name__}: {e}")

async def main():
    await test_model("llama-3.3-70b-versatile")
    await test_model("llama-3.1-8b-instant")
    await test_model("qwen/qwen3.6-27b")

asyncio.run(main())
