import discord
from config import BRAND_COLOR, ACCENT_COLOR, SUCCESS_COLOR, WARNING_COLOR, ERROR_COLOR, BRAND_NAME


def embed(title: str, description: str = "", *, color: int = BRAND_COLOR) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text=f"{BRAND_NAME} • Valorant Assistant")
    return e


def success(title: str, description: str = "") -> discord.Embed:
    return embed(title, description, color=SUCCESS_COLOR)


def warning(title: str, description: str = "") -> discord.Embed:
    return embed(title, description, color=WARNING_COLOR)


def error(title: str, description: str = "") -> discord.Embed:
    return embed(title, description, color=ERROR_COLOR)


def info(title: str, description: str = "") -> discord.Embed:
    return embed(title, description, color=ACCENT_COLOR)
