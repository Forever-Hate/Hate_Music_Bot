import asyncio
import datetime
from enum import Enum
import re
from discord import ButtonStyle, Embed, SelectOption, TextStyle, app_commands,Interaction,Object,utils,Color,WebhookMessage,User,Member
from discord.ext import commands,tasks
from discord.ui import Button,View
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
    def __init__(self,song,user):
        self.song = song
        self.user = user

class ControlView(View):
    def __init__(self,player:wavelink.Player):
        super().__init__(timeout = None)
        self.player = player
        self.length = 0
        self.position = 1
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
        await interaction.response.edit_message(embed=self.create_current_song_embed(),view=self)

    async def cycle_callback(self,interaction:Interaction):
        if not self.cycle:
            self.cycle = True
        else:
            self.cycle = False
        await interaction.response.edit_message(embed=self.create_current_song_embed(),view=self)   

    async def cycle_type_callback(self,interaction:Interaction):
        if self.cycle_type == self.CycleType.SINGLE:
            self.cycle_type = self.CycleType.ALL
        else:
            self.cycle_type = self.CycleType.SINGLE
        await interaction.response.edit_message(embed=self.create_current_song_embed(),view=self)  


    async def skip_callback(self,interaction:Interaction):
        self.skip = True
        await self.player.stop()
        await asyncio.sleep(1.5)
        await interaction.response.edit_message(embed=self.create_current_song_embed(),view=self)  

    async def stop_callback(self,interaction:Interaction):
        self.player.queue.clear()
        self._stop = True
        await self.player.stop()

    def create_current_song_embed(self):
        miko = Embed(color=Color.green())
        miko.set_author(name = "🎧現正播放中...")
        miko.set_thumbnail(url = self.history_thumbnails[self.position-1])
        miko.add_field(name = "🎯名稱:",value = self.player.source.info.get("title"))
        if self.player.source.info.get("uri") is not None:
            miko.add_field(name = "🔗網址:",value = self.player.source.info.get("uri"))    
        miko.add_field(name = "⌛長度:",value = f"{str(int(self.player.source.duration/3600)).zfill(2)}:{str(int(self.player.source.duration/60%60)).zfill(2)}:{str(int(self.player.source.duration%60)).zfill(2)}" if int(self.player.source.duration/3600) < 24 else "直播中",inline=False)
        miko.add_field(name="📼進度",value=self.get_current_song_position()) 
        miko.add_field(name = "🔊音量:",value = self.get_volume(),inline=False)
        miko.add_field(name = "🚩目前序位:",value = self.get_current_queue())
        self.ui_control()
        return miko

    def get_volume(self) -> str:
        return f"{self.player.volume}"

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

    def add(self,item,callback=None):
        self.add_item(item)
        if callback is not None:
            item.callback = callback
        return item

    @tasks.loop(minutes = 5)
    async def refresh_webhook(self):
        self.message = await self.channel.fetch_message(self.message_id) 

    @tasks.loop(seconds = 5)
    async def refresh_panel(self):
        await self.message.edit(embed=self.create_current_song_embed(),view=self)
        

async def create_selectsongview(interaction,tracks,player,control_panel):
    select_song = SelectSongView(tracks,player,control_panel) 
    miko = await select_song._init(interaction)
    return select_song,miko

class SelectSongView(View):

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
            neko = Embed()
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
            self.player = None
        await interaction.response.edit_message(content="已取消",embed=None,view=None)
    
    async def select_song(self,interaction:Interaction):
        await interaction.response.defer(ephemeral=True)
        song = self.tracks[int(interaction.data.get('custom_id'))+self.start]
        self.control_panel.history_thumbnails.append(song.thumbnail)
        self.control_panel.history_song.append(HistorySong(song,interaction.user))
        self.control_panel.length += 1
        if self.player.queue.is_empty and not self.player.is_playing(): 
            await self.player.play(song)
            await interaction.followup.edit_message(interaction.message.id,content = f'已新增歌曲 `{song.title}` 現正準備播放中....',embed=None,view=None)
            self.control_panel.message : WebhookMessage =  await interaction.followup.send(embed=self.control_panel.create_current_song_embed(),view=self.control_panel)         
            self.control_panel.message_id = self.control_panel.message.id
            self.control_panel.refresh_webhook.start()
            self.control_panel.refresh_panel.start()
        else:
            await self.player.queue.put_wait(song)
            await interaction.followup.edit_message(interaction.message.id,content = f'已新增歌曲 `{song.title}` 至隊列中 序列位置為:{self.control_panel.length}',embed=None,view=None)
            await self.control_panel.message.edit(content=f"<@{interaction.user.id}> 已新增歌曲 `{song.title}` 至隊列中" ,embed=self.control_panel.create_current_song_embed(),view=self.control_panel) 

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


    def add(self,item,callback=None):
        self.add_item(item)
        if callback is not None:
            item.callback = callback
        return item


