from __future__ import annotations

from datetime import datetime, timezone
import discord

from config import ACCENT_COLOR, BRAND_COLOR, BRAND_NAME, ERROR_COLOR, PANEL_COLOR, SUCCESS_COLOR, WARNING_COLOR

FOOTER_TEXT = f"{BRAND_NAME} • Player Intelligence"


def embed(title: str, description: str = "", *, color: int = BRAND_COLOR) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc))
    e.set_footer(text=FOOTER_TEXT)
    return e


def panel(title: str, description: str = "") -> discord.Embed:
    return embed(title, description, color=PANEL_COLOR)


def success(title: str, description: str = "") -> discord.Embed:
    return embed(title, description, color=SUCCESS_COLOR)


def warning(title: str, description: str = "") -> discord.Embed:
    return embed(title, description, color=WARNING_COLOR)


def error(title: str, description: str = "") -> discord.Embed:
    return embed(title, description, color=ERROR_COLOR)


def info(title: str, description: str = "") -> discord.Embed:
    return embed(title, description, color=ACCENT_COLOR)


def add_metric_grid(e: discord.Embed, metrics: list[tuple[str, str]]):
    for name, value in metrics:
        e.add_field(name=name, value=value, inline=True)
    return e
