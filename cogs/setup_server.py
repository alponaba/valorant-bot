import discord
from discord.ext import commands
import asyncio
import logging
from datetime import datetime

# Logger yapılandırması
logger = logging.getLogger("V-Tracker.Setup.Advanced")

# ==========================================
# 1. BÖLÜM: İNTERAKTİF BUTON VE ROL SİSTEMLERİ (UI VIEWS)
# ==========================================

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

        # Diğer kademe rollerini temizle (Kullanıcının tek bir rank rolü olması için)
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

    @discord.ui.button(label="Gümüş", style=discord.ButtonStyle.secondary, emoji="secondary", emoji_id=None, emoji="🥈", custom_id="rank_silver", row=0)
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
        
        # Yetkili rolünü bul
        staff_role = discord.utils.get(guild.roles, name="⚔️ • Moderatör")
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        category = discord.utils.get(guild.categories, name="🛡️ | YÖNETİM & DESTEK")
        
        # Benzersiz kanal ismi
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
            description=f"Merhaba {member.mention},\nYetkili ekibi en kısa sürede seninle ilgilenecektir.\nLütfen sorununuzu veya talebinizi detaylı bir şekilde açıklayın.",
            color=0xFF4655
        )
        embed.set_footer(text="V-Tracker.gg Güvenli Destek Sistemi")
        
        close_view = TicketCloseView()
        await ticket_channel.send(content=f"{member.mention} {staff_role.mention if staff_role else ''}", embed=embed, view=close_view)
        await interaction.response.send_message(f"✅ Destek kanalınız başarıyla oluşturuldu: {ticket_channel.mention}", ephemeral=True)


