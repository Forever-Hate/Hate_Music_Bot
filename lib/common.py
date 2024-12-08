import abc
import datetime
from enum import Enum
import json
import requests
from discord.ext import commands
from discord.ui import Button, View
from discord import ButtonStyle, Colour, Embed, Interaction, User
from typing import Dict, List, Tuple, Union

import wavelink

class Platform(Enum):
    YOUTUBE = "<:yt:1032640435375583342>" 
    SPOTIFY = "<:sp:1132579820681834559>"
    TWITCH = "<:th:1032831426959245423>"

platform_mapping = {
    "youtube": Platform.YOUTUBE,
    "spotify": Platform.SPOTIFY,
    "twitch":  Platform.TWITCH
}
def get_platform_info_by_string(s:str) -> Platform:
    return platform_mapping.get(s)

def get_string_by_platform(enum_value: Platform) -> str:
    return next(key for key, value in platform_mapping.items() if value == enum_value)

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

# 訂閱的頻道
class Channel():
    def __init__(self, id: str, title: str, thumbnail: str, latest_video: str,platform: Platform):
        self.id = id # 頻道ID
        self.title = title # 頻道名稱
        self.thumbnail = thumbnail # 頻道縮圖
        self.latest_video = latest_video # 最新影片url
        self.guild_id = None # 訂閱的伺服器
        self.platform = platform # 平台 e.g. youtube, twitch

    # 轉換成 Embed
    def toEmbed(self, current_guild_id,index: int = 0) -> Embed:
        miko = Embed(colour = Colour.random())
        miko.set_author(name = f"第 {index+1} 個頻道{'(非本伺服器訂閱)' if current_guild_id not in self.guild_id else ''}:")
        miko.set_thumbnail(url = self.thumbnail)
        miko.add_field(name = "🎯名稱:", value = self.title, inline = False)
        miko.add_field(name = "🔗網址:", value = f"https://www.youtube.com/channel/{self.id}" if self.platform == Platform.YOUTUBE else f"https://www.twitch.tv/{self.id}", inline = False)
        miko.add_field(name = "🎞️最新影片url:", value = self.latest_video, inline = False)
        miko.add_field(name = "🚩平台:", value = f"{Platform.YOUTUBE.value}Youtube" if self.platform == Platform.YOUTUBE else f"{Platform.TWITCH.value}Twitch")
        return miko

    # 設定訂閱的伺服器(embed 顯示用)
    def setGuild_id(self, guild_id: List[int]):
        self.guild_id = guild_id
    
    # 建立一個新的物件
    def copy(self):
        return Channel(self.id, self.title, self.thumbnail, self.latest_video, self.platform)

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

class Song:

    def __init__(self, url: str):
        self.url = url
        self.karaoke: bool = False

    async def init(self) -> Union[bool, Tuple[bool, str]]:
        try:
            self.track = (await wavelink.Playable.search(self.url))[0]
            self.title = self.track.title
            self.thumbnail = self.track.artwork
            self.duration = self.track.length
            self.duration_str = f"{self.duration // 1000 // 3600:02d}:{(self.duration // 1000 % 3600) // 60:02d}:{self.duration // 1000 % 60:02d}"
            self.source = self.track.source
        except (IndexError, ValueError,wavelink.LavalinkLoadException) as e:
            print("無法取得音樂，錯誤:", e)
            return (False, "無效的網址，請重新輸入")
        else:
            return True

    def setExtras(self, extra: Dict[str, str]):
        old_extras = dict(self.track.extras)
        old_extras.update(extra)
        self.track.extras = old_extras
            
    # async def get_lyrics(self) -> Union[Dict[int, str], None]:
    #     lyrics = {}
    #     try:
    #         data = requests.get(f"https://spotify-lyric-api-984e7b4face0.herokuapp.com/?trackid={self.id}", timeout=5).text
    #         data = json.loads(data)
    #     except Exception:
    #         return None
    #     word = ""
    #     if 'message' not in data:
    #         for index, lyric in enumerate(data["lines"]):
    #             if lyric["words"] == "" and index != len(data['lines']) - 1:
    #                 word = "♪"
    #             else:
    #                 word = bytes(lyric["words"], "utf-8").decode("unicode_escape").encode("iso-8859-1").decode("utf-8")
    #             if data["syncType"] == "LINE_SYNCED":
    #                 lyrics[int(lyric["startTimeMs"])] = word
    #                 self.karaoke = True
    #             else:
    #                 lyrics[index] = word
    #                 self.karaoke = False
    #     else:
    #         self.karaoke = False
    #         lyrics = None
    #     return lyrics
    
class Playlist():

    def __init__(self, song_list: List[Song], creater: User,play_count: int):
        self.song_list = song_list
        self.creater = creater
        self.play_count = play_count