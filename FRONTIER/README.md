# 🎓 CampusSync AI – Frontend

CampusSync AI is an AI-powered academic assistant designed to help students organize assignments and generate personalized study plans through an interactive dashboard.

This repository contains the **Streamlit frontend** of the application, which communicates with the FastAPI backend to display assignments, study plans, and AI-generated recommendations.

---

## ✨ Features

- 🔐 Student Login
- 📊 Interactive Dashboard
- 📚 Assignment Management
- 🤖 AI Study Planner
- ⏰ Timed & Untimed Study Plans
- 📅 Weekly Planning
- 🔥 Priority-based Task Display
- 🌙 Modern Responsive UI
- 🔗 FastAPI Integration

---

## 🖥️ Tech Stack

- Streamlit
- Python
- Requests
- HTML/CSS
- FastAPI (Backend Communication)

---

## 📂 Project Structure

```
frontend/
│
├── api/
│   └── backend_api.py
│
├── components/
│   ├── assignment_card.py
│   ├── planner_cards.py
│   └── action_buttons.py
│
├── pages/
│   └── dashboard.py
│
├── styles/
│   ├── style.css
│   └── particles.html
│
app.py
requirements.txt
README.md
```

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/CampusSync-AI-Frontend.git
```

### 2. Navigate to the project

```bash
cd CampusSync-AI-Frontend
```

### 3. Create a virtual environment

```bash
python -m venv .venv
```

### 4. Activate the environment

**Windows**

```bash
.venv\Scripts\activate
```

**Linux / macOS**

```bash
source .venv/bin/activate
```

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

### 6. Start the backend

Make sure the FastAPI backend is running before launching the frontend.

### 7. Run Streamlit

```bash
streamlit run app.py
```

---

## 📸 Screens

- Login Page
- Dashboard
- Assignment Cards
- Today's Focus
- AI Planner
- Weekly Planner

---

## 🔄 Workflow

```
Student Login
        │
        ▼
Streamlit Frontend
        │
        ▼
FastAPI Backend
        │
        ▼
AI Planning Engine
        │
        ▼
Generated Study Plan
        │
        ▼
Interactive Dashboard
```

---

## 🌟 Current Capabilities

- Student authentication
- Assignment visualization
- Priority tracking
- Daily study planner
- Weekly study planner
- Timed study schedules
- Responsive dashboard

---

## 🔮 Future Enhancements

- Google Classroom Integration
- Learning Management System (LMS) Integration
- Personalized Notifications
- Calendar Synchronization
- AI Chat Assistant
- Progress Analytics
- Multi-user Authentication

---

## 👥 Team

Developed as part of an **Agentic AI** academic project.

---

## 📄 License

This project is developed for educational and research purposes.
