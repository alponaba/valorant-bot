# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import json
import os
import random

# Kendi Discord ID'ni buraya yazmalısın (Sınırsız paraver yetkisi için)
OWNER_ID = 000000000000000000  # Örn: 123456789012345678

# ================= MINEFIELD (MAYIN TARLASI) VIEW =================
class MinesView(discord.ui.View):
    def __init__(self, ctx, amount, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.amount = amount
        self.cog = cog
        self.uid = str(ctx.author.id)
        
        self.board = ["safe"] * 7 + ["bomb"] * 2
        random.shuffle(self.board)
        self.revealed = [False] * 9
        self.game_over = False
        self.safe_count = 0
        
        self.multipliers = [1.2, 1.4, 1.8, 2.3, 3.0, 4.5, 7.0]

        for i in range(9):
            btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="❓", row=i//3, custom_id=f"tile_{i}")
            btn.callback = self.make_callback(i)
            self.add_item(btn)
            
        self.cashout_btn = discord.ui.Button(style=discord.ButtonStyle.success, label="💰 Parayı Çek", row=3, disabled=True)
        self.cashout_btn.callback = self.cashout_callback
        self.add_item(self.cashout_btn)

    def make_callback(self, index):
        async def button_callback(interaction: discord.Interaction):
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message("❌ Bu oyunu sen başlatmadın!", ephemeral=True)
            
            if self.game_over:
                return await interaction.response.send_message("❌ Bu oyun zaten sona erdi!", ephemeral=True)

            if self.revealed[index]:
                return await interaction.response.send_message("⚠️ Bu kutuyu zaten açtın!", ephemeral=True)

            self.revealed[index] = True
            tile_type = self.board[index]
            button = self.children[index]

            if tile_type == "bomb":
                self.game_over = True
                for idx, item in enumerate(self.children[:-1]):
                    item.disabled = True
                    if self.board[idx] == "bomb":
                        item.style = discord.ButtonStyle.danger
                        item.label = "💣"
                    else:
                        item.style = discord.ButtonStyle.success
                        item.label = "💎"
                self.cashout_btn.disabled = True

                self.cog.update_user_balance(self.uid, -self.amount)
                new_bal = self.cog.get_user_balance(self.uid)
                
                embed = discord.Embed(
                    title="💥 MAYINA BASTIN!",
                    description=f"Maalesef mayına denk geldin!\n• Kaybedilen: **-{self.amount:,} V-Coin**\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                button.style = discord.ButtonStyle.success
                button.label = "💎"
                self.safe_count += 1
                self.cashout_btn.disabled = False

                current_mult = self.multipliers[self.safe_count - 1]
                potential_win = int(self.amount * current_mult)

                if self.safe_count == 7:
                    self.game_over = True
                    for item in self.children:
                        item.disabled = True
                    
                    profit = potential_win - self.amount
                    self.cog.update_user_balance(self.uid, profit)
                    new_bal = self.cog.get_user_balance(self.uid)
                    
                    embed = discord.Embed(
                        title="🎉 7 HAZİNENİN HEPSİNİ BULDUN!",
                        description=f"Kusursuz zafer! Tüm mayınlardan kaçtın.\n• Çarpan: `{current_mult}x`\n• Kazanılan: **+{potential_win:,} V-Coin**\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
                        color=discord.Color.green()
                    )
                    await interaction.response.edit_message(embed=embed, view=self)
                else:
                    embed = discord.Embed(
                        title="🧭 V-TRACKER | MAYIN TARLASI",
                        description=f"💎 Harika! Hazineyi buldun.\n• Mevcut Çarpan: **{current_mult}x**\n• O anki Ödül: `{potential_win:,} V-Coin`\n• İstersen **Parayı Çek** butonuna basıp kazancını alabilirsin!",
                        color=discord.Color.blurple()
                    )
                    await interaction.response.edit_message(embed=embed, view=self)

        return button_callback

    async def cashout_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu senin oyunun değil!", ephemeral=True)
        
        if self.game_over or self.safe_count == 0:
            return await interaction.response.send_message("❌ Henüz hiç hazine bulamadın!", ephemeral=True)

        self.game_over = True
        for item in self.children:
            item.disabled = True

        current_mult = self.multipliers[self.safe_count - 1]
        total_payout = int(self.amount * current_mult)
        profit = total_payout - self.amount

        self.cog.update_user_balance(self.uid, profit)
        new_bal = self.cog.get_user_balance(self.uid)

        embed = discord.Embed(
            title="💰 PARA BAŞARIYLA ÇEKİLDİ!",
            description=f"Risk almayı bıraktın ve paranı güvenceye aldın!\n• Bulunan Hazine: `{self.safe_count}/7`\n• Çarpan: `{current_mult}x`\n• Eklenen Kâr: **+{profit:,} V-Coin**\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=embed, view=self)

# ================= ŞANS ÇARKI (WHEEL) VIEW =================
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

        sectors = [
            {"name": "0x (İflas)", "mult": 0.0, "weight": 20, "emoji": "💀"},
            {"name": "0.5x (Yarım Kayıp)", "mult": 0.5, "weight": 20, "emoji": "📉"},
            {"name": "1x (Para İadesi)", "mult": 1.0, "weight": 25, "emoji": "🔄"},
            {"name": "1.5x Kâr", "mult": 1.5, "weight": 15, "emoji": "🪙"},
            {"name": "2x Kat", "mult": 2.0, "weight": 10, "emoji": "💵"},
            {"name": "3x Süper", "mult": 3.0, "weight": 6, "emoji": "🔥"},
            {"name": "5x Mega", "mult": 5.0, "weight": 3, "emoji": "⚡"},
            {"name": "10x JACKPOT!", "mult": 10.0, "weight": 1, "emoji": "💎"}
        ]

        weights = [s["weight"] for s in sectors]
        chosen = random.choices(sectors, weights=weights, k=1)[0]

        if chosen["mult"] == 0.0:
            change = -self.amount
            desc_text = f"Çark 💀 **0x (İflas)** diliminde durdu!\n• Kaybedilen: **-{self.amount:,} V-Coin**"
            color = discord.Color.red()
        elif chosen["mult"] < 1.0:
            loss = int(self.amount * (1.0 - chosen["mult"]))
            change = -loss
            desc_text = f"Çark {chosen['emoji']} **{chosen['name']}** diliminde durdu!\n• Kaybedilen: **-{loss:,} V-Coin**"
            color = discord.Color.orange()
        elif chosen["mult"] == 1.0:
            change = 0
            desc_text = f"Çark {chosen['emoji']} **{chosen['name']}** diliminde durdu!\n• Ne kazandın ne kaybettin (`0 V-Coin`)."
            color = discord.Color.gold()
        else:
            total_return = int(self.amount * chosen["mult"])
            change = total_return - self.amount
            desc_text = f"Çark {chosen['emoji']} **{chosen['name']}** diliminde durdu!\n• Kazanılan Kâr: **+{change:,} V-Coin** (Toplam Ödül: `{total_return:,} V-Coin`)"
            color = discord.Color.green()

        self.cog.update_user_balance(self.uid, change)
        new_bal = self.cog.get_user_balance(self.uid)

        embed = discord.Embed(
            title="🎡 V-TRACKER | ŞANS ÇARKI",
            description=f"{desc_text}\n\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
            color=color
        )
        await interaction.response.edit_message(embed=embed, view=self)

# ================= YAZI TURA (COINFLIP) VIEW =================
class CoinflipView(discord.ui.View):
    def __init__(self, ctx, amount, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.amount = amount
        self.cog = cog
        self.uid = str(ctx.author.id)

    @discord.ui.button(label="Yazı 🪙", style=discord.ButtonStyle.primary)
    async def yazi_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_coinflip(interaction, "Yazı")

    @discord.ui.button(label="Tura 🦅", style=discord.ButtonStyle.secondary)
    async def tura_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play_coinflip(interaction, "Tura")

    async def play_coinflip(self, interaction, choice):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu senin oyunun değil!", ephemeral=True)

        for child in self.children:
            child.disabled = True

        result = random.choice(["Yazı", "Tura"])
        won = (choice == result)

        if won:
            change = self.amount
            self.cog.update_user_balance(self.uid, change)
            new_bal = self.cog.get_user_balance(self.uid)
            embed = discord.Embed(
                title="🪙 YAZI TURA | KAZANDIN!",
                description=f"Seçimin: **{choice}** | Gelen: **{result}**\n• Kazanılan: **+{self.amount:,} V-Coin**\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
                color=discord.Color.green()
            )
        else:
            change = -self.amount
            self.cog.update_user_balance(self.uid, change)
            new_bal = self.cog.get_user_balance(self.uid)
            embed = discord.Embed(
                title="🪙 YAZI TURA | KAYBETTİN!",
                description=f"Seçimin: **{choice}** | Gelen: **{result}**\n• Kaybedilen: **-{self.amount:,} V-Coin**\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
                color=discord.Color.red()
            )

        await interaction.response.edit_message(embed=embed, view=self)

# ================= ZAR DÜELLOSU (DICE) VIEW =================
class DiceView(discord.ui.View):
    def __init__(self, ctx, amount, cog):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.amount = amount
        self.cog = cog
        self.uid = str(ctx.author.id)

    @discord.ui.button(label="🎲 Zar At!", style=discord.ButtonStyle.success)
    async def roll_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu senin oyunun değil!", ephemeral=True)

        button.disabled = True

        user_roll = random.randint(1, 6)
        bot_roll = random.randint(1, 6)

        if user_roll > bot_roll:
            change = self.amount
            self.cog.update_user_balance(self.uid, change)
            new_bal = self.cog.get_user_balance(self.uid)
            embed = discord.Embed(
                title="🎲 ZAR DÜELLOSU | KAZANDIN!",
                description=f"Senin Zarin: **{user_roll}** 🆚 Botun Zari: **{bot_roll}**\n• Kazanılan: **+{self.amount:,} V-Coin**\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
                color=discord.Color.green()
            )
        elif user_roll < bot_roll:
            change = -self.amount
            self.cog.update_user_balance(self.uid, change)
            new_bal = self.cog.get_user_balance(self.uid)
            embed = discord.Embed(
                title="🎲 ZAR DÜELLOSU | KAYBETTİN!",
                description=f"Senin Zarin: **{user_roll}** 🆚 Botun Zari: **{bot_roll}**\n• Kaybedilen: **-{self.amount:,} V-Coin**\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
                color=discord.Color.red()
            )
        else:
            new_bal = self.cog.get_user_balance(self.uid)
            embed = discord.Embed(
                title="🎲 ZAR DÜELLOSU | BERABERE!",
                description=f"Senin Zarin: **{user_roll}** 🆚 Botun Zari: **{bot_roll}**\n• Puan iade edildi (`0 V-Coin`).\n• Güncel Bakiye: `{new_bal:,} V-Coin`",
                color=discord.Color.gold()
            )

        await interaction.response.edit_message(embed=embed, view=self)

# ================= GAME SELECTOR VIEW (4 OYUN) =================
class GameSelectView(discord.ui.View):
    def __init__(self, ctx, amount, cog):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.amount = amount
        self.cog = cog

    @discord.ui.button(label="Mayın Tarlası 💣", style=discord.ButtonStyle.danger, row=0)
    async def mines_select(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu seçimi sen yapamazsın!", ephemeral=True)
        view = MinesView(self.ctx, self.amount, self.cog)
        embed = discord.Embed(
            title="🧭 V-TRACKER | MAYIN TARLASI",
            description=f"Oyun başladı! Kutuları açarak ilerle.\n• Yatırılan: `{self.amount:,} V-Coin`\n• Dilediğin an **Parayı Çek** butonuna basarak kazancını alabilirsin!",
            color=discord.Color.blurple()
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Şans Çarkı 🎡", style=discord.ButtonStyle.success, row=0)
    async def wheel_select(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu seçimi sen yapamazsın!", ephemeral=True)
        view = WheelView(self.ctx, self.amount, self.cog)
        embed = discord.Embed(
            title="🎡 V-TRACKER | ŞANS ÇARKI",
            description=f"Çark çevrilmeye hazır!\n• Yatırılan: `{self.amount:,} V-Coin`\n• 8 farklı dilim seni bekliyor.",
            color=discord.Color.blurple()
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Yazı Tura 🪙", style=discord.ButtonStyle.primary, row=1)
    async def coinflip_select(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu seçimi sen yapamazsın!", ephemeral=True)
        view = CoinflipView(self.ctx, self.amount, self.cog)
        embed = discord.Embed(
            title="🪙 V-TRACKER | YAZI TURA",
            description=f"Yazı mı Tura mı? Aşağıdaki butonlardan birini seçerek bahsini başlat!\n• Yatırılan: `{self.amount:,} V-Coin`",
            color=discord.Color.blurple()
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Zar Düellosu 🎲", style=discord.ButtonStyle.secondary, row=1)
    async def dice_select(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("❌ Bu seçimi sen yapamazsın!", ephemeral=True)
        view = DiceView(self.ctx, self.amount, self.cog)
        embed = discord.Embed(
            title="🎲 V-TRACKER | ZAR DÜELLOSU",
            description=f"Bot ile zarlarınızı yarıştırın!\n• Yatırılan: `{self.amount:,} V-Coin`",
            color=discord.Color.blurple()
        )
        await interaction.response.edit_message(embed=embed, view=view)

# ================= MAIN BET COG =================
class Bet(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ECONOMY_FILE = "economy.json"

    def load_json(self, filepath):
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_json(self, filepath, data):
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def get_user_balance(self, user_id_str):
        eco = self.load_json(self.ECONOMY_FILE)
        val = eco.get(user_id_str, 1000)
        if isinstance(val, dict):
            return int(val.get("balance", val.get("money", 1000)))
        try:
            return int(val)
        except Exception:
            return 1000

    def update_user_balance(self, user_id_str, amount):
        eco = self.load_json(self.ECONOMY_FILE)
        current = self.get_user_balance(user_id_str)
        new_balance = current + amount
        eco[user_id_str] = {"balance": new_balance}
        self.save_json(self.ECONOMY_FILE, eco)
        return new_balance

    @commands.command(name="bet", aliases=["kumar", "oyna", "bahis"])
    async def bet(self, ctx, amount: int = None):
        """İnteraktif bahis oyunları menüsünü açar."""
        if amount is None:
            await ctx.send("❌ Lütfen yatırmak istediğin V-Coin miktarını yaz! Örnek: `v!bet 100`")
            return
            
        uid = str(ctx.author.id)
        current_bal = self.get_user_balance(uid)

        if amount <= 0:
            await ctx.send("❌ Geçersiz miktar! 0'dan büyük bir değer girmelisin.")
            return

        if amount > current_bal:
            await ctx.send(f"❌ Yetersiz bakiye! Mevcut bakiyen: **{current_bal:,} V-Coin**")
            return

        embed = discord.Embed(
            title="🎮 V-TRACKER.GG | OYUN SEÇİMİ",
            description=f"Yatırılan Miktar: **{amount:,} V-Coin**\n\nOynamak istediğin oyunu aşağıdaki butonlardan seç:",
            color=discord.Color.from_rgb(0, 240, 255)
        )
        view = GameSelectView(ctx, amount, self)
        await ctx.send(embed=embed, view=view)

    @commands.command(name="paraver", aliases=["give"])
    async def paraver(self, ctx, member: discord.Member = None, amount: int = None):
        """Kullanıcılara para verir. Normal kullanıcılara max 1M V-Coin sınırı vardır, sahibine yoktur."""
        if member is None or amount is None:
            return await ctx.send("❌ Hatalı kullanım! Örnek: `v!paraver @Kullanici 50000`")

        # 1M V-Coin sınırı kontrolü (Sahip dışındakiler için)
        if ctx.author.id != OWNER_ID:
            if amount > 1000000:
                return await ctx.send("❌ Normal kullanıcılar tek seferde en fazla **1,000,000 V-Coin** transfer edebilir!")

        if amount <= 0:
            return await ctx.send("❌ 0 veya daha düşük bir miktar veremezsin!")

        target_id = str(member.id)
        new_balance = self.update_user_balance(target_id, amount)

        embed = discord.Embed(
            title="💰 BAKİYE GÜNCELLENDİ",
            description=f"{member.mention} adlı kullanıcıya **+{amount:,} V-Coin** eklendi!\n• Yeni Bakiye: `{new_balance:,} V-Coin`",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Bet(bot))