# -*- coding: utf-8 -*-
"""
V-Tracker.gg - Riot OAuth2 (RSO) Güvenli Kayıt ve Doğrulama Modülü
Bu modül, kullanıcıların Riot hesaplarını resmi RSO (Riot Sign-On) altyapısı
ile %100 güvenli bir şekilde doğrulamalarını sağlar.
"""

import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
import logging
import re
import threading
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn

# ==============================================================================
# GÜVENLİ LOGLAMA VE YAPILANDIRMA
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("V-Tracker-Security")

# --- RIOT DEVELOPER BILGILERINI BURAYA GIR ---
CLIENT_ID = "SENIN_RIOT_CLIENT_ID"
CLIENT_SECRET = "SENIN_RIOT_CLIENT_SECRET"
REDIRECT_URI = "http://localhost:8000/auth/callback"  # Canlıda: https://uygulama-adi.onrender.com/auth/callback
# ---------------------------------------------

# ==============================================================================
# VERİTABANI YÖNETİMİ (GÜVENLİ DOSYA İŞLEMLERİ)
# ==============================================================================
file_lock = asyncio.Lock()

class SecureAuthDatabase:
    """JSON tabanlı veritabanı işlemlerini asenkron ve kilitli(lock) şekilde yönetir."""
    USERS_FILE = "global_registered_users.json"
    BACKUP_FILE = "global_registered_users_backup.json"

    @classmethod
    async def load_json(cls, filename: str) -> Dict[str, Any]:
        """Dosyayı güvenli bir şekilde okur, bozuksa yedeği dener."""
        if not os.path.exists(filename):
            return {}
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"Kritik Hata: {filename} bozuk! Yedek dosyaya başvuruluyor.")
            if os.path.exists(cls.BACKUP_FILE):
                with open(cls.BACKUP_FILE, "r", encoding="utf-8") as bf:
                    return json.loads(bf.read().strip())
        except Exception as e:
            logger.error(f"Dosya okuma hatası ({filename}): {e}")
        return {}

    @classmethod
    async def save_json(cls, filename: str, data: Dict[str, Any]) -> None:
        """Veriyi önce geçici bir dosyaya yazar, sonra asıl dosyanın üzerine güvenle yazar."""
        async with file_lock:
            temp_filename = f"{filename}.tmp"
            try:
                # Önce yedeği al
                if os.path.exists(filename):
                    import shutil
                    shutil.copy(filename, cls.BACKUP_FILE)
                
                # Yeni veriyi geçici dosyaya yaz
                with open(temp_filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                
                # Geçici dosyayı asıl dosya ile yer değiştir (Atomik işlem)
                os.replace(temp_filename, filename)
                logger.info(f"Veritabanı güncellendi: {filename}")
            except Exception as e:
                logger.error(f"Dosya yazma hatası ({filename}): {e}")
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)

# ==============================================================================
# FASTAPI WEB SUNUCUSU (RSO CALLBACK DİNLEYİCİ)
# ==============================================================================
app = FastAPI(title="V-Tracker RSO Auth", version="2.0")

