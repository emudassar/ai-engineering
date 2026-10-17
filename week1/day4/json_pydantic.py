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

from pydantic import BaseModel
class Ticket(BaseModel):
  name: str
  email: str
  issue: str

schema = Ticket.model_json_schema()

response_formate = {
  "type": "json_object"
}

system_prompt = f"""
Extract the personal information from ticket strictly on the base of this schema and give a json output.
{schema}
"""
message_system = {
  "role": "system",
  "content": system_prompt
}

text = "Hell my name is Mudassar, I have an iphone which is not working, my address is Lahore. my email is mudassar@gmail.com"
prompt = f"""
this is a customer ticket, extract the personal information from this
{text}
"""

message = {
  "role": role,
  "content": prompt
}
messages = [message_system, message]

response = client.chat.completions.create(model=model, messages=messages, response_format = response_formate)
answer = response.choices[0].message.content
print(answer)

import json
raw_json = answer
data_file = json.loads(raw_json)
ticket = Ticket(**data_file)

print(ticket.name)
print(ticket.email)
print(ticket.issue)