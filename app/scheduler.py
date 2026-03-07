from datetime import date, datetime

import httpx

from .database import SessionLocal
from .models import AdminSettings, ReminderLog, Resource

_DEFAULT_REMINDER_DAYS = [30, 14, 7, 3]
_DEFAULT_NOTIFY_HOUR = 9


async def check_reminders():
    db = SessionLocal()
    try:
        settings = db.get(AdminSettings, 1)
        reminder_days = settings.reminder_days if settings else _DEFAULT_REMINDER_DAYS
        notify_hour = settings.notify_hour if settings else _DEFAULT_NOTIFY_HOUR

        if datetime.now().hour != notify_hour:
            return

        resources = db.query(Resource).all()
        today = date.today()

        for resource in resources:
            days_until = (resource.expiration_date - today).days

            if days_until not in reminder_days:
                continue

            existing = (
                db.query(ReminderLog)
                .filter(
                    ReminderLog.resource_id == resource.id,
                    ReminderLog.expiration_date == resource.expiration_date,
                    ReminderLog.days_before == days_until,
                )
                .first()
            )

            if existing:
                continue

            await _send_slack_reminder(resource, days_until)

            log = ReminderLog(
                resource_id=resource.id,
                expiration_date=resource.expiration_date,
                days_before=days_until,
            )
            db.add(log)
            db.commit()
    finally:
        db.close()


async def send_deletion_notification(resource: Resource):
    payload = {
        "text": f"Resource *{resource.name}* has been deleted from Tribal.",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{resource.name} has been deleted"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Type:*\n{resource.type}"},
                    {"type": "mrkdwn", "text": f"*DRI:*\n{resource.dri}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "This resource has been removed from Tribal. No further reminders will be sent.",
                },
            },
        ],
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(resource.slack_webhook, json=payload, timeout=10)
    except Exception:
        pass


async def _send_slack_reminder(resource: Resource, days_until: int):
    urgency = "URGENT: " if days_until <= 7 else ""
    expiry_str = resource.expiration_date.strftime("%m/%d/%Y")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{urgency}{resource.name} expires in {days_until} days",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Expiration:*\n{expiry_str}"},
                {"type": "mrkdwn", "text": f"*DRI:*\n{resource.dri}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Purpose:*\n{resource.purpose}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Generation Instructions:*\n{resource.generation_instructions}",
            },
        },
    ]

    if resource.secret_manager_link:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Secret Manager:* <{resource.secret_manager_link}|View>",
                },
            }
        )

    payload = {
        "text": f"{urgency}{resource.name} expires in {days_until} days ({expiry_str})",
        "blocks": blocks,
    }

    try:
        async with httpx.AsyncClient() as client:
            await client.post(resource.slack_webhook, json=payload, timeout=10)
    except Exception:
        pass
