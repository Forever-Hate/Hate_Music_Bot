import asyncio
import datetime
from enum import Enum
import re
from discord import ButtonStyle, Embed, app_commands,Interaction,Object,utils,Colour,WebhookMessage,User,Member,TextStyle,SelectOption
from discord.ext import commands,tasks
from discord.ui import Button,View,Modal,TextInput,Select
import wavelink
import yarl
import json
import lib.notification as nc
import lib.mysql as mysql

URL_REGEX = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
OPTIONS = {
    "1️⃣": 0,
    "2️⃣": 1,
    "3️⃣": 2,
    "4️⃣": 3,
    "5️⃣": 4
}

class CustomView(View):
    def add(self,item,callback=None):
        self.add_item(item)
        if callback is not None:
            item.callback = callback
        return item

class VolumeModal(Modal):
    def __init__(self,control_panel):
        super().__init__(title = "調整音量大小/播放速度")
        self.control_panel = control_panel
        self.volume = TextInput(label='音量(0-1000):', style = TextStyle.short,default=f"{control_panel.player.volume}")
        self.speed = TextInput(label='播放速度(0-無限):', style = TextStyle.short,default=f"{control_panel.speed}")
        self.add_item(self.volume)
        self.add_item(self.speed)


    async def on_submit(self, interaction:Interaction):
        self.control_panel.speed = float(self.speed.value)
        await self.control_panel.player.set_filter(wavelink.Filter(timescale=wavelink.Timescale(speed=float(self.speed.value))),seek=True)
        await self.control_panel.set_volume(int(self.volume.value))
        await interaction.response.edit_message(embed=self.control_panel.create_embed(),view=self.control_panel)

class HistorySong():
    def __init__(self,song:wavelink.Track,user:User):
        self.song = song
        self.user = user

