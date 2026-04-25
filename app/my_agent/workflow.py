from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.2, max_tokens=500)