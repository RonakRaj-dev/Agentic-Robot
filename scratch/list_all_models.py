import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
api_key = os.environ.get("GROQ_API_KEY")
base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

client = AsyncOpenAI(api_key=api_key, base_url=base_url)

async def main():
    models = await client.models.list()
    print(f"Total models available: {len(models.data)}")
    for m in models.data:
        print(f"ID: {m.id} | Owned by: {getattr(m, 'owned_by', 'unknown')}")

asyncio.run(main())