class ControlView(CustomView):
    def __init__(self,player:wavelink.Player):
        super().__init__(timeout = None)
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
    
    class CycleType(Enum):
        SINGLE = "單首"
        ALL = "全部"

    async def play_and_pause(self,interaction:Interaction):
        if not self.player.is_paused():
            await self.player.pause()
        else:
            await self.player.resume()
        await interaction.response.edit_message(embed=self.create_embed(),view=self)

    async def cycle_callback(self,interaction:Interaction):
        if not self.cycle:
            self.cycle = True
        else:
            self.cycle = False
        await interaction.response.edit_message(embed=self.create_embed(),view=self)   

    async def cycle_type_callback(self,interaction:Interaction):
        if self.cycle_type == self.CycleType.SINGLE:
            self.cycle_type = self.CycleType.ALL
        else:
            self.cycle_type = self.CycleType.SINGLE
        await interaction.response.edit_message(embed=self.create_embed(),view=self)  


    async def skip_callback(self,interaction:Interaction):
        if not isinstance(self.history_song[self.position - 1],nc.Live):
            self.skip = True
            await self.player.stop()
            await asyncio.sleep(1.5)
        else:
            if not isinstance(self.history_song[self.position],nc.Live):
                new = await self.player.queue.get_wait()
                await self.player.play(new)
                if int(new.duration/3600) < 24: #非直播
                    if not self.refresh_panel.is_running():
                        self.refresh_panel.start()
                else: #直播
                    self.refresh_panel.cancel()
            self.position += 1
        await interaction.response.edit_message(embed=self.create_embed(),view=self)

    async def stop_callback(self,interaction:Interaction):
        if not isinstance(self.history_song[self.position - 1],nc.Live):
            print(789)
            self.player.queue.clear()
            self._stop = True
            await self.player.stop()
        else:
            print(101112)
            await self.player.disconnect()
            await self.message.delete()
            self.refresh_panel.cancel()
            self.refresh_webhook.cancel()
            interaction.client.get_cog("Music").players.pop(interaction.guild_id)
            interaction.client.get_cog("Music").control_panels.pop(interaction.guild_id)

    async def volume_callback(self,interaction:Interaction):
        await interaction.response.send_modal(VolumeModal(self))  

    def create_current_live_waiting_embed(self):
        miko = Embed(colour = Colour.random())
        miko.set_author(name = "🎧現正等待中...")
        miko.set_thumbnail(url = self.history_thumbnails[self.position-1])
        miko.add_field(name = "🎯名稱:",value = self.history_song[self.position-1].title)
        miko.add_field(name = "🔗網址:",value = self.history_song[self.position-1].url)    
        if self.history_song[self.position-1].reconnection_times == 0:
            miko.add_field(name = "⌛距離開始直播還有:",value = f"<t:{self.history_song[self.position-1].start_time}:R>",inline=False)
        else:
            miko.add_field(name = "⌛等待直播開始:",value = f"已嘗試連接 {self.history_song[self.position-1].reconnection_times} 次",inline=False)
        miko.add_field(name = "頻道:",value=self.history_song[self.position-1].channel_title)
        miko.add_field(name = "🔊音量:",value = f"{self.get_volume()}%",inline=False)
        miko.add_field(name = "🚩目前序位:",value = self.get_current_queue())
        self.ui_control()
        return miko

    def create_embed(self):
        if isinstance(self.history_song[self.position -1],HistorySong):
            return self.create_current_song_embed()
        else:
            return self.create_current_live_waiting_embed()

    def create_current_song_embed(self):
        miko = Embed(colour = Colour.random())
        miko.set_author(name = "🎧現正播放中...")
        miko.set_thumbnail(url = self.history_thumbnails[self.position-1])
        miko.add_field(name = "🎯名稱:",value = self.player.source.info.get("title"))
        if self.player.source.info.get("uri") is not None:
            miko.add_field(name = "🔗網址:",value = self.player.source.info.get("uri"))
        miko.add_field(name = "⌛長度:",value = f"{str(int(self.player.source.duration/3600)).zfill(2)}:{str(int(self.player.source.duration/60%60)).zfill(2)}:{str(int(self.player.source.duration%60)).zfill(2)}" if int(self.player.source.duration/3600) < 24 else "直播中",inline=False)
        miko.add_field(name="⏩播放速度:",value=f"{self.speed}x")
        miko.add_field(name="📼進度:",value=self.get_current_song_position(),inline=False) 
        miko.add_field(name = "🔊音量:",value = f"{self.get_volume()}%",inline=False)
        miko.add_field(name = "🚩目前序位:",value = self.get_current_queue())
        self.ui_control()
        return miko

    def get_volume(self) -> str:
        return self.player.volume
    
    async def set_volume(self,volume):
        await self.player.set_volume(volume)

    def get_current_queue(self) -> str:
        return f"{self.position}/{self.length}"

    async def get_current_song_list(self,interaction:Interaction):
        if (self.player.is_playing() | self.player.is_paused()) & (self.player.source is not None):
            song_list = ""
            is_done = True
            for index,item in enumerate(self.history_song):
                song_list = song_list + f"{index+1}. {item.song.title}(<@{item.user.id}>)"
                if self.player.source.info.get('title') == item.song.title:
                    song_list = song_list + "-💿\n"
                    is_done = False
                    continue
                elif is_done:
                    song_list = song_list + "-🏁\n"
                else:
                    song_list = song_list + "-💤\n"
            await interaction.response.send_message(content=f"<:moo:1017734836426915860>當前歌單:\n{song_list}",ephemeral=True)
        else:
            await interaction.response.send_message(content="請在播放或暫停時再點選此按鈕",ephemeral=True)

    def get_current_song_position(self) -> str:
        return f"{str(int(self.player.position/3600)).zfill(2)}:{str(int(self.player.position/60%60)).zfill(2)}:{str(int(self.player.position%60)).zfill(2)}/{str(int(self.player.source.duration/3600)).zfill(2)}:{str(int(self.player.source.duration/60%60)).zfill(2)}:{str(int(self.player.source.duration%60)).zfill(2)}" if int(self.player.source.duration/3600) < 24 else "-"


    def ui_control(self):
        self.clear_items()
        if not self.player.is_paused():
            self.add(Button(style = ButtonStyle.gray,label="暫停",emoji="⏸️"),self.play_and_pause) 
        else:
            self.add(Button(style = ButtonStyle.green,label="播放",emoji="▶️"),self.play_and_pause) 
        self.add(Button(style = ButtonStyle.red,label = "停止",emoji="⏹️"),self.stop_callback)
        self.add(Button(style = ButtonStyle.primary,label = "跳過",emoji="⏭️"),self.skip_callback)
        self.add(Button(style = ButtonStyle.green,label = "調整音量/播放速度",emoji="🎤"),self.volume_callback)
        if self.position == self.length:
            self.children[2].disabled = True
        if not self.cycle:
            self.add(Button(style = ButtonStyle.gray,label = "循環:關",emoji="🔄"),self.cycle_callback)
        else:
            self.add(Button(style = ButtonStyle.green,label = "循環:開",emoji="🔄"),self.cycle_callback) 
        if self.cycle_type == self.CycleType.SINGLE:
            self.add(Button(style = ButtonStyle.primary,label = "循環模式:單首",emoji="🔂"),self.cycle_type_callback)
        else:
            self.add(Button(style = ButtonStyle.green,label = "循環模式:全部",emoji="🔁"),self.cycle_type_callback)
        self.add(Button(style = ButtonStyle.primary,label = "當前歌單",emoji="📢"),self.get_current_song_list)
        
    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, value:WebhookMessage):
        self._message = value

    @tasks.loop(minutes = 5)
    async def refresh_webhook(self):
        self.message = await self.channel.fetch_message(self.message_id) 

    @tasks.loop(seconds = 5)
    async def refresh_panel(self):
        await self.message.edit(embed=self.create_embed(),view=self)
        

