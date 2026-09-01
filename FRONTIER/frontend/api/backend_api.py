import requests

BASE_URL = "http://127.0.0.1:8000"


def generate_plan(student_id, mode):

    response = requests.post(
        f"{BASE_URL}/generate-plan",
        json={
            "registration_no": student_id,
            "mode": mode
        }
    )

    response.raise_for_status()

    return response.json()