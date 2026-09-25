import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

def get_model(model_name: str = None, temperature: float = 0.2):
    actual_model = model_name or os.getenv("MODEL_NAME", "openai/gpt-oss-120b")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured in .env or environment variables.")
    return ChatGroq(
        model=actual_model,
        temperature=temperature,
        api_key=api_key
    )