async def create_selectsongview(interaction,tracks,player,control_panel):
    select_song = SelectSongView(tracks,player,control_panel) 
    miko = await select_song._init(interaction)
    return select_song,miko

class SelectSongView(CustomView):

    def __init__(self,tracks,player:wavelink.Player,control_panel:ControlView):
        super().__init__(timeout = None)
        self.tracks = tracks
        self.player = player
        self.control_panel = control_panel
        self.start = 0
        self.end = 5

    async def _init(self,interaction:Interaction):
        self.add_base_button()
        return self.create_song_embed(interaction)

    def create_song_embed(self,interaction:Interaction):
        miko = []
        for index,song in enumerate(self.tracks[self.start:self.end]):
            neko = Embed(colour = Colour.random())
            neko.set_author(name=f"第{index+1}首:")
            neko.set_thumbnail(url = song.thumbnail)
            neko.add_field(name = "歌名:",value = f"{song.title}")
            neko.add_field(name = f'長度',value = f'{str(int(song.duration/3600)).zfill(2)}:{str(int(song.duration/60%60)).zfill(2)}:{str(int(song.duration%60)).zfill(2)}',inline=False)
            neko.add_field(name = "是否為串流:",value = song.is_stream())
            miko.append(neko)
        self.ui_control(self.tracks[self.start:self.end])
        return miko
    
    async def cancel(self,interaction:Interaction):
        if self.player.queue.is_empty and not self.player.is_playing():
            await self.player.disconnect()
            interaction.client.get_cog("Music").players.pop(interaction.guild_id)
            interaction.client.get_cog("Music").control_panels.pop(interaction.guild_id)
        await interaction.response.edit_message(content="已取消",embed=None,view=None)
    
    async def select_song(self,interaction:Interaction):
        await interaction.response.defer(ephemeral=True)
        song = self.tracks[int(interaction.data.get('custom_id'))+self.start]
        self.control_panel.history_thumbnails.append(song.thumbnail)
        self.control_panel.history_song.append(HistorySong(song,interaction.user))
        self.control_panel.length += 1
        if self.player.queue.is_empty and not self.player.is_playing() and len(self.control_panel.history_song) == 1: 
            await self.player.play(song)
            await interaction.followup.edit_message(interaction.message.id,content = f'已新增歌曲 `{song.title}` 現正準備播放中....',embed=None,view=None)
            self.control_panel.message : WebhookMessage =  await interaction.followup.send(embed=self.control_panel.create_embed(),view=self.control_panel)         
            self.control_panel.message_id = self.control_panel.message.id
            self.control_panel.refresh_webhook.start()
            self.control_panel.refresh_panel.start()
        else:
            await self.player.queue.put_wait(song)
            await interaction.followup.edit_message(interaction.message.id,content = f'已新增歌曲 `{song.title}` 至隊列中 序列位置為:{self.control_panel.length}',embed=None,view=None)
            await self.control_panel.message.edit(content=f"<@{interaction.user.id}> 已新增歌曲 `{song.title}` 至隊列中" ,embed=self.control_panel.create_embed(),view=self.control_panel) 

    async def next(self,interaction:Interaction):
        await interaction.response.defer(ephemeral=True)
        self.start += int(interaction.data.get('custom_id'))
        self.end += int(interaction.data.get('custom_id'))
        miko = self.create_song_embed(interaction)
        await interaction.followup.edit_message(interaction.message.id,view=self,embeds=miko)

    def add_base_button(self):
        self.add(Button(style=ButtonStyle.red,label="取消",emoji="❌"),self.cancel)
        for value,key in OPTIONS.items():
            self.add(Button(style = ButtonStyle.primary,label = f"{key+1}",emoji=f"{value}",custom_id=f"{key}"),self.select_song)
        self.add(Button(style = ButtonStyle.green,label = "前五首",emoji="⏮️",custom_id="-5"),self.next)
        self.add(Button(style = ButtonStyle.green,label = "下五首",emoji="⏭️",custom_id="5"),self.next)
        
    def ui_control(self,current_track):
        self.children[6].disabled = False
        self.children[7].disabled = False
        if self.start == 0:
            self.children[6].disabled = True
        if len(current_track) < 5:
            self.children[7].disabled = True
            for i in range(len(current_track)+1,6):
                self.children[i].disabled = True
        else:
            for i in range(1,len(current_track)+1):
                self.children[i].disabled = False
        if self.end == 20:
            self.children[7].disabled = True



