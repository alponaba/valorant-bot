import discord
from discord.ext import commands
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger("V-Tracker.Setup.Advanced")

class ValorantRankSelectView(discord.ui.View):
    """Kullanıcıların kendi Valorant kademelerini seçebileceği interaktif buton paneli."""
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
            await interaction.response.send_message(f"❌ Rol güncellenirken bir hata oluştu: {e}", ephemeral=True)

    @discord.ui.button(label="Unranked", style=discord.ButtonStyle.secondary, emoji="🔘", custom_id="rank_unranked", row=0)
    async def unranked_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "🔘 • Unranked")

    @discord.ui.button(label="Demir", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="rank_iron", row=0)
    async def iron_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "⚙️ • Demir")

    @discord.ui.button(label="Bronz", style=discord.ButtonStyle.secondary, emoji="🥉", custom_id="rank_bronze", row=0)
    async def bronze_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "🥉 • Bronz")

    @discord.ui.button(label="Gümüş", style=discord.ButtonStyle.secondary, emoji="🥈", custom_id="rank_silver", row=0)
    async def silver_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "🥈 • Gümüş")

    @discord.ui.button(label="Altın", style=discord.ButtonStyle.primary, emoji="🥇", custom_id="rank_gold", row=1)
    async def gold_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "🥇 • Altın")

    @discord.ui.button(label="Platin", style=discord.ButtonStyle.primary, emoji="💠", custom_id="rank_platinum", row=1)
    async def platinum_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "💠 • Platin")

    @discord.ui.button(label="Elmas", style=discord.ButtonStyle.primary, emoji="💎", custom_id="rank_diamond", row=1)
    async def diamond_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "💎 • Elmas")

    @discord.ui.button(label="Yücelik", style=discord.ButtonStyle.success, emoji="⚜️", custom_id="rank_ascendant", row=2)
    async def ascendant_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "⚜️ • Yücelik")

    @discord.ui.button(label="Ölümsüz", style=discord.ButtonStyle.success, emoji="⚡", custom_id="rank_immortal", row=2)
    async def immortal_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "⚡ • Ölümsüz")

    @discord.ui.button(label="Radyant", style=discord.ButtonStyle.danger, emoji="🌟", custom_id="rank_radiant", row=2)
    async def radiant_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "🌟 • Radyant")


