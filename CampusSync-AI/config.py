from langchain_ollama import ChatOllama
from pathlib import Path

llm = ChatOllama(
    model="qwen2.5:3b",
    temperature=0
)


BASE_DIR = Path(__file__).parent

DOCUMENTS_DIR = BASE_DIR / "data" / "documents"

TIMETABLE_DIR = DOCUMENTS_DIR / "timetable"

LMS_DIR = DOCUMENTS_DIR / "lms"