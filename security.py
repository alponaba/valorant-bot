from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

import discord

from config import TRUSTED_IMAGE_HOSTS

MENTION_RE = re.compile(r"@(everyone|here)|<@&?\d+>|<@!?\d+>")
DISCORD_ALLOWED_MENTIONS = discord.AllowedMentions.none()


def sanitize_text(text: str, max_len: int = 1000) -> str:
    text = (text or "").strip()
    text = MENTION_RE.sub("[mention-blocked]", text)
    return text[:max_len]


def trusted_banner_url(url: str, extra_hosts: Iterable[str] = ()) -> tuple[bool, str]:
    value = (url or "").strip()
    if not value:
        return False, "Boş URL gönderilemez."
    if len(value) > 500:
        return False, "URL çok uzun."
    try:
        parsed = urlparse(value)
    except Exception:
        return False, "URL çözümlenemedi."
    if parsed.scheme.lower() != "https":
        return False, "Banner yalnızca HTTPS bağlantısı olabilir."
    host = (parsed.netloc or "").lower()
    if not host:
        return False, "Geçerli bir alan adı bulunamadı."
    allowed = set(TRUSTED_IMAGE_HOSTS) | {h.lower() for h in extra_hosts}
    if not any(host == a or host.endswith(f".{a}") for a in allowed):
        return False, "Bu görsel kaynağı izinli değil. Discord CDN / Imgur gibi güvenilen bir kaynak kullan."
    if parsed.username or parsed.password:
        return False, "Kimlik bilgisi içeren URL kabul edilmez."
    return True, value


def masked_puuid(value: str) -> str:
    value = str(value or "")
    if len(value) <= 18:
        return value
    return f"{value[:8]}…{value[-6:]}"
