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
                {"role": "system", "content": "You are a helpful education assistant. Respond strictly in JSON format."},
                {"role": "user", "content": "Explain why leaves are green in 1 sentence. Output JSON: {\"answer\": \"...\"}"}
            ],
            response_format={"type": "json_object"},
            max_tokens=200
        )
        duration = time.time() - start
        print(f"[{model_name}] JSON SUCCESS in {duration:.3f}s -> {res.choices[0].message.content}")
    except Exception as e:
        duration = time.time() - start
        print(f"[{model_name}] JSON FAILED in {duration:.3f}s -> {type(e).__name__}: {e}")

async def test_model_text(model_name):
    start = time.time()
    try:
        res = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": "Explain why leaves are green in 1 sentence."}
            ],
            max_tokens=100
        )
        duration = time.time() - start
        print(f"[{model_name}] TEXT SUCCESS in {duration:.3f}s -> {res.choices[0].message.content[:80]}")
    except Exception as e:
        duration = time.time() - start
        print(f"[{model_name}] TEXT FAILED in {duration:.3f}s -> {type(e).__name__}: {e}")

async def main():
    for m in ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.6-27b"]:
        print(f"\n--- Testing {m} ---")
        await test_model(m)
        await test_model_text(m)

asyncio.run(main())