@app.get("/auth/callback")
async def riot_callback(code: str, state: str):
    """
    Riot giriş yaptıktan sonra kullanıcıyı bu adrese yönlendirir.
    state: Discord User ID
    code: Riot Authorization Code
    """
    discord_user_id = state
    
    # Adım 1: Riot Authorization Code kullanarak Access Token alma
    token_url = "https://auth.riotgames.com/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(token_url, headers=headers, data=payload) as resp:
                if resp.status != 200:
                    logger.error(f"Token alınamadı. HTTP {resp.status}")
                    return HTMLResponse("<h1>Hata: Riot token alınamadı. İşlem iptal edildi.</h1>", status_code=400)
                
                token_data = await resp.json()
                access_token = token_data.get("access_token")

            # Adım 2: Access Token kullanarak benzersiz PUUID alma
            userinfo_url = "https://auth.riotgames.com/userinfo"
            auth_headers = {"Authorization": f"Bearer {access_token}"}
            
            async with session.get(userinfo_url, headers=auth_headers) as resp:
                if resp.status != 200:
                    logger.error(f"Userinfo alınamadı. HTTP {resp.status}")
                    return HTMLResponse("<h1>Hata: Kullanıcı kimliği (PUUID) alınamadı.</h1>", status_code=400)
                
                user_info = await resp.json()
                puuid = user_info.get("sub")
                region = user_info.get("region", "eu").lower()

            # Adım 3: HenrikDev üzerinden güncel İsim ve Tag bilgilerini alma
            account_url = f"https://api.henrikdev.xyz/valorant/v1/by-puuid/account/{puuid}"
            async with session.get(account_url) as resp:
                if resp.status != 200:
                    logger.warning(f"HenrikDev API hatası. PUUID: {puuid}")
                    name, tag = "Bilinmiyor", "TR1"
                else:
                    acc_json = await resp.json()
                    acc_data = acc_json.get("data", {})
                    name = acc_data.get("name", "Bilinmiyor")
                    tag = acc_data.get("tag", "TR1")

            # Adım 4: Kullanıcıyı V-Tracker veritabanına kaydetme
            users = await SecureAuthDatabase.load_json(SecureAuthDatabase.USERS_FILE)
            
            # Eski verileri koruma (Kozmetikler ve paralar silinmesin)
            existing_cosmetics = users.get(discord_user_id, {}).get("cosmetics", {
                "color": "0x00FFFF", "emoji": "", "banner": "", "gif": "", "unlocked": []
            })
            existing_coins = users.get(discord_user_id, {}).get("v_coins", 0)

            # Yeni güvenli veriyi oluşturma
            users[discord_user_id] = {
                "puuid": puuid,
                "name": name,
                "tag": tag,
                "region": region,
                "dc_name": "DiscordUser",
                "v_coins": existing_coins,
                "cosmetics": existing_cosmetics,
                "is_verified": True
            }
            
            await SecureAuthDatabase.save_json(SecureAuthDatabase.USERS_FILE, users)
            logger.info(f"Kullanıcı başarıyla doğrulandı: Discord ID {discord_user_id} -> {name}#{tag}")

            # Başarılı HTML Yanıtı
            success_html = """
            <!DOCTYPE html>
            <html lang="tr">
            <head>
                <meta charset="UTF-8">
                <title>Doğrulama Başarılı - V-Tracker</title>
                <style>
                    body { background-color: #0f1923; color: #ece8e1; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; margin-top: 15vh; }
                    .container { background-color: #1f2326; padding: 40px; border-radius: 12px; border-top: 5px solid #ff4655; display: inline-block; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
                    h1 { color: #ff4655; margin-bottom: 10px; }
                    p { font-size: 1.1em; color: #a9a9a9; margin-bottom: 20px; }
                    .success-icon { font-size: 60px; margin-bottom: 10px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success-icon">✔️</div>
                    <h1>Hesap Başarıyla Doğrulandı!</h1>
                    <p>Riot hesabınız (<strong>%s#%s</strong>) V-Tracker sistemine güvenle bağlandı.</p>
                    <p>Bu pencereyi kapatıp Discord'a dönebilirsiniz.</p>
                </div>
            </body>
            </html>
            """ % (name, tag)
            
            return HTMLResponse(content=success_html)

        except Exception as e:
            logger.error(f"Callback işlemi sırasında beklenmeyen hata: {e}")
            return HTMLResponse("<h1>Kritik Sunucu Hatası. Lütfen daha sonra tekrar deneyin.</h1>", status_code=500)

def run_fastapi():
    """FastAPI sunucusunu Uvicorn ile arka planda çalıştırır."""
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")


