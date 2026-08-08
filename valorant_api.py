from __future__ import annotations

import asyncio
import time
import urllib.parse
from typing import Any, Dict, Optional

import aiohttp

from config import HENRIK_API_KEY


class ValorantAPI:
    def __init__(self):
        self.base = "https://api.henrikdev.xyz"
        self.timeout = aiohttp.ClientTimeout(total=15)
        self.cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self.cache_ttl = 120

    @property
    def headers(self) -> Dict[str, str]:
        h = {"User-Agent": "V-Tracker-Rebuild/2.0"}
        if HENRIK_API_KEY:
            h["Authorization"] = HENRIK_API_KEY
        return h

    async def _get(self, session: aiohttp.ClientSession, urls: list[str]) -> Optional[Dict[str, Any]]:
        for url in urls:
            cached = self.cache.get(url)
            if cached and time.time() - cached[0] < self.cache_ttl:
                return cached[1]
            for attempt in range(3):
                try:
                    async with session.get(url, headers=self.headers, timeout=self.timeout) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            if isinstance(data, dict):
                                self.cache[url] = (time.time(), data)
                                return data
                        if resp.status == 404:
                            break
                        if resp.status == 429 or 500 <= resp.status < 600:
                            await asyncio.sleep(1.0 + attempt * 1.2)
                            continue
                        break
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    if attempt == 2:
                        break
                    await asyncio.sleep(1.0 + attempt)
        return None

    async def account(self, session: aiohttp.ClientSession, name: str, tag: str) -> Optional[Dict[str, Any]]:
        n = urllib.parse.quote(name, safe="")
        t = urllib.parse.quote(tag, safe="")
        return await self._get(session, [
            f"{self.base}/valorant/v1/account/{n}/{t}",
            f"{self.base}/v1/account/{n}/{t}",
        ])

    async def account_by_puuid(self, session: aiohttp.ClientSession, puuid: str) -> Optional[Dict[str, Any]]:
        p = urllib.parse.quote(puuid, safe="")
        return await self._get(session, [
            f"{self.base}/valorant/v1/by-puuid/account/{p}",
            f"{self.base}/v1/by-puuid/account/{p}",
        ])

    async def mmr(self, session: aiohttp.ClientSession, region: str, puuid: str) -> Optional[Dict[str, Any]]:
        region = self._region(region)
        p = urllib.parse.quote(puuid, safe="")
        return await self._get(session, [
            f"{self.base}/valorant/v2/by-puuid/mmr/{region}/{p}",
            f"{self.base}/v2/by-puuid/mmr/{region}/{p}",
        ])

    async def matches(self, session: aiohttp.ClientSession, region: str, puuid: str, size: int = 15) -> Optional[Dict[str, Any]]:
        region = self._region(region)
        p = urllib.parse.quote(puuid, safe="")
        size = min(max(int(size), 1), 20)
        return await self._get(session, [
            f"{self.base}/valorant/v3/by-puuid/matches/{region}/{p}?size={size}",
            f"{self.base}/v3/by-puuid/matches/{region}/{p}?size={size}",
        ])

    @staticmethod
    def _region(region: str) -> str:
        r = (region or "eu").lower()
        return "eu" if r in {"tr", "ru", "europe"} else r

    @staticmethod
    def account_data(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not payload:
            return None
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            return None
        puuid = data.get("puuid") or data.get("subject")
        name = data.get("name") or data.get("game_name")
        tag = data.get("tag") or data.get("tagline") or data.get("tag_line")
        if not (puuid and name and tag):
            return None
        card = data.get("card") if isinstance(data.get("card"), dict) else {}
        return {
            "puuid": str(puuid),
            "name": str(name),
            "tag": str(tag),
            "region": str(data.get("region") or "eu").lower(),
            "level": int(data.get("account_level") or data.get("level") or 0),
            "title": str(data.get("account_title") or data.get("title") or ""),
            "card": card,
        }


api = ValorantAPI()
