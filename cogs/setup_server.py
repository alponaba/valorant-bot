import discord
from discord.ext import commands
import asyncio
import logging

# Logger yapılandırması
logger = logging.getLogger("V-Tracker.Setup")

class ValorantServerSetup:
    def __init__(self, bot):
        self.bot = bot

    async def execute_setup(self, ctx):
        """
        V-Tracker.gg Valorant ve Eğlence Temalı Otomatik Sunucu Kurulum Sistemi.
        Bu fonksiyon, sunucuyu profesyonel bir espor ve topluluk merkezine dönüştürür.
        """
        guild = ctx.guild
        
        # Kurulumun başladığını belirten başlangıç mesajı / embed
        start_embed = discord.Embed(
            title="⚡ V-TRACKER | OTOMATİK SUNUCU KURULUMU",
            description="Sunucunuz Valorant ve Eğlence temasına uygun olarak yapılandırılıyor. Lütfen işlem tamamlanana kadar bekleyin...",
            color=0xFF4655
        )
        start_embed.set_footer(text="V-Tracker.gg • Profesyonel Discord Altyapısı")
        status_msg = await ctx.send(embed=start_embed)

        try:
            # 1. ADIM: ROL HİYERARŞİSİ VE OLUŞTURULMASI
            await self.update_status(status_msg, "Adım 1/5: Roller ve yetkiler oluşturuluyor...", 10)
            roles_config = {
                "👑 • Kurucu": {"color": 0xFF4655, "hoist": True, "mentionable": True, "permissions": discord.Permissions(administrator=True)},
                "🛡️ • Yönetici": {"color": 0x8A2BE2, "hoist": True, "mentionable": True, "permissions": discord.Permissions(manage_guild=True, manage_roles=True, kick_members=True, ban_members=True)},
                "⚔️ • Moderatór": {"color": 0x00F0FF, "hoist": True, "mentionable": True, "permissions": discord.Permissions(manage_messages=True, mute_members=True, deafen_members=True, move_members=True)},
                "🤖 • Bot Yetkilisi": {"color": 0x2ECC71, "hoist": True, "mentionable": False, "permissions": discord.Permissions(manage_webhooks=True)},
                "🌟 • Booster": {"color": 0xF1C40F, "hoist": True, "mentionable": True, "permissions": discord.Permissions(priority_speaker=True)},
                "🏆 • Immortal 3": {"color": 0xE67E22, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "💎 • Ascendant": {"color": 0x9B59B6, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "🔥 • Diamond": {"color": 0x3498DB, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "🎯 • Ajan": {"color": 0xECE8E1, "hoist": True, "mentionable": True, "permissions": discord.Permissions.none()},
                "🔇 • Susturulmuş": {"color": 0x95A5A6, "hoist": False, "mentionable": False, "permissions": discord.Permissions(send_messages=False, speak=False)}
            }

            created_roles = {}
            for role_name, data in roles_config.items():
                existing_role = discord.utils.get(guild.roles, name=role_name)
                if not existing_role:
                    role = await guild.create_role(
                        name=role_name,
                        color=discord.Color(data["color"]),
                        hoist=data["hoist"],
                        mentionable=data["mentionable"],
                        permissions=data["permissions"],
                        reason="V-Tracker Otomatik Sunucu Kurulumu"
                    )
                    created_roles[role_name] = role
                else:
                    created_roles[role_name] = existing_role

            await asyncio.sleep(1.5)

            # 2. ADIM: KATEGORİ VE KANAL YAPILANDIRMASI
            await self.update_status(status_msg, "Adım 2/5: Kategoriler ve kanallar inşa ediliyor...", 35)

            # Temel Yetki Tanımları
            everyone_role = guild.default_role
            staff_role = created_roles.get("⚔️ • Moderatór")
            muted_role = created_roles.get("🔇 • Susturulmuş")

            # Kanal izinleri şablonları
            overwrites_public = {
                everyone_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                muted_role: discord.PermissionOverwrite(send_messages=False, speak=False)
            }
            overwrites_readonly = {
                everyone_role: discord.PermissionOverwrite(read_messages=True, send_messages=False)
            }
            overwrites_staff = {
                everyone_role: discord.PermissionOverwrite(read_messages=False),
                staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }

            # Kanal Ağacı Sözlüğü
            server_structure = {
                "📌 | BİLGİ & DUYURULAR": {
                    "type": "category",
                    "channels": [
                        ("kurallar", "text", overwrites_readonly, "Sunucu ve topluluk kuralları."),
                        ("duyurular", "text", overwrites_readonly, "Güncellemeler, etkinlikler ve duyurular."),
                        ("güncellemeler", "text", overwrites_readonly, "V-Tracker bot sürüm notları."),
                        ("rol-seçim", "text", overwrites_readonly, "Ajan ve oyun rollendirme merkezi."),
                        ("boost-odası", "text", overwrites_readonly, "Sunucu takviye tebrik kanalı.")
                    ]
                },
                "💬 | TOPLULUK MERKEZİ": {
                    "type": "category",
                    "channels": [
                        ("genel-sohbet", "text", overwrites_public, "Serbest genel sohbet ve muhabbet alanı."),
                        ("bot-komutları", "text", overwrites_public, "V-Tracker komutlarının (/stats, /coach) kullanıldığı alan."),
                        ("medya-ve-klip", "text", overwrites_public, "Valorant en iyi anlar, vuruşlar ve klipler."),
                        ("anket-ve-etkinlik", "text", overwrites_public, "Topluluk anketleri ve ödüllü etkinlikler.")
                    ]
                },
                "🎮 | VALORANT ARENA": {
                    "type": "category",
                    "channels": [
                        ("valorant-sohbet", "text", overwrites_public, "Valorant meta, ajan ve harita tartışmaları."),
                        ("lobi-arayışı", "text", overwrites_public, "Dereceli (Ranked) ve unrated takım arkadaşı arama."),
                        ("taktik-ve-koçluk", "text", overwrites_public, "AI koçluk önerileri ve strateji paylaşımı."),
                        ("liderlik-tablosu", "text", overwrites_readonly, "Sunucu içi en yüksek ranklı oyuncular.")
                    ]
                },
                "🎉 | EĞLENCE & OYUN": {
                    "type": "category",
                    "channels": [
                        ("bot-oyunları", "text", overwrites_public, "Eğlence botları, ekonomi ve mini oyunlar."),
                        ("müzik-odası", "text", overwrites_public, "Müzik botu komutları ve şarkı istekleri.")
                    ]
                },
                "🔊 | SES KANALLARI": {
                    "type": "category",
                    "channels": [
                        ("🔊 Bekleme Odası", "voice", overwrites_public, None),
                        ("🎮 Ranked Lobi #1", "voice", overwrites_public, None),
                        ("🎮 Ranked Lobi #2", "voice", overwrites_public, None),
                        ("🎯 Casual / Swiftplay", "voice", overwrites_public, None),
                        ("☕ Chill & Sohbet", "voice", overwrites_public, None),
                        ("💤 AFK Odası", "voice", overwrites_public, None)
                    ]
                },
                "🛡️ | YÖNETİM & DESTEK": {
                    "type": "category",
                    "channels": [
                        ("ticket-oluştur", "text", overwrites_public, "Yetkili ekibiyle iletişim kurma ve destek talebi."),
                        ("mod-log", "text", overwrites_staff, "Sunucu denetim ve işlem günlükleri."),
                        ("yönetim-sohbet", "text", overwrites_staff, "Yetkili ekibi özel koordinasyon kanalı.")
                    ]
                }
            }

            created_channels = {}
            for cat_name, cat_data in server_structure.items():
                category = await guild.create_category(cat_name)
                for ch_info in cat_data["channels"]:
                    ch_name, ch_type, ch_overwrites, ch_topic = ch_info
                    if ch_type == "text":
                        channel = await guild.create_text_channel(
                            name=ch_name,
                            category=category,
                            overwrites=ch_overwrites,
                            topic=ch_topic
                        )
                        created_channels[ch_name] = channel
                    elif ch_type == "voice":
                        channel = await guild.create_voice_channel(
                            name=ch_name,
                            category=category,
                            overwrites=ch_overwrites
                        )
                        created_channels[ch_name] = channel

            await asyncio.sleep(1.5)

            # 3. ADIM: GÖMÜLÜ (EMBED) BİLGİ VE KONTROL PANELİ MESAJLARI
            await self.update_status(status_msg, "Adım 3/5: Kurallar ve karşılama panelleri yerleştiriliyor...", 65)

            # Kurallar Kanalı Embed
            rules_channel = created_channels.get("kurallar")
            if rules_channel:
                rules_embed = discord.Embed(
                    title="📜 V-TRACKER TOPLULUK KURALLARI",
                    description="Sunucumuzda huzurlu, saygılı ve rekabetçi bir ortam sağlamak için aşağıdaki kurallara uymak zorunludur.",
                    color=0xFF4655
                )
                rules_embed.add_field(
                    name="1️⃣ Saygı ve Dil",
                    value="Her üyeye karşı saygılı olunmalıdır. Din, dil, ırk, cinsiyet ayrımcılığı, nefret söylemi ve hakaret kesinlikle yasaktır.",
                    inline=False
                )
                rules_embed.add_field(
                    name="2️⃣ Spam ve Reklam",
                    value="Her türlü sosyal medya, Discord sunucusu, site veya ürün reklamı yapmak, DM üzerinden reklam atmak yasaktır.",
                    inline=False
                )
                rules_embed.add_field(
                    name="3️⃣ Ses Kanalları Düzeni",
                    value="Mikrofon basmak, kulak tırmalayıcı sesler çıkarmak, ses kanallarını taciz etmek veya botları kötüye kullanmak yasaktır.",
                    inline=False
                )
                rules_embed.add_field(
                    name="4️⃣ Valorant Kanalları",
                    value="Lobi arayışı ve taktik paylaşımları ilgili kanallarda yapılmalıdır. Uygunsuz içerik paylaşımı cezalandırılır.",
                    inline=False
                )
                rules_embed.set_footer(text="Kurallara uymayan üyeler uyarı almaksızın uzaklaştırılabilir.")
                await rules_channel.send(embed=rules_embed)

            # Rol Seçim Kanalı Embed
            role_channel = created_channels.get("rol-seçim")
            if role_channel:
                role_embed = discord.Embed(
                    title="🎯 AJAN VE KADEME ROL MERKEZİ",
                    description="Sunucumuzdaki bildirimlerden haberdar olmak ve kendi Valorant kademenizi göstermek için aşağıdaki butonları kullanabilirsiniz.",
                    color=0x00F0FF
                )
                role_embed.add_field(
                    name="🎮 Oyun Bildirimleri",
                    value="Etkinlikler, turnuvalar ve özel duyurular için rol alabilirsiniz.",
                    inline=False
                )
                role_embed.set_footer(text="V-Tracker.gg Rol Sistemi")
                await role_channel.send(embed=role_embed)

            # Ticket / Destek Kanalı Embed
            ticket_channel = created_channels.get("ticket-oluştur")
            if ticket_channel:
                ticket_embed = discord.Embed(
                    title="🎫 V-TRACKER DESTEK TALEBİ",
                    description="Yetkili ekibiyle iletişime geçmek, bir sorun bildirmek veya ortaklık/öneri sunmak için aşağıdaki butona tıklayarak özel destek kanalı oluşturabilirsiniz.",
                    color=0x8A2BE2
                )
                ticket_embed.set_footer(text="Destek ekibi en kısa sürede sizinle ilgilenecektir.")
                await ticket_channel.send(embed=ticket_embed)

            await asyncio.sleep(1.5)

            # 4. ADIM: BOT AYARLARI VE GÜVENLİK YAPilandirmasi
            await self.update_status(status_msg, "Adım 4/5: Güvenlik ve entegrasyonlar yapılandırılıyor...", 85)
            
            # Mod Log kanalına başlangıç bildirimi
            mod_log_channel = created_channels.get("mod-log")
            if mod_log_channel:
                log_embed = discord.Embed(
                    title="🛡️ DENETİM SİSTEMİ AKTİF",
                    description="V-Tracker otomatik kurulum sistemi başarıyla tamamlandı. Tüm güvenlik ve denetim logları bu kanala aktarılacaktır.",
                    color=0x2ECC71
                )
                log_embed.set_footer(text=f"Kurulum Zamanı: {ctx.message.created_at.strftime('%d.%m.%Y %H:%M')}")
                await mod_log_channel.send(embed=log_embed)

            await asyncio.sleep(1.0)

            # 5. ADIM: TAMAMLAMA RAPORU
            await self.update_status(status_msg, "Adım 5/5: Kurulum tamamlanıyor...", 100)

            success_embed = discord.Embed(
                title="✅ KURULUM BAŞARIYLA TAMAMLANDI!",
                description="V-Tracker.gg Valorant ve Eğlence sunucusu altyapısı eksiksiz olarak kuruldu.",
                color=0x2ECC71
            )
            success_embed.add_field(name="Oluşturulan Kategori", value="6 Adet", inline=True)
            success_embed.add_field(name="Oluşturulan Kanal", value="20+ Kanal", inline=True)
            success_embed.add_field(name="Rol Hiyerarşisi", value="Tamamlandı", inline=True)
            success_embed.set_footer(text="V-Tracker.gg — Radarınızdaki En Güçlü Asistan")

            await status_msg.edit(embed=success_embed)

        except Exception as e:
            logger.error(f"Sunucu kurulumu sırasında hata oluştu: {e}")
            error_embed = discord.Embed(
                title="❌ KURULUM HATASI",
                description=f"Kurulum sırasında bir hata oluştu. Lütfen botun `Yönetici` yetkisine sahip olduğundan emin olun.\n\n`Hata: {e}`",
                color=0xFF4655
            )
            await status_msg.edit(embed=error_embed)

    async def update_status(self, message, text, percentage):
        """Kurulum sürecindeki ilerlemeyi dinamik olarak günceller."""
        embed = discord.Embed(
            title="⚡ V-TRACKER | OTOMATİK SUNUCU KURULUMU",
            description=f"{text}\n\n`[{'█' * (percentage // 10)}{'░' * (10 - (percentage // 10))}] %{percentage}`",
            color=0xFF4655
        )
        embed.set_footer(text="V-Tracker.gg • Profesyonel Discord Altyapısı")
        try:
            await message.edit(embed=embed)
        except Exception:
            pass

async def setup(bot):
    @bot.command(name="setup", help="Sunucuyu Valorant ve Eğlence temasına göre otomatik kurar.")
    @commands.has_permissions(administrator=True)
    async def setup_command(ctx):
        installer = ValorantServerSetup(bot)
        await installer.execute_setup(ctx)

    @setup_command.error
    async def setup_error(ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Bu komutu kullanabilmek için **Yönetici** yetkisine sahip olmalısın.")
        else:
            await ctx.send(f"❌ Komut çalıştırılırken bir hata oluştu: {error}")