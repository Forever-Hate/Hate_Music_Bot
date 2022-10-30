import asyncio
from enum import Enum
import re
import json
from discord import ButtonStyle, Colour, Embed, Interaction, WebhookMessage
import requests
from bs4 import BeautifulSoup
from discord.ext import tasks, commands
from discord.ui import Button,View
import wavelink
import datetime

class Channel():
    def __init__(self, id: str, title: str, thumbnail: str, latest_video: str, platform: str):
        self.id = id
        self.title = title
        self.thumbnail = thumbnail
        self.latest_video = latest_video
        self.platform = platform


class Guild():
    def __init__(self, guild_id: int, text_id: int, voice_id: int):
        self.guild_id = guild_id
        self.text_id = text_id
        self.voice_id = voice_id

import lib.mysql as ms
import commands.music as music

with open('./config/settings.json',"r",encoding='utf-8') as f:
    settings = json.load(f)

class Live():
    def __init__(self, title: str, channel_title: str, url: str, start_time: int, thumbnail: str,platform: str):
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
        print("- 距離開始還有:",self.start_time - int(datetime.datetime.now().timestamp()))
        print("- 縮圖:", self.thumbnail)
        print("========================================")
    
    def create_embed(self):
        miko = Embed(colour = Colour.random())
        miko.set_author(name = "🎧即將到來的直播:")
        miko.set_thumbnail(url = self.thumbnail)
        miko.add_field(name = "<:yt:1032640435375583342>頻道:",value=self.channel_title)
        miko.add_field(name = "🎯名稱:",value = self.title)
        miko.add_field(name = "🔗網址:",value = self.url,inline=False)
        miko.add_field(name = "⌛直播時間:",value = f"<t:{self.start_time}:f>")    
        miko.add_field(name = "⌛距離開始直播:",value = f"<t:{self.start_time}:R>",inline=False)
        return miko

