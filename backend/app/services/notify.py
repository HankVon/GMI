"""运维告警通知 — 定时任务/关键流程失败时推送到企业微信/钉钉/通用 Webhook。

配置: 环境变量 NOTIFY_WEBHOOK_URL(为空则不发通知, 仅记日志)。
格式:
  - 企业微信机器人: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
  - 钉钉机器人:     https://oapi.dingtalk.com/robot/send?access_token=xxx
  - 其他:           POST JSON {title, content, level}
"""
from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger("notify")


def send_alert(title: str, content: str, level: str = "error") -> bool:
    """发送运维告警。失败/未配置时仅记日志, 不影响主流程。"""
    url = settings.NOTIFY_WEBHOOK_URL
    if not url:
        logger.warning("[notify] 未配置 NOTIFY_WEBHOOK_URL, 跳过告警: %s - %s", title, content[:120])
        return False
    try:
        import httpx
        if "qyapi.weixin.qq.com" in url:
            payload = {"msgtype": "text", "text": {"content": f"[{level}] {title}\n{content}"}}
        elif "oapi.dingtalk.com" in url:
            payload = {"msgtype": "text", "text": {"content": f"[{level}] {title}\n{content}"}}
        else:
            payload = {"title": title, "content": content, "level": level}
        r = httpx.post(url, json=payload, timeout=8)
        logger.info("[notify] alert sent: %s -> %s", title, r.status_code)
        return r.status_code < 400
    except Exception as e:  # noqa: BLE001 - 通知失败不阻断业务
        logger.warning("[notify] alert send failed: %s", e)
        return False
