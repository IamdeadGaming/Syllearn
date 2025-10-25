from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()  
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing")    

class OpenAIClient:
    def __init__(self, api_key=OPENAI_API_KEY):
        self.client = OpenAI(api_key=api_key)

    def Request(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4o", 
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()