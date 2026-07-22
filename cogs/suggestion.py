import discord
from discord.ext import commands

class Suggestion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.V_CYAN = 0x00F0FF
        self.SERVER_SUGGESTION_CHANNEL = "öneri-kanal"      # Herkesin oyladığı sunucu öneri kanalı
        self.BOT_FEEDBACK_CHANNEL = "🔒-bot-gorus-log"        # Sadece senin (kurucunun) görebileceği bot talep kanalı

    @commands.command(name="öneri", aliases=["oneri", "talep"])
    async def suggestion(self, ctx, suggestion_type: str = None, *, content: str = None):
        """Sunucu veya bot için öneri/talep oluşturur.
        Kullanım: v!öneri sunucu [Öneri metni] veya v!öneri bot [Bot öneri/hata metni]
        """
        if not suggestion_type or not content:
            embed = discord.Embed(
                title="❌ EKSİK KULLANIM",
                description=(
                    "Lütfen öneri türünü belirtin!\n\n"
                    "• **Sunucu önerisi için:** `v!öneri sunucu [öneriniz]`\n"
                    "• **Bot talebi/hatası için:** `v!öneri bot [botla ilgili talebiniz]`"
                ),
                color=0xFF0055
            )
            await ctx.send(embed=embed)
            return

        suggestion_type = suggestion_type.lower()
        guild = ctx.guild

        # 1. SUNUCU İLE İLGİLİ ÖNERİLER (Genel Kanala Gider, Oylanır)
        if suggestion_type == "sunucu":
            channel = discord.utils.get(guild.text_channels, name=self.SERVER_SUGGESTION_CHANNEL)
            if not channel:
                channel = ctx.channel # Kanal yoksa komutun yazıldığı yere atar

            embed = discord.Embed(
                title="💡 YENİ SUNUCU ÖNERİSİ",
                description=content,
                color=self.V_CYAN
            )
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
            embed.set_footer(text="Oylamak için aşağıdaki emojileri kullanın!")
            
            msg = await channel.send(embed=embed)
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
            await ctx.message.delete() # Komut kirliliği olmasın diye kullanıcının mesajını siliyoruz

        # 2. BOT İLE İLGİLİ TALEPLER (Sadece Senin Görebileceğin Gizli Kanala Gider)
        elif suggestion_type == "bot":
            channel = discord.utils.get(guild.text_channels, name=self.BOT_FEEDBACK_CHANNEL)
            
            embed = discord.Embed(
                title="🤖 YENİ BOT TALEBİ / GERİ BİLDİRİM",
                description=content,
                color=0xFFD700
            )
            embed.add_field(name="Gönderen:", value=f"{ctx.author.mention} (`{ctx.author.id}`)", inline=False)
            embed.set_footer(text="Bu mesaj gizli kurucu/bot log kanalındadır.")

            if channel:
                await channel.send(embed=embed)
            else:
                # Eğer özel gizli kanal henüz kurulmadıysa doğrudan bot sahibine DM atabilir veya bilgilendirme geçebilirsin
                await ctx.author.send("⚠️ `🔒-bot-gorus-log` adında bir kanal bulunamadığı için bot talebiniz işleme alınamadı. Lütfen sunucuda bu kanalı oluşturun.", embed=embed)

            await ctx.message.delete()
            await ctx.send("✅ Botla ilgili talebiniz gizli yönetici paneline iletildi. Teşekkürler!", delete_after=5)

        else:
            await ctx.send("❌ Geçersiz tür! `sunucu` veya `bot` yazmalısın. Örn: `v!öneri bot Ek özellik eklensin`", delete_after=6)

async def setup(bot):
    await bot.add_cog(Suggestion(bot))