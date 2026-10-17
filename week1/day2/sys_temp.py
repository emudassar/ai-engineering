import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
my_api_key = os.getenv("GROQ_API_KEY")

if not my_api_key:
  raise ValueError("api error")
client = Groq(api_key=my_api_key)
model = "openai/gpt-oss-20b"
role = "user"
prompt = "suggest the name for my food company"

message_system = {
  "role": "system",
  "content": "You are a brand manager who suggest the name for my food company, name shoud be one word, give just one name"
}

message = {
  "role": role,
  "content": prompt
}
messages = [message_system, message]

response = client.chat.completions.create(model=model, messages=messages, temperature=2)
answer = response.choices[0].message.content
print(answer)