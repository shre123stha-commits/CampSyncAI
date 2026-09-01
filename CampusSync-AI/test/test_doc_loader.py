from pathlib import Path

from utils.doc_loader import read_docx

text = read_docx(
    Path("data/documents/24BME1001.docx")
)

print("\n========== DOCUMENT ==========\n")

print(text)