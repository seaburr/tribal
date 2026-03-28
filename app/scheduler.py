import calendar as _cal
import logging
import re
from datetime import date, datetime, timezone

import httpx

from .cert_utils import fetch_cert_expiry_from_endpoint
from .database import SessionLocal
from .models import AdminSettings, AuditLog, ReminderLog, Resource

logger = logging.getLogger(__name__)

_DEFAULT_REMINDER_DAYS = [30, 14, 7, 3]


def _audit_notification(resource_id: int, resource_name: str, action: str, detail: dict):
    db = SessionLocal()
    try:
        db.add(AuditLog(
            resource_id=resource_id,
            resource_name=resource_name,
            action=action,
            detail=detail,
        ))
        db.commit()
    except Exception:
        logger.exception("Failed to write audit log for %s on resource %d", action, resource_id)
    finally:
        db.close()
_URL_RE = re.compile(r'(https?://[^\s<>]+)')


def _slackify_links(text: str) -> str:
    """Wrap bare URLs in Slack mrkdwn <url> format so they render as clickable links."""
    return _URL_RE.sub(r'<\1>', text)
_DEFAULT_NOTIFY_HOUR = 9

_TRIBAL_FOOTER = {
    "type": "context",
    "elements": [{"type": "mrkdwn", "text": "Sent by *Tribal* — The expiration & rotation tracker."}],
}


async def check_reminders():
    logger.info("check_reminders: starting")
    db = SessionLocal()
    try:
        settings = db.get(AdminSettings, 1)
        reminder_days = settings.reminder_days if settings else _DEFAULT_REMINDER_DAYS
        notify_hour = settings.notify_hour if settings else _DEFAULT_NOTIFY_HOUR
        alert_on_overdue = settings.alert_on_overdue if settings else False
        admin_webhook = settings.slack_webhook if settings else None

        current_hour = datetime.now().hour
        if current_hour != notify_hour:
            logger.info("check_reminders: outside notify_hour=%d (current=%d), skipping", notify_hour, current_hour)
            return

        resources = db.query(Resource).filter(Resource.deleted_at.is_(None)).all()
        today = date.today()
        review_cadence = settings.review_cadence_months if settings else None
        logger.info("check_reminders: evaluating %d resources", len(resources))

        for resource in resources:
            # ── Expiry reminders (skip does-not-expire resources) ──
            if resource.expiration_date is not None and not resource.does_not_expire:
                days_until = (resource.expiration_date - today).days

                if days_until in reminder_days:
                    existing = (
                        db.query(ReminderLog)
                        .filter(
                            ReminderLog.resource_id == resource.id,
                            ReminderLog.expiration_date == resource.expiration_date,
                            ReminderLog.days_before == days_until,
                            ReminderLog.reminder_type == "expiry",
                        )
                        .first()
                    )
                    if not existing:
                        logger.info("check_reminders: sending reminder for %r (%d days)", resource.name, days_until)
                        await _send_slack_reminder(resource, days_until, db)
                        db.add(ReminderLog(
                            resource_id=resource.id,
                            expiration_date=resource.expiration_date,
                            days_before=days_until,
                            reminder_type="expiry",
                        ))
                        db.commit()

                if alert_on_overdue and admin_webhook and days_until < 0:
                    existing = (
                        db.query(ReminderLog)
                        .filter(
                            ReminderLog.resource_id == resource.id,
                            ReminderLog.expiration_date == resource.expiration_date,
                            ReminderLog.days_before == -1,
                            ReminderLog.reminder_type == "expiry",
                        )
                        .first()
                    )
                    if not existing:
                        logger.info("check_reminders: sending overdue alert for %r", resource.name)
                        await _send_overdue_alert(resource, admin_webhook, db)
                        db.add(ReminderLog(
                            resource_id=resource.id,
                            expiration_date=resource.expiration_date,
                            days_before=-1,
                            reminder_type="expiry",
                        ))
                        db.commit()

            # ── Review reminders ──
            if review_cadence and resource.slack_webhook:
                next_review = _next_review_date(resource, review_cadence)
                review_days_until = (next_review - today).days

                if review_days_until in reminder_days:
                    existing = (
                        db.query(ReminderLog)
                        .filter(
                            ReminderLog.resource_id == resource.id,
                            ReminderLog.expiration_date == next_review,
                            ReminderLog.days_before == review_days_until,
                            ReminderLog.reminder_type == "review",
                        )
                        .first()
                    )
                    if not existing:
                        logger.info("check_reminders: sending review reminder for %r (%d days)", resource.name, review_days_until)
                        await _send_review_reminder(resource, review_days_until, next_review, db)
                        db.add(ReminderLog(
                            resource_id=resource.id,
                            expiration_date=next_review,
                            days_before=review_days_until,
                            reminder_type="review",
                        ))
                        db.commit()

                if review_days_until < 0:
                    existing = (
                        db.query(ReminderLog)
                        .filter(
                            ReminderLog.resource_id == resource.id,
                            ReminderLog.expiration_date == next_review,
                            ReminderLog.days_before == -1,
                            ReminderLog.reminder_type == "review",
                        )
                        .first()
                    )
                    if not existing:
                        logger.info("check_reminders: sending overdue review reminder for %r", resource.name)
                        await _send_review_reminder(resource, review_days_until, next_review, db)
                        db.add(ReminderLog(
                            resource_id=resource.id,
                            expiration_date=next_review,
                            days_before=-1,
                            reminder_type="review",
                        ))
                        db.commit()

        logger.info("check_reminders: complete")
    except Exception:
        logger.exception("check_reminders: unhandled error")
    finally:
        db.close()


