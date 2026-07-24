# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Otomatik Riot Hesap Sahipliği Doğrulama Modülü (vsecurity.py)
Kapsam: OAuth / Challenge Tabanlı Güvenli Otomatik Hesap Eşleştirme
Geliştirici: AI Assistant & Mustafa Alperen Gözüdok
"""

import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
import random
import logging

logger = logging.getLogger("V-Tracker-Security")

file_lock = asyncio.Lock()

class SecureAuthDatabase:
    USERS_FILE = "vtracker_users.json"
    CHALLENGES_FILE = "vtracker_challenges.json"

    @classmethod
    async def load_json(cls, filename):
        if not os.path.exists(filename):
            return {}
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
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
        self.headers = {"User-Agent": "V-Tracker-Bot/2.5"}

    # --- 1. ADIM: DOĞRULAMA KODU OLUŞTURMA VE BAŞLATMA ---
    @commands.hybrid_command(name="dogrula", description="Riot hesabınızın size ait olduğunu otomatik doğrular.")
    async def dogrula(self, ctx, riot_id: str):
        if "#" not in riot_id:
            return await ctx.send("❌ Hatalı format! Örnek kullanım: `v!dogrula TenZ#0000`")

        name, tag = riot_id.split("#", 1)
        user_id = str(ctx.author.id)

        # Kullanıcı zaten kayıtlı mı?
        users = await SecureAuthDatabase.load_json(SecureAuthDatabase.USERS_FILE)
        if user_id in users:
            return await ctx.send("⚠️ Zaten doğrulanmış ve sisteme bağlı bir Riot hesabın var!")

        # Riot hesabının varlığını kontrol et
        url = f"https://api.henrikdev.xyz/valorant/v1/account/{name}/{tag}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200:
                    return await ctx.send("❌ Riot hesabı bulunamadı! İsim ve etiketini doğru yazdığından emin ol.")
                data = await resp.json()
                acc_data = data.get("data", {})

        puuid = acc_data.get("puuid")
        
        # Başka bir Discord kullanıcısı bu Riot hesabını çoktan bağlamış mı?
        for uid, udata in users.items():
            if udata.get("puuid") == puuid:
                return await ctx.send("❌ Bu Riot hesabı zaten başka bir Discord kullanıcısı tarafından doğrulanmış!")

        # Benzersiz Güvenlik Kodu Üret
        challenge_code = f"VTRK-{random.randint(1000, 9999)}"

        # Bekleyen doğrulamalara kaydet
        challenges = await SecureAuthDatabase.load_json(SecureAuthDatabase.CHALLENGES_FILE)
        challenges[user_id] = {
            "puuid": puuid,
            "region": acc_data.get("region", "eu"),
            "name": acc_data.get("name"),
            "tag": acc_data.get("tag"),
            "code": challenge_code
        }
        await SecureAuthDatabase.save_json(SecureAuthDatabase.CHALLENGES_FILE, challenges)

        embed = discord.Embed(
            title="🛡️ Otomatik Riot Hesap Doğrulama",
            description=f"**{acc_data.get('name')}#{acc_data.get('tag')}** hesabının sana ait olduğunu doğrulamamız gerekiyor.\n\n"
                        f"🔑 **Doğrulama Kodun:** `{challenge_code}`\n\n"
                        f"**Nasıl Onaylayacaksın?**\n"
                        f"1. Riot Games hesabına web üzerinden giriş yap.\n"
                        f"2. Profilindeki **Slogan (Tagline)** kısmına veya Riot ID adna geçici olarak bu kodu ekle **VEYA** aşağıdaki butona benzer şekilde doğrula.\n"
                        f"3. Kodunu ekledikten sonra **`v!onayla`** komutunu yaz!",
            color=0x00FFFF
        )
        await ctx.send(embed=embed)

    # --- 2. ADIM: OTOMATİK KOD KONTROLÜ VE TAMAMLAMA ---
    @commands.hybrid_command(name="onayla", description="Riot profiline eklediğin kodu kontrol ederek hesabı otomatik bağlar.")
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

        # Riot API'den güncel hesap verisini çekerek kodun eklenip eklenmediğini kontrol et
        url = f"https://api.henrikdev.xyz/valorant/v1/account/{name}/{tag}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status != 200:
                    return await ctx.send("❌ Riot API'ye ulaşılamadı. Lütfen birkaç dakika sonra tekrar dene.")
                data = await resp.json()
                current_acc = data.get("data", {})

        # Kontrol: Riot Tagline veya Name içinde güvenlik kodu geçiyor mu?
        current_tag = current_acc.get("tag", "")
        current_name = current_acc.get("name", "")

        # Güvenlik doğrulaması: Kod hesap bilgilerinde bulunmalı
        if expected_code not in current_tag and expected_code not in current_name:
            return await ctx.send(f"❌ Doğrulama başarısız! Riot profilinde (İsim veya Tagline kısmında) **`{expected_code}`** kodunu bulamadık. Lütfen kodu eklediğinden emin ol ve tekrar dene.")

        # Doğrulama Başarılı! Kalıcı veritabanına kaydet
        challenges.pop(user_id)
        await SecureAuthDatabase.save_json(SecureAuthDatabase.CHALLENGES_FILE, challenges)

        users = await SecureAuthDatabase.load_json(SecureAuthDatabase.USERS_FILE)
        users[user_id] = {
            "puuid": chal_info["puuid"],
            "region": region,
            "name": name,
            "tag": tag
        }
        await SecureAuthDatabase.save_json(SecureAuthDatabase.USERS_FILE, users)

        embed = discord.Embed(
            title="🎉 Hesap Başarıyla Doğrulandı!",
            description=f"Tebrikler! **{name}#{tag}** hesabı hiçbir yetkili müdahalesine gerek kalmadan tamamen otomatik olarak Discord hesabınla eşleştirildi.",
            color=0x00FF00
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AutomatedSecuritySystem(bot))
    logger.info("Otomatik Güvenlik & Doğrulama Modülü (AutomatedSecuritySystem) başarıyla yüklendi!")