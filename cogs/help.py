from discord.ext import commands
from theme import info

class Help(commands.Cog):
    def __init__(self,bot): self.bot=bot
    @commands.hybrid_command(name="help",aliases=["yardim","yardım"],description="V-Tracker komutlarını gösterir.")
    async def help(self,ctx):
        e=info("V-Tracker • Komut Merkezi","Prefix: `v!` • Slash komutları da desteklenir.")
        e.add_field(name="🔐 Kayıt",value="`register` • `sync` • `verification`\nTek Discord = tek Riot hesabı; PUUID ile kalıcı kilit.",inline=False)
        e.add_field(name="📊 Valorant",value="`stats` • `lastmatch` • `compare @üye` • `coach`",inline=False)
        e.add_field(name="🧠 Taktik",value="`agents` • `comp <harita>` • `counterstrat <stil>`",inline=False)
        e.add_field(name="💰 V-Coin",value="`balance` • `daily` • `weekly` • `transfer` • `leaderboard` • `shop` • `buy` • `customize` • `challenges`",inline=False)
        e.add_field(name="🛠️ Sunucu",value="`suggest` • `join` • `leave` • `setup`\nModerasyon: `warn`, `warnings`, `timeout`, `clear`, `lockdown`, `kick`, `ban`",inline=False)
        e.set_footer(text="V-Tracker Rebuild 2.0 • Tek-kayıt + API doğrulama + SQLite")
        await ctx.send(embed=e)

async def setup(bot): await bot.add_cog(Help(bot))
