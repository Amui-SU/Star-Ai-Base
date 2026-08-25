"""
邮件发送服务 — 通过 SMTP 发送验证码邮件
"""

import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger
from typing import Literal

from app.config import settings

VERIFICATION_HTML = """\
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 20px; color: #222220;">
  <h2 style="margin:0 0 8px;font-size:22px;">你的验证码</h2>
  <p style="margin:0 0 24px;color:#8a8680;font-size:15px;">{purpose_text}，{valid_minutes} 分钟内有效。</p>
  <div style="background:#f5f3ee;border-radius:12px;padding:24px;text-align:center;margin-bottom:24px;">
    <span style="font-size:36px;font-weight:700;letter-spacing:6px;color:#222220;">{code}</span>
  </div>
  <p style="margin:0;color:#8a8680;font-size:13px;">如果这不是你的操作，请忽略此邮件。</p>
</body>
</html>
"""


async def send_verification_email(
    to_email: str,
    code: str,
    *,
    purpose: Literal["registration", "password_reset"] = "registration",
) -> bool:
    """发送验证码邮件。成功返回 True，失败记录日志并返回 False。"""
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP 未配置，验证码邮件未发送到 {}", to_email)
        return False

    msg = MIMEMultipart("alternative")
    subject, purpose_text = {
        "registration": ("智库云 — 邮箱验证码", "用于注册 智库云 账号"),
        "password_reset": ("智库云 — 密码重置验证码", "用于重置 智库云 账号密码"),
    }[purpose]
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_email

    html = VERIFICATION_HTML.format(
        code=code,
        purpose_text=purpose_text,
        valid_minutes=5,
    )
    msg.attach(MIMEText(html, "html", "utf-8"))

    def _send():
        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=15
            )
        try:
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], [to_email], msg.as_string())
            return True
        finally:
            server.quit()

    try:
        await asyncio.to_thread(_send)
        logger.info("验证码邮件已发送到 {}", to_email)
        return True
    except Exception as e:
        logger.error("发送验证码邮件到 {} 失败: {}", to_email, e)
        return False