class TicketControlView(discord.ui.View):
    """Destek talebi (Ticket) oluşturma butonu."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Destek Talebi Oluştur", style=discord.ButtonStyle.danger, emoji="🎫", custom_id="create_ticket_btn")
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

    @discord.ui.button(label="Talebi Kapat", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Destek talebi kapatılıyor...", ephemeral=True)
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete()
        except Exception:
            pass


class ValorantServerSetupAdvanced:
    def __init__(self, bot):
        self.bot = bot

    async def execute_full_setup(self, ctx):
        guild = ctx.guild
        init_embed = discord.Embed(
            title="⚡ V-TRACKER | GELİŞMİŞ SUNUCU KURULUMU",
            description="Sunucu mimarisi kuruluyor, lütfen bekleyin...",
            color=0xFF4655
        )
        status_msg = await ctx.send(embed=init_embed)

        try:
            roles_hierarchy = {
                "👑 • Kurucu": {"color": 0xFF4655, "hoist": True, "mentionable": True, "permissions": discord.Permissions(administrator=True)},
                "🛡️ • Yönetici": {"color": 0x8A2BE2, "hoist": True, "mentionable": True, "permissions": discord.Permissions(manage_guild=True, manage_roles=True, kick_members=True, ban_members=True)},
                "⚔️ • Moderatör": {"color": 0x00F0FF, "hoist": True, "mentionable": True, "permissions": discord.Permissions(manage_messages=True, mute_members=True)},
                "🤖 • Bot Ekibi": {"color": 0x2ECC71, "hoist": True, "mentionable": False, "permissions": discord.Permissions(manage_webhooks=True)},
                "🌟 • Sunucu Booster": {"color": 0xF1C40F, "hoist": True, "mentionable": True, "permissions": discord.Permissions(priority_speaker=True)},
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
                "🎯 • Ajan": {"color": 0xECE8E1, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "🔇 • Susturulmuş": {"color": 0x333333, "hoist": False, "mentionable": False, "permissions": discord.Permissions(send_messages=False, speak=False)}
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

            everyone = guild.default_role
            staff_role = created_roles.get("⚔️ • Moderatör")
            muted_role = created_roles.get("🔇 • Susturulmuş")

            ow_public = {everyone: discord.PermissionOverwrite(read_messages=True, send_messages=True), muted_role: discord.PermissionOverwrite(send_messages=False, speak=False)}
            ow_readonly = {everyone: discord.PermissionOverwrite(read_messages=True, send_messages=False), muted_role: discord.PermissionOverwrite(send_messages=False)}
            ow_staff = {everyone: discord.PermissionOverwrite(read_messages=False), staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)}

            master_blueprint = {
                "📌 | BİLGİ & DUYURULAR": [
                    ("kurallar", "text", ow_readonly),
                    ("duyurular", "text", ow_readonly),
                    ("rol-seçim", "text", ow_readonly)
                ],
                "💬 | TOPLULUK MERKEZİ": [
                    ("genel-sohbet", "text", ow_public),
                    ("bot-komutları", "text", ow_public),
                    ("medya-ve-klip", "text", ow_public)
                ],
                "🎮 | VALORANT ARENA": [
                    ("valorant-sohbet", "text", ow_public),
                    ("lobi-arayışı", "text", ow_public)
                ],
                "🔊 | SES KANALLARI": [
                    ("🔊 | Bekleme Odası", "voice", ow_public),
                    ("🎮 | Ranked Lobi #1", "voice", ow_public),
                    ("🎮 | Ranked Lobi #2", "voice", ow_public)
                ],
                "🛡️ | YÖNETİM & DESTEK": [
                    ("ticket-oluştur", "text", ow_readonly),
                    ("mod-log", "text", ow_staff)
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

            rules_ch = created_channels.get("kurallar")
            if rules_ch:
                emb = discord.Embed(title="📜 V-TRACKER KURALLAR", description="Sunucu kuralları bu kanalda yer almaktadır.", color=0xFF4655)
                await rules_ch.send(embed=emb)

            role_ch = created_channels.get("rol-seçim")
            if role_ch:
                emb = discord.Embed(title="🎯 VALORANT KADEME SEÇİMİ", description="Butonlara tıklayarak kademeni seçebilirsin.", color=0x00F0FF)
                await role_ch.send(embed=emb, view=ValorantRankSelectView())

            ticket_ch = created_channels.get("ticket-oluştur")
            if ticket_ch:
                emb = discord.Embed(title="🎫 DESTEK MERKEZİ", description="Destek talebi açmak için aşağıdaki butona tıkla.", color=0x8A2BE2)
                await ticket_ch.send(embed=emb, view=TicketControlView())

            await status_msg.edit(content="✅ V-Tracker sunucu kurulumu başarıyla tamamlandı!", embed=None, view=None)

        except Exception as e:
            await status_msg.edit(content=f"❌ Kurulum sırasında hata oluştu: {e}", embed=None, view=None)


class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setup", help="Sunucuyu Valorant kademeleriyle kurar.")
    @commands.has_permissions(administrator=True)
    async def setup_command(self, ctx):
        installer = ValorantServerSetupAdvanced(self.bot)
        await installer.execute_full_setup(ctx)

    @setup_command.error
    async def setup_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Bu komutu kullanmak için yönetici yetkisine sahip olmalısın.")
        else:
            await ctx.send(f"❌ Hata: {error}")


async def setup(bot):
    await bot.add_cog(SetupCog(bot))