import asyncio
import os
from litellm import acompletion
from dotenv import load_dotenv

load_dotenv()

async def test_gemini():
    print(f"API_KEY: {os.getenv('GEMINI_API_KEY')[:10]}...")
    try:
        response = await acompletion(
            model="gemini/gemini-1.5-flash",
            messages=[{"role": "user", "content": "Hi"}],
            api_key=os.getenv("GEMINI_API_KEY")
        )
        print("Success!")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini())
