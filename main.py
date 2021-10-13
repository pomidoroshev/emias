import json
import secrets
import smtplib
import string
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from pprint import pprint
from typing import List, Optional

import requests
from loguru import logger

from status import load_status, update_status

BASE_URL = "https://emias.info/api/new/eip5orch"

config = json.load(open("config.json"))


def get_appointment_id() -> Optional[int]:
    req = {
        "jsonrpc": "2.0",
        "id": gen_id(),
        "method": "getAppointmentReceptionsByPatient",
        "params": {
            "omsNumber": config["oms_number"],
            "birthDate": config["birth_date"],
        },
    }
    response = requests.post(
        url=BASE_URL,
        params={"getAppointmentReceptionsByPatient": "null"},
        json=req,
    )
    data = response.json()
    result = data.get("result")
    if result:
        appointment = result[0]
        return appointment["id"]

    if "error" in data:
        logger.error(f"get_appointment_id error: {data['error']}")
        raise ValueError(f"get_appointment_id error: {data['error']}")

    return None


def gen_id() -> str:
    return "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(21)
    )


def find_slots(schedule: list, catch_within_days: int) -> List[str]:
    result: List[str] = []
    if not schedule:
        return result

    for day in schedule:
        for schedule_by_slot in day["scheduleBySlot"]:
            for slot in schedule_by_slot["slot"]:
                slot_datetime = datetime.fromisoformat(slot["startTime"]).replace(
                    tzinfo=None
                )
                if slot_datetime - timedelta(days=catch_within_days) <= datetime.now():
                    result.append(slot_datetime.strftime("%Y-%m-%d %H:%M"))

    return result


def get_schedule(doctor_name: str, appointment_id: Optional[int]) -> list:
    req = {
        "jsonrpc": "2.0",
        "id": gen_id(),
        "method": "getAvailableResourceScheduleInfo",
        "params": {
            "appointmentId": appointment_id,
            "availableResourceId": config["doctors"][doctor_name],
            "omsNumber": config["oms_number"],
            "birthDate": config["birth_date"],
        },
    }
    response = requests.post(
        url=BASE_URL,
        params={"getAvailableResourceScheduleInfo": "null"},
        json=req,
    )
    data = response.json()
    if not "result" in data:
        if (
            "error" in data
            and data["error"]["data"]["code"] != "APPOINTMENT_RECEPTION_NOT_FOUND"
        ):
            logger.error(f"Some error: {data['error']}")
            return []
        raise ValueError(f"Please check parameters, response: {data}")
    return data["result"].get("scheduleOfDay", [])


def send_email(subject, body="(no content)"):
    msg = EmailMessage()
    msg["subject"] = subject
    msg["From"] = "DD <notify@doroshev.com>"
    msg["To"] = config["mail"]["to"]
    msg.set_content(body)

    try:
        smtp_server = smtplib.SMTP_SSL(
            config["mail"]["smtp_domain"], config["mail"]["smtp_port"]
        )
        smtp_server.ehlo()
        smtp_server.login(config["mail"]["smtp_user"], config["mail"]["smtp_password"])
        smtp_server.send_message(msg)
        smtp_server.close()
        logger.info("Email sent successfully!")
    except Exception as ex:
        logger.exception("Something went wrong")
        raise


def notify(slots: List[str], doctor_name: str) -> None:
    if not slots:
        return
    if len(slots) == 1:
        send_email(f"Свободный слот: {doctor_name} - {slots[0]}")
    else:
        send_email(f"Свободные слоты: {doctor_name}", ", ".join(slots))
    update_status(doctor_name, slots)


def has_already_notified(slots: List[str], doctor_name: str) -> bool:
    notified_slots = load_status(doctor_name)
    return not set(slots) - set(notified_slots)


def run() -> None:
    try:
        while True:
            try:
                appointment_id = get_appointment_id()
            except Exception:
                time.sleep(30)
                continue

            for doctor_name in config["doctors"]:
                schedule = get_schedule(doctor_name, appointment_id)
                slots = find_slots(schedule, config["catch_within_days"])
                if slots and not has_already_notified(slots, doctor_name):
                    logger.warning(f"Caught {slots} {doctor_name}")
                    notify(slots, doctor_name)

            time.sleep(60)
    except Exception as e:
        logger.exception("Error")
        send_email(f"Скрипт поломался", f"{e!r}")


if __name__ == "__main__":
    run()