async def _send_overdue_alert(resource: Resource, admin_webhook: str, db=None):
    expiry_str = resource.expiration_date.strftime("%m/%d/%Y")
    days_overdue = (date.today() - resource.expiration_date).days
    payload = {
        "text": f":rotating_light: OVERDUE: {resource.name} expired {days_overdue}d ago ({expiry_str})",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f":rotating_light: OVERDUE: {resource.name}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Expired:*\n{expiry_str}"},
                    {"type": "mrkdwn", "text": f"*Days overdue:*\n{days_overdue}"},
                    {"type": "mrkdwn", "text": f"*Type:*\n{resource.type}"},
                    {"type": "mrkdwn", "text": f"*DRI:*\n{resource.dri}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Purpose:*\n{_slackify_links(resource.purpose)}"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Rotation Instructions:*\n{_slackify_links(resource.generation_instructions)}",
                },
            },
            *(
                [{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Secret Manager:* <{resource.secret_manager_link}|View>",
                    },
                }]
                if resource.secret_manager_link else []
            ),
            _TRIBAL_FOOTER,
        ],
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(admin_webhook, json=payload, timeout=10)
        if db is not None:
            db.add(AuditLog(resource_id=resource.id, resource_name=resource.name, action="notification.overdue_alert", detail={"days_overdue": days_overdue, "expiration_date": expiry_str}))
            db.commit()
        else:
            _audit_notification(resource.id, resource.name, "notification.overdue_alert", {"days_overdue": days_overdue, "expiration_date": expiry_str})
    except Exception:
        logger.exception("Failed to send overdue alert for resource %d", resource.id)


async def send_admin_deletion_notification(resource: Resource, admin_webhook: str, deleted_by: str | None = None):
    """Send a deletion alert to the admin Slack webhook when alert_on_delete is enabled."""
    expiry_str = resource.expiration_date.strftime("%m/%d/%Y")
    deleted_by_text = deleted_by or "Unknown"
    payload = {
        "text": f":wastebasket: Resource deleted: {resource.name}",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f":wastebasket: Resource deleted: {resource.name}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Type:*\n{resource.type}"},
                    {"type": "mrkdwn", "text": f"*DRI:*\n{resource.dri}"},
                    {"type": "mrkdwn", "text": f"*Expiration:*\n{expiry_str}"},
                    {"type": "mrkdwn", "text": f"*Deleted by:*\n{deleted_by_text}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "This resource has been removed from Tribal. No further reminders will be sent.",
                },
            },
            _TRIBAL_FOOTER,
        ],
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(admin_webhook, json=payload, timeout=10)
    except Exception:
        logger.exception("Failed to send admin deletion notification for resource %d", resource.id)


async def send_deletion_notification(resource: Resource, deleted_by: str | None = None):
    payload = {
        "text": f":wastebasket: {resource.name} has been deleted from Tribal.",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f":wastebasket: {resource.name} deleted"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Type:*\n{resource.type}"},
                    {"type": "mrkdwn", "text": f"*DRI:*\n{resource.dri}"},
                    *(
                        [{"type": "mrkdwn", "text": f"*Deleted by:*\n{deleted_by}"}]
                        if deleted_by else []
                    ),
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "This resource has been removed from Tribal. No further reminders will be sent.",
                },
            },
            _TRIBAL_FOOTER,
        ],
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(resource.slack_webhook, json=payload, timeout=10)
        _audit_notification(resource.id, resource.name, "notification.deletion", {"deleted_by": deleted_by})
    except Exception:
        logger.exception("Failed to send deletion notification for resource %d", resource.id)


async def _send_slack_reminder(resource: Resource, days_until: int, db=None):
    expiry_str = resource.expiration_date.strftime("%m/%d/%Y")

    if days_until <= 3:
        urgency_prefix = ":rotating_light: URGENT: "
        color_emoji = ":red_circle:"
    elif days_until <= 7:
        urgency_prefix = ":warning: "
        color_emoji = ":large_orange_circle:"
    else:
        urgency_prefix = ""
        color_emoji = ":large_yellow_circle:"

    header_text = f"{urgency_prefix}{resource.name} expires in {days_until} day{'s' if days_until != 1 else ''}"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Expiration:*\n{color_emoji} {expiry_str}"},
                {"type": "mrkdwn", "text": f"*Days remaining:*\n{days_until}"},
                {"type": "mrkdwn", "text": f"*Type:*\n{resource.type}"},
                {"type": "mrkdwn", "text": f"*DRI:*\n{resource.dri}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Purpose:*\n{_slackify_links(resource.purpose)}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Rotation Instructions:*\n{_slackify_links(resource.generation_instructions)}",
            },
        },
    ]

    if resource.secret_manager_link:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Secret Manager:* <{resource.secret_manager_link}|View>",
            },
        })

    blocks.append(_TRIBAL_FOOTER)

    payload = {
        "text": f"{urgency_prefix}{resource.name} expires in {days_until} day{'s' if days_until != 1 else ''} ({expiry_str})",
        "blocks": blocks,
    }

    try:
        async with httpx.AsyncClient() as client:
            await client.post(resource.slack_webhook, json=payload, timeout=10)
        if db is not None:
            db.add(AuditLog(resource_id=resource.id, resource_name=resource.name, action="notification.reminder", detail={"days_until": days_until, "expiration_date": expiry_str}))
            db.commit()
        else:
            _audit_notification(resource.id, resource.name, "notification.reminder", {"days_until": days_until, "expiration_date": expiry_str})
    except Exception:
        logger.exception("Failed to send Slack reminder for resource %d", resource.id)


