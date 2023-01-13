import asyncio
import datetime
from typing import List, Tuple
from discord import app_commands, ButtonStyle, Colour, Embed, Interaction , TextStyle , User, WebhookMessage
from discord.ext import commands, tasks
from discord.ui import Button, Modal, TextInput
from enum import Enum
from lib.common import Channel, CustomView, Guild, Live, ObjectEmbedView, Playlist, Song
import lib.notification as nc
import lib.sql as sql
import re
import wavelink
import yarl

URL_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
OPTIONS = {
    "1️⃣": 0,
    "2️⃣": 1,
    "3️⃣": 2,
    "4️⃣": 3,
    "5️⃣": 4
}

class HistorySong():

    def __init__(self, song: Song, user: User):
        self.song = song
        self.user = user

class HistorySongView(CustomView):

    def __init__(self, player: wavelink.Player, history_song: list, position: int):
        super().__init__(timeout = None)
        self.player = player
        self.history_song = history_song
        self.position = position
        self.start = 0
        self.end = 10
        self.get_history_song_info()
        self.add_base_button()

    def get_history_song_info(self):
        if (self.player.is_playing() | self.player.is_paused()) & (self.player.source is not None):
            self.song_list = f"<:moo:1017734836426915860>當前歌單:(第{self.start+1}首 ~ 第{self.end if len(self.history_song) >= self.end else len(self.history_song)}首 共{len(self.history_song)}首)\n"
            if self.position - 1 < self.start:
                is_done = False
            else:
                is_done = True
            for index, item in enumerate(self.history_song[self.start:self.end]):
                self.song_list = self.song_list + f"{index + 1}. {item.song.title}(<@{item.user.id}>)"
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
        if len(self.history_song) <= self.end:
            self.children[1].disabled = True

class Mode(Enum):
    NORMAL = "普通"
    PLAY = "播放"
    PLAYLIST = "清單"

