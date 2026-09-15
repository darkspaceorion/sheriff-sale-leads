"""One email per run. Gmail SMTP with an app password. Skips quietly if not configured."""
import os
import smtplib
from email.message import EmailMessage


def send(subject: str, body: str, to: str) -> bool:
    user, pw = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    if not (user and pw and to):
        print("[notify] email not configured, skipping")
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = user, to, subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.send_message(msg)
    return True


def summary(new: list[dict], updated: list[dict], failed: list[dict], errors: list[str]) -> str:
    lines = [f"New leads: {len(new)}", f"Status updates: {len(updated)}",
             f"Failed (in fallback sheet): {len(failed)}", ""]
    for l in new:
        lines.append(f"NEW  {l['county']}  {l['case_number']}  {l['street']}, {l['city']} {l['zip']}  "
                     f"{l['last_name']}  {l['status']}")
    for l in updated:
        lines.append(f"UPD  {l['county']}  {l['case_number']}  now {l['status']}")
    if errors:
        lines += ["", "Errors:"] + [f"  {e}" for e in errors]
    return "\n".join(lines)