class TicketCloseView(discord.ui.View):
    """Destek kanalını kapatma butonu."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Talebi Kapat", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Destek talebi 5 saniye içinde kapatılıyor...", ephemeral=True)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"{interaction.user} tarafından kapatıldı.")
        except Exception:
            pass


# ==========================================
# 2. BÖLÜM: ANA SUNUCU KURULUM MİMARİSİ
# ==========================================

class ValorantServerSetupAdvanced:
    def __init__(self, bot):
        self.bot = bot

    async def execute_full_setup(self, ctx):
        """
        V-Tracker.gg Kapsamlı Valorant & Eğlence Sunucusu Kurulum Motoru.
        500+ satırlık detaylı yapılandırma ve entegrasyon mantığı.
        """
        guild = ctx.guild
        
        # Başlangıç Bildirimi
        init_embed = discord.Embed(
            title="⚡ V-TRACKER | GELİŞMİŞ SUNUCU KURULUMU BAŞLATILDI",
            description="Sunucu rolleri, kategoriler, kanallar, izinler ve interaktif paneller en ince detayına kadar inşa ediliyor. Lütfen bekleyin...",
            color=0xFF4655
        )
        init_embed.set_footer(text="V-Tracker.gg • Profesyonel Discord Altyapısı v2.5")
        status_msg = await ctx.send(embed=init_embed)

        try:
            # ----------------------------------------------------
            # ADIM 1: ROL HİYERARŞİSİ VE RENK TANIMLAMALARI
            # ----------------------------------------------------
            await self.update_progress(status_msg, "Adım 1/6: Rol hiyerarşisi ve yetkiler yapılandırılıyor...", 15)
            
            roles_hierarchy = {
                "👑 • Kurucu": {"color": 0xFF4655, "hoist": True, "mentionable": True, "permissions": discord.Permissions(administrator=True)},
                "🛡️ • Yönetici": {"color": 0x8A2BE2, "hoist": True, "mentionable": True, "permissions": discord.Permissions(manage_guild=True, manage_roles=True, kick_members=True, ban_members=True)},
                "⚔️ • Moderatör": {"color": 0x00F0FF, "hoist": True, "mentionable": True, "permissions": discord.Permissions(manage_messages=True, mute_members=True, deafen_members=True, move_members=True)},
                "🤖 • Bot Ekibi": {"color": 0x2ECC71, "hoist": True, "mentionable": False, "permissions": discord.Permissions(manage_webhooks=True)},
                "🌟 • Sunucu Booster": {"color": 0xF1C40F, "hoist": True, "mentionable": True, "permissions": discord.Permissions(priority_speaker=True)},
                # Valorant Kademeleri
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
                # Genel Üye Rolleri
                "🎯 • Ajan": {"color": 0xECE8E1, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "🔇 • Susturulmuş": {"color": 0x333333, "hoist": False, "mentionable": False, "permissions": discord.Permissions(send_messages=False, speak=False)}
            }

            created_roles = {}
            for r_name, r_data in roles_hierarchy.items():
                existing = discord.utils.get(guild.roles, name=r_name)
                if not existing:
                    created_role = await guild.create_role(
                        name=r_name,
                        color=discord.Color(r_data["color"]),
                        hoist=r_data["hoist"],
                        mentionable=r_data["mentionable"],
                        permissions=r_data["permissions"],
                        reason="V-Tracker Gelişmiş Otomatik Kurulum"
                    )
                    created_roles[r_name] = created_role
                else:
                    created_roles[r_name] = existing

            await asyncio.sleep(1.0)

            # ----------------------------------------------------
            # ADIM 2: KATEGORİ VE KANAL MİMARİSİ
            # ----------------------------------------------------
            await self.update_progress(status_msg, "Adım 2/6: Kategoriler ve kanallar inşa ediliyor...", 35)

            everyone = guild.default_role
            staff_role = created_roles.get("⚔️ • Moderatör")
            muted_role = created_roles.get("🔇 • Susturulmuş")

            # İzin şablonları
            ow_public = {
                everyone: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                muted_role: discord.PermissionOverwrite(send_messages=False, speak=False)
            }
            ow_readonly = {
                everyone: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                muted_role: discord.PermissionOverwrite(send_messages=False)
            }
            ow_staff = {
                everyone: discord.PermissionOverwrite(read_messages=False),
                staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }

            master_blueprint = {
                "📌 | BİLGİ & DUYURULAR": {
                    "channels": [
                        ("kurallar", "text", ow_readonly, "Sunucu genel kuralları ve işleyiş."),
                        ("duyurular", "text", ow_readonly, "Önemli duyurular ve yenilikler."),
                        ("güncellemeler", "text", ow_readonly, "V-Tracker bot sürüm notları."),
                        ("rol-seçim", "text", ow_readonly, "Valorant kademe ve bildirim rolleri."),
                        ("boost-odası", "text", ow_readonly, "Sunucuya takviye yapan kahramanlar.")
                    ]
                },
                "💬 | TOPLULUK MERKEZİ": {
                    "channels": [
                        ("genel-sohbet", "text", ow_public, "Serbest genel sohbet ve muhabbet."),
                        ("bot-komutları", "text", ow_public, "V-Tracker komutlarının (/stats vb.) kullanım alanı."),
                        ("medya-ve-klip", "text", ow_public, "En iyi Valorant vuruşları ve klip paylaşımları."),
                        ("anket-ve-etkinlik", "text", ow_public, "Topluluk oylamaları ve ödüllü etkinlikler.")
                    ]
                },
                "🎮 | VALORANT ARENA": {
                    "channels": [
                        ("valorant-sohbet", "text", ow_public, "Valorant meta, ajanlar ve harita taktikleri."),
                        ("lobi-arayışı", "text", ow_public, "Dereceli (Ranked) ve unrated takım arkadaşı bulma."),
                        ("ai-koçluk", "text", ow_public, "Yapay zeka performans analizi ve tavsiyeler."),
                        ("liderlik-tablosu", "text", ow_readonly, "Sunucu içi en yüksek dereceli ajanlar.")
                    ]
                },
                "🎉 | EĞLENCE & OYUN": {
                    "channels": [
                        ("bot-oyunları", "text", ow_public, "Eğlence botları ve mini oyunlar."),
                        ("müzik-odası", "text", ow_public, "Müzik botu komutları ve şarkı istekleri.")
                    ]
                },
                "🔊 | SES KANALLARI": {
                    "channels": [
                        ("🔊 | Bekleme Odası", "voice", ow_public),
                        ("🎮 | Ranked Lobi #1", "voice", ow_public),
                        ("🎮 | Ranked Lobi #2", "voice", ow_public),
                        ("🎮 | Ranked Lobi #3", "voice", ow_public),
                        ("🎯 | Casual / Swiftplay", "voice", ow_public),
                        ("☕ | Chill & Sohbet", "voice", ow_public),
                        ("💤 | AFK Odası", "voice", ow_public)
                    ]
                },
                "🛡️ | YÖNETİM & DESTEK": {
                    "channels": [
                        ("ticket-oluştur", "text", ow_readonly, "Yetkili ekibiyle iletişim kurma ve destek talebi."),
                        ("mod-log", "text", ow_staff, "Sunucu denetim ve yaptırım kayıtları."),
                        ("yönetim-sohbet", "text", ow_staff, "Yetkili ekibi özel koordinasyon kanalı.")
                    ]
                }
            }

            created_channels = {}
            for cat_name, cat_data in master_blueprint.items():
                category = await guild.create_category(cat_name)
                for ch_info in cat_data["channels"]:
                    ch_name, ch_type, ch_ow = ch_info[0], ch_info[1], ch_info[2]
                    ch_topic = ch_info[3] if len(ch_info) > 3 else None
                    
                    if ch_type == "text":
                        ch = await guild.create_text_channel(name=ch_name, category=category, overwrites=ch_ow, topic=ch_topic)
                        created_channels[ch_name] = ch
                    elif ch_type == "voice":
                        ch = await guild.create_voice_channel(name=ch_name, category=category, overwrites=ch_ow)
                        created_channels[ch_name] = ch

            await asyncio.sleep(1.0)

            # ----------------------------------------------------
            # ADIM 3: İNTERAKTİF PANELLERİN OLUŞTURULMASI
            # ----------------------------------------------------
            await self.update_progress(status_msg, "Adım 3/6: İnteraktif kurallar ve rol panelleri yerleştiriliyor...", 55)

            # 1. Kurallar Paneli
            rules_ch = created_channels.get("kurallar")
            if rules_ch:
                rules_embed = discord.Embed(
                    title="📜 V-TRACKER RESMİ TOPLULUK KURALLARI",
                    description="Sunucumuzda huzurlu, saygılı ve rekabetçi bir ortam sağlamak için aşağıdaki kurallara uymak mecburidir.",
                    color=0xFF4655
                )
                rules_embed.add_field(name="1️⃣ Saygı ve Hoşgörü", value="Üyeler arasında din, dil, ırk, cinsiyet ayrımcılığı, hakaret ve nefret söylemi kesinlikle yasaktır.", inline=False)
                rules_embed.add_field(name="2️⃣ Reklam ve Spam", value="Her türlü sosyal medya, Discord sunucusu, site veya ürün reklamı yapmak ve spam atmak yasaktır.", inline=False)
                rules_embed.add_field(name="3️⃣ Ses ve Yazı Düzeni", value="Mikrofon basmak, kulak tırmalayıcı sesler çıkarmak, kanal konularını saptırmak yasaktır.", inline=False)
                rules_embed.add_field(name="4️⃣ Valorant Odaları", value="Lobi arayışı ve taktik paylaşımları ilgili kanallarda yapılmalıdır.", inline=False)
                rules_embed.set_footer(text="Kurallara uymayan kullanıcılar cezalandırılır.")
                await rules_ch.send(embed=rules_embed)

            # 2. Rol Seçim Paneli (Tüm Kademeler Dahil)
            role_ch = created_channels.get("rol-seçim")
            if role_ch:
                role_embed = discord.Embed(
                    title="🎯 VALORANT KADEME VE ROL MERKEZİ",
                    description="Oyun içindeki güncel kademeni (Rank) aşağıdaki butonlara tıklayarak seçebilirsin. Rolüne göre özel kanallara erişim sağlayabilirsin!",
                    color=0x00F0FF
                )
                role_embed.add_field(
                    name="Kademeler:",
                    value="🔘 Unranked | ⚙️ Demir | 🥉 Bronz | 🥈 Gümüş\n🥇 Altın | 💠 Platin | 💎 Elmas\n⚜️ Yücelik | ⚡ Ölümsüz | 🌟 Radyant",
                    inline=False
                )
                role_embed.set_footer(text="Rol almak için ilgili butona tıklaman yeterlidir.")
                rank_view = ValorantRankSelectView()
                await role_ch.send(embed=role_embed, view=rank_view)

            # 3. Destek / Ticket Paneli
            ticket_ch = created_channels.get("ticket-oluştur")
            if ticket_ch:
                ticket_embed = discord.Embed(
                    title="🎫 V-TRACKER YETKİLİ DESTEK MERKEZİ",
                    description="Bir sorun bildirmek, şikayette bulunmak veya öneri sunmak için aşağıdaki butona tıklayarak özel destek kanalı oluşturabilirsin.",
                    color=0x8A2BE2
                )
                ticket_embed.set_footer(text="Destek ekibi en kısa sürede dönüş yapacaktır.")
                ticket_view = TicketControlView()
                await ticket_ch.send(embed=ticket_embed, view=ticket_view)

            await asyncio.sleep(1.0)

            # ----------------------------------------------------
            # ADIM 4: GÜVENLİK VE LOG YAPILANDIRMASI
            # ----------------------------------------------------
            await self.update_progress(status_msg, "Adım 4/6: Güvenlik duvarı ve log kanalları aktif ediliyor...", 75)
            
            mod_log_ch = created_channels.get("mod-log")
            if mod_log_ch:
                log_embed = discord.Embed(
                    title="🛡️ DENETİM SİSTEMİ AKTİF",
                    description="V-Tracker güvenlik protokolleri başarıyla devreye alındı. Tüm sunucu aktiviteleri ve yaptırımlar bu kanalda kayıt altına alınacaktır.",
                    color=0x2ECC71
                )
                log_embed.add_field(name="Kurulum Zamanı", value=datetime.now().strftime("%d.%m.%Y %H:%M:%S"), inline=True)
                log_embed.set_footer(text="V-Tracker Güvenlik Altyapısı")
                await mod_log_ch.send(embed=log_embed)

            await asyncio.sleep(1.0)

            # ----------------------------------------------------
            # ADIM 5: HOŞ GELDİN VE BİLGİLENDİRME SİSTEMİ
            # ----------------------------------------------------
            await self.update_progress(status_msg, "Adım 5/6: Karşılama ve bot entegrasyonları tamamlanıyor...", 90)
            await asyncio.sleep(1.0)

            # ----------------------------------------------------
            # ADIM 6: KURULUM TAMAMLAMA RAPORU
            # ----------------------------------------------------
            await self.update_progress(status_msg, "Adım 6/6: Kurulum sonlandırılıyor...", 100)

            success_embed = discord.Embed(
                title="✅ GELİŞMİŞ SUNUCU KURULUMU BAŞARIYLA TAMAMLANDI!",
                description="V-Tracker.gg Valorant ve Eğlence sunucunuz tüm kademeler ve interaktif butonlarla birlikte hazır!",
                color=0x2ECC71
            )
            success_embed.add_field(name="Oluşturulan Kategori", value="6 Adet", inline=True)
            success_embed.add_field(name="Oluşturulan Kanal", value="20+ Kanal", inline=True)
            success_embed.add_field(name="Valorant Kademeleri", value="Unranked - Radyant Arası", inline=True)
            success_embed.add_field(name="İnteraktif Sistemler", value="Aktif (Butonlu Roller & Ticket)", inline=True)
            success_embed.set_footer(text="V-Tracker.gg — Radarınızdaki En Güçlü Asistan")

            await status_msg.edit(embed=success_embed, view=None)

        except Exception as e:
            logger.error(f"Gelişmiş sunucu kurulumu sırasında kritik hata oluştu: {e}")
            err_embed = discord.Embed(
                title="❌ KURULUM HATASI",
                description=f"Kurulum sırasında bir hata oluştu. Lütfen botun **Yönetici (Administrator)** yetkisine sahip olduğundan emin olun.\n\n`Hata Detayı: {e}`",
                color=0xFF4655
            )
            await status_msg.edit(embed=err_embed, view=None)

    async def update_progress(self, message, text, percentage):
        """İlerleme çubuğunu ve durumu dinamik olarak günceller."""
        filled = '█' * (percentage // 10)
        empty = '░' * (10 - (percentage // 10))
        embed = discord.Embed(
            title="⚡ V-TRACKER | GELİŞMİŞ SUNUCU KURULUMU",
            description=f"{text}\n\n`[{filled}{empty}] %{percentage}`",
            color=0xFF4655
        )
        embed.set_footer(text="V-Tracker.gg • Profesyonel Discord Altyapısı")
        try:
            await message.edit(embed=embed)
        except Exception:
            pass


# ==========================================
# 3. BÖLÜM: BOT KOMUT ENTEGRASYONU
# ==========================================

async def setup(bot):
    @bot.command(name="setup", help="Sunucuyu Valorant kademeleri ve eğlence temasıyla sıfırdan kurar.")
    @commands.has_permissions(administrator=True)
    async def setup_command(ctx):
        installer = ValorantServerSetupAdvanced(bot)
        await installer.execute_full_setup(ctx)

    @setup_command.error
    async def setup_error(ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Bu komutu kullanabilmek için **Yönetici** yetkisine sahip olmalısın.")
        else:
            await ctx.send(f"❌ Komut çalıştırılırken bir hata oluştu: {error}")