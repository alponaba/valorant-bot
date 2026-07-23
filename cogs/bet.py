# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import json
import os
import random

OWNER_ID = 000000000000000000  # Kendi Discord ID'ni buraya yaz

# ================= GELİŞMİŞ MAYIN TARLASI (ADVANCED MINES) =================
class AdvancedMinesView(discord.ui.View):
    def __init__(self, ctx, amount, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.amount = amount
        self.cog = cog
        self.uid = str(ctx.author.id)
        
        # 16 kutuluk 4x4 matris: 12 Hazine, 4 Mayın (Daha yüksek risk & kazanç)
        self.board = ["safe"] * 12 + ["bomb"] * 4
        random.shuffle(self.board)
        self.revealed = [False] * 16
        self.game_over = False
        self.safe_count = 0
        
        # Her bulguda katlanarak artan yüksek çarpanlar
        self.multipliers = [1.3, 1.7, 2.2, 2.9, 3.8, 5.0, 6.5, 8.5, 11.0, 15.0, 20.0, 30.0]

        for i in range(16):
            btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="❓", row=i//4, custom_id=f"tile_{i}")
            btn.callback = self.make_callback(i)
            self.add_item(btn)
            
        self.cashout_btn = discord.ui.Button(style=discord.ButtonStyle.success, label="💰 Kasayı Al & Çekil", row=4, disabled=True)
        self.cashout_btn.callback = self.cashout_callback
        self.add_item(self.cashout_btn)

    def make_callback(self, index):
        async def button_callback(interaction: discord.Interaction):
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message("❌ Bu oyunu sen başlatmadın!", ephemeral=True)
            if self.game_over:
                return await interaction.response.send_message("❌ Bu oyun bitti!", ephemeral=True)
            if self.revealed[index]:
                return await interaction.response.send_message("⚠️ Burayı zaten açtın!", ephemeral=True)

            self.revealed[index] = True
            if self.board[index] == "bomb":
                self.game_over = True
                for idx, item in enumerate(self.children[:-1]):
                    item.disabled = True
                    item.style = discord.ButtonStyle.danger if self.board[idx] == "bomb" else discord.ButtonStyle.success
                    item.label = "💣" if self.board[idx] == "bomb" else "💎"
                self.cashout_btn.disabled = True

                self.cog.update_user_balance(self.uid, -self.amount)
                new_bal = self.cog.get_user_balance(self.uid)
                embed = discord.Embed(
                    title="💥 MAYIN TARLASI | MAYINA BASTIN!",
                    description=f"4x4 Alan patladı!\n• Kaybedilen: **-{self.amount:,} V-Coin**\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                self.children[index].style = discord.ButtonStyle.success
                self.children[index].label = "💎"
                self.safe_count += 1
                self.cashout_btn.disabled = False

                current_mult = self.multipliers[self.safe_count - 1]
                potential_win = int(self.amount * current_mult)

                if self.safe_count == 12:
                    self.game_over = True
                    for item in self.children: item.disabled = True
                    profit = potential_win - self.amount
                    self.cog.update_user_balance(self.uid, profit)
                    new_bal = self.cog.get_user_balance(self.uid)
                    embed = discord.Embed(
                        title="🏆 4X4 EFSANEVİ KUSURSUZ ZAFER!",
                        description=f"12 Hazinenin hepsini buldun!\n• Çarpan: `{current_mult}x`\n• Kazanılan: **+{potential_win:,} V-Coin**",
                        color=discord.Color.gold()
                    )
                    await interaction.response.edit_message(embed=embed, view=self)
                else:
                    embed = discord.Embed(
                        title="🧭 GELİŞMİŞ MAYIN TARLASI (4x4)",
                        description=f"💎 Harika! Mücevher buldun.\n• Mevcut Çarpan: **{current_mult}x**\n• O anki Ödül: `{potential_win:,} V-Coin`",
                        color=discord.Color.blurple()
                    )
                    await interaction.response.edit_message(embed=embed, view=self)
        return button_callback

    async def cashout_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu senin oyunun değil!", ephemeral=True)
        if self.game_over or self.safe_count == 0:
            return await interaction.response.send_message("❌ Henüz ödül kazanmadın!", ephemeral=True)

        self.game_over = True
        for item in self.children: item.disabled = True
        current_mult = self.multipliers[self.safe_count - 1]
        total_payout = int(self.amount * current_mult)
        profit = total_payout - self.amount

        self.cog.update_user_balance(self.uid, profit)
        new_bal = self.cog.get_user_balance(self.uid)
        embed = discord.Embed(
            title="💰 KASA GÜVENCEYE ALINDI!",
            description=f"• Bulunan Hazine: `{self.safe_count}/12`\n• Çarpan: `{current_mult}x`\n• Kâr: **+{profit:,} V-Coin**\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=self)

# ================= GELİŞMİŞ ÇARKIFELEK (ADVANCED WHEEL) =================
class AdvancedWheelView(discord.ui.View):
    def __init__(self, ctx, amount, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.amount = amount
        self.cog = cog
        self.uid = str(ctx.author.id)

    @discord.ui.button(label="🎡 MEGA ÇARKI ÇEVİR!", style=discord.ButtonStyle.blurple)
    async def spin_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu senin çarkın değil!", ephemeral=True)
        button.disabled = True

        # Genişletilmiş ve Dengelenmiş 10 Dilimli Risk Çarkı
        sectors = [
            {"name": "💀 SIFIR (İflas)", "mult": 0.0, "weight": 22},
            {"name": "📉 0.25x Büyük Kayıp", "mult": 0.25, "weight": 15},
            {"name": "📉 0.5x Yarım Kayıp", "mult": 0.5, "weight": 15},
            {"name": "🔄 1x Para İadesi", "mult": 1.0, "weight": 20},
            {"name": "🪙 1.5x Küçük Kâr", "mult": 1.5, "weight": 12},
            {"name": "💵 2x Kazanç", "mult": 2.0, "weight": 8},
            {"name": "🔥 3x Süper", "mult": 3.0, "weight": 4},
            {"name": "⚡ 5x Mega", "mult": 5.0, "weight": 2},
            {"name": "💎 10x ULTRA", "mult": 10.0, "weight": 1.5},
            {"name": "👑 25x EFSANE JACKPOT!", "mult": 25.0, "weight": 0.5}
        ]

        weights = [s["weight"] for s in sectors]
        chosen = random.choices(sectors, weights=weights, k=1)[0]

        if chosen["mult"] == 0.0:
            change = -self.amount
            desc = f"Çark 💀 **{chosen['name']}** diliminde durdu!\n• Kayıp: **-{self.amount:,} V-Coin**"
            color = discord.Color.red()
        elif chosen["mult"] < 1.0:
            loss = int(self.amount * (1.0 - chosen["mult"]))
            change = -loss
            desc = f"Çark {chosen['name']} diliminde durdu!\n• Kayıp: **-{loss:,} V-Coin**"
            color = discord.Color.orange()
        elif chosen["mult"] == 1.0:
            change = 0
            desc = f"Çark 🔄 **Para İadesi** diliminde durdu (`0 V-Coin`)."
            color = discord.Color.gold()
        else:
            total_ret = int(self.amount * chosen["mult"])
            change = total_ret - self.amount
            desc = f"Çark {chosen['name']} diliminde durdu!\n• Kazanılan Kâr: **+{change:,} V-Coin** (Toplam: `{total_ret:,}`)"
            color = discord.Color.green()

        self.cog.update_user_balance(self.uid, change)
        new_bal = self.cog.get_user_balance(self.uid)
        embed = discord.Embed(title="🎡 V-TRACKER | MEGA ÇARKIFELEK", description=f"{desc}\n\n• Güncel Bakiye: `{new_bal:,} V-Coin`", color=color)
        await interaction.response.edit_message(embed=embed, view=self)

# ================= DİĞER OYUNLAR & MENÜ =================
class CoinflipView(discord.ui.View):
    def __init__(self, ctx, amount, cog):
        super().__init__(timeout=60)
        self.ctx = ctx; self.amount = amount; self.cog = cog; self.uid = str(ctx.author.id)

    @discord.ui.button(label="Yazı 🪙", style=discord.ButtonStyle.primary)
    async def yazi(self, interaction: discord.Interaction, b: discord.ui.Button): await self.finish(interaction, "Yazı")
    @discord.ui.button(label="Tura 🦅", style=discord.ButtonStyle.secondary)
    async def tura(self, interaction: discord.Interaction, b: discord.ui.Button): await self.finish(interaction, "Tura")

    async def finish(self, interaction, choice):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Senin oyunun değil!", ephemeral=True)
        for c in self.children: c.disabled = True
        res = random.choice(["Yazı", "Tura"])
        won = (choice == res)
        change = self.amount if won else -self.amount
        self.cog.update_user_balance(self.uid, change)
        new_bal = self.cog.get_user_balance(self.uid)
        col = discord.Color.green() if won else discord.Color.red()
        embed = discord.Embed(title=f"🪙 YAZI TURA | {'KAZANDIN!' if won else 'KAYBETTİN!'}", description=f"Seçim: **{choice}** | Gelen: **{res}**\n• Bakiye: `{new_bal:,} V-Coin`", color=col)
        await interaction.response.edit_message(embed=embed, view=self)

class DiceView(discord.ui.View):
    def __init__(self, ctx, amount, cog):
        super().__init__(timeout=60)
        self.ctx = ctx; self.amount = amount; self.cog = cog; self.uid = str(ctx.author.id)

    @discord.ui.button(label="🎲 Zar At!", style=discord.ButtonStyle.success)
    async def roll(self, interaction: discord.Interaction, b: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Senin oyunun değil!", ephemeral=True)
        b.disabled = True
        u_roll, b_roll = random.randint(1, 6), random.randint(1, 6)
        if u_roll > b_roll:
            change, col, title = self.amount, discord.Color.green(), "KAZANDIN!"
        elif u_roll < b_roll:
            change, col, title = -self.amount, discord.Color.red(), "KAYBETTİN!"
        else:
            change, col, title = 0, discord.Color.gold(), "BERABERE!"
        self.cog.update_user_balance(self.uid, change)
        new_bal = self.cog.get_user_balance(self.uid)
        embed = discord.Embed(title=f"🎲 ZAR DÜELLOSU | {title}", description=f"Sen: **{u_roll}** 🆚 Bot: **{b_roll}**\n• Bakiye: `{new_bal:,} V-Coin`", color=col)
        await interaction.response.edit_message(embed=embed, view=self)

class GameSelectView(discord.ui.View):
    def __init__(self, ctx, amount, cog):
        super().__init__(timeout=30)
        self.ctx = ctx; self.amount = amount; self.cog = cog

    @discord.ui.button(label="Gelişmiş Mayın Tarlası 💣", style=discord.ButtonStyle.danger, row=0)
    async def mines(self, interaction: discord.Interaction, b: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Seçemezsin!", ephemeral=True)
        await interaction.response.edit_message(embed=discord.Embed(title="🧭 V-TRACKER | GELİŞMİŞ MAYIN TARLASI (4x4)", description="4x4 matris yüklendi! Kutuları açmaya başla.", color=discord.Color.blurple()), view=AdvancedMinesView(self.ctx, self.amount, self.cog))

    @discord.ui.button(label="Gelişmiş Çarkıfelek 🎡", style=discord.ButtonStyle.success, row=0)
    async def wheel(self, interaction: discord.Interaction, b: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Seçemezsin!", ephemeral=True)
        await interaction.response.edit_message(embed=discord.Embed(title="🎡 V-TRACKER | MEGA ÇARK", description="Çevirmek için aşağıdaki butona tıkla!", color=discord.Color.blurple()), view=AdvancedWheelView(self.ctx, self.amount, self.cog))

    @discord.ui.button(label="Yazı Tura 🪙", style=discord.ButtonStyle.primary, row=1)
    async def cf(self, interaction: discord.Interaction, b: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Seçemezsin!", ephemeral=True)
        await interaction.response.edit_message(embed=discord.Embed(title="🪙 YAZI TURA", description="Yazı mı Tura mı seç.", color=discord.Color.blurple()), view=CoinflipView(self.ctx, self.amount, self.cog))

    @discord.ui.button(label="Zar Düellosu 🎲", style=discord.ButtonStyle.secondary, row=1)
    async def dice(self, interaction: discord.Interaction, b: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Seçemezsin!", ephemeral=True)
        await interaction.response.edit_message(embed=discord.Embed(title="🎲 ZAR DÜELLOSU", description="Zarını at.", color=discord.Color.blurple()), view=DiceView(self.ctx, self.amount, self.cog))

class Bet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot; self.ECONOMY_FILE = "economy.json"

    def load_json(self, path):
        if not os.path.exists(path): return {}
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}

    def save_json(self, path, data):
        try:
            with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)
        except: pass

    def get_user_balance(self, uid):
        eco = self.load_json(self.ECONOMY_FILE)
        val = eco.get(uid, 1000)
        return int(val.get("balance", val.get("money", 1000))) if isinstance(val, dict) else int(val)

    def update_user_balance(self, uid, amt):
        eco = self.load_json(self.ECONOMY_FILE)
        new_bal = self.get_user_balance(uid) + amt
        eco[uid] = {"balance": new_bal}
        self.save_json(self.ECONOMY_FILE, eco)
        return new_bal

    @commands.command(name="bet", aliases=["kumar", "oyna", "bahis"])
    async def bet(self, ctx, amount: int = None):
        if amount is None or amount <= 0: return await ctx.send("❌ Geçerli bir miktar gir! Örnek: `v!bet 100`")
        bal = self.get_user_balance(str(ctx.author.id))
        if amount > bal: return await ctx.send(f"❌ Yetersiz bakiye! (`{bal:,} V-Coin`)")
        embed = discord.Embed(title="🎮 V-TRACKER.GG | OYUN SEÇİMİ", description=f"Yatırılan: **{amount:,} V-Coin**\nOynamak istediğin gelişmiş oyunu seç:", color=discord.Color.from_rgb(0, 240, 255))
        await ctx.send(embed=embed, view=GameSelectView(ctx, amount, self))

    @commands.command(name="paraver", aliases=["give"])
    async def paraver(self, ctx, member: discord.Member = None, amount: int = None):
        if not member or not amount: return await ctx.send("❌ Örnek kullanım: `v!paraver @Kullanici 50000`")
        if ctx.author.id != OWNER_ID and amount > 1000000:
            return await ctx.send("❌ Normal kullanıcılar en fazla **1,000,000 V-Coin** transfer edebilir!")
        if amount <= 0: return await ctx.send("❌ Pozitif bir miktar girmelisin!")
        new_bal = self.update_user_balance(str(member.id), amount)
        await ctx.send(embed=discord.Embed(title="💰 BAKİYE GÜNCELLENDİ", description=f"{member.mention} kullanıcısına **+{amount:,} V-Coin** eklendi!\n• Yeni Bakiye: `{new_bal:,} V-Coin`", color=discord.Color.gold()))

async def setup(bot): await bot.add_cog(Bet(bot))