class ControlView(CustomView):

    def __init__(self, player: wavelink.Player, mode: Mode = Mode.PLAY):
        super().__init__(timeout=None)
        self.player = player
        self.length = 0
        self.position = 1
        self.speed = 1.0
        self.history_thumbnails = []
        self.cycle = False
        self.cycle_type = self.CycleType.SINGLE
        self.skip = False
        self._stop = False
        self._message = None
        self.history_song = []
        self.message_id = None
        self.channel = None
        self.mode = mode

    class CycleType(Enum):
        SINGLE = "單首"
        ALL = "全部"

    class PlayType(Enum):
        PLAYING = "播放中"
        PAUSING = "暫停中"

    class VolumeModal(Modal):
        def __init__(self, control_panel):
            super().__init__(title="調整音量大小/播放速度")
            self.control_panel = control_panel
            self.volume = TextInput(label = '音量(0-1000):', style = TextStyle.short, default = f"{control_panel.player.volume}")
            self.speed = TextInput(label = '播放速度(0-無限):', style = TextStyle.short, default = f"{control_panel.speed}")
            self.add_item(self.volume)
            self.add_item(self.speed)

        async def on_submit(self, interaction: Interaction):
            self.control_panel.speed = float(self.speed.value)
            await self.control_panel.player.set_filter(wavelink.Filter(timescale = wavelink.Timescale(speed = float(self.speed.value))), seek = True)
            await self.control_panel.set_volume(int(self.volume.value))
            await interaction.response.edit_message(embed=self.control_panel.create_embed(), view = self.control_panel)

    async def play_and_pause(self, interaction: Interaction):
        if not self.player.is_paused():
            await self.player.pause()
        else:
            await self.player.resume()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    async def cycle_callback(self, interaction: Interaction):
        if not self.cycle:
            self.cycle = True
        else:
            self.cycle = False
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    async def cycle_type_callback(self, interaction: Interaction):
        if self.cycle_type == self.CycleType.SINGLE:
            self.cycle_type = self.CycleType.ALL
        else:
            self.cycle_type = self.CycleType.SINGLE
        await interaction.response.edit_message(embed = self.create_embed(), view = self)

    async def skip_callback(self, interaction: Interaction):
        if not isinstance(self.history_song[self.position - 1], Live):
            self.skip = True
            await self.player.stop()
            await asyncio.sleep(1.5)
        else:
            if not isinstance(self.history_song[self.position], Live):
                new = await self.player.queue.get_wait()
                await self.player.play(new)
                if int(new.duration/3600) < 24:  # 非直播
                    if not self.refresh_panel.is_running():
                        self.refresh_panel.start()
                else:  # 直播
                    self.refresh_panel.cancel()
            self.position += 1
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    async def stop_callback(self, interaction: Interaction):
        if not isinstance(self.history_song[self.position - 1], Live):
            self.player.queue.clear()
            self._stop = True
            await self.player.stop()
        else:
            await self.player.disconnect()
            await self.message.delete()
            self.refresh_panel.cancel()
            self.refresh_webhook.cancel()
            interaction.client.get_cog("Music").players.pop(interaction.guild_id)
            interaction.client.get_cog("Music").control_panels.pop(interaction.guild_id)

    async def volume_callback(self, interaction: Interaction):
        await interaction.response.send_modal(self.VolumeModal(self))

    async def delete_callback(self, interaction: Interaction):
        self.history_song.pop(self.position-1)
        self.history_thumbnails.pop(self.position-1)
        self.position -= 1
        await self.player.stop()
        await asyncio.sleep(1.5)
        if self.position != 0:
            await interaction.response.edit_message(content = f"<@{interaction.user.id}>已移除上首歌曲", embed = self.create_embed(), view = self)

    def create_current_live_waiting_embed(self) -> Embed:
        miko = Embed(colour = Colour.random())
        miko.set_author(name = "🎧現正等待中...")
        miko.set_thumbnail(url = self.history_thumbnails[self.position-1])
        miko.add_field(name = "🎯名稱:", value = self.history_song[self.position-1].title)
        miko.add_field(name = "🔗網址:", value = self.history_song[self.position-1].url)
        if self.history_song[self.position-1].reconnection_times == 0:
            miko.add_field(name = "⌛距離開始直播還有:", value = f"<t:{self.history_song[self.position-1].start_time}:R>", inline = False)
        else:
            miko.add_field(name = "⌛等待直播開始:", value = f"已嘗試連接 {self.history_song[self.position-1].reconnection_times} 次", inline = False)
        if self.history_song[self.position-1].platform == "youtube":
            miko.add_field(name = "<:yt:1032640435375583342>頻道:",value = self.history_song[self.position-1].channel_title)
        elif self.history_song[self.position-1].platform == "twitch":
            miko.add_field(name = "<:th:1032831426959245423>頻道:",value = self.history_song[self.position-1].channel_title)
        miko.add_field(name = "🔊音量:", value = f"{self.get_volume()}%", inline = False)
        miko.add_field(name = "🚩目前序位:", value = self.get_current_queue())
        self.ui_control()
        return miko

    def create_embed(self) -> Embed:
        if isinstance(self.history_song[self.position - 1], HistorySong):
            return self.create_current_song_embed()
        else:
            return self.create_current_live_waiting_embed()

    def create_current_song_embed(self) -> Embed:
        miko = Embed(colour = Colour.random())
        miko.set_author(name = "🎧現正播放中...")
        miko.set_thumbnail(url = self.history_thumbnails[self.position-1])
        miko.add_field(name = "🎯名稱:", value = self.player.source.info.get("title"))
        if self.player.source.info.get("uri") is not None:
            miko.add_field(name = "🔗網址:", value = self.player.source.info.get("uri"))
        miko.add_field(name = "⌛長度:", value = f"{str(int(self.player.source.duration/3600)).zfill(2)}:{str(int(self.player.source.duration/60%60)).zfill(2)}:{str(int(self.player.source.duration%60)).zfill(2)}" if int(
                                                    self.player.source.duration/3600) < 24 else "直播中", inline = False)
        miko.add_field(name = "⏩播放速度:", value = f"{self.speed}x")
        miko.add_field(name = "📼進度:", value = self.get_current_song_position(), inline = False)
        miko.add_field(name = "🔊音量:", value = f"{self.get_volume()}%", inline = False)
        miko.add_field(name = "🚩目前序位:", value = self.get_current_queue())
        self.ui_control()
        return miko

    def get_volume(self) -> int:
        return self.player.volume

    async def set_volume(self, volume:int):
        await self.player.set_volume(volume)

    def get_current_queue(self) -> str:
        self.length = len(self.history_song)
        return f"{self.position}/{self.length}"

    async def get_current_song_list(self, interaction: Interaction):
        if (self.player.is_playing() | self.player.is_paused()) & (self.player.source is not None):
            histroy = HistorySongView(
                self.player, self.history_song, self.position)
            await interaction.response.send_message(content = histroy.song_list, view = histroy, ephemeral = True)
        else:
            await interaction.response.send_message(content="請在播放或暫停時再點選此按鈕", ephemeral=True)

    def get_current_song_position(self) -> str:
        return f"{str(int(self.player.position/3600)).zfill(2)}:{str(int(self.player.position/60%60)).zfill(2)}:{str(int(self.player.position%60)).zfill(2)}/{str(int(self.player.source.duration/3600)).zfill(2)}:{str(int(self.player.source.duration/60%60)).zfill(2)}:{str(int(self.player.source.duration%60)).zfill(2)}" if int(self.player.source.duration/3600) < 24 else "-"

    def ui_control(self):
        self.clear_items()
        if not self.player.is_paused():
            self.add(Button(style = ButtonStyle.gray, label = "暫停",emoji = "⏸️"), self.play_and_pause)
        else:
            self.add(Button(style = ButtonStyle.green, label = "播放",emoji = "▶️"), self.play_and_pause)
        self.add(Button(style = ButtonStyle.red, label = "停止",emoji = "⏹️"), self.stop_callback)
        self.add(Button(style = ButtonStyle.primary,label = "跳過", emoji = "⏭️"), self.skip_callback)
        self.add(Button(style = ButtonStyle.red, label = "刪除",emoji = "⛔"), self.delete_callback)
        self.add(Button(style = ButtonStyle.green, label = "調整音量/播放速度",emoji = "🎤"), self.volume_callback)
        if self.position == self.length:
            self.children[2].disabled = True
        if not self.cycle:
            self.add(Button(style = ButtonStyle.gray, label = "循環:關",emoji = "🔄"), self.cycle_callback)
        else:
            self.add(Button(style = ButtonStyle.green, label = "循環:開",emoji = "🔄"), self.cycle_callback)
        if self.cycle_type == self.CycleType.SINGLE:
            self.add(Button(style = ButtonStyle.primary, label = "循環模式:單首",emoji = "🔂"), self.cycle_type_callback)
        else:
            self.add(Button(style = ButtonStyle.green, label = "循環模式:全部",emoji = "🔁"), self.cycle_type_callback)
        self.add(Button(style = ButtonStyle.primary, label = "當前歌單",emoji = "📢"), self.get_current_song_list)

    def add_base_button(self):
        pass

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, value: WebhookMessage):
        self._message = value

    @tasks.loop(minutes=5)
    async def refresh_webhook(self):
        self.message = await self.channel.fetch_message(self.message_id)

    @tasks.loop(seconds = 5)
    async def refresh_panel(self):
        await self.message.edit(content=None, embed=self.create_embed(), view=self)

    def toEmbed(self, bot: commands.Bot, guild_id: int, index: int = 0) -> Embed:
        guild = bot.get_guild(guild_id)
        miko = Embed(colour = Colour.random())
        miko.set_author(name= f"📻第 {index+1} 個音樂控制面板:")
        miko.set_thumbnail(url = self.history_thumbnails[self.position-1])
        miko.add_field(name = "🎯伺服器名稱:", value = guild.name, inline = False)
        miko.add_field(name = "👑擁有者:", value = f"{guild.owner}", inline = False)
        miko.add_field(name = "⚡當前狀態:", value = f"{self.PlayType.PLAYING.value}" if not self.player.is_paused() 
                                                        else f"{self.PlayType.PAUSING.value}", inline = False)
        miko.add_field(name = "🎧現正播放中:", value = self.player.source.info.get("title"), inline = False)
        miko.add_field(name = "⏩播放速度:", value = f"{self.speed}x")
        miko.add_field(name = "🔊音量:", value = f"{self.get_volume()}%", inline = False)
        miko.add_field(name = "🚩目前序位:", value = self.get_current_queue())
        return miko