class Music(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.players = {}
        self.control_panels = {} 
        self.notification_channels = nc.init() 
        self.subscribe_channel_list = {} #訂閱頻道暫存
        self.watch_list = {} #直播觀察清單
        bot.loop.create_task(self.create_nodes())
    
    notification_group = app_commands.Group(name='notification', description='channel')

    @notification_group.command(name = "add", description="新增頻道直播/新片通知")
    async def add(self,interaction: Interaction,platform:str,channel_url:str):
        if interaction.user.voice is None:
            await interaction.response.send_message("請先加入語音頻道，再輸入指令",ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        message = await interaction.followup.send(f"搜尋中...",ephemeral=True)
        notice = await nc.create_channel(platform,channel_url)
        g = nc.Guild(interaction.guild_id,interaction.channel.id,interaction.user.voice.channel.id)
        channels:list = self.get_subscribe_channel(interaction.guild_id)
        if self.notification_channels.__contains__(notice.id):
            if g.guild_id in self.notification_channels.get(notice.id)['channels'].keys():
                await message.edit(content = f"已經新增過{notice.title}的直播/新片通知")  
            else:
                self.notification_channels.get(notice.id)['channels'][g.guild_id] = g
                channels.append(notice)
                mysql.subscribe_channel(notice,g)
                await message.edit(content = f"已新增{notice.title}的直播/新片通知") 
        else:
            self.notification_channels[notice.id] = {
                "obj":notice,
                "channels":{
                    g.guild_id:g
                }
            }
            channels.append(notice)
            mysql.subscribe_channel(notice,g)
            await message.edit(content = f"已新增{notice.title}的直播/新片通知")

    @add.autocomplete('platform')
    async def add_autocomplete_callback(self,interaction:Interaction, current: str):
        return [
            app_commands.Choice(name='youtube', value='youtube'),
            app_commands.Choice(name='twitch', value='twitch')
        ]

    @notification_group.command(name = "delete", description="移除頻道直播/新片通知")
    async def delete(self,interaction: Interaction,deleted_channel_title:str):
        if deleted_channel_title == "None":
            await interaction.response.send_message(f"目前此群沒有訂閱任何頻道的通知喔",ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        subscribe_channels:list = self.subscribe_channel_list.get(interaction.guild_id)
        for item in subscribe_channels:
            if item.title == deleted_channel_title:
                deleted_channel = item
                channels:dict = self.notification_channels.get(item.id)['channels']
                if len(channels) != 1:
                    channels.pop(interaction.guild_id)
                else:
                    self.notification_channels.pop(deleted_channel.id)

                if len(subscribe_channels) != 1:
                    subscribe_channels.remove(item)
                else:
                    self.subscribe_channel_list.pop(interaction.guild_id)
                
                break
        mysql.unsubscribe_channel(deleted_channel,interaction.guild_id)
        await interaction.followup.send(f"已移除{deleted_channel.title}的直播/新片通知")

    @delete.autocomplete('deleted_channel_title')
    async def delete_autocomplete_callback(self,interaction:Interaction, current: str):
        channel_list = self.get_subscribe_channel(interaction.guild_id)
        if len(channel_list) != 0:
            return [
                app_commands.Choice(name=f'{item.title} - {item.platform}', value=f'{item.title}') for item in channel_list
                ]
        else:
            return [
                app_commands.Choice(name="None",value="None")
            ]
    
    @notification_group.command(name = "show", description="顯示所有訂閱的頻道")
    async def show(self,interaction: Interaction):
        channel_embeds = []
        channels:list = self.get_subscribe_channel(interaction.guild_id)
        for (index,channel) in enumerate(channels) :
            miko = Embed(colour = Colour.random())
            miko.set_author(name = f"第 {index+1} 個頻道:")
            miko.set_thumbnail(url = channel.thumbnail)
            miko.add_field(name = "🎯名稱:",value = channel.title,inline=False)
            miko.add_field(name = "🔗網址:",value = f"https://www.youtube.com/channel/{channel.id}" if channel.platform == "youtube" else f"https://www.twitch.tv/{channel.id}",inline=False)
            miko.add_field(name = "🚩平台:",value = channel.platform)
            channel_embeds.append(miko)
        await interaction.response.send_message(content=f"此群訂閱的所有頻道(共{len(channels)}個):",embeds=channel_embeds,ephemeral=True)

    def get_subscribe_channel(self,guild_id:int) -> list:
        if not self.subscribe_channel_list.__contains__(guild_id):  
            self.subscribe_channel_list[guild_id] = []
            channel_list = self.subscribe_channel_list.get(guild_id)
            for (key,value) in self.notification_channels.items():
                if guild_id not in value['channels'].keys():
                    continue
                else:
                    channel_list.append(value['obj'])
        else:
            channel_list = self.subscribe_channel_list.get(guild_id)
        return channel_list

    async def timeout_user(self,*,user_id:int,guild_id:int,until):
        headers = {"Authorization":f"Bot {self.bot.http.token}"}
        url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}"
        timeout = (datetime.datetime.utcnow() + datetime.timedelta(minutes=until)).isoformat()
        json = {'communication_disabled_until':timeout}
        async with self.bot.session.patch(url,json=json,headers=headers) as session:
            if session.status in range(200,299):
                return True
            return False
    
    async def create_nodes(self):
        await self.bot.wait_until_ready()
        await wavelink.NodePool.create_node(bot=self.bot, host="127.0.0.1", port="2333", password="youshallnotpass", region="asia")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self,node:wavelink.Node):
        self.node = node
        print(f"Node {node.identifier} is ready!")
        nc.checkforvideos.start(self.bot,self.notification_channels,self.players,self.control_panels,self.watch_list,self.node)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: wavelink.Player, track:wavelink.Track, reason): #自然循環有問題(有直播時)
        guild_id = list(self.players.keys())[list(self.players.values()).index(player)]
        control_panel = self.control_panels[guild_id]
        control_panel.speed = 1.0
        await player.set_filter(wavelink.Filter(timescale=wavelink.Timescale(speed=float(1.0))),seek=True)
        if not player.queue.is_empty: #隊列不為空
            if (control_panel.cycle_type == control_panel.CycleType.SINGLE) & control_panel.cycle & (not control_panel.skip):
                await player.play(track)
                return

        else: #按下停止後，隊列為空
            if control_panel._stop | ((not control_panel.cycle) & (control_panel.position == control_panel.length)): #(按下停止)或(未開循環且播到最後一首)
                await player.disconnect()
                self.players.pop(guild_id)
                control_panel.refresh_panel.cancel()
                await control_panel.message.delete()
                control_panel.refresh_webhook.cancel()
                self.control_panels.pop(guild_id)
                return
            else:
                if control_panel.cycle:
                    if control_panel.cycle_type == control_panel.CycleType.SINGLE: #開循環且開啟單首循環模式
                        await player.play(track)
                        return
                    else: #開循環且開啟全部循環模式
                        for item in control_panel.history_song:
                            if isinstance(item,HistorySong):
                                await player.queue.put_wait(item.song) 
                        control_panel.length = len(control_panel.history_song)
                        control_panel.position = 0

        if control_panel.skip:
            control_panel.skip = False
        #-------正常循環------#
        if not isinstance(control_panel.history_song[control_panel.position],nc.Live):
            new = await player.queue.get_wait()
            await player.play(new)
            if int(new.duration/3600) < 24: #非直播
                if not control_panel.refresh_panel.is_running():
                    control_panel.refresh_panel.start()
            else: #直播
                control_panel.refresh_panel.cancel()
        control_panel.position += 1
        await control_panel.message.edit(embed=control_panel.create_embed(),view=control_panel)

        

    @app_commands.command(name = "play", description="播放音樂") 
    async def play(self,interaction:Interaction,query:str): 
        if interaction.user.voice is None:
            await interaction.response.send_message("請先加入語音頻道，再輸入指令",ephemeral=True)
            return
        elif not self.players.__contains__(interaction.guild_id):
            self.players[interaction.guild_id] = await interaction.user.voice.channel.connect(cls=wavelink.Player) 
            await asyncio.sleep(1)
            if self.players[interaction.guild_id].is_connected():
                self.control_panels[interaction.guild_id] = ControlView(self.players.get(interaction.guild_id))
                self.control_panels.get(interaction.guild_id).channel = interaction.channel
            else:
                self.players.pop(interaction.guild_id)
                await interaction.response.send_message("無法加入語音頻道，請稍後再嘗試",ephemeral=True)
                return

        control_panel = self.control_panels.get(interaction.guild_id)
        player = self.players.get(interaction.guild_id)
        await interaction.response.defer(ephemeral=True)
        message:WebhookMessage = await interaction.followup.send(f"搜尋中...") 
        if re.match(URL_REGEX,query):
            check = yarl.URL(query)
            if check.query.get("list"):
                try:
                    search:wavelink.YouTubePlaylist = await wavelink.NodePool.get_node().get_playlist(wavelink.YouTubePlaylist,query)
                except wavelink.LoadTrackError as e:
                    await interaction.followup.edit_message(message.id,content = f"播放音樂時發生錯誤，錯誤訊息為:{e}")
                    await asyncio.sleep(3)
                    deleted = self.players.pop(interaction.guild_id)
                    await deleted.disconnect()
                    return 
                for song in search.tracks:
                    control_panel.history_thumbnails.append(song.thumbnail)
                    control_panel.history_song.append(HistorySong(song,interaction.user))
                control_panel.length += len(search.tracks)
                if player.queue.is_empty and not player.is_playing() and len(control_panel.history_song) == len(search.tracks):
                    await player.play(search.tracks[0])
                    for index,song in enumerate(search.tracks):
                        if index == 0:
                            continue
                        await player.queue.put_wait(song)
                    await interaction.followup.edit_message(message.id,content = f'已新增歌單 `{search.name}` 現正準備播放中......')
                    control_panel.message : WebhookMessage =  await interaction.followup.send(embed = control_panel.create_embed(),view = control_panel,ephemeral=False)
                    control_panel.message_id = control_panel.message.id
                    control_panel.refresh_webhook.start()
                    control_panel.refresh_panel.start()
                else:
                    for song in search.tracks:
                        await player.queue.put_wait(song) 
                    await interaction.followup.edit_message(message.id,content = f'已新增歌單 `{search.name}` 至隊列中 共{len(search.tracks)}首')
                    await control_panel.message.edit(content =f"<@{interaction.user.id}> 已新增歌單 `{search.name}` 至隊列中  共{len(search.tracks)}首", embed = control_panel.create_embed(),view = control_panel) 
            else:
                try:
                    search = (await wavelink.NodePool.get_node().get_tracks(wavelink.YouTubeTrack,query))[0]
                except wavelink.LoadTrackError as e:
                    await interaction.followup.edit_message(message.id,content = f"播放音樂時發生錯誤，錯誤訊息為:{e}")
                    await asyncio.sleep(3)
                    deleted = self.players.pop(interaction.guild_id)
                    await deleted.disconnect()
                    return
                control_panel.history_thumbnails.append(search.thumbnail)
                control_panel.history_song.append(HistorySong(search,interaction.user))
                control_panel.length += 1
                if player.queue.is_empty and not player.is_playing() and len(control_panel.history_song) == 1: 
                    await player.play(search)
                    await interaction.followup.edit_message(message.id,content = f'已新增歌曲 `{search.title}` 現正準備播放中......')
                    control_panel.message : WebhookMessage =  await interaction.followup.send(embed = control_panel.create_embed(),view = control_panel,ephemeral=False)
                    control_panel.message_id = control_panel.message.id
                    control_panel.refresh_webhook.start()
                    if int(search.duration/3600) < 24:
                        control_panel.refresh_panel.start()
                else:
                    await player.queue.put_wait(search)
                    await interaction.followup.edit_message(message.id,content = f'已新增歌曲 `{search.title}` 至隊列中 序列位置為:{control_panel.length}')
                    await control_panel.message.edit(content = f"<@{interaction.user.id}> 已新增歌曲 `{search.title}` 至隊列中", embed = control_panel.create_embed(),view = control_panel) 
        else:
            search = await wavelink.YouTubeTrack.search(query = query)
            select,miko = await create_selectsongview(interaction , search[:20], player, control_panel)
            await interaction.followup.edit_message(message.id,view = select,embeds = miko)


async def setup(bot:commands.Bot):
     await bot.add_cog(Music(bot)) #,guilds = [Object(id = 469507920808116234)] #目前為全域都有安裝此模組(非特定伺服器)