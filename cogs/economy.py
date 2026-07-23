# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Ekonomi, Günlük Ödül, Transfer ve Liderlik Sistemi
Modül: cogs.economy
"""

import discord
from discord.ext import commands
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger("VTracker.Economy")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s]: %(message)s"))
    logger.addHandler(handler)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GLOBAL_DB_FILE = os.path.join(BASE_DIR, "global_registered_users.json")

class EconomyDatabase:
    @staticmethod
    def load_db() -> Dict[str, Any]:
        if os.path.exists(GLOBAL_DB_FILE):
            try:
                with open(GLOBAL_DB_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
            except Exception as e:
                logger.error(f"Ekonomi DB okuma hatası: {e}")
        return {}

    @staticmethod
    def save_db(data: Dict[str, Any]) -> None:
        try:
            with open(GLOBAL_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Ekonomi DB yazma hatası: {e}")

    @staticmethod
    def get_user_data(discord_id: str) -> Dict[str, Any]:
        db = EconomyDatabase.load_db()
        d_id = str(discord_id)
        if d_id not in db:
            db[d_id] = {
                "puuid": "",
                "name": "Bilinmiyor",
                "tag": "TR1",
                "region": "eu",
                "v_coins": 1000,  # Başlangıç bonusu
                "last_daily": None,
                "total_given": 0
            }
            EconomyDatabase.save_db(db)
        return db[d_id]

    @staticmethod
    def update_user_balance(discord_id: str, amount: int) -> int:
        db = EconomyDatabase.load_db()
        d_id = str(discord_id)
        if d_id not in db:
            EconomyDatabase.get_user_data(d_id)
            db = EconomyDatabase.load_db()
        
        db[d_id]["v_coins"] = max(0, db[d_id].get("v_coins", 0) + amount)
        EconomyDatabase.save_db(db)
        return db[d_id]["v_coins"]

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="balance", aliases=["bakiye", "bal", "para"])
    async def balance_command(self, ctx, member: Optional[discord.Member] = None):
        target = member or ctx.author
        data = EconomyDatabase.get_user_data(target.id)
        coins = data.get("v_coins", 0)

        embed = discord.Embed(
            title="🏦 V-Tracker.gg Cüzdan Durumu",
            description=f"**{target.mention}** adlı kullanıcının varlık bilgileri:",
            color=0xF1C40F
        )
        embed.add_field(name="V-Coin Miktarı", value=f"🪙 **{coins:,} V-Coin**", inline=False)
        embed.set_footer(text=f"Sorgulayan: {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.command(name="daily", aliases=["gunluk"])
    async def daily_command(self, ctx):
        d_id = str(ctx.author.id)
        db = EconomyDatabase.load_db()
        user_data = db.get(d_id)
        
        if not user_data:
            user_data = EconomyDatabase.get_user_data(d_id)
            db = EconomyDatabase.load_db()

        now = datetime.utcnow()
        last_daily_str = user_data.get("last_daily")
        
        daily_reward = 750

        if last_daily_str:
            last_daily = datetime.fromisoformat(last_daily_str)
            next_available = last_daily + timedelta(hours=24)
            if now < next_available:
                remaining = next_available - now
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                return await ctx.send(f"⏳ Günlük ödülünü zaten almışsın! Tekrar alabilmek için **{hours} saat {minutes} dakika** beklemelisin.")

        user_data["last_daily"] = now.isoformat()
        db[d_id] = user_data
        EconomyDatabase.save_db(db)
        
        new_balance = EconomyDatabase.update_user_balance(ctx.author.id, daily_reward)

        embed = discord.Embed(
            title="🎁 Günlük V-Coin Ödülü",
            description=f"Başarıyla günlük ödülünü topladın!\n\nCüzdanına eklenen: **+{daily_reward} V-Coin**\nGüncel Bakiyen: **{new_balance:,} V-Coin**",
            color=0x2ECC71
        )
        await ctx.send(embed=embed)

    @commands.command(name="give", aliases=["gonder", "transfer"])
    async def give_command(self, ctx, member: Optional[discord.Member] = None, amount: int = 0):
        if not member or amount <= 0:
            return await ctx.send("❌ Hatalı kullanım! Örnek: `v!give @Kullanici 500`")

        if member.id == ctx.author.id:
            return await ctx.send("❌ Kendine V-Coin gönderemezsin!")

        sender_id = str(ctx.author.id)
        sender_data = EconomyDatabase.get_user_data(sender_id)
        sender_balance = sender_data.get("v_coins", 0)

        # Give limiti kontrolü (Örn: Tek seferde max 50,000 V-Coin veya bakiye kontrolü)
        if amount > 50000:
            return await ctx.send("❌ Tek seferde en fazla **50,000 V-Coin** transfer edebilirsin!")

        if sender_balance < amount:
            return await ctx.send(f"❌ Yetersiz bakiye! Cüzdanında **{sender_balance:,} V-Coin** var.")

        # Transfer işlemi
        EconomyDatabase.update_user_balance(ctx.author.id, -amount)
        EconomyDatabase.update_user_balance(member.id, amount)

        embed = discord.Embed(
            title="💸 V-Coin Transferi Başarılı",
            description=f"**{ctx.author.mention}**, **{member.mention}** adlı kullanıcıya **{amount:,} V-Coin** gönderdi.",
            color=0x3498DB
        )
        await ctx.send(embed=embed)

    @commands.command(name="leaderboard", aliases=["lb", "top", "zenginler"])
    async def leaderboard_command(self, ctx):
        db = EconomyDatabase.load_db()
        if not db:
            return await ctx.send("📊 Henüz sistemde kayıtlı kullanıcı bulunmuyor.")

        # V-Coin miktarına göre sırala
        sorted_users = sorted(db.items(), key=lambda x: x[1].get("v_coins", 0), reverse=True)[:10]

        embed = discord.Embed(
            title="🏆 V-Tracker.gg V-Coin Liderlik Tablosu",
            description="Sunucudaki en zengin Valorant oyuncuları:",
            color=0xF39C12
        )

        desc_list = ""
        for idx, (u_id, u_info) in enumerate(sorted_users, 1):
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`#{idx}`"
            name = u_info.get("name", "Bilinmiyor")
            coins = u_info.get("v_coins", 0)
            desc_list += f"{medal} <@İD_{u_id}> ({name}) — **{coins:,} V-Coin**\n".replace("İD_", "")

        embed.add_field(name="Top 10 Zenginler", value=desc_list or "Veri yok.", inline=False)
        embed.set_footer(text="Düzenli aktif olarak ve oyunlar oynayarak sıralamanı yükseltebilirsin!")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))