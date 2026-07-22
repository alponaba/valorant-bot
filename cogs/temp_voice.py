import discord
from discord.ext import commands

class TempVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CREATOR_CHANNEL_NAME = "➕ | Oda Oluştur"

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild

        # 1. Kullanıcı "Oda Oluştur" kanalına katıldıysa
        if after.channel and after.channel.name == self.CREATOR_CHANNEL_NAME:
            category = after.channel.category
            
            # Yeni özel oda adını kullanıcının adına göre yapıyoruz
            channel_name = f"🔊 {member.display_name}'in Odası"
            
            # Özel ses kanalını oluşturuyoruz
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=True),
                member: discord.PermissionOverwrite(manage_channels=True, manage_permissions=True, mute_members=True)
            }
            
            new_channel = await guild.create_voice_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason="[Temp-Voice] Geçici özel oda açıldı."
            )
            
            # Kullanıcıyı hemen yeni açtığı odaya taşıyoruz
            try:
                await member.move_to(new_channel, reason="[Temp-Voice] Kullanıcı kendi odasına taşındı.")
            except Exception:
                pass

        # 2. Kullanıcı odadan çıktığında boş kaldıysa kanalı silme kontrolü
        if before.channel and before.channel != after.channel:
            # Eğer kanal "'in Odası" ile bitiyorsa ve içinde kimse kalmadıysa sil
            if "Odası" in before.channel.name and len(before.channel.members) == 0:
                try:
                    await before.channel.delete(reason="[Temp-Voice] Boş kalan geçici oda silindi.")
                except Exception:
                    pass

async def setup(bot):
    await bot.add_cog(TempVoice(bot))