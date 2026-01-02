# app/services/azure_llm.py
import os
from openai import AzureOpenAI

_client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
)

def chat(messages, temperature=0.2):
    deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]  # e.g. "gpt-4.1-mini"
    resp = _client.chat.completions.create(
        model=deployment,
        messages=messages,
        temperature=temperature,
    )
    return resp.choices[0].message.content
