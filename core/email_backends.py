import json
from urllib import error, request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class ResendEmailBackend(BaseEmailBackend):
    api_url = "https://api.resend.com/emails"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        sent_count = 0

        for message in email_messages:
            payload = {
                "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
                "to": message.to,
                "subject": message.subject,
                "text": message.body,
            }

            req = request.Request(
                self.api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": "KZCRMS/1.0",
                },
                method="POST",
            )

            try:
                with request.urlopen(req, timeout=settings.EMAIL_TIMEOUT) as response:
                    if 200 <= response.status < 300:
                        sent_count += 1
            except error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="ignore")
                if not self.fail_silently:
                    raise RuntimeError(f"Resend API error: {detail}") from exc
            except error.URLError as exc:
                if not self.fail_silently:
                    raise RuntimeError("Resend API is unreachable") from exc

        return sent_count
