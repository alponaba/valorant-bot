# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Otomatik Güvenlik & Doğrulama Modülü (V + 4 Rakam Uyumlu)
"""

import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
import random
import logging
import urllib.parse

logger = logging.getLogger("V-Tracker-Security")

file_lock = asyncio.Lock()

class SecureAuthDatabase:
    USERS_FILE = "global_registered_users.json"
    CHALLENGES_FILE = "vtracker_challenges.json"

    @classmethod
    async def load_json(cls, filename):
        if not os.path.exists(filename):
            return {}
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except Exception as e:
            logger.error(f"Dosya okuma hatası ({filename}): {e}")
        return {}

    @classmethod
    async def save_json(cls, filename, data):
        async with file_lock:
            temp_filename = f"{filename}.tmp"
            try:
                with open(temp_filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                os.replace(temp_filename, filename)
            except Exception as e:
                logger.error(f"Dosya yazma hatası ({filename}): {e}")
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)

class AutomatedSecuritySystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.headers = {"User-Agent": "V-Tracker-Bot/8.0", "Authorization": "HDEV-b0b6fb9c-f082-4311-a42c-59d1b958b0d6"}

    @commands.hybrid_command(name="dogrula", description="Riot hesabınızın size ait olduğunu 5 haneli tag kodu ile doğrular.")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def dogrula(self, ctx, *, riot_id: str = None):
        if not riot_id or "#" not in riot_id or len(riot_id.split("#")) != 2:
            return await ctx.send("❌ Hatalı format! Örnek kullanım: `v!dogrula OyuncuAdı#TR1`")

        name, tag = [x.strip() for x in riot_id.split("#")]
        user_id = str(ctx.author.id)

        users = await SecureAuthDatabase.load_json(SecureAuthDatabase.USERS_FILE)
        if user_id in users and users[user_id].get("name"):
            return await ctx.send("⚠️ Zaten doğrulanmış ve sisteme bağlı bir Riot hesabın var! Değiştirmek için önce `v!unregister` kullanmalısın.")

        encoded_name = urllib.parse.quote(name, safe='')
        encoded_tag = urllib.parse.quote(tag, safe='')
        url = f"https://api.henrikdev.xyz/valorant/v1/account/{encoded_name}/{encoded_tag}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200:
                    return await ctx.send("❌ Riot hesabı bulunamadı! İsim ve etiketini doğru yazdığından emin ol.")
                data = await resp.json()
                acc_data = data.get("data", {})

        puuid = acc_data.get("puuid")
        
        for uid, udata in users.items():
            if udata.get("puuid") == puuid:
                return await ctx.send("❌ Bu Riot hesabı zaten başka bir Discord kullanıcısı tarafından doğrulanmış!")

        # V harfi + 4 rakam (Örn: V4829 - Tam 5 karakter, Riot tag sınırına birebir uygun)
        challenge_code = f"V{random.randint(1000, 9999)}"

        challenges = await SecureAuthDatabase.load_json(SecureAuthDatabase.CHALLENGES_FILE)
        challenges[user_id] = {
            "puuid": puuid,
            "region": (acc_data.get("region") or "eu").lower(),
            "name": acc_data.get("name"),
            "tag": acc_data.get("tag"),
            "code": challenge_code
        }
        await SecureAuthDatabase.save_json(SecureAuthDatabase.CHALLENGES_FILE, challenges)

        embed = discord.Embed(
            title="🛡️ Otomatik Riot Hesap Doğrulama",
            description=f"**{acc_data.get('name')}#{acc_data.get('tag')}** hesabının sana ait olduğunu doğrulamamız gerekiyor.\n\n"
                        f"🔑 **Doğrulama Tag Kodun:** `{challenge_code}`\n\n"
                        f"**Nasıl Onaylayacaksın?**\n"
                        f"1. Riot Games hesabına web üzerinden giriş yap.\n"
                        f"2. Profilindeki **Tag / Etiket** kısmını geçici olarak **`{challenge_code}`** yapın (5 karakter sınırına tam uyar).\n"
                        f"3. Kodunu tag kısmına kaydettikten sonra **`v!onayla`** komutunu yaz!",
            color=0x00FFFF
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="onayla", description="Riot tag kısmına eklediğin V+4 haneli kodu kontrol ederek hesabı güvenle bağlar.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def onayla(self, ctx):
        user_id = str(ctx.author.id)
        challenges = await SecureAuthDatabase.load_json(SecureAuthDatabase.CHALLENGES_FILE)

        if user_id not in challenges:
            return await ctx.send("❌ Aktif bir doğrulama işlemin bulunmuyor. Önce `v!dogrula İsim#Tag` komutunu kullanmalısın.")

        chal_info = challenges[user_id]
        name = chal_info["name"]
        tag = chal_info["tag"]
        region = chal_info["region"]
        expected_code = chal_info["code"]
        puuid = chal_info["puuid"]

        encoded_name = urllib.parse.quote(name, safe='')
        encoded_tag = urllib.parse.quote(tag, safe='')
        url = f"https://api.henrikdev.xyz/valorant/v1/account/{encoded_name}/{encoded_tag}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200:
                    return await ctx.send("❌ Riot API'ye ulaşılamadı. Lütfen birkaç dakika sonra tekrar dene.")
                data = await resp.json()
                current_acc = data.get("data", {})

        current_tag = current_acc.get("tag", "")

        if expected_code.lower() not in current_tag.lower():
            return await ctx.send(f"❌ Doğrulama başarısız! Riot tag kısmında **`{expected_code}`** kodunu bulamadık. Lütfen etiketini bu kodla güncellediğinden emin ol ve tekrar dene.")

        challenges.pop(user_id)
        await SecureAuthDatabase.save_json(SecureAuthDatabase.CHALLENGES_FILE, challenges)

        users = await SecureAuthDatabase.load_json(SecureAuthDatabase.USERS_FILE)
        
        existing_cosmetics = users.get(user_id, {}).get("cosmetics", {
            "color": "0x00FFFF", "emoji": "", "banner": "", "gif": "", "unlocked": []
        })
        existing_coins = users.get(user_id, {}).get("v_coins", 0)

        users[user_id] = {
            "puuid": puuid,
            "name": name,
            "tag": tag,
            "region": region,
            "dc_name": ctx.author.name,
            "v_coins": existing_coins,
            "cosmetics": existing_cosmetics
        }
        await SecureAuthDatabase.save_json(SecureAuthDatabase.USERS_FILE, users)

        embed = discord.Embed(
            title="🎉 Hesap Başarıyla Doğrulandı ve Bağlandı!",
            description=f"Tebrikler! **{name}#{tag}** hesabı V-Security ile doğrulandı ve Discord hesabınla eşleştirildi.",
            color=0x00FF00
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AutomatedSecuritySystem(bot))
    logger.info("Otomatik Güvenlik & Doğrulama Modülü başarıyla yüklendi!")