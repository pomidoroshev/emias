import json
from typing import List


def update_status(doctor_name: str, slots: List[str]) -> None:
    try:
        current_status = json.load(open("status.json"))
    except Exception:
        current_status = {}

    if doctor_name in current_status:
        current_status[doctor_name] = [*{*current_status[doctor_name], *slots}]
    else:
        current_status[doctor_name] = slots

    json.dump(current_status, open("status.json", "w"))


def load_status(doctor_name: str) -> List[str]:
    try:
        current_status = json.load(open("status.json"))
    except Exception:
        current_status = {}

    return current_status.get(doctor_name, [])
