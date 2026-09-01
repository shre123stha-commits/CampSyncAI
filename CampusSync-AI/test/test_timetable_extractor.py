from pathlib import Path

from utils.doc_loader import read_docx
from extractors.timetable_extractor import extract_timetable

text = read_docx(
    Path("data/documents/timetable/24BAI1127.docx")
)

lectures = extract_timetable(text)

print("\n========== LECTURES ==========\n")

for lecture in lectures:
    print(lecture)