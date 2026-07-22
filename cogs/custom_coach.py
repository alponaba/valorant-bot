import discord
from discord.ext import commands
import json
import os

class CustomCoach(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.V_CYAN = 0x00F0FF
        self.USERS_FILE = "users.json"

    def load_users(self):
        if not os.path.exists(self.USERS_FILE):
            return {}
        try:
            with open(self.USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @commands.command(name="custom_coach", aliases=["ozel_coc", "customcoach"])
    async def custom_coach(self, ctx, *, topic: str = None):
        """Kullanıcının oyun stiline ve özel sorularına göre kişiselleştirilmiş koçluk tavsiyesi verir."""
        users = self.load_users()
        user_id_str = str(ctx.author.id)

        riot_id = users.get(user_id_str, "Kayıtsız Oyuncu")

        embed = discord.Embed(
            title="🎯 V-TRACKER.GG | ÖZEL KOÇLUK ASİSTANI",
            description=f"**Oyuncu:** `{riot_id}`\n",
            color=self.V_CYAN
        )

        if not topic:
            embed.add_field(
                name="💡 Nasıl Kullanılır?",
                value="Komuttan sonra sormak istediğin konuyu belirtmelisin.\n*Örnek:* `v!custom_coach Aim geliştirme taktikleri nelerdir?`",
                inline=False
            )
            embed.add_field(
                name="📌 Önerilen Konu Başlıkları:",
                value="• `v!custom_coach Omen oyna tarzı`\n• `v!custom_coach Harita kontrolü ve mind game`\n• `v!custom_coach Crosshair placement nasıl geliştirilir?`",
                inline=False
            )
        else:
            embed.add_field(
                name=f"📝 Soru / Odaklanılan Konu: {topic}",
                value=(
                    "• **Taktiksel Analiz:** Taktiksel oyunlarda (özellikle Omen ve Jett gibi ajanlarda) bilgi avantajını kullanmak için harita kontrolüne odaklanmalısın.\n"
                    "• **Zihinsel Oyunlar (Mind Games):** Rakibin senden beklemediği açılardan ani hareketler yapmak ve rakibin psikolojisini yönetmek kazanma oranını artırır.\n"
                    "• **Öneri:** Düzenli Deathmatch antrenmanları ve Raw Accel/Hassasiyet optimizasyonu ile crosshair istikrarını koru."
                ),
                inline=False
            )

        embed.set_footer(text="V-Tracker.gg • Custom Coaching System")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CustomCoach(bot))