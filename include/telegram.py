import os

import requests


def _get_telegram_bot_token() -> str:
    return os.environ["TELEGRAM_BOT_TOKEN"]

def _get_telegram_chat_id() -> str:
    return os.environ["TELEGRAM_CHAT_ID"]

def send_telegram_message(message: str) -> None:
    url = f"https://api.telegram.org/bot{_get_telegram_bot_token()}/sendMessage"
    resp = requests.post(
        url,
        data={
            "chat_id": _get_telegram_chat_id(),
            "text": message,
        },
        timeout=10,
    )
    resp.raise_for_status()

def notify_failure(context) -> None:
    ti = context.get("task_instance")
    send_telegram_message(
        f"❌ Pipeline gagal\n"
        f"DAG: {ti.dag_id}\n"
        f"Task: {ti.task_id}\n"
        f"Run: {context['run_id']}"
    )
