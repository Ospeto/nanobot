import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def test_sdk():
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        response = model.generate_content("Hi")
        print("Success!")
        print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_sdk()
