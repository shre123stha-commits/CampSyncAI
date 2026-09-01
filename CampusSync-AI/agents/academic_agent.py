from config import TIMETABLE_DIR, LMS_DIR

from utils.doc_loader import read_docx

from extractors.timetable_extractor import extract_timetable
from extractors.task_extractor import extract_tasks
from datetime import datetime


def academic_agent(state):

    print("\n========== Academic Agent ==========")
    print(state)

    reg_no = state["registration_no"]

    # ---------- Timetable ----------

    timetable_path = TIMETABLE_DIR / f"{reg_no}.docx"

    timetable_text = read_docx(timetable_path)

    lectures = extract_timetable(timetable_text)

    # ---------- LMS ----------

    lms_path = LMS_DIR / f"{reg_no}.docx"

    lms_text = read_docx(lms_path)

    tasks = extract_tasks(
        lms_text,
        platform="LMS"
    )
    today = datetime.today()

    for task in tasks:
        try:
            deadline = datetime.strptime(task.deadline, "%d %B %Y")
            task.days_remaining = (deadline - today).days
        except:
            task.days_remaining = 999
            
    state["timetable"] = lectures
    state["assignments"] = tasks

    print("Academic data loaded successfully.")

    return state