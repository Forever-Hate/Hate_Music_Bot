import abc
import datetime
from discord import ButtonStyle, Colour, Embed, Interaction, User
from discord.ext import commands
from discord.ui import Button, View
from typing import List, Tuple, Union
from wavelink import LavalinkException, LoadTrackError, NodePool, YouTubeTrack

class CustomView(View, metaclass = abc.ABCMeta):
    def __init__(self, timeout):
        super().__init__(timeout = timeout)

    def add(self, item, callback = None):
        self.add_item(item)
        if callback is not None:
            item.callback = callback
        return item

    @abc.abstractmethod
    def add_base_button(self):
        return NotImplemented

    @abc.abstractmethod
    def ui_control(self):
        return NotImplemented

class ObjectEmbedView(CustomView):

    def __init__(self, embed_list:List[Embed]):
        super().__init__(timeout = None)
        self.embed_list = embed_list
        self.start = 0
        self.end = 10
        self.add_base_button()

    async def next(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        self.start += int(interaction.data.get('custom_id'))
        self.end += int(interaction.data.get('custom_id'))
        self.ui_control()
        await interaction.followup.edit_message(interaction.message.id, embeds = self.embed_list[self.start:self.end], view = self)

    def add_base_button(self):
        self.add(Button(style = ButtonStyle.green, label = "上十項",emoji = "⏮️", custom_id = "-10"), self.next)
        self.add(Button(style = ButtonStyle.green, label = "下十項",emoji = "⏭️", custom_id =  "10"), self.next)
        self.ui_control()

    def ui_control(self):
        self.children[0].disabled = False
        self.children[1].disabled = False
        if self.start == 0:
            self.children[0].disabled = True
        if len(self.embed_list) <= self.end:
            self.children[1].disabled = True

class Channel():
    def __init__(self, id: str, title: str, thumbnail: str, latest_video: str, platform: str):
        self.id = id
        self.title = title
        self.thumbnail = thumbnail
        self.latest_video = latest_video
        self.platform = platform

    def toEmbed(self, index: int = 0) -> Embed:
        miko = Embed(colour = Colour.random())
        miko.set_author(name = f"第 {index+1} 個頻道:")
        miko.set_thumbnail(url = self.thumbnail)
        miko.add_field(name = "🎯名稱:", value = self.title, inline = False)
        miko.add_field(name = "🔗網址:", value = f"https://www.youtube.com/channel/{self.id}" if self.platform == "youtube" 
                                                 else f"https://www.twitch.tv/{self.id}", inline = False)
        miko.add_field(name = "🎞️最新影片url:", value = self.latest_video, inline = False)
        miko.add_field(name = "🚩平台:", value = f"<:yt:1032640435375583342>Youtube" if self.platform == "youtube" 
                                                 else f"<:th:1032831426959245423>Twitch")
        return miko

class Guild():

    def __init__(self, guild_id: int, text_id: int, voice_id: int):
        self.guild_id = guild_id
        self.text_id = text_id
        self.voice_id = voice_id

    def toEmbed(self, bot: commands.Bot, index: int = 0, number: int = 0) -> Embed:
        guild = bot.get_guild(self.guild_id)
        miko = Embed(colour=Colour.random())
        miko.set_thumbnail(url = guild.icon)
        miko.set_author(name = f"第 {index+1}-{number+1} 個伺服器:")
        miko.add_field(name = "🎯名稱:", value = guild.name, inline = False)
        miko.add_field(name = "👑擁有者:", value = f"{guild.owner}", inline = False)
        miko.add_field(name = "👀人數:", value = f"{guild.member_count}人", inline = False)
        return miko

class Live():

    def __init__(self, title: str, channel_title: str, url: str, start_time: int, thumbnail: str, platform: str):
        self.title = title
        self.channel_title = channel_title
        self.url = url
        self.start_time = start_time
        self.thumbnail = thumbnail
        self.platform = platform
        self.reconnection_times = 0

    def toString(self):
        print("===============新直播排程===============")
        print("- 標題:", self.title)
        print("- 頻道名稱:", self.channel_title)
        print("- url:", self.url)
        print("- 開始時間:", datetime.datetime.fromtimestamp(self.start_time).strftime('%Y年%m月%d日 %H點%M分%S秒'))
        print("- 距離開始還有:", self.start_time -int(datetime.datetime.now().timestamp()))
        print("- 縮圖:", self.thumbnail)
        print("========================================")

    def toEmbed(self, index: int = 0) -> Embed:
        miko = Embed(colour = Colour.random())
        miko.set_thumbnail(url = self.thumbnail)
        miko.set_author(name = f"第 {index+1} 個直播排程:")
        miko.add_field(name = "🎯標題:", value = self.title, inline = False)
        miko.add_field(name = "👑頻道名稱:", value = self.channel_title, inline = False)
        miko.add_field(name = "🔗url:", value = self.url, inline = False)
        miko.add_field(name = "⏰開始時間:", value = datetime.datetime.fromtimestamp(self.start_time).strftime('%Y年%m月%d日 %H點%M分%S秒'), inline = False)
        miko.add_field(name = "⌛距離開始還有:", value = f"{self.start_time - int(datetime.datetime.now().timestamp())}秒", inline = False)
        return miko

    def create_embed(self) -> Embed:
        miko = Embed(colour = Colour.random())
        miko.set_author(name = "🎧即將到來的直播:")
        miko.set_thumbnail(url = self.thumbnail)
        miko.add_field(name = "<:yt:1032640435375583342>頻道:",value = self.channel_title)
        miko.add_field(name = "🎯名稱:", value = self.title)
        miko.add_field(name = "🔗網址:", value = self.url, inline = False)
        miko.add_field(name = "⏰直播時間:", value = f"<t:{self.start_time}:f>")
        miko.add_field(name = "⌛距離開始直播:",value = f"<t:{self.start_time}:R>", inline = False)
        return miko

class Playlist():

    def __init__(self, song_list: list, creater: User):
        self.song_list = song_list
        self.creater = creater

class Song():

    def __init__(self, url: str):
        self.url = url

    async def init(self) -> Union[bool , Tuple[bool,str]]:
        try:
            self.track = (await NodePool.get_node().get_tracks(YouTubeTrack, self.url))[0]
            self.title = self.track.title
            self.thumbnail = self.track.thumbnail
            self.duration = self.track.duration
            self.duration_str = f'({str(int(self.track.duration/3600)).zfill(2)}:{str(int(self.track.duration/60%60)).zfill(2)}:{str(int(self.track.duration%60)).zfill(2)})'
        except (LoadTrackError, LavalinkException) as e:
            return (False , str(e))
        else:
            return True
