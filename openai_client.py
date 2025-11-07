import requests

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
            "messages": [{"role": "user", "content": messages}]
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        try:
            response = requests.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=60
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
        
def Request(prompt):
    proxy = OpenAIProxy(
        supabase_url="https://bqejpjyrpcqqgtvxeeds.supabase.co/functions/v1/Open-AI-Request-Handler",
        supabase_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJxZWpwanlycGNxcWd0dnhlZWRzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjE4NzY0MzAsImV4cCI6MjA3NzQ1MjQzMH0._Xe84oZ3Sm1spV_ZUfnUYI-xfhQdlAaNmdsDjMmDtvg"
    )
    response = proxy.chat(prompt, model="gpt-4o")
    return response