# ==============================================================================
# DISCORD BOT - KOMUT SINIFI
# ==============================================================================
class RiotOAuthSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # FastAPI sunucusunu Daemon thread olarak başlat (Bot kapanınca kapanır)
        threading.Thread(target=run_fastapi, daemon=True).start()

    def is_valid_format(self, riot_id: str) -> bool:
        """Kullanıcının girdiği formatın İsim#Etiket olup olmadığını kontrol eder."""
        if not riot_id:
            return False
        # Örnek: Tenz#NA1, Alperen#TR1
        pattern = r"^.{3,16}#.{2,5}$"
        return bool(re.match(pattern, str(riot_id).strip()))

    # --------------------------------------------------------------------------
    # SAHTE REGISTER KOMUTU (Eskiyi iptal edip kullanıcıyı yönlendirmek için)
    # --------------------------------------------------------------------------
    @commands.hybrid_command(name="register", aliases=["kayit", "kayıt"], hidden=True)
    async def override_register(self, ctx):
        """Eski register komutunu ezip kullanıcıyı doğru komuta yönlendirir."""
        embed = discord.Embed(
            title="⚠️ Komut Değiştirildi",
            description=(
                "Güvenlik güncellemeleri nedeniyle `v!register` komutu **kaldırılmıştır**.\n\n"
                "Lütfen hesabınızı doğrulamak için yeni komutumuzu kullanın:\n"
                "👉 **`v!dogrula İsim#Etiket`**\n\n"
                "*Örnek: `v!dogrula nxbx#TR1`*"
            ),
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed, ephemeral=True)

    # --------------------------------------------------------------------------
    # YENİ VE GÜVENLİ DOĞRULA KOMUTU
    # --------------------------------------------------------------------------
    @commands.hybrid_command(name="dogrula", aliases=["verify"], description="Riot hesabınızın size ait olduğunu resmi olarak doğrular.")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def dogrula_command(self, ctx, *, riot_id: str = None):
        """
        Kullanıcının Riot hesabını doğrulaması için güvenli link üretir.
        Format zorunluluğu: İsim#Etiket
        """
        # Adım 1: Format Kontrolü (Hatalıysa açıklayıcı mesaj at)
        if not self.is_valid_format(riot_id):
            error_embed = discord.Embed(
                title="❌ Hatalı Kullanım Formatı",
                description=(
                    "Hesabını doğrulamak için Riot ismini ve etiketini birlikte yazmalısın.\n\n"
                    "**Doğru Kullanım:**\n"
                    "`v!dogrula İsim#Etiket`\n\n"
                    "**Örnekler:**\n"
                    "✅ `v!dogrula nxbx#TR1`\n"
                    "✅ `v!dogrula TenZ#NA1`\n\n"
                    "*Lütfen arada boşluk bırakmadan, tam Riot ID'nizi yazarak tekrar deneyin.*"
                ),
                color=discord.Color.red()
            )
            return await ctx.send(embed=error_embed, ephemeral=True)

        user_id = str(ctx.author.id)

        # Adım 2: Zaten kayıtlı mı kontrolü
        users = await SecureAuthDatabase.load_json(SecureAuthDatabase.USERS_FILE)
        if user_id in users and users[user_id].get("is_verified"):
            registered_name = f"{users[user_id].get('name')}#{users[user_id].get('tag')}"
            return await ctx.send(f"⚠️ Zaten doğrulanmış ve sisteme bağlı bir Riot hesabın var (**{registered_name}**). Yeni bir hesap doğrulamak için önce eskini silmelisin.")

        # Adım 3: Riot OAuth2 RSO (Riot Sign-On) Linkini Oluşturma
        # 'state' parametresi aracılığıyla Discord User ID'sini Riot sunucusuna gönderiyoruz.
        auth_url = (
            f"https://auth.riotgames.com/authorize?"
            f"client_id={CLIENT_ID}&"
            f"redirect_uri={REDIRECT_URI}&"
            f"response_type=code&"
            f"scope=openid&"
            f"state={user_id}"
        )

        # Adım 4: Güven Temeli Veren Şeffaf Açıklama Mesajı (Embed)
        embed = discord.Embed(
            title="🛡️ Riot Games Resmi Hesap Doğrulama",
            description=(
                f"Merhaba! **{riot_id}** hesabının gerçekten sana ait olduğunu kanıtlaman gerekiyor. "
                "Başkalarının senin hesabınla kayıt olmasını engellemek için V-Tracker, **Resmi Riot Games Güvenlik Altyapısını (RSO)** kullanır.\n\n"
                "Aşağıdaki bağlantıya tıklayarak doğrudan Riot Games'in resmi web sitesi üzerinden giriş yapmalısın."
            ),
            color=0xFF4655
        )
        
        # Güvenlik ve Gizlilik alanları
        embed.add_field(
            name="🔒 Şifremi Bot Görecek Mi?",
            value="**KESİNLİKLE HAYIR.** Yönlendirileceğin sayfa V-Tracker'a ait değildir; adres çubuğunda `auth.riotgames.com` yazan **resmi Riot Games** sitesidir. Şifren tamamen Riot'un sunucularında kalır.",
            inline=False
        )
        embed.add_field(
            name="🔑 PUUID Nedir ve Biz Ne Alıyoruz?",
            value="Giriş yaptıktan sonra Riot bize sadece **PUUID** adı verilen uzun, anlamsız bir kimlik numarası (örn: `c83j...`) gönderir. Biz bu numara üzerinden sadece senin Valorant istatistiklerini eşleştiririz. Hesabında maç başlatma veya mağaza satın alımı gibi işlemler yapılması teknik olarak **imkansızdır**.",
            inline=False
        )
        embed.add_field(
            name="✅ Nasıl Yapacağım?",
            value="1️⃣ Aşağıdaki mavi linke tıkla.\n2️⃣ Riot Games sayfasına giriş yap.\n3️⃣ 'Doğrulandı' sayfasını görünce Discord'a geri dön.",
            inline=False
        )

        embed.set_footer(text="V-Tracker.gg • Yetkisiz erişimleri engellemek için geliştirilmiştir.")
        embed.set_thumbnail(url="https://logodownload.org/wp-content/uploads/2019/12/riot-games-logo-0.png")

        # Görünmez URL butonu (Kullanıcı için pratik tıklama)
        view = discord.ui.View()
        button = discord.ui.Button(label="Riot İle Doğrula", style=discord.ButtonStyle.link, url=auth_url, emoji="🔗")
        view.add_item(button)

        await ctx.send(embed=embed, view=view, ephemeral=True)


    # --------------------------------------------------------------------------
    # YARDIMCI KOMUT: HESAP SİL / UNREGISTER
    # --------------------------------------------------------------------------
    @commands.hybrid_command(name="hesapsil", aliases=["unregister"], description="Doğrulanmış Riot hesabınızın bağlantısını keser.")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def hesapsil_command(self, ctx):
        user_id = str(ctx.author.id)
        users = await SecureAuthDatabase.load_json(SecureAuthDatabase.USERS_FILE)
        
        if user_id not in users or not users[user_id].get("is_verified"):
            return await ctx.send("❌ Sisteme doğrulanmış bir hesabın bulunmuyor.", ephemeral=True)
            
        # Veriyi sil
        del users[user_id]
        await SecureAuthDatabase.save_json(SecureAuthDatabase.USERS_FILE, users)
        
        await ctx.send("✅ Riot hesabının V-Tracker ile olan bağlantısı başarıyla kesildi ve doğrulama silindi.", ephemeral=True)

# ==============================================================================
# MODÜL YÜKLEME (SETUP)
# ==============================================================================
async def setup(bot):
    # Çakışmaları kökten engellemek için eski komutları siliyoruz.
    # Kullanıcı vtracker.py'den silmeyi unutsa bile buradan eziyoruz.
    try:
        bot.remove_command("register")
        bot.remove_command("kayit")
        bot.remove_command("kayıt")
        bot.remove_command("dogrula") 
    except Exception as e:
        logger.warning(f"Komut temizleme uyarısı: {e}")
        
    await bot.add_cog(RiotOAuthSystem(bot))
    logger.info("Riot OAuth2 Doğrulama Modülü YÜKLENDİ. Eski komutlar eklendi/kaldırıldı.")