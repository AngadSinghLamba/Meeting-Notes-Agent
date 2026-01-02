import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

print("KEY?", bool(os.getenv("OPENAI_API_KEY")))
print("BASE?", os.getenv("OPENAI_BASE_URL"))

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

resp = client.chat.completions.create(
    model=deployment,  # Azure: deployment name
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Reply with exactly: OK"},
    ],
)

print(resp.choices[0].message.content)