class SelectPlaylistView(CustomView):

    def __init__(self, playlists: dict):
        super().__init__(timeout=None)
        self.playlists = playlists
        self.position = 0
        self.current_playlist = None
        self.add_base_button()

    class New_Playlist_Modal(Modal):
        def __init__(self, view):
            super().__init__(title="建立新的播放清單:")
            self.view = view
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
                await interaction.followup.edit_message(message_id = interaction.message.id, content = "已超過規定字數，請重新輸入",
                                                        view = self.view, embed = await self.view.get_current_playlist_embed())

    class Double_Check_Delete_Playlist_Modal(Modal):
        def __init__(self, view):
            super().__init__(title = "再次確認刪除清單:")
            self.view = view
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

    def ui_control(self):
        self.children[1].disabled = False
        self.children[2].disabled = False
        self.children[4].disabled = False
        self.children[5].disabled = False
        self.children[6].disabled = False
        self.children[7].disabled = False
        if self.position == 0:
            self.children[1].disabled = True
        if (len(self.playlists)-1 == self.position) or (len(self.playlists) == 0):
            self.children[2].disabled = True
        if (len(self.playlists) == 0):
            self.children[4].disabled = True
            self.children[5].disabled = True
            self.children[6].disabled = True
            self.children[7].disabled = True
        if self.current_playlist is not None:
            if (len(self.current_playlist[1].song_list) == 0):
                self.children[7].disabled = True

    def add_base_button(self):
        self.clear_items()
        self.add(Button(style = ButtonStyle.red,label = "關閉", emoji = "❌"), self.cancel)
        self.add(Button(style = ButtonStyle.green, label = "上一項",emoji = "⏮️", custom_id = "-1"), self.next)
        self.add(Button(style = ButtonStyle.green, label = "下一項",emoji = "⏭️", custom_id = "1"), self.next)
        self.add(Button(style = ButtonStyle.gray,label = "新增歌單", emoji = "📈"), self.new)
        self.add(Button(style = ButtonStyle.gray,label = "刪除歌單", emoji = "📉"), self.delete)
        self.add(Button(style = ButtonStyle.green,label = "更換歌單名稱", emoji = "▶️"), self.update)
        self.add(Button(style = ButtonStyle.green,label = "編輯歌單", emoji = "⚙️"), self.edit)
        self.add(Button(style = ButtonStyle.green,label = "播放歌單", emoji = "▶️"), self.play)

    async def get_current_playlist_embed(self) -> Embed:
        playlist = list(self.playlists.items())
        miko = Embed(colour = Colour.random())
        if len(playlist) == 0:
            miko.set_author(name = f"裡面空空的，什麼也沒有")
            self.current_playlist = None
        else:
            self.current_playlist = (title, item) = playlist[self.position]
            miko.set_author(name = f"第 {self.position + 1} 個播放清單(共 {len(self.playlists)} 個):")
            miko.add_field(name = "🎯名稱:", value = title, inline = False)
            miko.add_field(name = "🎲歌曲數目:", value = f"共 {len(item.song_list)} 首", inline = False)
            if len(item.song_list) != 0:
                songs = ""
                for index, song in enumerate(item.song_list[:5]):
                    songs = f"{songs}{index + 1}. {song[0].title} {song[0].duration_str}\n"
                miko.add_field(name = "👀預覽歌曲(前5首):",value = f"{songs}", inline = False)
            else:
                miko.add_field(name = "👀預覽歌曲(前5首):", value = "裡面空空的，什麼也沒有", inline = False)
        self.ui_control()
        return miko

    async def new(self, interaction: Interaction):
        await interaction.response.send_modal(self.New_Playlist_Modal(self))

    async def delete(self, interaction: Interaction):
        await interaction.response.send_modal(self.Double_Check_Delete_Playlist_Modal(self))

    async def update(self, interaction: Interaction):
        await interaction.response.send_modal(self.Update_Playlist_title_Modal(self))

    async def edit(self, interaction: Interaction):
        edit_view = PlayerlistEditView(self)
        await interaction.response.edit_message(view = edit_view, embed = await edit_view.get_current_playlist_song_embed())

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
            if players[interaction.guild_id].is_connected():
                control_panels[interaction.guild_id] = ControlView(
                    players.get(interaction.guild_id), Mode.PLAYLIST)
                control_panels.get(interaction.guild_id).channel = interaction.channel
            else:
                players.pop(interaction.guild_id)
                await interaction.followup.send("無法加入語音頻道，請稍後再嘗試", ephemeral=True)
                return
        control_panel = control_panels[interaction.guild_id]
        player = players[interaction.guild_id]
        for (song, user) in self.current_playlist[1].song_list:
            control_panel.history_thumbnails.append(song.thumbnail)
            control_panel.history_song.append(HistorySong(song, user))
        if player.queue.is_empty and not player.is_playing() and len(control_panel.history_song) == len(self.current_playlist[1].song_list):
            await player.play(control_panel.history_song[0].song.track)
            for item in control_panel.history_song[1:len(control_panel.history_song)]:
                await player.queue.put_wait(item.song.track)
            await interaction.followup.edit_message(interaction.message.id, content = f'已點播歌單 `{self.current_playlist[0]}` 現正準備播放中......')
            control_panel.message: WebhookMessage = await interaction.followup.send(content = None, embed = control_panel.create_embed(), view = control_panel, ephemeral = False)
            control_panel.message_id = control_panel.message.id
            control_panel.refresh_webhook.start()
            control_panel.refresh_panel.start()
        else:
            for item in self.current_playlist[1].song_list:
                await player.queue.put_wait(item[0].track)
            await interaction.followup.edit_message(interaction.message.id, content = f'已插入歌單 `{self.current_playlist[0]}` 至隊列中 共{len(self.current_playlist[1].song_list)}首')
            await control_panel.message.edit(content = f"<@{interaction.user.id}> 已插入歌單 `{self.current_playlist[0]}` 至隊列中  共{len(self.current_playlist[1].song_list)}首", embed = control_panel.create_embed(), view = control_panel)

    async def cancel(self, interaction: Interaction):
        await interaction.response.edit_message(content="已關閉", embed = None, view = None)

    async def next(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        self.position += int(interaction.data.get('custom_id'))
        self.ui_control()
        await interaction.followup.edit_message(interaction.message.id, content = None, view = self, embed = await self.get_current_playlist_embed())

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
            self.view = view
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
                        result = await song.init()
                        if isinstance(result,tuple):
                            await interaction.followup.edit_message(interaction.message.id, content = f"無效的歌曲，請重新輸入", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                            return
                        if int(self.position.value) == len(self.view.playlist) + 1:
                            self.view.playlist.append((song, interaction.user))
                        else:
                            self.view.playlist.insert(
                                int(self.position.value) - 1, (song, interaction.user))
                        sql.insert_playlist_song(self.view.title, int(self.position.value), self.query.value, interaction.user.id)
                        await interaction.followup.edit_message(interaction.message.id, content = f"插入成功，已插入位置:{self.position.value}", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                    else:
                        search = await wavelink.YouTubeTrack.search(query = self.query.value)
                        select, miko = await create_selectsongview(search[:20], Mode.NORMAL, None, None, self.view, int(self.position.value))
                        await interaction.followup.edit_message(interaction.message.id, content = None, view = select, embeds = miko)
            except ValueError:
                await interaction.followup.edit_message(interaction.message.id, content = f"無效的位置{self.position.value}，請重新輸入", view = self.view, embed = await self.view.get_current_playlist_song_embed())
                return

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
                songs = f"{songs}{index + self.start + 1}. {song[0].title} {song[0].duration_str}\n"
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
        self.children[1].disabled = False
        self.children[2].disabled = False
        self.children[4].disabled = False
        self.children[5].disabled = False
        if self.start == 0:
            self.children[1].disabled = True
        if len(self.playlist) <= self.end:
            self.children[2].disabled = True
        if len(self.playlist) == 0:
            self.children[4].disabled = True
        if len(self.playlist) <= 1:
            self.children[5].disabled = True

    async def new(self, interaction: Interaction):
        await interaction.response.send_modal(self.New_Song_Modal(self))

    async def delete(self, interaction: Interaction):
        await interaction.response.send_modal(self.Delete_Song_Modal(self))

    async def edit(self, interaction: Interaction):
        await interaction.response.send_modal(self.Swap_Song_Modal(self))

    async def cancel(self, interaction: Interaction):
        self.last_view.add_base_button()
        await interaction.response.edit_message(content = None, view = self.last_view, embed = await self.last_view.get_current_playlist_embed())

    async def next(self, interaction: Interaction):
        await interaction.response.defer(ephemeral = True)
        self.start += int(interaction.data.get('custom_id'))
        self.end += int(interaction.data.get('custom_id'))
        await interaction.followup.edit_message(interaction.message.id, content = None, view = self, embed = await self.get_current_playlist_song_embed())

class SelectSongView(CustomView):

    def __init__(self, tracks:List[wavelink.YouTubeTrack], mode: Mode = Mode.PLAY, player: wavelink.Player = None, control_panel: ControlView = None, edit_view: PlayerlistEditView = None, position: int = None):
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
            neko.set_thumbnail(url = song.thumbnail)
            neko.add_field(name = "歌名:", value = f"{song.title}")
            neko.add_field(name = f'長度', value = f'{str(int(song.duration/3600)).zfill(2)}:{str(int(song.duration/60%60)).zfill(2)}:{str(int(song.duration%60)).zfill(2)}', inline = False)
            neko.add_field(name = "是否為串流:", value = song.is_stream())
            miko.append(neko)
        self.ui_control(self.tracks[self.start:self.end])
        return miko

    async def cancel(self, interaction: Interaction):
        if self.mode == Mode.PLAY:
            if self.player.queue.is_empty and not self.player.is_playing():
                await self.player.disconnect()
                interaction.client.get_cog("Music").players.pop(interaction.guild_id)
                interaction.client.get_cog("Music").control_panels.pop(interaction.guild_id)
        await interaction.response.edit_message(content = "已關閉", embed = None, view = None)

    async def select_song(self, interaction: Interaction):
        await interaction.response.defer(ephemeral = True)
        song = Song(self.tracks[int(interaction.data.get('custom_id'))+self.start].info.get("uri"))
        await song.init()
        if self.mode == Mode.PLAY:
            self.control_panel.history_thumbnails.append(song.thumbnail)
            self.control_panel.history_song.append(HistorySong(song, interaction.user))
            if self.player.queue.is_empty and not self.player.is_playing() and len(self.control_panel.history_song) == 1:
                await self.player.play(song.track)
                await interaction.followup.edit_message(interaction.message.id, content = f'已新增歌曲 `{song.title}` 現正準備播放中....', embed = None, view = None)
                self.control_panel.message: WebhookMessage = await interaction.followup.send(embed = self.control_panel.create_embed(), view = self.control_panel)
                self.control_panel.message_id = self.control_panel.message.id
                self.control_panel.refresh_webhook.start()
                self.control_panel.refresh_panel.start()
            else:
                await self.player.queue.put_wait(song.track)
                await interaction.followup.edit_message(interaction.message.id, content = f'已新增歌曲 `{song.title}` 至隊列中 序列位置為:{self.control_panel.length}', embed = None, view = None)
                await self.control_panel.message.edit(content = f"<@{interaction.user.id}> 已新增歌曲 `{song.title}` 至隊列中", embed=self.control_panel.create_embed(), view = self.control_panel)
        else:
            if self.position == len(self.edit_view.playlist) + 1:
                self.edit_view.playlist.append((song, interaction.user))
            else:
                self.edit_view.playlist.insert(
                    self.position - 1, (song, interaction.user))
            sql.insert_playlist_song(self.edit_view.title, self.position, song.url, interaction.user.id)
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

    def ui_control(self, current_track:List[wavelink.YouTubeTrack]):
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

async def create_selectsongview(tracks:List[wavelink.YouTubeTrack], mode = Mode.PLAY, player = None, control_panel = None, edit_view = None, position = None) -> Tuple[SelectSongView,List[Embed]]:
    select_song = SelectSongView(tracks, mode, player, control_panel, edit_view, position)
    miko = await select_song._init()
    return select_song, miko

class Music(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players = {}
        self.control_panels = {}
        self.subscribe_channel_list = {}  # 訂閱頻道暫存
        self.watch_list = {}  # 直播觀察清單
        bot.loop.create_task(self.create_nodes())

    notification_group = app_commands.Group(name = 'notification', description = 'channel', guild_only = True)

    @notification_group.command(name = "add", description = "新增頻道直播/新片通知")
    async def add(self, interaction: Interaction, platform: str, channel_url: str):
        if interaction.user.voice is None:
            await interaction.response.send_message("請先加入語音頻道，再輸入指令", ephemeral = True)
            return
        await interaction.response.defer(ephemeral = True)
        message = await interaction.followup.send(f"搜尋中...", ephemeral = True)
        notice = await nc.create_channel(platform, channel_url)
        g = Guild(interaction.guild_id, interaction.channel.id,interaction.user.voice.channel.id)
        channels: list = self.get_subscribe_channel(interaction.guild_id)
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
        subscribe_channels: list = self.subscribe_channel_list.get(
            interaction.guild_id)
        for item in subscribe_channels:
            if item.title == deleted_channel_title:
                deleted_channel = item
                channels: dict = self.notification_channels.get(item.id)[
                    'channels']
                if len(channels) != 1:
                    channels.pop(interaction.guild_id)
                else:
                    self.notification_channels.pop(deleted_channel.id)

                if len(subscribe_channels) != 1:
                    subscribe_channels.remove(item)
                else:
                    self.subscribe_channel_list.pop(interaction.guild_id)

                break
        sql.unsubscribe_channel(deleted_channel, interaction.guild_id)
        await interaction.followup.send(f"已移除{deleted_channel.title}的直播/新片通知")

    @delete.autocomplete('deleted_channel_title')
    async def delete_autocomplete_callback(self, interaction: Interaction, current: str):
        channel_list:List[Channel] = self.get_subscribe_channel(interaction.guild_id)
        if len(channel_list) != 0:
            return [
                app_commands.Choice(name=f'{item.title} - {item.platform}', value=f'{item.title}') for item in channel_list
            ]
        else:
            return [
                app_commands.Choice(name="None", value="None")
            ]

    @notification_group.command(name="show", description="顯示所有訂閱的頻道")
    async def show(self, interaction: Interaction):
        channel_embeds = []
        channels: list = self.get_subscribe_channel(interaction.guild_id)
        for (index, channel) in enumerate(channels):
            channel_embeds.append(channel.toEmbed(index))
        await interaction.response.send_message(content=f"此群訂閱的所有頻道(共{len(channels)}個):", embeds=channel_embeds[0:10], view=ObjectEmbedView(channel_embeds), ephemeral=True)

    def get_subscribe_channel(self, guild_id: int) -> List[Channel]:
        if not self.subscribe_channel_list.__contains__(guild_id):
            self.subscribe_channel_list[guild_id] = []
            channel_list = self.subscribe_channel_list.get(guild_id)
            for (key, value) in self.notification_channels.items():
                if guild_id not in value['channels'].keys():
                    continue
                else:
                    channel_list.append(value['obj'])
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
        await wavelink.NodePool.create_node(bot = self.bot, host = "127.0.0.1", port = "2333", password = "youshallnotpass", region = "asia")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        self.node = node
        print(f"Node {node.identifier} is ready!")
        self.playlists, self.notification_channels = await nc.init(self.bot)
        nc.checkforvideos.start(self.bot,self.notification_channels,self.players,self.control_panels,self.watch_list)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: wavelink.Player, track: wavelink.Track, reason):
        guild_id = list(self.players.keys())[list(self.players.values()).index(player)]
        control_panel: ControlView = self.control_panels[guild_id]
        control_panel.speed = 1.0
        await player.set_filter(wavelink.Filter(timescale = wavelink.Timescale(speed = float(1.0))), seek = True)
        if not player.queue.is_empty:  # 隊列不為空
            if (control_panel.cycle_type == control_panel.CycleType.SINGLE) & control_panel.cycle & (not control_panel.skip):
                await player.play(track)
                return
        else:  # 按下停止後，隊列為空
            # (按下停止)或(未開循環且播到最後一首)
            if control_panel._stop | ((not control_panel.cycle) & (control_panel.position == control_panel.length)):
                await player.disconnect()
                self.players.pop(guild_id)
                control_panel.refresh_panel.cancel()
                await control_panel.message.delete()
                control_panel.refresh_webhook.cancel()
                self.control_panels.pop(guild_id)
                return
            else:
                if control_panel.cycle:
                    if control_panel.cycle_type == control_panel.CycleType.SINGLE:  # 開循環且開啟單首循環模式
                        await player.play(track)
                        return
                    else:  # 開循環且開啟全部循環模式
                        for item in control_panel.history_song:
                            if isinstance(item, HistorySong):
                                await player.queue.put_wait(item.song.track)
                        control_panel.position = 0

        if control_panel.skip:
            control_panel.skip = False
        #-------正常循環------#
        if not isinstance(control_panel.history_song[control_panel.position], Live):
            new = await player.queue.get_wait()
            await player.play(new)
            if int(new.duration/3600) < 24:  # 非直播
                if not control_panel.refresh_panel.is_running():
                    control_panel.refresh_panel.start()
            else:  # 直播
                control_panel.refresh_panel.cancel()
        control_panel.position += 1
        await control_panel.message.edit(embed = control_panel.create_embed(), view = control_panel)

    @app_commands.guild_only()
    @app_commands.command(name="play", description="播放音樂")
    async def play(self, interaction: Interaction, query: str):
        if interaction.user.voice is None:
            await interaction.response.send_message("請先加入語音頻道，再輸入指令", ephemeral = True)
            return
        elif not self.players.__contains__(interaction.guild_id):
            self.players[interaction.guild_id] = await interaction.user.voice.channel.connect(cls = wavelink.Player)
            await asyncio.sleep(1)
            if self.players[interaction.guild_id].is_connected():
                self.control_panels[interaction.guild_id] = ControlView(
                    self.players.get(interaction.guild_id))
                self.control_panels.get(interaction.guild_id).channel = interaction.channel
            else:
                self.players.pop(interaction.guild_id)
                await interaction.response.send_message("無法加入語音頻道，請稍後再嘗試", ephemeral = True)
                return

        control_panel = self.control_panels.get(interaction.guild_id)
        player = self.players.get(interaction.guild_id)
        await interaction.response.defer(ephemeral = True)
        message: WebhookMessage = await interaction.followup.send(f"搜尋中...")
        if re.match(URL_REGEX, query):
            check = yarl.URL(query)
            if check.query.get("list"):
                try:
                    search: wavelink.YouTubePlaylist = await wavelink.NodePool.get_node().get_playlist(wavelink.YouTubePlaylist, query)
                except wavelink.LoadTrackError as e:
                    await interaction.followup.edit_message(message.id, content = f"播放音樂時發生錯誤，錯誤訊息為:{e}")
                    await asyncio.sleep(3)
                    deleted = self.players.pop(interaction.guild_id)
                    await deleted.disconnect()
                    return
                for track in search.tracks:
                    song = Song(track.info.get('uri'))
                    await song.init()
                    control_panel.history_thumbnails.append(song.thumbnail)
                    control_panel.history_song.append(
                        HistorySong(song, interaction.user))
                if player.queue.is_empty and not player.is_playing() and len(control_panel.history_song) == len(search.tracks):
                    await player.play(search.tracks[0])
                    for song in search.tracks[1:len(search.tracks)]:
                        await player.queue.put_wait(song)
                    await interaction.followup.edit_message(message.id, content = f'已新增歌單 `{search.name}` 現正準備播放中......')
                    control_panel.message: WebhookMessage = await interaction.followup.send(embed = control_panel.create_embed(), view = control_panel, ephemeral = False)
                    control_panel.message_id = control_panel.message.id
                    control_panel.refresh_webhook.start()
                    control_panel.refresh_panel.start()
                else:
                    for song in search.tracks:
                        await player.queue.put_wait(song)
                    await interaction.followup.edit_message(message.id, content = f'已新增歌單 `{search.name}` 至隊列中 共{len(search.tracks)}首')
                    await control_panel.message.edit(content = f"<@{interaction.user.id}> 已新增歌單 `{search.name}` 至隊列中  共{len(search.tracks)}首", embed = control_panel.create_embed(), view = control_panel)
            else:
                song = Song(query)
                result = await song.init()
                if isinstance(result,bool):
                    control_panel.history_thumbnails.append(song.thumbnail)
                    control_panel.history_song.append(
                        HistorySong(song, interaction.user))
                    if player.queue.is_empty and not player.is_playing() and len(control_panel.history_song) == 1:
                        await player.play(song.track)
                        await interaction.followup.edit_message(message.id, content=f'已新增歌曲 `{song.title}` 現正準備播放中......')
                        control_panel.message: WebhookMessage = await interaction.followup.send(embed = control_panel.create_embed(), view = control_panel, ephemeral = False)
                        control_panel.message_id = control_panel.message.id
                        control_panel.refresh_webhook.start()
                        if int(song.duration/3600) < 24:
                            control_panel.refresh_panel.start()
                    else:
                        await player.queue.put_wait(song.track)
                        await interaction.followup.edit_message(message.id, content=f'已新增歌曲 `{song.title}` 至隊列中 序列位置為:{control_panel.length}')
                        await control_panel.message.edit(content = f"<@{interaction.user.id}> 已新增歌曲 `{song.title}` 至隊列中", embed = control_panel.create_embed(), view = control_panel)
                else:
                    await interaction.followup.edit_message(message.id, content=f"播放音樂時發生錯誤，錯誤訊息為:{result[1]}")
                    await asyncio.sleep(3)
                    deleted = self.players.pop(interaction.guild_id)
                    await deleted.disconnect()
                    return
        else:
            search = await wavelink.YouTubeTrack.search(query = query)
            select, miko = await create_selectsongview(search[:20], Mode.PLAY, player, control_panel)
            await interaction.followup.edit_message(message.id, view=select, embeds=miko)

    @app_commands.guild_only()
    @app_commands.command(name="playlist", description="自訂歌單")
    async def playlist(self, interaction: Interaction):
        select_view = SelectPlaylistView(self.playlists)
        await interaction.response.send_message(view = select_view, embed = await select_view.get_current_playlist_embed(), ephemeral = True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot)) # ,guilds = [Object(id = 469507920808116234)] #目前為全域都有安裝此模組(非特定伺服器)
    # await bot.tree.sync(guild = Object(id = 469507920808116234))
