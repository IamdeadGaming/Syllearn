from dotenv import load_dotenv
import os
import openai

load_dotenv()  
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing")    

class OpenAIClient:
    def __init__(self, api_key=OPENAI_API_KEY):
        self.api_key = api_key
        openai.api_key = self.api_key
    def Request(self, prompt):
        response = openai.ChatCompletion.create(
            model="gpt-5.0-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message['content'].strip()