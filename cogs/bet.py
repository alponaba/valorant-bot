# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import json
import os
import random

OWNER_ID = 000000000000000000  # Kendi Discord ID'ni buraya yaz

# ================= 3x3, 4x4, 5x5 MAYIN TARLASI VIEW =================
class MinesGridView(discord.ui.View):
    def __init__(self, ctx, amount, cog, size, mines_count):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.amount = amount
        self.cog = cog
        self.size = size
        self.uid = str(ctx.author.id)
        
        total_cells = size * size
        safe_count_total = total_cells - mines_count
        
        self.board = ["safe"] * safe_count_total + ["bomb"] * mines_count
        random.shuffle(self.board)
        self.revealed = [False] * total_cells
        self.game_over = False
        self.safe_count = 0
        
        # Boyuta göre kademeli artan katsayılar
        if size == 3:
            self.multipliers = [1.3, 1.7, 2.3, 3.2, 4.5]
        elif size == 4:
            self.multipliers = [1.4, 1.9, 2.6, 3.5, 4.8, 6.5, 9.0, 13.0]
        else: # 5x5
            self.multipliers = [1.5, 2.1, 2.9, 4.0, 5.5, 7.5, 10.0, 14.0, 19.0, 26.0, 36.0, 50.0]

        for i in range(total_cells):
            btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="❓", row=i // size, custom_id=f"tile_{i}")
            btn.callback = self.make_callback(i)
            self.add_item(btn)
            
        self.cashout_btn = discord.ui.Button(style=discord.ButtonStyle.success, label="💰 Parayı Çek", row=4 if size == 5 else size, disabled=True)
        self.cashout_btn.callback = self.cashout_callback
        self.add_item(self.cashout_btn)

    def make_callback(self, index):
        async def button_callback(interaction: discord.Interaction):
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message("❌ Bu oyunu sen başlatmadın!", ephemeral=True)
            if self.game_over:
                return await interaction.response.send_message("❌ Oyun bitti!", ephemeral=True)
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
                    title="💥 MAYINA BASTIN!",
                    description=f"Patlama yaşadın!\n• Kaybedilen: **-{self.amount:,} V-Coin**\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
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
                max_safe = len(self.multipliers)

                if self.safe_count == max_safe:
                    self.game_over = True
                    for item in self.children: item.disabled = True
                    profit = potential_win - self.amount
                    self.cog.update_user_balance(self.uid, profit)
                    new_bal = self.cog.get_user_balance(self.uid)
                    embed = discord.Embed(
                        title="🎉 KUSURSUZ ZAFER!",
                        description=f"Bütün hazineleri buldun!\n• Çarpan: `{current_mult}x`\n• Kazanılan: **+{potential_win:,} V-Coin**",
                        color=discord.Color.gold()
                    )
                    await interaction.response.edit_message(embed=embed, view=self)
                else:
                    embed = discord.Embed(
                        title=f"🧭 MAYIN TARLASI ({self.size}x{self.size})",
                        description=f"💎 Hazine bulundu!\n• Çarpan: **{current_mult}x**\n• O anki Ödül: `{potential_win:,} V-Coin`",
                        color=discord.Color.blurple()
                    )
                    await interaction.response.edit_message(embed=embed, view=self)
        return button_callback

    async def cashout_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Senin oyunun değil!", ephemeral=True)
        if self.game_over or self.safe_count == 0:
            return await interaction.response.send_message("❌ Henüz ödül almadın!", ephemeral=True)

        self.game_over = True
        for item in self.children: item.disabled = True
        current_mult = self.multipliers[self.safe_count - 1]
        total_payout = int(self.amount * current_mult)
        profit = total_payout - self.amount

        self.cog.update_user_balance(self.uid, profit)
        new_bal = self.cog.get_user_balance(self.uid)
        embed = discord.Embed(
            title="💰 PARA ÇEKİLDİ!",
            description=f"• Bulunan Hazine: `{self.safe_count}/{len(self.multipliers)}`\n• Çarpan: `{current_mult}x`\n• Kâr: **+{profit:,} V-Coin**\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=self)


# ================= 10X10 ULTRA MOD (MODAL TABANLI) =================
class Mines10x10Modal(discord.ui.Modal, title="10x10 Ultra Mayın Tarlası - Kutu Seç"):
    box_num = discord.ui.TextInput(label="Kutu Numarası Yaz (1 - 100)", placeholder="Örn: 42", min_length=1, max_length=3)

    def __init__(self, game_view):
        super().__init__()
        self.game_view = game_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.box_num.value) - 1
            if val < 0 or val >= 100:
                return await interaction.response.send_message("❌ 1 ile 100 arasında bir sayı girmelisin!", ephemeral=True)
        except ValueError:
            return await interaction.response.send_message("❌ Lütfen geçerli bir sayı gir!", ephemeral=True)

        await self.game_view.process_move(interaction, val)


