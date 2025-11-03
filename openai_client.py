'''from dotenv import load_dotenv
import os
from openai import OpenAI
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

#https://bqejpjyrpcqqgtvxeeds.supabase.co
#ROOT = Path(__file__).resolve().parent
#load_dotenv(ROOT.parent / ".env")  
load_dotenv(".env")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing")    
a
class OpenAIClient:
    def __init__(self, api_key=OPENAI_API_KEY):
        self.client = OpenAI(api_key=api_key)

    def Request(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model="gpt-4o", 
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()'''
        
import requests
import json

class OpenAIProxy:
    def __init__(self, supabase_url, supabase_key=None):
        self.url = supabase_url
        self.key = supabase_key
    
    def chat(self, messages, model="gpt-4o", max_tokens=None):
        headers = {"Content-Type": "application/json"}
        
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        
        payload = {
            "model": model,
            "messages": messages
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        try:
            response = requests.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                print(f"Error {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            print("Request timed out")
            return None
        except Exception as e:
            print(f"Request failed: {e}")
            return None

proxy = OpenAIProxy(
    supabase_url="https://bqejpjyrpcqqgtvxeeds.supabase.co/functions/v1/Open-AI-Request-Handler",
    supabase_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJxZWpwanlycGNxcWd0dnhlZWRzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjE4NzY0MzAsImV4cCI6MjA3NzQ1MjQzMH0._Xe84oZ3Sm1spV_ZUfnUYI-xfhQdlAaNmdsDjMmDtvg"
)

response = proxy.chat([
    {"role": "user", "content": "What is Python?"}
])
print(response)

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What's the capital of France?"},
    {"role": "assistant", "content": "The capital of France is Paris."},
    {"role": "user", "content": "What's the population?"}
]
response = proxy.chat(messages, model="gpt-4o")
print(response)