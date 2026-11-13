#!/usr/bin/env python3
"""钉钉自定义群机器人推送（加签方式）。

用法：
  python report_v2/dingtalk_notify.py            # 真实发送
  python report_v2/dingtalk_notify.py --dry-run  # 只生成签名与消息体，不发网络请求

凭证只从环境变量读取，绝不写入仓库文件：
  DINGTALK_WEBHOOK  完整 Webhook URL（含 access_token）
  DINGTALK_SECRET    SEC 开头的加签密钥
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
MESSAGE_FILE = OUT / "dingtalk.md"
STATUS_FILE = OUT / "notify_status.json"
TITLE = "对照品信息对账日报"
# 保守的自定义长度上限（非官方限制），防止差异清单过长导致发送失败
MAX_TEXT_LEN = 15000


def signed_url(webhook: str, secret: str) -> str:
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest))
    separator = "&" if "?" in webhook else "?"
    return f"{webhook}{separator}timestamp={timestamp}&sign={sign}"


def mask_url(url: str) -> str:
    masked = re.sub(r"(access_token=)[^&]+", r"\1***", url)
    return re.sub(r"(sign=)[^&]+", r"\1***", masked)


def write_status(sent: bool, detail: str) -> None:
    payload = {
        "sent": sent,
        "detail": detail,
        "checked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
    }
    STATUS_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="不发送，仅打印脱敏后的请求")
    parser.add_argument("--message", default=str(MESSAGE_FILE))
    args = parser.parse_args()

    webhook = os.environ.get("DINGTALK_WEBHOOK", "").strip()
    secret = os.environ.get("DINGTALK_SECRET", "").strip()
    if not webhook or not secret:
        print("[dingtalk] 缺少环境变量 DINGTALK_WEBHOOK / DINGTALK_SECRET")
        write_status(False, "missing credentials")
        return 2

    message_path = Path(args.message)
    if not message_path.exists():
        print(f"[dingtalk] 消息文件不存在：{message_path}")
        write_status(False, "missing message file")
        return 2

    text = message_path.read_text(encoding="utf-8")
    if len(text) > MAX_TEXT_LEN:
        text = text[:MAX_TEXT_LEN] + "\n\n> 内容过长已截断，完整清单见查询网页。"

    payload = {
        "msgtype": "markdown",
        "markdown": {"title": TITLE, "text": text},
        "at": {"isAtAll": False},
    }
    url = signed_url(webhook, secret)

    if args.dry_run:
        print("[dingtalk] dry-run，未发送任何网络请求")
        print(f"[dingtalk] URL: {mask_url(url)}")
        print(f"[dingtalk] 正文字符数: {len(text)}")
        print("[dingtalk] 正文预览:")
        print(text[:600])
        return 0

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json;charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"[dingtalk] 请求失败：{type(exc).__name__}: {exc}")
        write_status(False, f"request failed: {exc}")
        return 1

    if result.get("errcode") == 0:
        print("[dingtalk] 发送成功")
        write_status(True, "ok")
        return 0

    detail = f"errcode={result.get('errcode')} errmsg={result.get('errmsg')}"
    print(f"[dingtalk] 发送失败：{detail}")
    write_status(False, detail)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
