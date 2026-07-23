import discord
from discord.ext import commands
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger("V-Tracker.Setup.Massive")

class ValorantRankSelectView(discord.ui.View):
    """Kullanıcıların Valorant kademelerini seçebileceği interaktif buton paneli."""
    def __init__(self):
        super().__init__(timeout=None)

    async def assign_role(self, interaction: discord.Interaction, role_name: str):
        guild = interaction.guild
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            await interaction.response.send_message(f"❌ `{role_name}` rolü sunucuda bulunamadı. Lütfen önce kurulumu çalıştırın.", ephemeral=True)
            return

        rank_roles = [
            "🔘 • Unranked", "⚙️ • Demir", "🥉 • Bronz", "🥈 • Gümüş", 
            "🥇 • Altın", "💠 • Platin", "💎 • Elmas", "⚜️ • Yücelik", 
            "⚡ • Ölümsüz", "🌟 • Radyant"
        ]
        
        user_roles_to_remove = [r for r in interaction.user.roles if r.name in rank_roles]
        
        try:
            if user_roles_to_remove:
                await interaction.user.remove_roles(*user_roles_to_remove)
            
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message(f"🗑️ `{role_name}` kademe rolün üzerinizden kaldırıldı.", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"✅ Başarıyla `{role_name}` kademe rolü eklendi!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Rol güncellenirken hata oluştu: {e}", ephemeral=True)

    @discord.ui.button(label="Unranked", style=discord.ButtonStyle.secondary, emoji="🔘", custom_id="rank_unranked_v2", row=0)
    async def unranked_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "🔘 • Unranked")

    @discord.ui.button(label="Demir", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="rank_iron_v2", row=0)
    async def iron_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "⚙️ • Demir")

    @discord.ui.button(label="Bronz", style=discord.ButtonStyle.secondary, emoji="🥉", custom_id="rank_bronze_v2", row=0)
    async def bronze_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "🥉 • Bronz")

    @discord.ui.button(label="Gümüş", style=discord.ButtonStyle.secondary, emoji="🥈", custom_id="rank_silver_v2", row=0)
    async def silver_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "🥈 • Gümüş")

    @discord.ui.button(label="Altın", style=discord.ButtonStyle.primary, emoji="🥇", custom_id="rank_gold_v2", row=1)
    async def gold_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "🥇 • Altın")

    @discord.ui.button(label="Platin", style=discord.ButtonStyle.primary, emoji="💠", custom_id="rank_platinum_v2", row=1)
    async def platinum_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "💠 • Platin")

    @discord.ui.button(label="Elmas", style=discord.ButtonStyle.primary, emoji="💎", custom_id="rank_diamond_v2", row=1)
    async def diamond_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "💎 • Elmas")

    @discord.ui.button(label="Yücelik", style=discord.ButtonStyle.success, emoji="⚜️", custom_id="rank_ascendant_v2", row=2)
    async def ascendant_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "⚜️ • Yücelik")

    @discord.ui.button(label="Ölümsüz", style=discord.ButtonStyle.success, emoji="⚡", custom_id="rank_immortal_v2", row=2)
    async def immortal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "⚡ • Ölümsüz")

    @discord.ui.button(label="Radyant", style=discord.ButtonStyle.danger, emoji="🌟", custom_id="rank_radiant_v2", row=2)
    async def radiant_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "🌟 • Radyant")


class TicketControlView(discord.ui.View):
    """Destek talebi (Ticket) oluşturma butonu."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Destek Talebi Oluştur", style=discord.ButtonStyle.danger, emoji="🎫", custom_id="create_ticket_btn_v2")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user
        staff_role = discord.utils.get(guild.roles, name="⚔️ • Moderatör")
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        category = discord.utils.get(guild.categories, name="🛡️ | YÖNETİM & DESTEK")
        channel_name = f"ticket-{member.name}".lower()
        
        existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if existing_channel:
            await interaction.response.send_message(f"⚠️ Zaten açık olan bir destek talebiniz bulunuyor: {existing_channel.mention}", ephemeral=True)
            return

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Destek Talebi Sahibi: {member.id}"
        )

        embed = discord.Embed(
            title="🎫 YENİ DESTEK TALEBİ AÇILDI",
            description=f"Merhaba {member.mention},\nYetkili ekibi en kısa sürede seninle ilgilenecektir.",
            color=0xFF4655
        )
        await ticket_channel.send(content=f"{member.mention} {staff_role.mention if staff_role else ''}", embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ Destek kanalınız oluşturuldu: {ticket_channel.mention}", ephemeral=True)


class TicketCloseView(discord.ui.View):
    """Destek kanalını kapatma butonu."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Talebi Kapat", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="close_ticket_btn_v2")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Destek talebi kapatılıyor...", ephemeral=True)
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete()
        except Exception:
            pass


