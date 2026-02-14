"""Send screenshot emails via SMTP."""

import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone

from .config import get_email_config


def send_screenshots_email(
    screenshot_results: list[dict],
    config_path: str | None = None,
) -> None:
    """Email all screenshots as attachments."""
    email_cfg = get_email_config(config_path)

    recipient = email_cfg.get("recipient", "")
    smtp_host = email_cfg.get("smtp_host", "smtp.gmail.com")
    smtp_port = email_cfg.get("smtp_port", 587)
    smtp_user = email_cfg.get("smtp_user", "")
    smtp_password = email_cfg.get("smtp_password", "")

    if not recipient:
        raise ValueError("No recipient email configured. Set it in the Settings page.")
    if not smtp_user or not smtp_password:
        raise ValueError("SMTP credentials not configured. Set them in the Settings page.")

    now = datetime.now(timezone.utc)
    month_str = now.strftime("%B %Y")

    msg = EmailMessage()
    msg["Subject"] = f"Portfolio Snapshots - {month_str}"
    msg["From"] = smtp_user
    msg["To"] = recipient

    successful = [r for r in screenshot_results if r.get("path")]
    failed = [r for r in screenshot_results if r.get("error")]

    body_lines = [
        f"Monthly portfolio screenshots - {now.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Total URLs: {len(screenshot_results)}",
        f"Screenshots captured: {len(successful)}",
    ]
    if failed:
        body_lines.append(f"Failed: {len(failed)}")
        for f_item in failed:
            body_lines.append(f"  - {f_item['label']}: {f_item['error']}")

    body_lines.append("")
    body_lines.append("URLs captured:")
    for r in successful:
        body_lines.append(f"  - {r['label']}")
        body_lines.append(f"    {r['url']}")

    msg.set_content("\n".join(body_lines))

    for result in successful:
        filepath = result["path"]
        if filepath and os.path.exists(filepath):
            filename = result.get("filename") or os.path.basename(filepath)
            with open(filepath, "rb") as f:
                img_data = f.read()
            msg.add_attachment(
                img_data,
                maintype="image",
                subtype="png",
                filename=filename,
            )

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)

    print(f"Email sent to {recipient} with {len(successful)} screenshot(s).")
