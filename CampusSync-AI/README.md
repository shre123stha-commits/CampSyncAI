# 🎓 CampusSync AI

CampusSync AI is an AI-powered academic planning system that automatically creates personalized study schedules by extracting information from student documents and intelligently organizing academic tasks around their timetable.

Instead of manually checking multiple platforms like LMS, Microsoft Teams, and Google Classroom, students receive one consolidated study plan generated using an AI planning agent.

---

# 🚀 Features

- 📄 Automatic timetable extraction from uploaded documents
- 📚 Automatic LMS task extraction
- 🧠 AI-powered study planning using Qwen LLM
- 📅 Personalized schedules based on lecture timings
- ⏳ Deadline-aware task prioritization
- 📝 Four planning modes:
  - Day with Timings
  - Day without Timings
  - Week with Timings
  - Week without Timings
- 🔄 Extensible architecture for Google Classroom (MCP)
- 📦 Structured JSON output for frontend integration

---

# 🏗 System Architecture

```
                Registration Number
                        │
                        ▼
               Academic Agent
        (Timetable + LMS Extraction)
                        │
                        ▼
         Google Classroom Agent
        (Future MCP Integration)
                        │
                        ▼
          Study Slot Extraction
                        │
                        ▼
            AI Planning Agent
               (Qwen via Ollama)
                        │
                        ▼
          Structured JSON Output
                        │
                        ▼
                 Frontend UI
```

---

# 🧠 How It Works

## 1. Student Login

The student logs in using their registration number.

Example:

```
24BAI1127
```

The system automatically identifies the student's documents.

---

## 2. Document Processing

CampusSync AI reads

- Timetable document
- LMS document

using

- python-docx
- Qwen LLM

Information extracted includes

- Lecture timings
- Subjects
- Assignments
- Projects
- Quizzes
- Deadlines

---

## 3. Study Slot Detection

The scheduler automatically finds

- Free periods
- After-college study slots

Very short gaps (<30 minutes) are ignored.

---

## 4. AI Planning

The Planning Agent receives

- Lecture timetable
- Available study slots
- Academic tasks
- Current date

The planner then

- prioritizes urgent tasks
- distributes workload
- avoids lecture hours
- balances work realistically

---

# Planning Modes

## Day With Timings

Example

```
Monday

4:00 PM – 5:30 PM

Machine Learning Assignment

6:00 PM – 7:00 PM

Python Lab
```

---

## Day Without Timings

Example

```
Today's Tasks

• Machine Learning Assignment

• Python Lab

• Revise Deep Learning
```

---

## Week With Timings

Generates a complete weekly schedule with timings.

---

## Week Without Timings

Generates a weekly task plan without exact timings.

---

# AI Workflow

```
DOCX Files
      │
      ▼
Text Extraction
      │
      ▼
Qwen Extraction
      │
      ▼
Task Objects
      │
      ▼
Python Scheduler
      │
      ▼
Qwen Planning Agent
      │
      ▼
JSON Response
```

---

# JSON Output

Example

```json
{
  "mode": "day_without_timings",
  "plan": [
    {
      "day": "Monday",
      "start_time": "",
      "end_time": "",
      "subject": "Machine Learning",
      "task_type": "Assignment",
      "work": "Build and evaluate a Decision Tree classifier.",
      "deadline": "12 August 2026",
      "days_remaining": 12,
      "priority": "Medium",
      "reason": "Started early because the task requires significant effort."
    }
  ]
}
```

---

# Technologies Used

## AI

- Qwen (Ollama)
- LangGraph
- LangChain

## Backend

- Python
- FastAPI *(integration in progress)*

## Document Processing

- python-docx

## Data Models

- Pydantic

## Workflow

- LangGraph StateGraph

---

# Project Structure

```
CampusSync-AI/

│
├── agents/
│   ├── academic_agent.py
│   ├── classroom_agent.py
│   └── planning_agent.py
│
├── extractors/
│   ├── timetable_extractor.py
│   └── task_extractor.py
│
├── scheduler/
│   └── study_slots.py
│
├── models/
│   ├── timetable.py
│   ├── task.py
│   ├── free_slot.py
│   └── state.py
│
├── prompts/
│   ├── timetable_prompt.py
│   ├── task_prompt.py
│   └── planning_prompt.py
│
├── utils/
│   ├── doc_loader.py
│   ├── prompt_formatter.py
│   └── mode_prompt.py
│
├── test/
│
├── data/
│   ├── timetable/
│   └── documents/
│
├── graph.py
├── config.py
└── README.md
```

---

# Current Status

✅ Timetable Extraction

✅ LMS Task Extraction

✅ Study Slot Detection

✅ AI Planning Agent

✅ JSON Output

✅ Deadline-aware Planning

⬜ FastAPI Integration

⬜ Frontend Integration

⬜ Google Classroom MCP



---

# Future Enhancements

- Google Classroom integration using MCP
- Microsoft Teams integration
- Alternative schedule generation
- Notifications and reminders
- Calendar synchronization
- Mobile application
- Study analytics dashboard

---

# Installation

Clone the repository

```bash
git clone https://github.com/<your-username>/CampusSync-AI.git
```

Move into the project

```bash
cd CampusSync-AI
```

Install dependencies

```bash
uv sync
```

Run Ollama

```bash
ollama serve
```

Run the Qwen model

```bash
ollama run qwen3:8b
```

Run the project

```bash
uv run python -m test.test_graph
```

---

# Team

Developed as an Agentic AI academic assistant project.

---

# License

This project is intended for educational and research purposes.
