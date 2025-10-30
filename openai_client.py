from dotenv import load_dotenv
import os
from openai import OpenAI
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

#ROOT = Path(__file__).resolve().parent
#load_dotenv(ROOT.parent / ".env")  
load_dotenv(".env")
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