class CheckView(View): 
    def __init__(self,live:Live,channels:dict,bot:commands.bot,node:wavelink.Node,watch_list:dict,players:dict,control_panels:dict):
        super().__init__(timeout = None)
        self.live = live
        self.bot = bot
        self.channels = channels
        self.already_joined_channels = {}
        self.node = node
        self.watch_list = watch_list
        self.players = players
        self.control_panels = control_panels
        self.message = None
        self.add(Button(style = ButtonStyle.green,label="新增至隊列",emoji="✅"),self.add_in_query)
        self.add(Button(style = ButtonStyle.red,label="移除通知",emoji="❌"),self.remove_notification)
        self.time_to_start.start()

    def add(self,item,callback=None):
        self.add_item(item)
        if callback is not None:
            item.callback = callback
        return item


    @tasks.loop(count = 1)
    async def time_to_start(self):
        self.join.start()
        print(f"~~~~~~~~~~現正開始直播:{self.live.title}~~~~~~~~~~")
    
    @time_to_start.before_loop
    async def before_time_to_start(self):
        await asyncio.sleep(float(self.live.start_time - int(datetime.datetime.now().timestamp())))

    @tasks.loop(seconds = 30)
    async def join(self):
        try:
            search = (await wavelink.NodePool.get_node().get_tracks(wavelink.YouTubeTrack,self.live.url))[0]
        except wavelink.LoadTrackError: #每30秒嘗試重新取得串流
            self.live.reconnection_times += 1
            print(f"        嘗試取得{self.live.title}串流{self.live.reconnection_times}次")
        else: #取的直播串流後執行
            self.join.cancel()
            players = self.players
            control_panels = self.control_panels
            for (key,value) in self.already_joined_channels.items():
                history = control_panels[key].history_song
                for index,song in enumerate(history):
                    if not isinstance(song,music.HistorySong) and song.title == search.title:
                        history[index] = music.HistorySong(search,self.bot.user)
                        if index == control_panels[key].position - 1: #當前正在等待
                            await control_panels[key].player.play(search)
                        else:
                            control_panels[key].player.queue.put_at_index(index,search)
            self.watch_list.pop(self.live.title)
            print(f"          已取得{self.live.title}串流")
            print(f"~~~~~~~~~~結束監測直播:{self.live.title}~~~~~~~~~~")
    
    @join.before_loop
    async def before_join(self): 
        players = self.players
        control_panels = self.control_panels
        for key,value in self.channels.items():
            if key not in players:
                players[key] = await self.bot.get_channel(value['obj'].voice_id).connect(cls=wavelink.Player)
                await asyncio.sleep(1)
                if players[key].is_connected():
                    control_panels[key] = music.ControlView(players.get(key))
                    control_panels[key].channel = self.bot.get_channel(value['obj'].text_id)
                    control_panels[key].history_song.append(self.live)
                    control_panels[key].history_thumbnails.append(self.live.thumbnail)
                    control_panels[key].length += 1
                    control_panels[key].message: WebhookMessage = await control_panels[key].channel.send(embed=control_panels[key].create_embed(), view=control_panels[key])
                    control_panels[key].message_id = control_panels[key].message.id
                    control_panels[key].refresh_webhook.start()
                    control_panels[key].refresh_panel.start()
                else:
                    players.pop(key)
            else:
                control_panel: music.ControlView = control_panels.get(key)
                control_panel.history_song.append(self.live)
                control_panel.history_thumbnails.append(self.live.thumbnail)
                control_panel.length += 1
                await control_panel.message.edit(content=f"<@{self.bot.user.id}>已新增等待 {self.live.channel_title} 直播開始至隊列中", embed=control_panel.create_embed(), view=control_panel)
            await self.message.delete()
        self.already_joined_channels.update(self.channels)   


    async def add_in_query(self,interaction:Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.message.delete()
        players = self.players
        control_panels = self.control_panels
        key = interaction.guild_id
        if key not in players:
            players[key] = await self.bot.get_channel(self.channels[interaction.guild_id]['obj'].voice_id).connect(cls=wavelink.Player)
            if players[key].is_connected():
                control_panels[key] = music.ControlView(players.get(key))
                control_panels[key].channel = self.bot.get_channel(self.channels[interaction.guild_id]['obj'].text_id)
                control_panels[key].history_song.append(self.live)
                control_panels[key].history_thumbnails.append(self.live.thumbnail)
                control_panels[key].length += 1
                control_panels[key].message: WebhookMessage = await control_panels[key].channel.send(embed=control_panels[key].create_embed(), view=control_panels[key])
                control_panels[key].message_id = control_panels[key].message.id
                control_panels[key].refresh_webhook.start()
                control_panels[key].refresh_panel.start()
                await interaction.followup.send(f"已新增等待 {self.live.channel_title} 直播開始至隊列中",ephemeral=True)
            else:
                players.pop(key)
        else:
            control_panel: music.ControlView = control_panels.get(key)
            control_panel.history_song.append(self.live)
            control_panel.history_thumbnails.append(self.live.thumbnail)
            control_panel.length += 1
            await control_panel.message.edit(content=f"<@{interaction.user.id}>已新增等待 {self.live.channel_title} 直播開始至隊列中", embed=control_panel.create_embed(), view=control_panel)
            await interaction.followup.send(f"已新增等待 {self.live.channel_title} 直播開始至隊列中",ephemeral=True)
        self.already_joined_channels[interaction.guild_id] = self.channels.pop(interaction.guild_id)

    async def remove_notification(self,interaction:Interaction):
        await self.message.delete()
        self.channels.pop(interaction.guild_id)
        if not self.channels and not self.already_joined_channels: #當等待直播隊列與已加入頻道隊列為空時
            self.time_to_start.cancel()
            self.watch_list.pop(self.live.title)
        await interaction.response.send_message(f"已移除 {self.live.title} 直播通知",ephemeral=True)

async def create_channel(platform: str, URL: str) -> Channel:
    if platform == "youtube":
        soup = BeautifulSoup(requests.get(URL).content, "html.parser")
        data = re.search(r"var ytInitialData = ({.*});", str(soup)).group(1)
        try:
            json_data = json.loads(data)
            channel_id = json_data['header']['c4TabbedHeaderRenderer']['channelId']
            channel_title = json_data['header']['c4TabbedHeaderRenderer']['title']
            channel_thumbnail = json_data['header']['c4TabbedHeaderRenderer']['avatar']['thumbnails'][2]['url']
        except json.JSONDecodeError:
            json_data = re.search(r"\"header\":(.*),\"metadata\"", data).group(1)
            json_data = json.loads(json_data)
            channel_id = json_data['c4TabbedHeaderRenderer']['channelId']
            channel_title = json_data['c4TabbedHeaderRenderer']['title']
            channel_thumbnail = json_data['c4TabbedHeaderRenderer']['avatar']['thumbnails'][2]['url']

        (latest_video_url,thumbnail,title) = await get_latest_video(URL+"/videos")
    else:
        pass

    return Channel(channel_id, channel_title, channel_thumbnail, latest_video_url, platform)


def init() -> dict:
    return ms.get_channels()

async def get_latest_video(url) -> tuple:    #取得新影片資訊
    videos_html = requests.get(url).text
    soup = BeautifulSoup(videos_html, "html.parser")
    data = re.search(
        r"var ytInitialData = ({.*});", str(soup)).group(1)
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        data = re.search(r"(.*);</script>", data).group(1)
        data = json.loads(data)

    for tab_item in data['contents']['twoColumnBrowseResultsRenderer']['tabs']:
        try:
            if tab_item['tabRenderer']['title'] == "影片":
                for item in tab_item['tabRenderer']['content']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'][0]['gridRenderer']['items']:
                    #print(item['gridVideoRenderer']['thumbnailOverlays'][0]['thumbnailOverlayTimeStatusRenderer']['style'])
                    print(f"最新影片title:{item['gridVideoRenderer']['title']['runs'][0]['text']} - {item['gridVideoRenderer']['thumbnailOverlays'][0]['thumbnailOverlayTimeStatusRenderer']['style']}")
                    if item['gridVideoRenderer']['thumbnailOverlays'][0]['thumbnailOverlayTimeStatusRenderer']['style'] == "LIVE":
                        continue
                    else:
                        latest_video_url = f"https://www.youtube.com/watch?v={item['gridVideoRenderer']['videoId']}"
                        try:
                            thumbnail = item['gridVideoRenderer']['thumbnail']['thumbnails'][3]['url']
                        except IndexError:
                            thumbnail = item['gridVideoRenderer']['thumbnail']['thumbnails'][0]['url']
                        title = item['gridVideoRenderer']['title']['runs'][0]['text']
                        print("最新影片URL:",latest_video_url)
                        break
                break
        except KeyError:
            print("----------新影片資訊取得失敗----------")
            return None,None,None
    return latest_video_url,thumbnail,title


@tasks.loop(seconds = settings['notification']['interval']) 
async def checkforvideos(bot: commands.Bot, notification_channels: dict, players: dict, control_panels: dict,watch_list:dict, node: wavelink.Node):

    def create_new_video_embed(channel:Channel,title:str,thumbnail:str): 
        miko = Embed(colour = Colour.random())
        miko.set_author(name = "🎧新的影片發布:")
        miko.set_thumbnail(url = channel.thumbnail)
        miko.add_field(name = "<:yt:1032640435375583342>頻道:",value=channel.title)
        miko.add_field(name = "🎯名稱:",value = title)
        miko.add_field(name = "🔗網址:",value = channel.latest_video,inline=False)
        miko.set_image(url = thumbnail)
        return miko
    print(f"------------------現在時間:{datetime.datetime.fromtimestamp(int(datetime.datetime.now().timestamp()))}------------------")
    for key, value in notification_channels.items():
        channel_url = f"https://www.youtube.com/channel/{key}"
        index_html = requests.get(channel_url).text
        c:Channel = value['obj']
        print("頻道:",c.title)
        if re.search('(?<="startTime":").*?(?=")', index_html) is not None:
            soup = BeautifulSoup(index_html, "html.parser")
            data = re.search(
                r"var ytInitialData = ({.*});", str(soup)).group(1)
            videos = []
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = re.search(r"(.*);</script>", data).group(1)
                data = json.loads(data)
            try:
                for tab_item in data['contents']['twoColumnBrowseResultsRenderer']['tabs']:
                    if tab_item['tabRenderer']['title'] == "首頁":
                        for section_item in tab_item['tabRenderer']['content']['sectionListRenderer']['contents']:
                            if section_item['itemSectionRenderer']['contents'][0].get('shelfRenderer') != None:
                                if section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['title']['runs'][0]['text'] == "已排定的直播影片":
                                    if section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['content'].get('expandedShelfContentsRenderer') != None: #只有一個影片會出現
                                        video_list = section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['content']['expandedShelfContentsRenderer']['items']
                                        for video in video_list:
                                            if video['videoRenderer'].get('upcomingEventData') != None:
                                                title = video['videoRenderer']['title']['simpleText']
                                                url = f"https://www.youtube.com/watch?v={video['videoRenderer']['videoId']}"
                                                start_time = int(video['videoRenderer']['upcomingEventData']['startTime'])
                                                thumbnail = video['videoRenderer']['thumbnail']['thumbnails'][3]['url']
                                                videos.append(Live(title, c.title, url, start_time, thumbnail,c.platform))
                                    else: #一個以上影片會出現
                                        video_list = section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['content']['horizontalListRenderer']['items']
                                        for video in video_list:
                                            if video['gridVideoRenderer'].get('upcomingEventData') != None:
                                                title = video['gridVideoRenderer']['title']['simpleText']
                                                url = f"https://www.youtube.com/watch?v={video['gridVideoRenderer']['videoId']}"
                                                start_time = int(video['gridVideoRenderer']['upcomingEventData']['startTime'])
                                                thumbnail = video['gridVideoRenderer']['thumbnail']['thumbnails'][3]['url']
                                                videos.append(Live(title, c.title, url, start_time, thumbnail,c.platform))
                                    break
                                elif section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['title']['runs'][0]['text'] == "上傳的影片": #影片未分類時出現
                                    video_list = section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['content']['horizontalListRenderer']['items']
                                    for video in video_list[:5]:
                                        if video['gridVideoRenderer'].get('upcomingEventData') != None:
                                            title = video['gridVideoRenderer']['title']['simpleText']
                                            url = f"https://www.youtube.com/watch?v={video['gridVideoRenderer']['videoId']}"
                                            start_time = int(video['gridVideoRenderer']['upcomingEventData']['startTime'])
                                            thumbnail = video['gridVideoRenderer']['thumbnail']['thumbnails'][3]['url']
                                            videos.append(Live(title, c.title, url, start_time, thumbnail,c.platform))
                                    break
                        break
            except KeyError:
                print("----------直播資訊取得失敗----------")
            for video in videos:
                video.toString()
                if video.start_time <= int((datetime.datetime.now() + datetime.timedelta(days=1)).timestamp()): #小於一天內開播
                    if watch_list.__contains__(video.title): #舊的直播
                        waiting_channels = watch_list[video.title].channels
                        print("waiting_channels_before:",waiting_channels)
                        for (id,guild) in value['channels'].items():
                            if not waiting_channels.__contains__(id): #新的頻道訂閱群
                                waiting_channels[id] = {
                                    "obj":guild
                                }
                                channel = await bot.fetch_channel(guild['obj'].text_id)
                                watch_list[video.title].message = await channel.send(embed = video.create_embed(),view = watch_list[video.title])
                        print("waiting_channels_after:",waiting_channels)
                    else: #新的直播加入
                        watch_list[video.title] = CheckView(video,dict(value['channels']),bot,node,watch_list,players,control_panels)
                        for (id,guild) in value['channels'].items():
                            channel = await bot.fetch_channel(guild['obj'].text_id)
                            watch_list[video.title].message = await channel.send(embed = video.create_embed(),view = watch_list[video.title])

        
        (latest_video_url,thumbnail,title) = await get_latest_video(channel_url+"/videos")
        if (c.latest_video != latest_video_url) & (latest_video_url is not None):
            c.latest_video = latest_video_url
            for (id,guild) in value['channels'].items():
                channel = await bot.fetch_channel(guild['obj'].text_id)
                await channel.send(embed = create_new_video_embed(c,title,thumbnail))
            ms.update_latest_video(c.title,latest_video_url)
            print("新片上架")
        print("==========================下一個頻道==========================")
    print(f"----------------下次執行時間:{datetime.datetime.fromtimestamp(int(datetime.datetime.now().timestamp())) + datetime.timedelta(seconds = settings['notification']['interval'])}----------------")