def _add_months(d: date, months: int) -> date:
    """Add months to a date, clamping to end of month if needed."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, _cal.monthrange(year, month)[1])
    return date(year, month, day)


def _next_review_date(resource: Resource, cadence_months: int) -> date:
    """Compute the next review date for a resource given a cadence in months."""
    base = resource.last_reviewed_at.date() if resource.last_reviewed_at else resource.created_at.date()
    return _add_months(base, cadence_months)


async def _send_review_reminder(resource: Resource, days_until: int, review_date: date, db=None):
    """Send a Slack review reminder to the per-resource webhook."""
    review_str = review_date.strftime("%m/%d/%Y")
    last_reviewed = resource.last_reviewed_at.strftime("%m/%d/%Y") if resource.last_reviewed_at else "Never"

    if days_until < 0:
        header_text = f":clipboard: OVERDUE FOR REVIEW: {resource.name}"
        days_label = f"{abs(days_until)} day(s) overdue"
    elif days_until == 0:
        header_text = f":clipboard: Review due today: {resource.name}"
        days_label = "Today"
    else:
        header_text = f":clipboard: Review due in {days_until} day{'s' if days_until != 1 else ''}: {resource.name}"
        days_label = f"{days_until} day(s)"

    payload = {
        "text": header_text,
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": header_text[:150]},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Review Due:*\n{review_str}"},
                    {"type": "mrkdwn", "text": f"*Days:*\n{days_label}"},
                    {"type": "mrkdwn", "text": f"*Type:*\n{resource.type}"},
                    {"type": "mrkdwn", "text": f"*DRI:*\n{resource.dri}"},
                    {"type": "mrkdwn", "text": f"*Last Reviewed:*\n{last_reviewed}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Please review this resource in Tribal to confirm the information is still accurate."},
            },
            _TRIBAL_FOOTER,
        ],
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(resource.slack_webhook, json=payload, timeout=10)
        if db is not None:
            db.add(AuditLog(resource_id=resource.id, resource_name=resource.name,
                            action="notification.review_reminder",
                            detail={"days_until_review": days_until, "review_date": review_str}))
            db.commit()
        else:
            _audit_notification(resource.id, resource.name, "notification.review_reminder",
                                {"days_until_review": days_until, "review_date": review_str})
    except Exception:
        logger.exception("Failed to send review reminder for resource %d", resource.id)


async def refresh_cert_expiry():
    """Daily job: re-fetch TLS certificate expiry for resources with auto_refresh_expiry enabled."""
    logger.info("refresh_cert_expiry: starting")
    db = SessionLocal()
    try:
        candidates = (
            db.query(Resource)
            .filter(
                Resource.deleted_at.is_(None),
                Resource.type == "Certificate",
                Resource.auto_refresh_expiry.is_(True),
                Resource.certificate_url.isnot(None),
            )
            .all()
        )
        logger.info("refresh_cert_expiry: checking %d resource(s)", len(candidates))
        for resource in candidates:
            try:
                new_expiry = fetch_cert_expiry_from_endpoint(resource.certificate_url)
            except Exception:
                logger.warning("refresh_cert_expiry: could not fetch cert for resource %d (%s)", resource.id, resource.certificate_url)
                continue

            if new_expiry != resource.expiration_date:
                old_expiry = resource.expiration_date.isoformat()
                resource.expiration_date = new_expiry
                resource.updated_at = datetime.now(timezone.utc)
                db.add(AuditLog(
                    resource_id=resource.id,
                    resource_name=resource.name,
                    action="resource.cert_expiry_refresh",
                    detail={"old_expiry": old_expiry, "new_expiry": new_expiry.isoformat(), "certificate_url": resource.certificate_url},
                ))
                db.commit()
                logger.info("refresh_cert_expiry: updated expiry for %r: %s → %s", resource.name, old_expiry, new_expiry.isoformat())
            else:
                logger.info("refresh_cert_expiry: expiry unchanged for %r (%s)", resource.name, resource.expiration_date)
        logger.info("refresh_cert_expiry: complete")
    except Exception:
        logger.exception("refresh_cert_expiry: unhandled error")
    finally:
        db.close()