class Mines10x10View(discord.ui.View):
    def __init__(self, ctx, amount, cog):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.amount = amount
        self.cog = cog
        self.uid = str(ctx.author.id)
        
        # 10x10 = 100 kutu, 49 mayın, 51 güvenli
        self.board = ["safe"] * 51 + ["bomb"] * 49
        random.shuffle(self.board)
        self.revealed = [False] * 100
        self.game_over = False
        self.safe_count = 0
        
        # 51 güvenli kutu için kademeli ultra çarpanlar (1.1x ile başlayıp 500x'e kadar gider)
        self.multipliers = [round(1.1 + (i * 0.35), 2) for i in range(51)]

    @discord.ui.button(label="🔢 Kutu Aç (1-100)", style=discord.ButtonStyle.primary)
    async def open_box(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu senin oyunun değil!", ephemeral=True)
        if self.game_over:
            return await interaction.response.send_message("❌ Bu oyun bitti!", ephemeral=True)
        
        modal = Mines10x10Modal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="💰 Parayı Çek", style=discord.ButtonStyle.success)
    async def cashout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Senin oyunun değil!", ephemeral=True)
        if self.game_over or self.safe_count == 0:
            return await interaction.response.send_message("❌ Henüz hazine bulmadın!", ephemeral=True)

        self.game_over = True
        for item in self.children: item.disabled = True
        current_mult = self.multipliers[self.safe_count - 1]
        total_payout = int(self.amount * current_mult)
        profit = total_payout - self.amount

        self.cog.update_user_balance(self.uid, profit)
        new_bal = self.cog.get_user_balance(self.uid)
        embed = discord.Embed(
            title="👑 10X10 ULTRA KASA ÇEKİLDİ!",
            description=f"• Bulunan Hazine: `{self.safe_count}/51`\n• Çarpan: `{current_mult}x`\n• Kâr: **+{profit:,} V-Coin**\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def process_move(self, interaction, index):
        if self.revealed[index]:
            return await interaction.response.send_message("⚠️ Bu kutuyu zaten açtın!", ephemeral=True)

        self.revealed[index] = True
        if self.board[index] == "bomb":
            self.game_over = True
            for item in self.children: item.disabled = True
            self.cog.update_user_balance(self.uid, -self.amount)
            new_bal = self.cog.get_user_balance(self.uid)
            embed = discord.Embed(
                title="💥 10X10 ULTRA | MAYINA BASTIN!",
                description=f"49 Mayından birine çarptın (Kutu #{index+1}).\n• Kayıp: **-{self.amount:,} V-Coin**\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            self.safe_count += 1
            current_mult = self.multipliers[self.safe_count - 1]
            potential_win = int(self.amount * current_mult)

            if self.safe_count == 51:
                self.game_over = True
                for item in self.children: item.disabled = True
                profit = potential_win - self.amount
                self.cog.update_user_balance(self.uid, profit)
                new_bal = self.cog.get_user_balance(self.uid)
                embed = discord.Embed(
                    title="🌟 10X10 ULTRA EFSANESİ!",
                    description=f"Tüm 51 hazineyi buldun!\n• Çarpan: `{current_mult}x`\n• Kazanılan: **+{potential_win:,} V-Coin**",
                    color=discord.Color.gold()
                )
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                embed = discord.Embed(
                    title="⚡ 10X10 ULTRA MAYIN TARLASI",
                    description=f"💎 Kutu #{index+1} temiz çıktı!\n• Bulunan Hazine: `{self.safe_count}/51`\n• Mevcut Çarpan: **{current_mult}x**\n• Ödül: `{potential_win:,} V-Coin`",
                    color=discord.Color.blurple()
                )
                await interaction.response.edit_message(embed=embed, view=self)


# ================= MAYIN TARLASI ZORLUK SEÇİMİ =================
class MinesDifficultyView(discord.ui.View):
    def __init__(self, ctx, amount, cog):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.amount = amount
        self.cog = cog

    @discord.ui.button(label="Kolay (3x3) 🟢", style=discord.ButtonStyle.success)
    async def mode_3x3(self, interaction: discord.Interaction, b: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Seçemezsin!", ephemeral=True)
        await interaction.response.edit_message(embed=discord.Embed(title="🧭 MAYIN TARLASI | 3x3 (Kolay)", description="5 Hazine, 4 Mayın. Başarılar!", color=discord.Color.green()), view=MinesGridView(self.ctx, self.amount, self.cog, 3, 4))

    @discord.ui.button(label="Orta (4x4) 🟡", style=discord.ButtonStyle.primary)
    async def mode_4x4(self, interaction: discord.Interaction, b: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Seçemezsin!", ephemeral=True)
        await interaction.response.edit_message(embed=discord.Embed(title="🧭 MAYIN TARLASI | 4x4 (Orta)", description="8 Hazine, 8 Mayın. Başarılar!", color=discord.Color.blurple()), view=MinesGridView(self.ctx, self.amount, self.cog, 4, 8))

    @discord.ui.button(label="Zor (5x5) 🟠", style=discord.ButtonStyle.danger)
    async def mode_5x5(self, interaction: discord.Interaction, b: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Seçemezsin!", ephemeral=True)
        await interaction.response.edit_message(embed=discord.Embed(title="🧭 MAYIN TARLASI | 5x5 (Zor)", description="12 Hazine, 13 Mayın. Başarılar!", color=discord.Color.orange()), view=MinesGridView(self.ctx, self.amount, self.cog, 5, 13))

    @discord.ui.button(label="Ultra (10x10) 👑", style=discord.ButtonStyle.secondary)
    async def mode_10x10(self, interaction: discord.Interaction, b: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Seçemezsin!", ephemeral=True)
        await interaction.response.edit_message(embed=discord.Embed(title="👑 MAYIN TARLASI | 10x10 (Ultra Mod)", description="51 Hazine, 49 Mayın! Kutu açmak için butona tıkla.", color=discord.Color.purple()), view=Mines10x10View(self.ctx, self.amount, self.cog))


# ================= ÇARKIFELEK (0.1x - 100x) =================
class WheelView(discord.ui.View):
    def __init__(self, ctx, amount, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.amount = amount
        self.cog = cog
        self.uid = str(ctx.author.id)

    @discord.ui.button(label="🎡 Çarkı Çevir!", style=discord.ButtonStyle.blurple)
    async def spin_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu senin çarkın değil!", ephemeral=True)
        button.disabled = True

        # 0.1x ile 100x Arası Katsayılar ve Şans Oranları
        sectors = [
            {"name": "📉 0.1x Ağır Kayıp", "mult": 0.1, "weight": 20},
            {"name": "📉 0.25x Kayıp", "mult": 0.25, "weight": 18},
            {"name": "📉 0.5x Yarım Kayıp", "mult": 0.5, "weight": 15},
            {"name": "🔄 1x Para İadesi", "mult": 1.0, "weight": 22},
            {"name": "🪙 1.5x Kâr", "mult": 1.5, "weight": 12},
            {"name": "💵 2x Kat", "mult": 2.0, "weight": 8},
            {"name": "🔥 5x Süper", "mult": 5.0, "weight": 3},
            {"name": "⚡ 10x Mega", "mult": 10.0, "weight": 1.5},
            {"name": "💎 50x ULTRA", "mult": 50.0, "weight": 0.4},
            {"name": "👑 100x JACKPOT!", "mult": 100.0, "weight": 0.1}
        ]

        weights = [s["weight"] for s in sectors]
        chosen = random.choices(sectors, weights=weights, k=1)[0]

        if chosen["mult"] < 1.0:
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
        embed = discord.Embed(title="🎡 V-TRACKER | ÇARKIFELEK", description=f"{desc}\n\n• Güncel Bakiye: `{new_bal:,} V-Coin`", color=color)
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

    @discord.ui.button(label="Mayın Tarlası 💣", style=discord.ButtonStyle.danger, row=0)
    async def mines(self, interaction: discord.Interaction, b: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Seçemezsin!", ephemeral=True)
        await interaction.response.edit_message(embed=discord.Embed(title="🧭 MAYIN TARLASI | ZORLUK SEÇ", description="Oynamak istediğin zorluk modunu seç:", color=discord.Color.blurple()), view=MinesDifficultyView(self.ctx, self.amount, self.cog))

    @discord.ui.button(label="Çarkıfelek 🎡", style=discord.ButtonStyle.success, row=0)
    async def wheel(self, interaction: discord.Interaction, b: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Seçemezsin!", ephemeral=True)
        await interaction.response.edit_message(embed=discord.Embed(title="🎡 V-TRACKER | ÇARKIFELEK", description="Çevirmek için butona tıkla!", color=discord.Color.blurple()), view=WheelView(self.ctx, self.amount, self.cog))

    @discord.ui.button(label="Yazı Tura 🪙", style=discord.ButtonStyle.primary, row=1)
    async def cf(self, interaction: discord.Interaction, b: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Seçemezsin!", ephemeral=True)
        await interaction.response.edit_message(embed=discord.Embed(title="🪙 YAZI TURA", description="Yazı mı Tura mı seç.", color=discord.Color.blurple()), view=CoinflipView(self.ctx, self.amount, self.cog))

    @discord.ui.button(label="Zar Düellosu 🎲", style=discord.ButtonStyle.secondary, row=1)
    async def dice(self, interaction: discord.Interaction, b: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message("❌ Seçemezsin!", ephemeral=True)
        await interaction.response.edit_message(embed=discord.Embed(title="🎲 ZAR DÜELLOSU", description="Zarını at.", color=discord.Color.blurple()), view=DiceView(self.ctx, self.amount, self.cog))


# ================= MAIN BET COG =================
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
        if amount is None or amount <= 0: 
            return await ctx.send("❌ Geçerli bir miktar gir! Örnek: `v!bet 100`")
        
        # 100k Bahis Sınırı Kuralı
        if amount > 100000:
            return await ctx.send("❌ Tek seferde en fazla **100,000 V-Coin** yatırabilirsin!")

        bal = self.get_user_balance(str(ctx.author.id))
        if amount > bal: 
            return await ctx.send(f"❌ Yetersiz bakiye! (`{bal:,} V-Coin`)")

        embed = discord.Embed(
            title="🎮 V-TRACKER.GG | OYUN SEÇİMİ", 
            description=f"Yatırılan Miktar: **{amount:,} V-Coin**\n\nOynamak istediğin oyunu seç:", 
            color=discord.Color.from_rgb(0, 240, 255)
        )
        await ctx.send(embed=embed, view=GameSelectView(ctx, amount, self))

    @commands.command(name="paraver", aliases=["give"])
    async def paraver(self, ctx, member: discord.Member = None, amount: int = None):
        if not member or not amount: 
            return await ctx.send("❌ Örnek kullanım: `v!paraver @Kullanici 50000`")
        
        # Normal kullanıcılara 1M limit, sahibine limitsiz
        if ctx.author.id != OWNER_ID and amount > 1000000:
            return await ctx.send("❌ Normal kullanıcılar en fazla **1,000,000 V-Coin** transfer edebilir!")
            
        if amount <= 0: 
            return await ctx.send("❌ Pozitif bir miktar girmelisin!")
            
        new_bal = self.update_user_balance(str(member.id), amount)
        embed = discord.Embed(
            title="💰 BAKİYE GÜNCELLENDİ", 
            description=f"{member.mention} kullanıcısına **+{amount:,} V-Coin** eklendi!\n• Yeni Bakiye: `{new_bal:,} V-Coin`", 
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

async def setup(bot): 
    await bot.add_cog(Bet(bot))