class Music(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.player = None
        bot.loop.create_task(self.create_nodes())

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

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: wavelink.Player, track:wavelink.Track, reason):
        if not player.queue.is_empty:
            if (self.control_panel.cycle_type == self.control_panel.CycleType.SINGLE) & self.control_panel.cycle & (not self.control_panel.skip):
                await player.play(track)
                return

            if self.control_panel.skip:
                self.control_panel.skip = False

            new = await player.queue.get_wait()
            await player.play(new)
            self.control_panel.position += 1
            await self.control_panel.message.edit(embed=self.control_panel.create_current_song_embed(),view=self.control_panel)
        else:
            if self.control_panel._stop | (not self.control_panel.cycle):
                await self.player.disconnect()
                self.player = None
                self.control_panel.refresh_panel.cancel()
                await self.control_panel.message.delete()
                self.control_panel.refresh_webhook.cancel()
            else:
                if self.control_panel.cycle_type == self.control_panel.CycleType.SINGLE:
                    await player.play(track)
                else:
                    for item in self.control_panel.history_song:
                        await player.queue.put_wait(item.song)
                    new = await player.queue.get_wait()
                    await player.play(new)
                    self.control_panel.position = 1
                    self.control_panel.length = len(self.control_panel.history_song)
                await self.control_panel.message.edit(embed=self.control_panel.create_current_song_embed(),view=self.control_panel)

    @app_commands.command(name = "play", description="播放音樂")
    async def play(self,interaction:Interaction,query:str):
        if interaction.user.voice is None:
            await interaction.response.send_message("請先加入語音頻道，再輸入指令",ephemeral=True)
            return
        elif self.player is None:
            self.player:wavelink.Player = await interaction.user.voice.channel.connect(cls=wavelink.Player)
            self.control_panel = ControlView(self.player)
            self.control_panel.channel = interaction.channel
            
        if re.match(URL_REGEX,query):
            check = yarl.URL(query)
            if check.query.get("list"): 
                search:wavelink.YouTubePlaylist = await wavelink.NodePool.get_node().get_playlist(wavelink.YouTubePlaylist,query)
                for song in search.tracks:
                    self.control_panel.history_thumbnails.append(song.thumbnail)
                    self.control_panel.history_song.append(HistorySong(song,interaction.user))
                self.control_panel.length += len(search.tracks)
                if self.player.queue.is_empty and not self.player.is_playing():
                    await interaction.response.defer() 
                    await self.player.play(search.tracks[0])
                    for index,song in enumerate(search.tracks):
                        if index == 0:
                            continue
                        await self.player.queue.put_wait(song)
                    self.control_panel.message : WebhookMessage =  await interaction.followup.send(embed=self.control_panel.create_current_song_embed(),view=self.control_panel)
                    self.control_panel.message_id = self.control_panel.message.id
                    self.control_panel.refresh_webhook.start()
                    self.control_panel.refresh_panel.start()
                else:
                    await interaction.response.defer(ephemeral=True)
                    for song in search.tracks:
                        await self.player.queue.put_wait(song) 
                    await interaction.followup.send(content = f'已新增歌單 `{search.name}` 至隊列中 共{len(search.tracks)}首')
                    await self.control_panel.message.edit(content =f"<@{interaction.user.id}> 已新增歌單 `{search.name}` 至隊列中  共{len(search.tracks)}首", embed=self.control_panel.create_current_song_embed(),view=self.control_panel) 
            else:
                search = (await wavelink.NodePool.get_node().get_tracks(wavelink.YouTubeTrack,query))[0]
                self.control_panel.history_thumbnails.append(search.thumbnail)
                self.control_panel.history_song.append(HistorySong(search,interaction.user))
                self.control_panel.length += 1
                if self.player.queue.is_empty and not self.player.is_playing():
                    await interaction.response.defer() 
                    await self.player.play(search)
                    self.control_panel.message : WebhookMessage =  await interaction.followup.send(embed=self.control_panel.create_current_song_embed(),view=self.control_panel)
                    self.control_panel.message_id = self.control_panel.message.id
                    self.control_panel.refresh_webhook.start()
                    if int(search.duration/3600) < 24:
                        self.control_panel.refresh_panel.start()
                else:
                    await interaction.response.defer(ephemeral=True) 
                    await self.player.queue.put_wait(search)
                    await interaction.followup.send(content = f'已新增歌曲 `{search.title}` 至隊列中 序列位置為:{self.control_panel.length}')
                    await self.control_panel.message.edit(content =f"<@{interaction.user.id}> 已新增歌曲 `{search.title}` 至隊列中", embed=self.control_panel.create_current_song_embed(),view=self.control_panel) 
        else:
            search = await wavelink.YouTubeTrack.search(query=query)
            select,miko = await create_selectsongview(interaction,search[:20],self.player,self.control_panel)
            await interaction.response.send_message(view=select,embeds=miko,ephemeral=True)
        
async def setup(bot:commands.Bot):
     await bot.add_cog(Music(bot)) #,guilds = [Object(id = 469507920808116234)] #目前為全域都有安裝此模組(非特定伺服器)