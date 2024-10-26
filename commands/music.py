import asyncio
import datetime
import os
import random
import re
import time
import wavelink
import yarl
import lib.notification as nc
import lib.sql as sql
from enum import Enum
from discord import Object, app_commands, ButtonStyle, Colour, Embed, Interaction , TextStyle , User, WebhookMessage
from discord.ext import commands, tasks
from discord.ui import Button, Modal, TextInput
from lib.common import Channel, CustomView, Guild, ObjectEmbedView, Playlist, Song,Platform,get_string_by_platform,get_platform_info_by_string
from typing import Dict, List, Tuple, Union

URL_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
OPTIONS = {
    "1️⃣": 0,
    "2️⃣": 1,
    "3️⃣": 2,
    "4️⃣": 3,
    "5️⃣": 4
}

MANAGE_USER_ID = int(os.getenv('MANAGE_USER_ID'))
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
WL_HOST = os.getenv('WL_HOST')
WL_PASSWORD = os.getenv('WL_PASSWORD')
DEFAULT_VOLUME = int(os.getenv('DEFAULT_VOLUME'))

class Mode(Enum):
    NORMAL = "普通"
    PLAY = "播放"
    PLAYLIST = "清單" #添加進歌單的模式

class HistorySongView(CustomView):

    def __init__(self, control_panel, player:wavelink.Player,position:int = 0):
        super().__init__(timeout = None)
        self.control_panel:ControlView = control_panel
        self.songs = player.queue.history.copy()
        self.songs.put(player.queue.copy())
        self.count = player.queue.count+player.queue.history.count
        self.start = 0
        self.end = 10
        self.position = position
        self.get_history_song_info()
        self.add_base_button()

    def get_history_song_info(self):
        self.song_list = f"<:moo:1017734836426915860>當前歌單:(第{self.start+1}首 ~ 第{self.end if self.count >= self.end else self.count}首 共{self.count}首)\n"
        if self.position - 1 < self.start:
            is_done = False
        else:
            is_done = True
        for index, item in enumerate(self.songs[self.start:self.end]):
            self.song_list = self.song_list + f"{self.start + index + 1}. {f'{Platform.YOUTUBE.value}' if get_platform_info_by_string(item.source) else f'{Platform.SPOTIFY.value}'}{item.title}(<@{item.extras.user}>)"
            if self.position - 1 == index + self.start:
                self.song_list = self.song_list + "-💿\n"
                is_done = False
                continue
            elif is_done:
                self.song_list = self.song_list + "-🏁\n"
            else:
                self.song_list = self.song_list + "-💤\n"

    async def next(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        self.start += int(interaction.data.get('custom_id'))
        self.end += int(interaction.data.get('custom_id'))
        self.get_history_song_info()
        self.ui_control()
        await interaction.followup.edit_message(interaction.message.id, content = f"{self.song_list}", view = self)

    def add_base_button(self):
        self.add(Button(style = ButtonStyle.green, label = "前十首",emoji = "⏮️", custom_id = "-10"), self.next)
        self.add(Button(style = ButtonStyle.green, label = "下十首",emoji = "⏭️", custom_id =  "10"), self.next)
        self.ui_control()

    def ui_control(self):
        self.children[0].disabled = False
        self.children[1].disabled = False
        if self.start == 0:
            self.children[0].disabled = True
        if self.count <= self.end:
            self.children[1].disabled = True

#音樂控制面板
class ControlView(CustomView):
    def __init__(self, player: wavelink.Player):
        super().__init__(timeout=None)
        self.player:wavelink.Player = player
        self.player.autoplay = wavelink.AutoPlayMode.partial
        self.player.queue.mode = wavelink.QueueMode.normal
        self.position:int = 1
        self.speed:float = 1.0
        self.cycle:bool = False
        self.cycle_type = self.CycleType.SINGLE
        self.play_type = self.PlayType.PLAYING
        self.skip:bool = False
        self.stop:bool = False
        self.delete:bool = False
        self._message:WebhookMessage = None
        self.message_id:int = None
        self.karaoke:bool = False
        self.karaoke_object = {}
        self._karaoke_message:WebhookMessage = None
        self.karaoke_message_id:int = None
        self.lyric_iswaiting:bool = False
        self.previous_song:wavelink.Playable = None
        self.current_song:wavelink.Playable = None
        self.song_count:int = 0
        self.temp_embed:Embed = None #embed暫存
        self.channel = None

    class CycleType(Enum):
        SINGLE = "單首"
        ALL = "全部"

    class PlayType(Enum):
        PLAYING = "播放中"
        PAUSING = "暫停中"
        LIVE = "直播中"


    class VolumeModal(Modal):
        def __init__(self, control_panel):
            super().__init__(title="調整音量大小/播放速度")
            self.control_panel:ControlView = control_panel
            self.volume = TextInput(label = '音量(0-1000):', style = TextStyle.short, default = f"{self.control_panel.player.volume}")
            self.speed = TextInput(label = '播放速度(0-無限):', style = TextStyle.short, default = f"{self.control_panel.speed}")
            self.add_item(self.volume)
            self.add_item(self.speed)

        async def on_submit(self, interaction: Interaction):
            self.control_panel.speed = float(self.speed.value)
            filters: wavelink.Filters = self.control_panel.player.filters
            filters.timescale.set(speed=self.control_panel.speed)
            await self.control_panel.player.set_filters(filters)
            await self.control_panel.set_volume(int(self.volume.value))
            await interaction.response.edit_message(embed=self.control_panel.create_embed(), view = self.control_panel)

    class SeekModal(Modal):
        def __init__(self, control_panel):
            super().__init__(title="調整音樂時間")
            self.control_panel:ControlView = control_panel
            self.hour = TextInput(label = '小時:', style = TextStyle.short, default = "0" , required = False)
            self.minute = TextInput(label = '分:', style = TextStyle.short, default = "0" , required = False)
            self.second = TextInput(label = '秒:', style = TextStyle.short, default = "0" , required = False)
            self.add_item(self.hour)
            self.add_item(self.minute)
            self.add_item(self.second)

        async def on_submit(self, interaction: Interaction):
            try:
                seek_time = (int(self.hour.value) * 3600 + int(self.minute.value) * 60 + int(self.second.value)) * 1000
                if seek_time > self.control_panel.player.current.length:
                    await interaction.response.send_message(content = "已超過當前歌曲長度，請重新輸入",ephemeral = True)
                else:
                    await self.control_panel.player.seek(seek_time)
                    await interaction.response.edit_message(embed=self.control_panel.create_embed(), view = self.control_panel)
            except:
                await interaction.response.send_message(content = "請不要輸入數字以外的字元",ephemeral = True)

    async def __play_and_pause(self, interaction: Interaction):
        await interaction.response.defer()
        if not self.player.paused:
            self.play_type = self.PlayType.PAUSING
            await self.player.pause(True)
        else:
            self.play_type = self.PlayType.PLAYING
            await self.player.pause(False)
        await interaction.followup.edit_message(message_id=self.message_id, embed=self.create_embed(), view=self)

    async def __cycle_callback(self, interaction: Interaction):
        await interaction.response.defer()
        if not self.cycle:
            self.cycle = True
            if self.cycle_type == self.CycleType.SINGLE:
                self.player.queue.mode = wavelink.QueueMode.loop
            elif self.cycle_type == self.CycleType.ALL:
                self.player.queue.mode = wavelink.QueueMode.loop_all
        else:
            self.cycle = False
            self.player.queue.mode = wavelink.QueueMode.normal
        await interaction.followup.edit_message(message_id=self.message_id, embed=self.create_embed(), view=self)

    async def __cycle_type_callback(self, interaction: Interaction):
        await interaction.response.defer()
        if self.cycle_type == self.CycleType.SINGLE:
            self.cycle_type = self.CycleType.ALL
            self.player.queue.mode = wavelink.QueueMode.loop_all
        else:
            self.cycle_type = self.CycleType.SINGLE
            self.player.queue.mode = wavelink.QueueMode.loop
        await interaction.followup.edit_message(message_id=self.message_id, embed=self.create_embed(), view=self)

    async def __skip_callback(self, interaction: Interaction):
        await interaction.response.defer()
        self.skip = True
        await self.player.stop()
        await asyncio.sleep(1.5)
        if self.position != 0:
            await interaction.followup.edit_message(message_id=self.message_id, content = f"<@{interaction.user.id}>已跳過`{self.previous_song.title}`",embed=self.create_embed(), view=self)

    async def __stop_callback(self, interaction: Interaction):
        self.stop = True
        await self.player.stop()
        await interaction.response.send_message(content = "已停止播放",ephemeral = True)

    async def __volume_callback(self, interaction: Interaction):
        await interaction.response.send_modal(self.VolumeModal(self))

    async def __seek_callback(self,interaction:Interaction):
        await interaction.response.send_modal(self.SeekModal(self))

    async def __delete_callback(self, interaction: Interaction):
        await interaction.response.defer()
        self.delete = True
        if self.position == self.song_count:
            self.position -= self.song_count
        else:
            self.position -= 1
        await self.player.stop()
        await asyncio.sleep(1.5)
        if self.position != 0:
            await interaction.followup.edit_message(message_id = self.message_id,content = f"<@{interaction.user.id}>已移除`{self.previous_song.title}`", embed = self.create_embed(), view = self)

    async def __get_lyric_callback(self,interaction:Interaction):
        await interaction.response.defer()
        lyric_string = ""
        if self.history_song[self.position-1].song.lyrics is not None:
            for lyric in self.history_song[self.position-1].song.lyrics.values():
                lyric_string = f"{lyric_string}{lyric}\n"
            await interaction.followup.send(content = lyric_string , ephemeral = True)
        else:
            await interaction.followup.send(content = "無法取得本首歌的歌詞，請見諒" , ephemeral = True)

    async def __karaoke_callback(self,interaction:Interaction):
        await interaction.response.defer()
        self.karaoke_object["interaction"] = interaction
        if not self.lyric_iswaiting:
            if self.karaoke:
                self.karaoke = False
                self.karaoke_object = {}
                if self.lyric_control.is_running():
                    self.lyric_control.cancel()
                await self.karaoke_message.delete()
                self.karaoke_message = None
                self.karaoke_message_id = None
                await interaction.followup.edit_message(message_id = interaction.message.id, embed = self.create_embed(), view = self)
                return
            else:
                if not self.history_song[self.position-1].song.karaoke:
                    await interaction.followup.send(content = "本首歌詞因無法取得時間軸，故無法提供此功能" , ephemeral = True)
                    self.karaoke_object = {}
                    return
                else:
                    self.karaoke = True
                    await interaction.followup.edit_message(message_id = interaction.message.id, embed = self.create_embed(), view = self)
                    await self.seek_lyric(None)
        else:
            await interaction.followup.send(content = "等待下一句歌詞中...請稍後再試",ephemeral = True)

    def create_embed(self) -> Embed:
        if self.player.paused:
            self.play_type = self.PlayType.PAUSING
        else:
            self.play_type = self.PlayType.PLAYING
        if (self.player.current.length // 1000 // 3600) > 24:
            self.play_type = self.PlayType.LIVE

        return self.create_current_song_embed(self.current_song)

    def create_current_song_embed(self,song:wavelink.Playable) -> Embed:
        miko = Embed(colour = Colour.random())
        miko.set_author(name = "🎧現正播放中...")
        miko.set_thumbnail(url = song.artwork)
        miko.add_field(name = "🎯名稱:", value = song.title)
        miko.add_field(name = "🔗網址:", value = song.uri)
        miko.add_field(name = "🔬歌曲來源:",value = f'{Platform.YOUTUBE.value}Youtube' if song.source else f'{Platform.SPOTIFY.value}Spotify',inline = False)
        miko.add_field(name = "⌛長度:", value = f"{song.length // 1000 // 3600:02d}:{(song.length // 1000 % 3600) // 60:02d}:{song.length // 1000 % 60:02d}" if self.play_type != self.PlayType.LIVE else "直播中", inline = False)
        miko.add_field(name = "⏩播放速度:", value = f"{self.speed}x")
        miko.add_field(name = "📼進度:", value = self.get_current_song_position(), inline = False)
        miko.add_field(name = "🔊音量:", value = f"{self.get_volume()}%", inline = False)
        miko.add_field(name = "🚩目前序位:", value = self.get_current_queue())
        self.ui_control()
        self.temp_embed = miko
        return miko

    def get_volume(self) -> int:
        return self.player.volume

    async def set_volume(self, volume:int):
        await self.player.set_volume(volume)

    def get_current_queue(self) -> str:
        return f"{self.position}/{self.song_count}"

    def refresh_song_count(self):
        self.song_count = self.player.queue.count + self.player.queue.history.count + (1 if self.player.current is not None else 0)
        if(self.player.current is not None):
            try:
                self.player.queue.history.index(self.player.current)
                self.song_count -= 1
            except (ValueError):
                pass

    async def __get_current_song_list(self, interaction: Interaction):
        await interaction.response.defer()
        histroy = HistorySongView(self, self.player,self.position)
        await interaction.followup.send(content = histroy.song_list, view = histroy,ephemeral = True)

    def get_current_song_position(self) -> str:
        position = self.player.position
        return f"{int(position) // 1000 // 3600:02d}:{(int(position) // 1000 % 3600) // 60:02d}:{int(position) // 1000 % 60:02d}" if self.play_type != self.PlayType.LIVE else "-" 

    def ui_control(self):
        self.clear_items()
        if not self.player.paused:
            self.add(Button(style = ButtonStyle.gray, label = "暫停",emoji = "⏸️"), self.__play_and_pause)
        else:
            self.add(Button(style = ButtonStyle.green, label = "播放",emoji = "▶️"), self.__play_and_pause)
        self.add(Button(style = ButtonStyle.red, label = "停止",emoji = "⏹️"), self.__stop_callback)
        self.add(Button(style = ButtonStyle.primary,label = "跳過", emoji = "⏭️"), self.__skip_callback)
        self.add(Button(style = ButtonStyle.red, label = "刪除",emoji = "⛔"), self.__delete_callback)
        self.add(Button(style = ButtonStyle.green, label = "調整音量/播放速度",emoji = "🔊"), self.__volume_callback)
        if self.position == self.song_count:
            self.children[2].disabled = True
        if not self.cycle:
            self.add(Button(style = ButtonStyle.gray, label = "循環:關",emoji = "🔄"), self.__cycle_callback)
        else:
            self.add(Button(style = ButtonStyle.green, label = "循環:開",emoji = "🔄"), self.__cycle_callback)
        if self.cycle_type == self.CycleType.SINGLE:
            self.add(Button(style = ButtonStyle.primary, label = "循環模式:單首",emoji = "🔂"), self.__cycle_type_callback)
        else:
            self.add(Button(style = ButtonStyle.green, label = "循環模式:全部",emoji = "🔁"), self.__cycle_type_callback)
        # if isinstance(self.history_song[self.position-1],HistorySong):
        #     if isinstance(self.history_song[self.position-1].song,STSong):
        #         self.add(Button(style = ButtonStyle.primary, label = "顯示歌詞",emoji = "📓"),self.__get_lyric_callback)
        #         if not self.karaoke:
        #             self.add(Button(style = ButtonStyle.gray, label = "卡拉OK:關",emoji = "🎤"),self.__karaoke_callback)
        #         else:
        #             self.add(Button(style = ButtonStyle.green, label = "卡拉OK:開",emoji = "🎤"),self.__karaoke_callback)
        self.add(Button(style = ButtonStyle.primary, label = "當前歌單",emoji = "📢"), self.__get_current_song_list)
        self.add(Button(style = ButtonStyle.green, label = "調整音樂時間",emoji = "⏳"), self.__seek_callback)
        
        if self.play_type == self.PlayType.LIVE:
            # 如果是直播，則不允許調整時間
            self.children[8].disabled = True

    def add_base_button(self):
        pass

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, value: WebhookMessage):
        self._message = value
    
    @property
    def karaoke_message(self):
        return self._karaoke_message

    @karaoke_message.setter
    def karaoke_message(self, value: WebhookMessage):
        self._karaoke_message = value

    @tasks.loop(minutes = 5)
    async def refresh_webhook(self):
        self.message:WebhookMessage = await self.channel.fetch_message(self.message_id)
        if self.karaoke_message is not None:
            self.karaoke_message:WebhookMessage = await self.channel.fetch_message(self.karaoke_message_id)

    @tasks.loop(seconds = 10)
    async def refresh_panel(self):
        self.refresh_song_count()
        await self.message.edit(content=None, embed=self.create_embed(), view=self)

    @tasks.loop(seconds = 1)
    async def lyric_control(self):
        sorted_keys = self.karaoke_object["sorted_keys"]
        self.karaoke_object["position"] += 1
        position = self.karaoke_object["position"]
        lyric_string = self.karaoke_object["lyrics"][sorted_keys[position]]
        player_position = self.player.position
        if lyric_string != "":
            await self.karaoke_message.edit(content = lyric_string)
        else:
            await self.karaoke_message.edit(content = "歌曲已結束，等待下一首歌曲")
        try:
            #有可能因為延遲而造成歌詞跟不上 因此需要跳過一句直接到下一句等待
            if (sorted_keys[position + 1] - player_position) < 0: 
                self.karaoke_object["position"] += 1
                position = self.karaoke_object["position"]
                lyric_string = self.karaoke_object["lyrics"][sorted_keys[position]]
                await self.karaoke_message.edit(content = lyric_string)
            self.lyric_control.change_interval(seconds = (int((sorted_keys[position + 1] - player_position)) / 1000))
        except IndexError: #歌曲播完後取消task
            if self.lyric_control.is_running():
                self.lyric_control.cancel()

    #尋找當前歌詞 play_position:指定當前歌曲位置 設為None = 當前歌曲位置
    async def seek_lyric(self,play_position:Union[int,None]):
        if play_position is None:
            play_position = self.player.position
        self.karaoke_object["lyrics"] = self.history_song[self.position-1].song.lyrics
        sorted_keys = sorted(self.karaoke_object["lyrics"].keys())
        self.karaoke_object["sorted_keys"] = sorted_keys
        sleep_secs = 0
        for index,ms in enumerate(sorted_keys):
            if play_position <= ms:
                self.karaoke_object["position"] = index - 1
                if index == 0:
                    self.karaoke_object["position"] = index #開頭第一句的position補正
                    lyric_string = self.karaoke_object["lyrics"][ms]
                    sleep_secs = int((sorted_keys[index + 1] - play_position)) / 1000 #如果還沒開始第一句就等待到第二句開始
                else:
                    lyric_string = self.karaoke_object["lyrics"][sorted_keys[index - 1]]
                    sleep_secs = int((ms - play_position)) / 1000 #等待到下一句開始
                self.karaoke_object["lyric_string"] = lyric_string 
                if self.karaoke_message is None:
                    self.karaoke_message:WebhookMessage = await self.karaoke_object["interaction"].followup.send(content = self.karaoke_object["lyric_string"])
                    self.karaoke_message_id = self.karaoke_message.id
                    self.lyric_control.change_interval(seconds = 1)
                else:
                    await self.karaoke_message.edit(content = self.karaoke_object["lyric_string"])
                    self.lyric_control.change_interval(seconds = 1)
                self.lyric_iswaiting = True
                await asyncio.sleep(sleep_secs)
                self.lyric_iswaiting = False 
                self.lyric_control.start()
                break

    def toEmbed(self, bot: commands.Bot, guild_id: int, index: int = 0) -> Embed:
        guild = bot.get_guild(guild_id)
        miko = Embed(colour = Colour.random())
        miko.set_author(name= f"📻第 {index+1} 個音樂控制面板:")
        miko.set_thumbnail(url = self.history_thumbnails[self.position-1])
        miko.add_field(name = "🎯伺服器名稱:", value = guild.name, inline = False)
        miko.add_field(name = "👑擁有者:", value = f"{guild.owner}", inline = False)
        miko.add_field(name = "⚡當前狀態:", value = f"{self.play_type.value}", inline = False)
        miko.add_field(name = "🎧現正播放中:", value = self.player.current.title, inline = False)
        miko.add_field(name = "⏩播放速度:", value = f"{self.speed}x")
        miko.add_field(name = "🔊音量:", value = f"{self.get_volume()}%", inline = False)
        miko.add_field(name = "🚩目前序位:", value = self.get_current_queue())
        return miko

#歌單選擇視窗
class SelectPlaylistView(CustomView):

    def __init__(self, playlists: dict):
        super().__init__(timeout=None)
        self.playlists = playlists #所有歌單
        self.position = 0 #當前播放清單位置
        self.current_playlist:Tuple[str,Playlist] = None #當前播放清單
        self.temp_playlist:List[Union[Song]] = None #暫存播放清單(因隨機跟指定都會跟原本的播放清單不同順序)
        self.random:bool = False #隨機播放
        self.specified:bool = False #指定位置播放
        self.add_base_button()

    class New_Playlist_Modal(Modal):
        def __init__(self, view):
            super().__init__(title="建立新的播放清單:")
            self.view:SelectPlaylistView = view
            self.playlists = view.playlists
            self.name = TextInput(label='請輸入名字:(上限45個字)', style = TextStyle.short)
            self.add_item(self.name)

        async def on_submit(self, interaction: Interaction):
            await interaction.response.defer(ephemeral = True)
            if len(self.name.value) <= 45:
                current = not self.playlists.__contains__(self.name.value)
                if current:
                    sql.create_new_playlist(self.name.value, interaction.user.id)
                    self.playlists[self.name.value] = Playlist([], interaction.user)
                await interaction.followup.edit_message(message_id = interaction.message.id, content = "建立成功" if current else f"建立失敗，{self.name.value} 已存在",
                                                        view = self.view, embed = await self.view.get_current_playlist_embed())
            else:
                await interaction.followup.edit_message(message_id = interaction.message.id, content = "已超過規定的字數(45)，請重新輸入",
                                                        view = self.view, embed = await self.view.get_current_playlist_embed())

    class Double_Check_Delete_Playlist_Modal(Modal):
        def __init__(self, view):
            super().__init__(title = "再次確認刪除清單:")
            self.view:SelectPlaylistView = view
            self.playlists = view.playlists
            self.current_playlist = view.current_playlist
            self.name = TextInput(label = f'請再次輸入名字:', style = TextStyle.short , placeholder = self.current_playlist[0])
            self.add_item(self.name)

        async def on_submit(self, interaction: Interaction):
            await interaction.response.defer(ephemeral = True)
            if self.current_playlist[0] == self.name.value:
                sql.delete_playlist(self.name.value)
                self.playlists.pop(self.name.value)
                if self.view.position != 0:
                    self.view.position -= 1
            await interaction.followup.edit_message(message_id = interaction.message.id, content="刪除成功" if self.current_playlist[0] == self.name.value else "刪除失敗，輸入不一致",
                                                    view = self.view, embed = await self.view.get_current_playlist_embed())

    class Update_Playlist_title_Modal(Modal):
        def __init__(self, view):
            super().__init__(title="更換當前播放清單名稱:")
            self.view = view
            self.playlists = view.playlists
            self.current_playlist = view.current_playlist
            self.name = TextInput(label='請輸入新的名字:', style = TextStyle.short)
            self.add_item(self.name)

        async def on_submit(self, interaction: Interaction):
            await interaction.response.defer(ephemeral = True)
            current = not self.playlists.__contains__(self.name.value)
            if current:
                sql.update_playlist_name(
                    self.current_playlist[0], self.name.value)
                self.playlists[self.name.value] = self.playlists[self.current_playlist[0]]
                self.playlists.pop(self.current_playlist[0])
            await interaction.followup.edit_message(message_id = interaction.message.id, content = "更新成功" if current else f"更新失敗，{self.name.value} 已存在",
                                                    view = self.view, embed = await self.view.get_current_playlist_embed())

    class Set_Position_To_Play_Modal(Modal):
        def __init__(self, view):
            super().__init__(title="您想要從哪一首開始播放:")
            self.view:SelectPlaylistView = view
            self.current_playlist = view.current_playlist[1].song_list
            self.position = TextInput(label=f"請輸入位置(1~{len(self.current_playlist)}):",default = "1")
            self.add_item(self.position)

        async def on_submit(self, interaction: Interaction):
            try:
                if int(self.position.value) > len(self.current_playlist):
                    await interaction.response.send_message("輸入的數字超過範圍，請重新輸入",ephemeral = True)
                else:
                    self.view.temp_playlist = self.current_playlist[int(self.position.value)-1:] + self.current_playlist[:int(self.position.value)-1]
                    self.view.specified = True
                    await self.view.play(interaction)
            except:
                await interaction.response.send_message("請不要輸入數字以外的字元",ephemeral = True)

    def ui_control(self):
        for i in range(1,10):
            if i == 3:
                continue
            self.children[i].disabled = False
        if self.position == 0:
            self.children[1].disabled = True
        if (len(self.playlists)-1 == self.position) or (len(self.playlists) == 0):
            self.children[2].disabled = True
        if (len(self.playlists) == 0):
            for i in range(4,10):
                self.children[i].disabled = True
        if self.current_playlist is not None:
            if (len(self.current_playlist[1].song_list) == 0):
                for i in range(7,10):
                    self.children[i].disabled = True

    def add_base_button(self):
        self.clear_items()
        self.add(Button(style = ButtonStyle.red,label = "關閉", emoji = "❌"), self.cancel)
        self.add(Button(style = ButtonStyle.green, label = "上一項",emoji = "⏮️", custom_id = "-1"), self.next)
        self.add(Button(style = ButtonStyle.green, label = "下一項",emoji = "⏭️", custom_id = "1"), self.next)
        self.add(Button(style = ButtonStyle.gray,label = "新增歌單", emoji = "📈"), self.new)
        self.add(Button(style = ButtonStyle.gray,label = "刪除歌單", emoji = "📉"), self.delete)
        self.add(Button(style = ButtonStyle.green,label = "更換歌單名稱", emoji = "▶️"), self.update)
        self.add(Button(style = ButtonStyle.green,label = "編輯歌單", emoji = "⚙️"), self.edit)
        self.add(Button(style = ButtonStyle.green,label = "指定位置播放", emoji = "🎲"), self.specified_play)
        self.add(Button(style = ButtonStyle.green,label = "隨機播放", emoji = "🎲"), self.random_play)
        self.add(Button(style = ButtonStyle.green,label = "播放", emoji = "▶️"), self.play)

    async def get_current_playlist_embed(self) -> Embed:
        playlist = list(self.playlists.items())
        miko = Embed(colour = Colour.random())
        if len(playlist) == 0:
            miko.set_author(name = f"裡面空空的，什麼也沒有")
            self.current_playlist = None
        else:
            self.current_playlist = (title, item) = playlist[self.position]
            miko.set_thumbnail(url = item.creater.display_avatar.url)
            miko.set_author(name = f"第 {self.position + 1} 個播放清單(共 {len(self.playlists)} 個):")
            miko.add_field(name = "🎯名稱:", value = title, inline = False)
            miko.add_field(name = "👑擁有者:", value = f"{item.creater.display_name}", inline = False)
            miko.add_field(name = "🎵播放次數:", value = f"{item.play_count}次", inline = False)
            miko.add_field(name = "🎲歌曲數目:", value = f"共 {len(item.song_list)} 首", inline = False)
            if len(item.song_list) != 0:
                songs = ""
                for index, song in enumerate(item.song_list[:5]):
                    songs = f"{songs}{index + 1}. {f'{Platform.YOUTUBE.value}' if song.source == 'youtube' else f'{Platform.SPOTIFY.value}'} {song.title} {song.duration_str}\n"
                miko.add_field(name = "👀預覽歌曲(前5首):",value = f"{songs}", inline = False)
            else:
                miko.add_field(name = "👀預覽歌曲(前5首):", value = "裡面空空的，什麼也沒有", inline = False)
        self.ui_control()
        return miko

    async def new(self, interaction: Interaction):
        if interaction.user.id != MANAGE_USER_ID:
            for playlist in self.playlists.values():
                if playlist.creater.id == interaction.user.id:
                    await interaction.response.send_message("您已經擁有一個歌單，無法再建立", ephemeral = True)
                    return
        await interaction.response.send_modal(self.New_Playlist_Modal(self))
    
    # 刪除歌單
    async def delete(self, interaction: Interaction):
        if interaction.user.id == MANAGE_USER_ID or interaction.user.id == self.current_playlist[1].creater.id:
            await interaction.response.send_modal(self.Double_Check_Delete_Playlist_Modal(self))
        else:
            await interaction.response.send_message("您不是此歌單的擁有者或管理員，無法刪除", ephemeral = True)
            return
    
    # 更換歌單名稱
    async def update(self, interaction: Interaction):
        if interaction.user.id == MANAGE_USER_ID or interaction.user.id == self.current_playlist[1].creater.id:
            await interaction.response.send_modal(self.Update_Playlist_title_Modal(self))
        else:
            await interaction.response.send_message("您不是此歌單的擁有者或管理員，無法更換名稱", ephemeral = True)
            return

    # 編輯歌單
    async def edit(self, interaction: Interaction):
        edit_view = PlayerlistEditView(self)
        await interaction.response.edit_message(view = edit_view, embed = await edit_view.get_current_playlist_song_embed())

    # 指定位置播放
    async def specified_play(self,interaction:Interaction):
        await interaction.response.send_modal(self.Set_Position_To_Play_Modal(self))

    # 隨機播放
    async def random_play(self,interaction:Interaction):
        self.temp_playlist = self.current_playlist[1].song_list.copy()
        random.shuffle(self.temp_playlist)
        self.random = True
        await self.play(interaction)        

    # 播放
    async def play(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        players: dict = interaction.client.get_cog("Music").players
        control_panels: dict = interaction.client.get_cog("Music").control_panels
        if interaction.user.voice is None:
            await interaction.followup.send("請先加入語音頻道，再點選此按鈕", ephemeral = True)
            return
        elif not players.__contains__(interaction.guild_id):
            players[interaction.guild_id] = await interaction.user.voice.channel.connect(cls = wavelink.Player)
            await asyncio.sleep(1)
            if players[interaction.guild_id].connected:
                control_panels[interaction.guild_id] = ControlView(players.get(interaction.guild_id))
                control_panels.get(interaction.guild_id).channel = interaction.channel
            else:
                players.pop(interaction.guild_id)
                await interaction.followup.send("無法加入語音頻道，請稍後再嘗試", ephemeral=True)
                return
        control_panel:ControlView = control_panels[interaction.guild_id]
        player:wavelink.Player = players[interaction.guild_id]
        if self.random or self.specified:
            song_list = self.temp_playlist
            self.random = False
            self.specified = False
        else:
            song_list = self.current_playlist[1].song_list
        self.current_playlist[1].play_count += 1
        sql.update_playlist_play_count(self.current_playlist[0], self.current_playlist[1].play_count)
        if player.queue.is_empty and not player.playing:
            song_list[0].setExtras({"user": interaction.user.id})
            for item in song_list[1:len(song_list)]:
                item.setExtras({"user": interaction.user.id})
                await player.queue.put_wait(item.track)
            await player.play(song_list[0].track)
            await interaction.followup.edit_message(interaction.message.id, content = f'已點播歌單 `{self.current_playlist[0]}` 現正準備播放中......')
            control_panel.message = await interaction.followup.send(content = None, embed = control_panel.create_embed(), view = control_panel, ephemeral = False)
            control_panel.message_id = control_panel.message.id
            control_panel.refresh_webhook.start()
            control_panel.refresh_panel.start()
        else:
            for item in song_list:
                item.setExtras({"user": interaction.user.id})
                await player.queue.put_wait(item.track)
            await interaction.followup.edit_message(interaction.message.id, content = f'已插入歌單 `{self.current_playlist[0]}` 至隊列中 共{len(song_list)}首')
            await control_panel.message.edit(content = f"<@{interaction.user.id}> 已插入歌單 `{self.current_playlist[0]}` 至隊列中  共{len(song_list)}首", embed = control_panel.create_embed(), view = control_panel)

    # 關閉視窗
    async def cancel(self, interaction: Interaction):
        await interaction.response.edit_message(content="已關閉", embed = None, view = None)

    # 切換至上/下一項
    async def next(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        self.position += int(interaction.data.get('custom_id'))
        self.ui_control()
        await interaction.followup.edit_message(interaction.message.id, content = None, view = self, embed = await self.get_current_playlist_embed())

#歌單編輯視窗
class PlayerlistEditView(CustomView):

    def __init__(self, view: SelectPlaylistView):
        super().__init__(timeout=None)
        self.title = view.current_playlist[0]
        self.playlist = view.current_playlist[1].song_list
        self.last_view = view
        self.start = 0
        self.end = 10
        self.add_base_button()

    class New_Song_Modal(Modal):
        def __init__(self, view):
            super().__init__(title = "新增新的歌曲:")
            self.view:PlayerlistEditView = view
            self.query = TextInput(label = '請輸入歌曲名稱或網址:', style = TextStyle.long)
            self.position = TextInput(label = f'請輸入要插入的位置:(1 ~ {len(self.view.playlist)+1 if len(self.view.playlist) != 0 else "1"})',
                                      style = TextStyle.short, default = len(self.view.playlist)+1 if len(self.view.playlist) != 0 else "1")
            self.add_item(self.query)
            self.add_item(self.position)

        async def on_submit(self, interaction: Interaction):
            await interaction.response.defer(ephemeral = True)
            try:
                if (int(self.position.value) > (len(self.view.playlist) + 1)) or int(self.position.value) <= 0:
                    await interaction.followup.edit_message(interaction.message.id, content = f"無效的位置{self.position.value}，請重新輸入", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                    return
                else:
                    if re.match(URL_REGEX, self.query.value):
                        song = Song(self.query.value)
                        await song.init()
                        # if spotify.decode_url(self.query.value) is None:
                        #     #youtube音樂
                        #     check = yarl.URL(self.query.value)
                        #     if not check.query.get("list"):
                        #         song = YTSong(self.query.value)
                        #         result = await song.init()
                        #         if isinstance(result,tuple):
                        #             await interaction.followup.edit_message(interaction.message.id, content = f"無效的歌曲，請重新輸入", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                        #             return
                        #     else:
                        #         await interaction.followup.edit_message(interaction.message.id, content = f"不支援歌單型式，請重新輸入", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                        #         return
                        # else:
                        #     #spotify音樂
                        #     type = spotify.decode_url(self.query.value)['type']
                        #     if (type == spotify.SpotifySearchType.track):
                        #         song = STSong(self.query.value)
                        #         result = await song.init()
                        #         if isinstance(result,tuple):
                        #             await interaction.followup.edit_message(interaction.message.id, content = f"無效的歌曲，請重新輸入", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                        #             return
                        #     else:
                        #         await interaction.followup.edit_message(interaction.message.id, content = f"不支援歌單型式，請重新輸入", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                        #         return
                        song.setExtras({"joiner":interaction.user.id})
                        if int(self.position.value) == len(self.view.playlist) + 1:
                            self.view.playlist.append(song)
                        else:
                            self.view.playlist.insert(int(self.position.value) - 1, song)
                        sql.insert_playlist_song(self.view.title, int(self.position.value), self.query.value, interaction.user.id)
                        await interaction.followup.edit_message(interaction.message.id, content = f"插入成功，已插入位置:{self.position.value}", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                    else:
                        search = await wavelink.Playable.search(self.query.value)
                        select, miko = await create_selectsongview(search[:20], Mode.NORMAL, None, None, self.view, int(self.position.value))
                        await interaction.followup.edit_message(interaction.message.id, content = None, view = select, embeds = miko)
            except ValueError:
                await interaction.followup.edit_message(interaction.message.id, content = f"無效的位置{self.position.value}，請重新輸入", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                
    class Delete_Song_Modal(Modal):
        def __init__(self, view):
            super().__init__(title = "刪除指定歌曲:")
            self.view = view
            self.position = TextInput(label = f'請輸入要刪除的歌曲位置:(1 ~ {len(self.view.playlist)})', style = TextStyle.short, default = f"{len(self.view.playlist)}")
            self.add_item(self.position)

        async def on_submit(self, interaction: Interaction):
            await interaction.response.defer(ephemeral = True)
            try:
                if (int(self.position.value) > (len(self.view.playlist))) or int(self.position.value) <= 0:
                    await interaction.followup.edit_message(interaction.message.id, content = f"無效的位置{self.position.value}，請重新輸入", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                    return
                else:
                    self.view.playlist.pop(int(self.position.value) - 1)
                    sql.delete_playlist_song(self.view.title, int(self.position.value))
                    await interaction.followup.edit_message(interaction.message.id, content = f"刪除成功，已刪除位置 {self.position.value} 的歌曲", view = self.view, embed = await self.view.get_current_playlist_song_embed())
            except ValueError:
                await interaction.followup.edit_message(interaction.message.id, content = f"無效的位置{self.position.value}，請重新輸入", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                return

    class Swap_Song_Modal(Modal):
        def __init__(self, view):
            super().__init__(title = "指定歌曲交換位置:")
            self.view = view
            self.old = TextInput(label = f'請輸入要被交換的歌曲位置1:(1 ~ {len(self.view.playlist)})', style = TextStyle.short)
            self.new = TextInput(label = f'請輸入要被交換的歌曲位置2:(1 ~ {len(self.view.playlist)})', style = TextStyle.short)
            self.add_item(self.old)
            self.add_item(self.new)

        async def on_submit(self, interaction: Interaction):
            await interaction.response.defer(ephemeral = True)
            try:
                self.old = int(self.old.value)
                self.new = int(self.new.value)
                if (self.old > (len(self.view.playlist))) or (self.old <= 0) or (self.old == self.new) or (self.new > (len(self.view.playlist))) or (self.new <= 0):
                    await interaction.followup.edit_message(interaction.message.id, content = f"無效的位置1: {self.old} 或位置2: {self.new} ，請重新輸入", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                    return
                else:
                    self.view.playlist[self.old - 1], self.view.playlist[self.new - 1] = self.view.playlist[self.new - 1], self.view.playlist[self.old - 1]
                    sql.update_playlist_song_order(self.view.title, self.old, self.new)
                    await interaction.followup.edit_message(interaction.message.id, content = f"交換成功，已交換指定歌曲位置", view = self.view, embed = await self.view.get_current_playlist_song_embed())
            except ValueError:
                await interaction.followup.edit_message(interaction.message.id, content = f"無效的位置1: {self.old.value} 或位置2: {self.new.value} ，請重新輸入", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                return

    async def get_current_playlist_song_embed(self) -> Embed:
        miko = Embed(colour = Colour.random())
        miko.set_author(name = f"{self.title} 的音樂清單:")
        if len(self.playlist) == 0:
            miko.add_field(name = chr(173), value = "裡面空空的，什麼也沒有", inline = False)
        else:
            miko.add_field(name = "🎯歌曲數目:", value = f"共 {len(self.playlist)} 首", inline = False)
            songs = ""
            for index, song in enumerate(self.playlist[self.start:self.end]):
                songs = f"{songs}{index + self.start + 1}. {f'{Platform.YOUTUBE.value}' if song.source == 'youtube' else f'{Platform.SPOTIFY.value}'} {song.title} {song.duration_str}\n"
            miko.add_field(name = "🎯預覽歌曲:", value = f"{songs}", inline = False)
        self.ui_control()
        return miko

    def add_base_button(self):
        self.add(Button(style = ButtonStyle.red,label = "返回", emoji = "◀️"), self.cancel)
        self.add(Button(style = ButtonStyle.blurple, label = "上十首",emoji = "⏮️", custom_id = "-10"), self.next)
        self.add(Button(style = ButtonStyle.blurple, label = "下十首",emoji = "⏭️", custom_id =  "10"), self.next)
        self.add(Button(style = ButtonStyle.green,label = "新增歌曲", emoji = "📥"), self.new)
        self.add(Button(style = ButtonStyle.red,label = "刪除歌曲", emoji = "📤"), self.delete)
        self.add(Button(style = ButtonStyle.green,label = "交換歌曲位置", emoji = "⚙️"), self.edit)

    def ui_control(self):
        for i in range(1,6):
            if i == 3:
                continue
            self.children[i].disabled = False
        if self.start == 0:
            self.children[1].disabled = True
        if len(self.playlist) <= self.end:
            self.children[2].disabled = True
        if len(self.playlist) == 0:
            self.children[4].disabled = True
        if len(self.playlist) <= 1:
            self.children[5].disabled = True

    # 新增歌曲
    async def new(self, interaction: Interaction):
        if interaction.user.id == MANAGE_USER_ID or interaction.user.id == self.current_playlist[1].creater.id:
            await interaction.response.send_modal(self.New_Song_Modal(self))
        else:
            await interaction.response.send_message("您不是此歌單的擁有者或管理員，無法新增歌曲", ephemeral = True)
            return

    # 刪除歌曲
    async def delete(self, interaction: Interaction):
        if interaction.user.id == MANAGE_USER_ID or interaction.user.id == self.current_playlist[1].creater.id:
            await interaction.response.send_modal(self.Delete_Song_Modal(self))
        else:
            await interaction.response.send_message("您不是此歌單的擁有者或管理員，無法刪除歌曲", ephemeral = True)
            return

    # 交換歌曲位置
    async def edit(self, interaction: Interaction):
        if interaction.user.id == MANAGE_USER_ID or interaction.user.id == self.current_playlist[1].creater.id:
            await interaction.response.send_modal(self.Swap_Song_Modal(self))
        else:
            await interaction.response.send_message("您不是此歌單的擁有者或管理員，無法交換歌曲位置", ephemeral = True)
            return

    # 關閉視窗
    async def cancel(self, interaction: Interaction):
        self.last_view.add_base_button()
        await interaction.response.edit_message(content = None, view = self.last_view, embed = await self.last_view.get_current_playlist_embed())

    # 切換至上/下十首
    async def next(self, interaction: Interaction):
        await interaction.response.defer(ephemeral = True)
        self.start += int(interaction.data.get('custom_id'))
        self.end += int(interaction.data.get('custom_id'))
        await interaction.followup.edit_message(interaction.message.id, content = None, view = self, embed = await self.get_current_playlist_song_embed())

#歌曲選擇視窗
class SelectSongView(CustomView):
    def __init__(self, tracks:List[wavelink.Playable], mode: Mode = Mode.PLAY, player: wavelink.Player = None, control_panel: ControlView = None, edit_view: PlayerlistEditView = None, position: int = None):
        super().__init__(timeout = None)
        self.tracks = tracks
        self.mode = mode
        self.player = player
        self.control_panel = control_panel
        self.start = 0
        self.end = 5
        self.edit_view = edit_view
        self.position = position

    async def _init(self) -> List[Embed]:
        self.add_base_button()
        return self.create_song_embed()

    def create_song_embed(self) -> List[Embed]:
        miko = []
        for index, song in enumerate(self.tracks[self.start:self.end]):
            neko = Embed(colour = Colour.random())
            neko.set_author(name = f"第{index+1}首:")
            neko.set_thumbnail(url = song.artwork)
            neko.add_field(name = "歌名:", value = f"{song.title}")
            neko.add_field(name = "長度", value = f"{song.length // 1000 // 3600:02d}:{(song.length // 1000 % 3600) // 60:02d}:{song.length // 1000 % 60:02d}", inline = False)
            miko.append(neko)
        self.ui_control(self.tracks[self.start:self.end])
        return miko

    async def cancel(self, interaction: Interaction):
        if self.mode == Mode.PLAY:
            if self.player.queue.is_empty and not self.player.playing:
                await self.player.disconnect()
                interaction.client.get_cog("Music").players.pop(interaction.guild_id)
                interaction.client.get_cog("Music").control_panels.pop(interaction.guild_id)
        await interaction.response.edit_message(content = "已關閉", embed = None, view = None)

    async def select_song(self, interaction: Interaction):
        await interaction.response.defer(ephemeral = True)
        song = self.tracks[int(interaction.data.get('custom_id'))+self.start]
        song.extras = {"user": interaction.user.id}
        if self.mode == Mode.PLAY:
            if self.player.queue.is_empty and not self.player.playing:
                await self.player.play(song)
                await interaction.followup.edit_message(interaction.message.id, content = f'已新增歌曲 `{song.title}` 現正準備播放中....', embed = None, view = None)
                self.control_panel.message = await interaction.followup.send(embed = self.control_panel.create_embed(), view = self.control_panel)
                self.control_panel.message_id = self.control_panel.message.id
                self.control_panel.refresh_webhook.start()
                self.control_panel.refresh_panel.start()
            else:
                await self.player.queue.put_wait(song)
                await interaction.followup.edit_message(interaction.message.id, content = f'已新增歌曲 `{song.title}` 至隊列中 序列位置為:{self.control_panel.song_count+1}', embed = None, view = None)
                await self.control_panel.message.edit(content = f"<@{interaction.user.id}> 已新增歌曲 `{song.title}` 至隊列中", embed=self.control_panel.create_embed(), view = self.control_panel)
        else:
            if self.position == len(self.edit_view.playlist) + 1:
                self.edit_view.playlist.append((song, interaction.user))
            else:
                self.edit_view.playlist.insert(
                    self.position - 1, (song, interaction.user))
            sql.insert_playlist_song(self.edit_view.title, self.position, song.uri, interaction.user.id)
            await interaction.followup.edit_message(interaction.message.id, content = f"插入成功，已插入位置:{self.position}", view = self.edit_view, embed = await self.edit_view.get_current_playlist_song_embed())

    async def next(self, interaction: Interaction):
        await interaction.response.defer(ephemeral = True)
        self.start += int(interaction.data.get('custom_id'))
        self.end += int(interaction.data.get('custom_id'))
        miko = self.create_song_embed()
        await interaction.followup.edit_message(interaction.message.id, view = self, embeds = miko)

    def add_base_button(self):
        self.add(Button(style = ButtonStyle.red,label = "關閉", emoji = "❌"), self.cancel)
        for value, key in OPTIONS.items():
            self.add(Button(style = ButtonStyle.primary,label = f"{key+1}", emoji = f"{value}", custom_id = f"{key}"), self.select_song)
        self.add(Button(style = ButtonStyle.green, label = "前五首",emoji = "⏮️", custom_id = "-5"), self.next)
        self.add(Button(style = ButtonStyle.green, label = "下五首",emoji = "⏭️", custom_id =  "5"), self.next)

    def ui_control(self, current_track:List[wavelink.Playable]):
        self.children[6].disabled = False
        self.children[7].disabled = False
        if self.start == 0:
            self.children[6].disabled = True
        if len(current_track) < 5:
            self.children[7].disabled = True
            for i in range(len(current_track)+1, 6):
                self.children[i].disabled = True
        else:
            for i in range(1, len(current_track)+1):
                self.children[i].disabled = False
        if self.end == 20:
            self.children[7].disabled = True

async def create_selectsongview(tracks:List[wavelink.Playable], mode = Mode.PLAY, player = None, control_panel = None, edit_view = None, position = None) -> Tuple[SelectSongView,List[Embed]]:
    select_song = SelectSongView(tracks, mode, player, control_panel, edit_view, position)
    miko = await select_song._init()
    return select_song, miko

class Music(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.node : wavelink.Node = wavelink.Node(uri=WL_HOST, password=WL_PASSWORD)
        self.players:Dict[int,wavelink.Player] = {}
        self.control_panels:Dict[int,ControlView] = {}
        self.subscribe_channel_list = {}  # 訂閱頻道暫存
        self.watch_list = {}  #正在被觀察的直播dict
        bot.loop.create_task(self.create_nodes())

    notification_group = app_commands.Group(name = 'notification', description = 'channel', guild_only = True)

    @notification_group.command(name = "add", description = "新增頻道直播/新片通知")
    async def add(self, interaction: Interaction, platform: str, channel_url: str):
        if interaction.user.voice is None:
            await interaction.response.send_message("請先加入語音頻道，再輸入指令", ephemeral = True)
            return
        await interaction.response.defer(ephemeral = True)
        message = await interaction.followup.send(f"搜尋中...", ephemeral = True)
        notice = await nc.create_channel(get_platform_info_by_string(platform), channel_url)
        if notice == None:
            await message.edit(content=f"無法新增此頻道直播/新片通知，請稍後再試")
            return
        g = Guild(interaction.guild_id, interaction.channel.id,interaction.user.voice.channel.id)
        channels: list = self.get_subscribe_channel(interaction.guild_id,interaction.user.id == MANAGE_USER_ID)
        if self.notification_channels.__contains__(notice.id):
            if g.guild_id in self.notification_channels.get(notice.id)['channels'].keys():
                await message.edit(content=f"已經新增過{notice.title}的直播/新片通知")
            else:
                self.notification_channels.get(
                    notice.id)['channels'][g.guild_id] = {'obj': g}
                channels.append(notice)
                sql.subscribe_channel(notice, g)
                await message.edit(content=f"已新增{notice.title}的直播/新片通知")
        else:
            self.notification_channels[notice.id] = {
                "obj": notice,
                "channels": {
                    g.guild_id: {'obj': g}
                }
            }
            channels.append(notice)
            sql.subscribe_channel(notice, g)
            await message.edit(content=f"已新增{notice.title}的直播/新片通知")
        print(self.notification_channels)

    @add.autocomplete('platform')
    async def add_autocomplete_callback(self, interaction: Interaction, current: str):
        return [
            app_commands.Choice(name='youtube', value='youtube'),
            app_commands.Choice(name='twitch', value='twitch')
        ]

    @notification_group.command(name="delete", description="移除頻道直播/新片通知")
    async def delete(self, interaction: Interaction, deleted_channel_title: str):
        if deleted_channel_title == "None":
            await interaction.response.send_message(f"目前此群沒有訂閱任何頻道的通知喔", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        deleted_guild_id = interaction.guild_id
        subscribe_channels: list[Channel] = self.get_subscribe_channel(deleted_guild_id,interaction.user.id == MANAGE_USER_ID)
        for item in subscribe_channels:
            if item.title == deleted_channel_title:
                deleted_channel = item
                channels: dict = self.notification_channels.get(item.id)['channels']
                if len(channels) != 1:
                    channels.pop(deleted_guild_id)
                else:
                    self.notification_channels.pop(deleted_channel.id)

                if len(subscribe_channels) != 1:
                    subscribe_channels.remove(item)
                else:
                    self.subscribe_channel_list.pop(deleted_guild_id)

                break
        sql.unsubscribe_channel(deleted_channel, deleted_guild_id)
        await interaction.followup.send(f"已移除{deleted_channel.title}的直播/新片通知")

    @delete.autocomplete('deleted_channel_title')
    async def delete_autocomplete_callback(self, interaction: Interaction, current: str):
        channel_list:List[Channel] = self.get_subscribe_channel(interaction.guild_id,interaction.user.id == MANAGE_USER_ID)
        if len(channel_list) != 0:
            return [
                app_commands.Choice(name=f'{item.title} - {get_string_by_platform(item.platform)}', value=f'{item.title}') for item in channel_list
            ]
        else:
            return [
                app_commands.Choice(name="None", value="None")
            ]

    @notification_group.command(name="show", description="顯示所有訂閱的頻道")
    async def show(self, interaction: Interaction):
        channels: list[Channel] = self.get_subscribe_channel(interaction.guild_id,interaction.user.id == MANAGE_USER_ID)
        channel_embeds = []
        for (index, channel) in enumerate(channels):
            channel_embeds.append(channel.toEmbed(interaction.guild_id,index))
        await interaction.response.send_message(content=f"此群訂閱的所有頻道(共{len(channels)}個):", embeds=channel_embeds[0:10], view=ObjectEmbedView(channel_embeds), ephemeral=True)

    def get_subscribe_channel(self, guild_id: int,is_manager:bool) -> List[Channel]:
        if not self.subscribe_channel_list.__contains__(guild_id):
            self.subscribe_channel_list[guild_id] = []
            channel_list = self.subscribe_channel_list.get(guild_id)
            for (key, value) in self.notification_channels.items():
                if is_manager or guild_id in value['channels']:
                    channel:Channel = value['obj'].copy()
                    channel.setGuild_id(list(value["channels"].keys()))
                    channel_list.append(channel)
        else:
            channel_list = self.subscribe_channel_list.get(guild_id)
        return channel_list

    async def timeout_user(self, *, user_id: int, guild_id: int, until):
        headers = {"Authorization": f"Bot {self.bot.http.token}"}
        url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}"
        timeout = (datetime.datetime.utcnow() + datetime.timedelta(minutes=until)).isoformat()
        json = {'communication_disabled_until': timeout}
        async with self.bot.session.patch(url, json = json, headers = headers) as session:
            if session.status in range(200, 299):
                return True
            return False

    async def create_nodes(self):
        await self.bot.wait_until_ready()
        await wavelink.Pool.connect(nodes= [self.node],client=self.bot,cache_capacity=None)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"Node {payload.session_id} is ready!")
        print("正在讀取歌單中......")
        start_time = time.time()
        self.playlists, self.notification_channels = await nc.init(self.bot)
        end_time = time.time()
        print(f"歌單讀取完成，共花費{end_time-start_time}秒")
        nc.checkforvideos.start(self.bot,self.notification_channels,self.players,self.control_panels,self.watch_list)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self,payload: wavelink.TrackEndEventPayload): #當播放結束後執行
        player = payload.player
        if player is not None:
            guild_id = list(self.players.keys())[list(self.players.values()).index(player)]
            control_panel: ControlView = self.control_panels[guild_id]
            control_panel.previous_song = payload.track
            control_panel.refresh_song_count()
            song_length = control_panel.song_count

            if control_panel.delete & (song_length != 0): #刪除模式且不只一首歌(只有一首歌時刪除會報錯)
                player.queue.history.remove(payload.track) #刪除當前歌曲
                song_length -= 1
                if not control_panel.karaoke:
                    control_panel.delete = False

            #(未開循環且播到最後一首)或(只有一首歌)或(停止播放)
            if ((not control_panel.cycle) & (control_panel.position == song_length)) | ((control_panel.position == 0) & (song_length == 0) | control_panel.stop):
                await player.disconnect()
                self.players.pop(guild_id)
                if control_panel.refresh_panel.is_running():
                    control_panel.refresh_panel.cancel()
                await control_panel.message.delete()
                if control_panel.refresh_webhook.is_running():
                    control_panel.refresh_webhook.cancel()
                if control_panel.karaoke:
                    await control_panel.karaoke_message.delete()
                self.control_panels.pop(guild_id)
                return
            
            #(開啟循環全部)且(開啟循環)且(播到最後一首)
            if (control_panel.cycle_type == control_panel.CycleType.ALL) & (control_panel.cycle) & (control_panel.position == song_length):  
                control_panel.position = 1
                return
            
            #(開啟循環單曲)且(開啟循環)
            if (control_panel.cycle_type == control_panel.CycleType.SINGLE) & (control_panel.cycle) & (not control_panel.skip) & (not control_panel.delete):
                return
            
            #判斷下一首是不是直播 如果是須把autoplay關掉 才不會播放音樂
            try:
                next_song = player.queue.peek(control_panel.position)
            except (wavelink.QueueEmpty, IndexError):
                next_song = None
            if next_song is not None:
                if next_song.is_stream:
                    player.autoplay = wavelink.AutoPlayMode.disabled
                    if control_panel.refresh_panel.is_running():
                        control_panel.refresh_panel.cancel()
                else:
                    player.autoplay = wavelink.AutoPlayMode.partial
                    if not control_panel.refresh_panel.is_running():
                        control_panel.refresh_panel.start()
            
            #未開循環且(開循環且(開啟循環全部))且不只一首
            control_panel.position += 1

    @commands.Cog.listener()
    async def on_wavelink_track_start(self,payload: wavelink.TrackStartEventPayload): #當播放開始時執行
        player = payload.player
        if player is not None:
            guild_id = list(self.players.keys())[list(self.players.values()).index(player)]
            control_panel: ControlView = self.control_panels[guild_id]
            control_panel.current_song = player.current
            control_panel.refresh_song_count()
            await control_panel.set_volume(DEFAULT_VOLUME) #還原成初始音量
            control_panel.skip = False #暫時
            try:
                next_song = player.queue.peek(control_panel.position)
            except (wavelink.QueueEmpty,IndexError):
                next_song = None
            if control_panel.message is not None:
                await control_panel.message.edit(embed = control_panel.create_embed(), view = control_panel)

    @app_commands.guild_only()
    @app_commands.command(name="play", description="播放音樂")
    @app_commands.describe(query ="網址或關鍵字")
    async def play(self, interaction: Interaction, query: str):
        
        async def play_single_song(query:str):
            try:
                song = (await wavelink.Playable.search(query))[0]
                song.extras = {"user": interaction.user.id}
            except (IndexError,ValueError,wavelink.LavalinkLoadException) as e:
                await interaction.followup.edit_message(message.id, content=f"播放音樂時發生錯誤，錯誤訊息為:{e}")
                await asyncio.sleep(3)
                deleted = self.players.pop(interaction.guild_id)
                await deleted.disconnect()
            if player.queue.is_empty and not player.playing:
                try:
                    await player.play(song)
                except:
                    await interaction.followup.edit_message(message.id, content=f'無法播放 `{song.title}` 造成您的不便，請見諒')
                    await asyncio.sleep(3)
                    deleted = self.players.pop(interaction.guild_id)
                    await deleted.disconnect()
                    return
                await interaction.followup.edit_message(message.id, content=f'已新增歌曲 `{song.title}` 現正準備播放中......')
                control_panel.refresh_song_count()
                control_panel.message = await interaction.followup.send(embed = control_panel.create_embed(), view = control_panel, ephemeral = False)
                control_panel.message_id = control_panel.message.id
                control_panel.refresh_webhook.start()
                control_panel.refresh_panel.start()
            else:
                await player.queue.put_wait(song)
                await interaction.followup.edit_message(message.id, content=f'已新增歌曲 `{song.title}` 至隊列中 序列位置為:{control_panel.song_count+1}')
                control_panel.refresh_song_count()
                await control_panel.message.edit(content = f"<@{interaction.user.id}> 已新增歌曲 `{song.title}` 至隊列中", embed = control_panel.create_embed(), view = control_panel)
        
        async def play_multiply_song(song_list:List[wavelink.Playable]):
            # 添加是誰播放的
            control_panel.song_count += len(song_list)
            for song in song_list:
                song.extras = {"user": interaction.user.id}

            if player.queue.is_empty and not player.playing:
                await player.queue.put_wait(song_list)
                await player.play(player.queue.get())
                await interaction.followup.edit_message(message.id, content = f'已新增歌單/專輯 現正準備播放中......')
                control_panel.message = await interaction.followup.send(embed = control_panel.create_embed(), view = control_panel, ephemeral = False)
                control_panel.message_id = control_panel.message.id
                control_panel.refresh_webhook.start()
                control_panel.refresh_panel.start()
            else:
                await player.queue.put_wait(song_list)
                await interaction.followup.edit_message(message.id, content = f'已新增歌單/專輯 至隊列中 共{len(song_list)}首')
                await control_panel.message.edit(content = f"<@{interaction.user.id}> 已新增歌單/專輯 至隊列中  共{len(song_list)}首", embed = control_panel.create_embed(), view = control_panel)

        if interaction.user.voice is None:
            await interaction.response.send_message("請先加入語音頻道，再輸入指令", ephemeral = True)
            return
        elif not self.players.__contains__(interaction.guild_id):
            self.players[interaction.guild_id] = await interaction.user.voice.channel.connect(cls = wavelink.Player)
            await asyncio.sleep(1)
            if self.players[interaction.guild_id].connected:
                self.control_panels[interaction.guild_id] = ControlView(self.players.get(interaction.guild_id))
                self.control_panels.get(interaction.guild_id).channel = interaction.channel
            else:
                self.players.pop(interaction.guild_id)
                await interaction.response.send_message("無法加入語音頻道，請稍後再嘗試", ephemeral = True)
                return

        control_panel:ControlView = self.control_panels.get(interaction.guild_id)
        player:wavelink.Player = self.players.get(interaction.guild_id)
        await interaction.response.defer(ephemeral = True)
        message: WebhookMessage = await interaction.followup.send(f"搜尋中...")

        if re.match(URL_REGEX, query):
            check = yarl.URL(query)
            if check.query.get("list"):
                try:
                    search: wavelink.Playable = await wavelink.Playable.search(query)
                except ValueError as e:
                    await interaction.followup.edit_message(message.id, content = f"播放歌單時發生錯誤，錯誤訊息為:{e}")
                    await asyncio.sleep(3)
                    deleted = self.players.pop(interaction.guild_id)
                    await deleted.disconnect()
                    return
                await play_multiply_song(search)
            else:
                await play_single_song(query)
                
        else:
            search = await wavelink.Playable.search(query)
            select, miko = await create_selectsongview(search[:20], Mode.PLAY, player, control_panel)
            await interaction.followup.edit_message(message.id, view=select, embeds=miko)

    @app_commands.guild_only()
    @app_commands.command(name="playlist", description="自訂歌單")
    async def playlist(self, interaction: Interaction):
        select_view = SelectPlaylistView(self.playlists)
        await interaction.response.send_message(view = select_view, embed = await select_view.get_current_playlist_embed(), ephemeral = True)

    @app_commands.guild_only()
    @app_commands.command(name="clean", description="如果bot出現問題，清除暫存")
    async def clean(self, interaction: Interaction):
        control_panels:Dict[int,ControlView] = interaction.client.get_cog("Music").control_panels
        players:Dict[int,wavelink.Player] = interaction.client.get_cog("Music").players
        if self.players.__contains__(interaction.guild_id):
            if not self.players[interaction.guild_id].connected or control_panels.get(interaction.guild_id).message is None:
                if control_panels.get(interaction.guild_id).refresh_panel.is_running():
                    control_panels.get(interaction.guild_id).refresh_panel.cancel()
                if control_panels.get(interaction.guild_id).refresh_webhook.is_running():
                    control_panels.get(interaction.guild_id).refresh_webhook.cancel()
                if control_panels.get(interaction.guild_id).message is not None:
                    await control_panels.get(interaction.guild_id).message.delete()
                if self.players[interaction.guild_id].connected:
                    await self.players[interaction.guild_id].disconnect()
                players.pop(interaction.guild_id)
                control_panels.pop(interaction.guild_id)
                await interaction.response.send_message("已清除暫存，請使用[/play <歌曲或網址>]重新開始", ephemeral = True)
            else:
                await interaction.response.send_message("請使用控制面板上的stop來清除暫存", ephemeral = True)
        else:
            await interaction.response.send_message("目前沒有需要清除的暫存，請使用[/play <歌曲或網址>]開始", ephemeral = True)
        
            
        
async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot)) #目前為全域都有安裝此模組(非特定伺服器) ,guilds = [Object(id = 469507920808116234)]
    await bot.tree.sync() #guild = Object(id = 469507920808116234)
    #https://about.abstractumbra.dev/discord.py/2023/01/29/sync-command-example.html 參考資料
