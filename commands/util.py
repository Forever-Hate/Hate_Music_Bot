from datetime import datetime
import os
from discord.ext import commands
from discord import Embed, Member, VoiceState

class Util(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot = bot
        self.voice_channel_tracking_enabled = os.getenv('VOICE_CHANNEL_TRACKING_ENABLED') == 'true'
        self.target_guild_ids = [int(id) for id in os.getenv('TARGET_GUILD_IDS').split(',')]
        self.manage_channel_id = int(os.getenv('MANAGE_CHANNEL_ID'))
        self.member_join_times = {}

    # 監聽成員加入語音頻道
    @commands.Cog.listener()
    async def on_voice_state_update(self,member:Member, before:VoiceState, after:VoiceState):
        if before.channel == after.channel or member == self.bot.user or not self.voice_channel_tracking_enabled or member.guild.id not in self.target_guild_ids:
            return  

        embed = Embed(title="語音頻道更新", timestamp=datetime.now())
        embed.set_author(name=str(member), icon_url=member.avatar.url)

        if before.channel is None and after.channel is not None:
            embed.color = 0x00FF00  # 綠色代表加入
            embed.description = f"{member.mention} 加入了語音頻道 {after.channel.mention}"
            self.member_join_times[member.id] = datetime.now()
        elif before.channel is not None and after.channel is None:
            embed.color = 0xFF0000  # 紅色代表離開
            join_time:datetime = self.member_join_times.pop(member.id, None)
            if join_time is not None:
                join_time_unix = int(join_time.timestamp())
                embed.description = f"{member.mention} 離開了語音頻道 {before.channel.mention}，進入時間為 <t:{join_time_unix}:F>。"
            else:
                embed.description = f"{member.mention} 離開了語音頻道 {before.channel.mention}"
        elif before.channel != after.channel:
            embed.color = 0xFFFF00  # 黃色代表移動
            embed.description = f"{member.mention} 從 {before.channel.mention} 移動到 {after.channel.mention}"
        await self.bot.get_channel(self.manage_channel_id).send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Util(bot))