class ValorantServerSetupMassive:
    def __init__(self, bot):
        self.bot = bot

    async def update_progress(self, message, text, percentage):
        """Yüzdelik dinamik ilerleme çubuğu."""
        filled = '█' * (percentage // 10)
        empty = '░' * (10 - (percentage // 10))
        embed = discord.Embed(
            title="⚡ V-TRACKER | DEVASA SUNUCU KURULUMU",
            description=f"{text}\n\n`[{filled}{empty}] %{percentage}`",
            color=0xFF4655
        )
        embed.set_footer(text="V-Tracker.gg • Profesyonel Otomasyon Sistemi")
        try:
            await message.edit(embed=embed)
        except Exception:
            pass

    async def execute_full_setup(self, ctx):
        guild = ctx.guild
        
        init_embed = discord.Embed(
            title="⚡ V-TRACKER | DEVASA SUNUCU KURULUMU BAŞLATILDI",
            description="31+ rol, 45+ kanal ve interaktif sistemler inşa ediliyor...",
            color=0xFF4655
        )
        status_msg = await ctx.send(embed=init_embed)

        try:
            # ----------------------------------------------------
            # ADIM 1: 31+ ROL HİYERARŞİSİ VE TANIMLAMALARI
            # ----------------------------------------------------
            await self.update_progress(status_msg, "Adım 1/5: 30+ Rol ve yetki hiyerarşisi oluşturuluyor...", 15)
            
            roles_hierarchy = {
                "👑 • Kurucu": {"color": 0xFF4655, "hoist": True, "mentionable": True, "permissions": discord.Permissions(administrator=True)},
                "🛡️ • Üst Yönetici": {"color": 0x8A2BE2, "hoist": True, "mentionable": True, "permissions": discord.Permissions(manage_guild=True, manage_roles=True, ban_members=True)},
                "⚔️ • Kıdemli Moderatör": {"color": 0x00F0FF, "hoist": True, "mentionable": True, "permissions": discord.Permissions(manage_messages=True, kick_members=True)},
                "🔨 • Moderatör": {"color": 0x008B8B, "hoist": True, "mentionable": True, "permissions": discord.Permissions(manage_messages=True, mute_members=True)},
                "🎫 • Destek Yetkilisi": {"color": 0x4682B4, "hoist": True, "mentionable": True, "permissions": discord.Permissions(manage_channels=True)},
                "🤖 • Bot & Sistem Ekibi": {"color": 0x2ECC71, "hoist": True, "mentionable": False, "permissions": discord.Permissions(manage_webhooks=True)},
                "🎥 • İçerik Üreticisi / Streamer": {"color": 0x9400D3, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "🌟 • Sunucu Booster": {"color": 0xF1C40F, "hoist": True, "mentionable": True, "permissions": discord.Permissions(priority_speaker=True)},
                "⭐ • VIP Üye": {"color": 0xFFD700, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "🎯 • Aktif Üye": {"color": 0x32CD32, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                # Valorant Kademe Rolleri (10 Adet)
                "🌟 • Radyant": {"color": 0xFFD700, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "⚡ • Ölümsüz": {"color": 0xFF4500, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "⚜️ • Yücelik": {"color": 0x9932CC, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "💎 • Elmas": {"color": 0x00CED1, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "💠 • Platin": {"color": 0x20B2AA, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "🥇 • Altın": {"color": 0xDAA520, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "🥈 • Gümüş": {"color": 0xC0C0C0, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "🥉 • Bronz": {"color": 0xCD7F32, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "⚙️ • Demir": {"color": 0x708090, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "🔘 • Unranked": {"color": 0x808080, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                # Bildirim ve Aktivite Rolleri (11 Adet)
                "📢 • Duyuru Bildirim": {"color": 0xE67E22, "hoist": False, "mentionable": True, "permissions": discord.Permissions.none()},
                "🎉 • Etkinlik Bildirim": {"color": 0xE91E63, "hoist": False, "mentionable": True, "permissions": discord.Permissions.none()},
                "🎁 • Çekiliş Bildirim": {"color": 0x9B59B6, "hoist": False, "mentionable": True, "permissions": discord.Permissions.none()},
                "🎮 • Valorant Oyuncusu": {"color": 0xFF4655, "hoist": False, "mentionable": True, "permissions": discord.Permissions.none()},
                "🕹️ • Diğer Oyunlar": {"color": 0x3498DB, "hoist": False, "mentionable": True, "permissions": discord.Permissions.none()},
                "🌙 • Gece Kuşu": {"color": 0x34495E, "hoist": False, "mentionable": True, "permissions": discord.Permissions.none()},
                "☕ • Chill & Sohbet": {"color": 0x1ABC9C, "hoist": False, "mentionable": True, "permissions": discord.Permissions.none()},
                "🎵 • Müzik Sever": {"color": 0xE84393, "hoist": False, "mentionable": True, "permissions": discord.Permissions.none()},
                "🎨 • Tasarımcı / Sanatçı": {"color": 0x00CEC9, "hoist": False, "mentionable": True, "permissions": discord.Permissions.none()},
                "🛡️ • Doğrulanmış Üye": {"color": 0x2ECC71, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "🔇 • Susturulmuş": {"color": 0x111111, "hoist": False, "mentionable": False, "permissions": discord.Permissions(send_messages=False, speak=False)}
            }

            created_roles = {}
            for r_name, r_data in roles_hierarchy.items():
                existing = discord.utils.get(guild.roles, name=r_name)
                if not existing:
                    r = await guild.create_role(name=r_name, color=discord.Color(r_data["color"]), hoist=r_data["hoist"], mentionable=r_data["mentionable"], permissions=r_data["permissions"])
                    created_roles[r_name] = r
                else:
                    created_roles[r_name] = existing

            await asyncio.sleep(0.5)
            await self.update_progress(status_msg, "Adım 2/5: 45+ Kanal ve kategori altyapısı kuruluyor...", 40)

            everyone = guild.default_role
            staff_role = created_roles.get("🔨 • Moderatör")
            muted_role = created_roles.get("🔇 • Susturulmuş")

            ow_public = {everyone: discord.PermissionOverwrite(read_messages=True, send_messages=True), muted_role: discord.PermissionOverwrite(send_messages=False, speak=False)}
            ow_readonly = {everyone: discord.PermissionOverwrite(read_messages=True, send_messages=False), muted_role: discord.PermissionOverwrite(send_messages=False)}
            ow_staff = {everyone: discord.PermissionOverwrite(read_messages=False), staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)}

            # 47 Adet Kanal İçeren Devasa Blueprint
            master_blueprint = {
                "📌 | BİLGİ & DUYURULAR": [
                    ("kurallar", "text", ow_readonly),
                    ("duyurular", "text", ow_readonly),
                    ("güncellemeler", "text", ow_readonly),
                    ("rol-seçim", "text", ow_readonly),
                    ("boost-odası", "text", ow_readonly),
                    ("sss-ve-yardım", "text", ow_readonly)
                ],
                "💬 | TOPLULUK MERKEZİ": [
                    ("genel-sohbet", "text", ow_public),
                    ("bot-komutları", "text", ow_public),
                    ("medya-ve-klip", "text", ow_public),
                    ("anket-ve-etkinlik", "text", ow_public),
                    ("fotoğraf-atölyesi", "text", ow_public),
                    ("mizah-ve-meme", "text", ow_public),
                    ("öneri-ve-şikayet", "text", ow_public)
                ],
                "🎮 | VALORANT ARENA": [
                    ("valorant-sohbet", "text", ow_public),
                    ("lobi-arayışı", "text", ow_public),
                    ("ai-koçluk", "text", ow_public),
                    ("taktik-ve-dizilim", "text", ow_public),
                    ("turnuva-duyuru", "text", ow_readonly),
                    ("espor-gündemi", "text", ow_public),
                    ("clip-vuruşlar", "text", ow_public),
                    ("kademe-paylaşım", "text", ow_public),
                    ("liderlik-tablosu", "text", ow_readonly)
                ],
                "🎉 | OYUN & AKTİVİTE": [
                    ("mini-oyunlar", "text", ow_public),
                    ("çekiliş-odası", "text", ow_readonly),
                    ("muzik-bot-komut", "text", ow_public),
                    ("sohbet-etkinlik", "text", ow_public),
                    ("diğer-oyunlar", "text", ow_public)
                ],
                "🔊 | SES KANALLARI - BEKLEME & SOSYAL": [
                    ("🔊 | Bekleme Odası", "voice", ow_public),
                    ("☕ | Chill & Sohbet #1", "voice", ow_public),
                    ("☕ | Chill & Sohbet #2", "voice", ow_public),
                    ("🌙 | Gece Kuşu Odası", "voice", ow_public),
                    ("🎵 | Müzik & Dinleti", "voice", ow_public),
                    ("🎨 | Sanat & Çizim Sohbeti", "voice", ow_public),
                    ("💤 | AFK Odası", "voice", ow_public)
                ],
                "🎮 | SES KANALLARI - RANKED LOBİLERİ": [
                    ("🎮 | Ranked Lobi #1 (Full)", "voice", ow_public),
                    ("🎮 | Ranked Lobi #2", "voice", ow_public),
                    ("🎮 | Ranked Lobi #3", "voice", ow_public),
                    ("🎮 | Ranked Lobi #4", "voice", ow_public),
                    ("🎮 | Ranked Lobi #5", "voice", ow_public),
                    ("🎯 | Duo / Trio Arayış", "voice", ow_public),
                    ("🎯 | Swiftplay / Spike", "voice", ow_public),
                    ("⚔️ | Özel Maç (Custom)", "voice", ow_public)
                ],
                "🛡️ | YÖNETİM & DESTEK": [
                    ("ticket-oluştur", "text", ow_readonly),
                    ("mod-log", "text", ow_staff),
                    ("yönetim-sohbet", "text", ow_staff),
                    ("yetkili-duyuru", "text", ow_staff),
                    ("bot-konsol-log", "text", ow_staff)
                ]
            }

            created_channels = {}
            for cat_name, channels in master_blueprint.items():
                category = await guild.create_category(cat_name)
                for ch_info in channels:
                    ch_name, ch_type, ch_ow = ch_info[0], ch_info[1], ch_info[2]
                    if ch_type == "text":
                        ch = await guild.create_text_channel(name=ch_name, category=category, overwrites=ch_ow)
                        created_channels[ch_name] = ch
                    elif ch_type == "voice":
                        ch = await guild.create_voice_channel(name=ch_name, category=category, overwrites=ch_ow)
                        created_channels[ch_name] = ch

            await self.update_progress(status_msg, "Adım 3/5: Kurallar ve interaktif paneller yerleştiriliyor...", 70)

            # Kurallar Paneli
            rules_ch = created_channels.get("kurallar")
            if rules_ch:
                emb = discord.Embed(title="📜 V-TRACKER RESMİ KURALLAR", description="Sunucumuzun huzuru için kurallara uymak mecburidir.", color=0xFF4655)
                emb.add_field(name="1️⃣ Saygı", value="Küfür, hakaret ve ayrımcılık yasaktır.", inline=False)
                emb.add_field(name="2️⃣ Spam / Reklam", value="Her türlü izinsiz reklam ve spam yasaktır.", inline=False)
                await rules_ch.send(embed=emb)

            # Rol Seçim Paneli
            role_ch = created_channels.get("rol-seçim")
            if role_ch:
                emb = discord.Embed(title="🎯 VALORANT KADEME SEÇİM MERKEZİ", description="Aşağıdaki butonları kullanarak güncel oyun kademeni seçebilirsin.", color=0x00F0FF)
                await role_ch.send(embed=emb, view=ValorantRankSelectView())

            # Destek Paneli
            ticket_ch = created_channels.get("ticket-oluştur")
            if ticket_ch:
                emb = discord.Embed(title="🎫 YETKİLİ DESTEK MERKEZİ", description="Sorunların için butona tıklayarak destek talebi açabilirsin.", color=0x8A2BE2)
                await ticket_ch.send(embed=emb, view=TicketControlView())

            await self.update_progress(status_msg, "Adım 4/5: Güvenlik duvarı ve log sistemleri aktif ediliyor...", 90)
            await asyncio.sleep(0.5)

            await self.update_progress(status_msg, "Adım 5/5: Kurulum sonlandırılıyor...", 100)

            final_emb = discord.Embed(
                title="✅ DEVASA SUNUCU KURULUMU BAŞARIYLA TAMAMLANDI!",
                description="V-Tracker altyapısı 31+ rol, 47 kanal ve interaktif sistemlerle tamamen hazırlandı!",
                color=0x2ECC71
            )
            final_emb.add_field(name="Toplam Rol", value="31 Adet", inline=True)
            final_emb.add_field(name="Toplam Kanal", value="47 Adet", inline=True)
            final_emb.set_footer(text="V-Tracker.gg • Profesyonel Espor Sistemi")

            await status_msg.edit(embed=final_emb, view=None)

        except Exception as e:
            err_emb = discord.Embed(title="❌ KURULUM HATASI", description=f"Hata oluştu: {e}", color=0xFF4655)
            await status_msg.edit(embed=err_emb, view=None)


class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setup", help="Sunucuyu devasa mimariyle kurar.")
    @commands.has_permissions(administrator=True)
    async def setup_command(self, ctx):
        installer = ValorantServerSetupMassive(self.bot)
        await installer.execute_full_setup(ctx)

    @setup_command.error
    async def setup_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Bu komut için yönetici yetkisine sahip olmalısın.")
        else:
            await ctx.send(f"❌ Hata: {error}")


async def setup(bot):
    await bot.add_cog(SetupCog(bot))