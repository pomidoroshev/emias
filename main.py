import json
import secrets
import smtplib
import string
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from pprint import pprint
from typing import Optional

import requests
from loguru import logger

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
    req = {
        "jsonrpc": "2.0",
        "id": gen_id(),
        "method": "getAvailableResourceScheduleInfo",
        "params": {
            "appointmentId": config["appointment_id"],
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
        if "error" in data and data["error"]["data"]["code"] == "Read timed out":
            logger.error("Timeout")
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


def notify(slot, doctor_name):
    send_email(f"Свободный слот: {doctor_name} - {slot}")
    json.dump(
        {
            "slot": str(slot),
            "doctor_name": doctor_name,
        },
        open("status.json", "w"),
    )


def has_already_notified(slot, doctor_name):
    try:
        status = json.load(open("status.json"))
    except Exception:
        return False
    return status["slot"] == str(slot) and status["doctor_name"] == doctor_name


def run():
    try:
        while True:
            for doctor_name in config["doctors"]:
                schedule = get_schedule(doctor_name)
                slot = earliest_slot(schedule)
                if (
                    slot
                    and slot - timedelta(days=config["catch_within_days"])
                    <= datetime.now()
                    and not has_already_notified(slot, doctor_name)
                ):
                    logger.warning(f"Caught {slot} {doctor_name}")
                    notify(slot, doctor_name)
            time.sleep(60)
    except Exception as e:
        logger.exception("Error")
        send_email(f"Скрипт поломался", f"{e!r}")


if __name__ == "__main__":
    run()
