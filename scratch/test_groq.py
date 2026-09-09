import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
api_key = os.environ.get("GROQ_API_KEY")
base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
model_name = os.environ.get("GROQ_PRIMARY_MODEL", "llama-3.3-70b-versatile")

print(f"Testing Groq API with model: {model_name}")
client = AsyncOpenAI(api_key=api_key, base_url=base_url)

async def main():
    try:
        models = await client.models.list()
        print("Available Groq models:")
        for m in models.data[:10]:
            print(" -", m.id)
    except Exception as e:
        print(f"Error listing models: {type(e).__name__}: {e}")

    try:
        res = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Hi, reply in 5 words."}]
        )
        print("Completion result:", res.choices[0].message.content)
    except Exception as e:
        print(f"Error creating completion with {model_name}: {type(e).__name__}: {e}")

asyncio.run(main())
