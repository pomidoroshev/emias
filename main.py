import json
import secrets
import string
from datetime import datetime, timedelta
from pprint import pprint
from typing import Optional

import requests

BASE_URL = "https://emias.info/api/new/eip5orch"

config = json.load(open("config.json"))


def gen_id():
    return "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(21)
    )


def earliest_slot(schedule: list) -> Optional[datetime]:
    if not schedule:
        return None

    for day in schedule:
        for schedule_by_slot in day["scheduleBySlot"]:
            for slot in schedule_by_slot["slot"]:
                return datetime.fromisoformat(slot["startTime"]).replace(tzinfo=None)

    return None


def get_schedule(doctor_name):
    response = requests.post(
        url=BASE_URL,
        params={"getAvailableResourceScheduleInfo": "null"},
        json={
            "jsonrpc": "2.0",
            "id": gen_id(),
            "method": "getAvailableResourceScheduleInfo",
            "params": {
                "appointmentId": config["appointment_id"],
                "availableResourceId": config["doctors"][doctor_name],
                "omsNumber": config["oms_number"],
                "birthDate": config["birth_date"],
            },
        },
    )
    return response.json()["result"].get("scheduleOfDay", [])


def run():
    for doctor_name in config["doctors"]:
        schedule = get_schedule(doctor_name)
        slot = earliest_slot(schedule)
        if (
            slot
            and slot - timedelta(days=config["catch_within_days"]) <= datetime.now()
        ):
            print("Caught", slot, doctor_name)


if __name__ == "__main__":
    run()
