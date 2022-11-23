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
from typing import List

class Channel():
    def __init__(self, id: str, title: str, thumbnail: str, latest_video: str, platform: str):
        self.id = id
        self.title = title
        self.thumbnail = thumbnail
        self.latest_video = latest_video
        self.platform = platform
    
    def toEmbed(self,index:int = 0) -> Embed:
        miko = Embed(colour = Colour.random())
        miko.set_author(name = f"第 {index+1} 個頻道:")
        miko.set_thumbnail(url = self.thumbnail)
        miko.add_field(name = "🎯名稱:",value = self.title,inline=False)
        miko.add_field(name = "🔗網址:",value = f"https://www.youtube.com/channel/{self.id}" if self.platform == "youtube" else f"https://www.twitch.tv/{self.id}",inline=False)
        miko.add_field(name = "🎞️最新影片url:",value = self.latest_video,inline=False)
        miko.add_field(name = "🚩平台:",value = f"<:yt:1032640435375583342>Youtube" if self.platform == "youtube" else f"<:th:1032831426959245423>Twitch")
        return miko

class Guild():
    def __init__(self, guild_id: int, text_id: int, voice_id: int):
        self.guild_id = guild_id
        self.text_id = text_id
        self.voice_id = voice_id
    
    def toEmbed(self,bot:commands.Bot,index:int = 0,number:int = 0) -> Embed:
        guild = bot.get_guild(self.guild_id)
        miko = Embed(colour = Colour.random())
        miko.set_thumbnail(url = guild.icon)
        miko.set_author(name = f"第 {index+1}-{number+1} 個伺服器:") 
        miko.add_field(name = "🎯名稱:",value = guild.name,inline=False)
        miko.add_field(name = "👑擁有者:",value = f"{guild.owner}",inline=False) 
        miko.add_field(name = "👀人數:",value = f"{guild.member_count}人",inline=False)
        return miko
    

import lib.mysql as ms
import commands.Music as Music

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
    
    def toEmbed(self,index:int = 0) -> Embed:
        miko = Embed(colour = Colour.random())
        miko.set_thumbnail(url = self.thumbnail)
        miko.set_author(name = f"第 {index+1} 個直播排程:") 
        miko.add_field(name = "🎯標題:",value = self.title,inline=False)
        miko.add_field(name = "👑頻道名稱:",value = self.channel_title,inline=False)
        miko.add_field(name = "👑url:",value = self.url,inline=False)
        miko.add_field(name = "👀開始時間:",value = datetime.datetime.fromtimestamp(self.start_time).strftime('%Y年%m月%d日 %H點%M分%S秒'),inline=False)
        miko.add_field(name = "👀距離開始還有:",value = f"{self.start_time - int(datetime.datetime.now().timestamp())}秒",inline=False)
        return miko
    
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
        self.add_base_button()
        self.time_to_start.start()

    def toEmbed(self,index:int = 0) -> Embed:
        miko = Embed(colour = Colour.random())
        miko.set_thumbnail(url = self.live.thumbnail)
        miko.set_author(name = f"📢第 {index+1} 個觀察目標:") 
        miko.add_field(name = "🎯標題:",value = self.live.title,inline=False)
        miko.add_field(name = "👑頻道名稱:",value = self.live.channel_title,inline=False)
        miko.add_field(name = "🔗url:",value = self.live.url,inline=False)
        miko.add_field(name = "⌛開始時間:",value = datetime.datetime.fromtimestamp(self.live.start_time).strftime('%Y年%m月%d日 %H點%M分%S秒'),inline=False)
        miko.add_field(name = "⏰距離開始還有:",value = f"{self.live.start_time - int(datetime.datetime.now().timestamp())}秒",inline=False)
        miko.add_field(name = "🔔訂閱頻道數:",value = f"{len(self.channels)}個",inline=False)
        miko.add_field(name = "👀已加入隊列頻道數:",value = f"{len(self.already_joined_channels)}個",inline=False)
        return miko

    def add(self,item,callback=None):
        self.add_item(item)
        if callback is not None:
            item.callback = callback
        return item

    def add_base_button(self):
        self.add(Button(style = ButtonStyle.green,label="新增至隊列",emoji="✅"),self.add_in_query)
        self.add(Button(style = ButtonStyle.red,label="移除通知",emoji="❌"),self.remove_notification)
        
    @tasks.loop(count = 1)
    async def time_to_start(self):
        self.join.start()
        print(f"~~~~~~~~~~現正開始直播:{self.live.title}~~~~~~~~~~")
    
    @time_to_start.before_loop
    async def before_time_to_start(self):
        await asyncio.sleep(float(self.live.start_time - int(datetime.datetime.now().timestamp())))

    @tasks.loop(seconds = settings['notification']['refresh_live_interval'])
    async def join(self):
        try:
            search = (await wavelink.NodePool.get_node().get_tracks(wavelink.YouTubeTrack,self.live.url))[0]
        except wavelink.LoadTrackError as e: 
            self.live.reconnection_times += 1
            print(f"        嘗試取得{self.live.title}串流{self.live.reconnection_times}次")
        else: #取的直播串流後執行
            self.join.cancel()
            control_panels = self.control_panels
            for key in self.already_joined_channels.keys():
                history = control_panels[key].history_song
                for index,song in enumerate(history):
                    if not isinstance(song,Music.HistorySong) and song.title == search.title:
                        history[index] = Music.HistorySong(search,self.bot.user)
                        if index == control_panels[key].position - 1: #當前正在等待
                            await control_panels[key].player.play(search)
                        else:
                            control_panels[key].player.queue.put_at_index(index,search)
            self.watch_list.pop(self.live.title)
            print(f"          已取得{self.live.title}串流")
            print(f"~~~~~~~~~~結束監測直播:{self.live.title}~~~~~~~~~~")
        finally:    #先暫時不修理
            pass
            # if "members-only" in str(e):
            #     self.join.cancel()
            #     control_panels = self.control_panels
            #     for key in self.already_joined_channels.keys():
            #         history = control_panels[key].history_song
            #         for index,song in enumerate(history):
            #             if not isinstance(song,Music.HistorySong) and song.title == search.title:
            #                 if index == control_panels[key].position - 1: #當前正在等待
            #                     await control_panels[key].player.play(search)
            #                 else:
            #                     control_panels[key].player.queue.put_at_index(index,search)

            #     self.watch_list.pop(self.live.title)
            #     print(f"        已強制結束監測，原因:會員限定直播")
            #     print(f"~~~~~~~~~~結束監測直播:{self.live.title}~~~~~~~~~~")
    
    @join.before_loop
    async def before_join(self): 
        players = self.players
        control_panels = self.control_panels
        for key,value in self.channels.items():
            if key not in players:
                players[key] = await self.bot.get_channel(value['obj'].voice_id).connect(cls=wavelink.Player)
                await asyncio.sleep(1)
                if players[key].is_connected():
                    control_panels[key] = Music.ControlView(players.get(key))
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
                control_panel: Music.ControlView = control_panels.get(key)
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
                control_panels[key] = Music.ControlView(players.get(key))
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
            control_panel: Music.ControlView = control_panels.get(key)
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

class Video():
    def __init__(self, title: str, url: str, thumbnail: str,date:datetime.datetime ,type:str):
        self.title = title
        self.thumbnail = thumbnail
        self.url = url
        self.date = date
        self.type = type

    def toString(self):
        print(f"===============新{self.type}影片===============")
        print("- 標題:", self.title)
        print("- url:", self.url)
        print("- 縮圖:", self.thumbnail)
        print("===========================================")

async def get_video_datetime(video_id):
    videos_html = requests.get(f"https://www.youtube.com/watch?v={video_id}").text
    soup = BeautifulSoup(videos_html, "html.parser")
    data = re.search(
        r"var ytInitialData = ({.*});", str(soup)).group(1)
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        data = re.search(r"(.*);</script>", data).group(1)
        data = json.loads(data)
    datetime_str = data['contents']['twoColumnWatchNextResults']['results']['results']['contents'][0]['videoPrimaryInfoRenderer']['dateText']['simpleText']
    datetime_str = datetime_str.split('：')
    if len(datetime_str) == 2:
        datetime_str = datetime_str[1]
    else:
        datetime_str = datetime_str[0]
    try:
        dateTime = datetime.datetime.strptime(datetime_str, '%Y年%m月%d日')
    except ValueError:
        dateTime = datetime.datetime.today()
        
    return dateTime

async def get_latest_video_from_videos(url):
    videos_html = requests.get(f"{url}/videos").text
    soup = BeautifulSoup(videos_html, "html.parser")
    data = re.search(
        r"var ytInitialData = ({.*});", str(soup)).group(1)
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        data = re.search(r"(.*);</script>", data).group(1)
        data = json.loads(data)

    try:
        for tab_item in data['contents']['twoColumnBrowseResultsRenderer']['tabs']:
            if tab_item['tabRenderer']['title'] == "影片":
                for item in tab_item['tabRenderer']['content']['richGridRenderer']['contents']:
                    #print(item['gridVideoRenderer'])
                    #print(re.findall('(?<="url":").*?(?=")', videos_html)[2])
                    if item['richItemRenderer']['content']['videoRenderer']['thumbnailOverlays'][0]['thumbnailOverlayTimeStatusRenderer']['style'] == "LIVE":
                        continue
                    else:
                        video_id = item['richItemRenderer']['content']['videoRenderer']['videoId']
                        thumbnail = item['richItemRenderer']['content']['videoRenderer']['thumbnail']['thumbnails'][3]['url']
                        title = item['richItemRenderer']['content']['videoRenderer']['title']['runs'][0]['text']
                        url = f"https://www.youtube.com/watch?v={video_id}"
                        break
                break
    except KeyError as e:
        print(e)
        return None
    return Video(title,url,thumbnail,await get_video_datetime(video_id),"videos")

async def get_latest_video_from_streams(url):
    videos_html = requests.get(f"{url}/streams").text
    soup = BeautifulSoup(videos_html, "html.parser")
    data = re.search(
        r"var ytInitialData = ({.*});", str(soup)).group(1)
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        data = re.search(r"(.*);</script>", data).group(1)
        data = json.loads(data)

    try:
        for tab_item in data['contents']['twoColumnBrowseResultsRenderer']['tabs']:
            if tab_item['tabRenderer']['title'] == "直播":
                for item in tab_item['tabRenderer']['content']['richGridRenderer']['contents']:
                    style = item['richItemRenderer']['content']['videoRenderer']['thumbnailOverlays'][0]['thumbnailOverlayTimeStatusRenderer']['style']
                    if style == "LIVE" or style == "UPCOMING":
                        continue
                    else:
                        video_id = item['richItemRenderer']['content']['videoRenderer']['videoId']
                        thumbnail = item['richItemRenderer']['content']['videoRenderer']['thumbnail']['thumbnails'][3]['url']
                        title = item['richItemRenderer']['content']['videoRenderer']['title']['runs'][0]['text']
                        url = f"https://www.youtube.com/watch?v={video_id}"
                        break
                break
    except KeyError as e:
        print(e)
        return None
    return Video(title,url,thumbnail,await get_video_datetime(video_id),"streams")

async def get_latest_video_from_Shorts(url):
    videos_html = requests.get(f"{url}/shorts").text
    soup = BeautifulSoup(videos_html, "html.parser")
    data = re.search(
        r"var ytInitialData = ({.*});", str(soup)).group(1)
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        data = re.search(r"(.*);</script>", data).group(1)
        data = json.loads(data)

    try:
        for tab_item in data['contents']['twoColumnBrowseResultsRenderer']['tabs']:
            if tab_item['tabRenderer']['title'] == "Shorts":
                for item in tab_item['tabRenderer']['content']['richGridRenderer']['contents'][:1]:
                    video_id = item['richItemRenderer']['content']['reelItemRenderer']['videoId']
                    thumbnail = item['richItemRenderer']['content']['reelItemRenderer']['thumbnail']['thumbnails'][0]['url']
                    title = item['richItemRenderer']['content']['reelItemRenderer']['headline']['simpleText']
                    url = f"https://www.youtube.com/shorts/{video_id}"
                break
    except KeyError as e:
        return None
    return Video(title,url,thumbnail,await get_video_datetime(video_id),"Shorts")

async def get_latest_video(channel_url : str) -> Video:
    videos_html = requests.get(channel_url).text 
    soup = BeautifulSoup(videos_html, "html.parser")
    data = re.search(
        r"var ytInitialData = ({.*});", str(soup)).group(1)
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        data = re.search(r"(.*);</script>", data).group(1)
        data = json.loads(data)
    videos = []
    try:
        for tab_item in data['contents']['twoColumnBrowseResultsRenderer']['tabs']:
            if tab_item['tabRenderer']['title'] == "首頁":
                # for section_item in tab_item['tabRenderer']['content']['sectionListRenderer']['contents']:
                #     if section_item['itemSectionRenderer']['contents'][0].get('shelfRenderer') != None:
                #         if section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['title']['runs'][0]['text'] == "影片": 
                #             video_list = section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['content']['horizontalListRenderer']['items']
                #             for video in video_list[:5]:
                #                 style = video['gridVideoRenderer']['thumbnailOverlays'][0]['thumbnailOverlayTimeStatusRenderer']['style']
                #                 if style == "LIVE" or style == "UPCOMING":
                #                     continue
                #                 else:
                #                     title = video['gridVideoRenderer']['title']['simpleText']
                #                     url = f"https://www.youtube.com/watch?v={video['gridVideoRenderer']['videoId']}"
                #                     thumbnail = video['gridVideoRenderer']['thumbnail']['thumbnails'][3]['url']
                #                     print("----------最新影片/直播----------")
                #                     print("- 標題:",title)
                #                     print("- 網址:",url)
                #                     print("- 縮圖:",thumbnail)
                #                     print("- 類型:",style)
                #                     print("---------------------------------")
                #                     return Video(title,url,thumbnail,None,"videos")
                # else:
                for tab_item in data['contents']['twoColumnBrowseResultsRenderer']['tabs']:
                    if tab_item.get('tabRenderer') != None:
                        print(tab_item['tabRenderer']['title'])
                        if tab_item['tabRenderer']['title'] == "影片":
                            video = await get_latest_video_from_videos(f"{channel_url}/videos")
                        elif tab_item['tabRenderer']['title'] == "直播":
                            video = await get_latest_video_from_streams(f"{channel_url}/streams")
                        elif tab_item['tabRenderer']['title'] == "Shorts":
                            video = await get_latest_video_from_Shorts(f"{channel_url}/shorts")
                        else:
                            continue
                        if video is not None:
                            videos.append(video)
                            video.toString()
                        print("--------------------------")

                latest_video:Video = videos[0]
                for video in videos[1:]:
                    if latest_video.date < video.date:
                        latest_video = video 
                else:
                    print("---------------最新影片/直播---------------")
                    latest_video.toString()
                    return latest_video
    except KeyError:
        print("----------新影片資訊取得失敗----------")
        return None  

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

        video:Video = await get_latest_video(URL)
    else:
        pass

    return Channel(channel_id, channel_title, channel_thumbnail, video.url, platform)

def init() -> dict:
    return ms.get_channels()

@tasks.loop(seconds = settings['notification']['interval']) 
async def checkforvideos(bot: commands.Bot, notification_channels: dict, players: dict, control_panels: dict,watch_list:dict, node: wavelink.Node):

    def create_new_video_embed(channel:Channel,video:Video): 
        miko = Embed(colour = Colour.random())
        miko.set_author(name = "🎧新的影片發布:")
        miko.set_thumbnail(url = channel.thumbnail)
        miko.add_field(name = "<:yt:1032640435375583342>頻道:",value=channel.title)
        miko.add_field(name = "🎯名稱:",value = video.title)
        miko.add_field(name = "🔗網址:",value = channel.latest_video,inline=False)
        miko.set_image(url = video.thumbnail)
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
            videos:List[Live] = []
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = re.search(r"(.*);</script>", data).group(1)
                data = json.loads(data)
            try:
                for tab_item in data['contents']['twoColumnBrowseResultsRenderer']['tabs']: #會員限定直播需過濾
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
            for v in videos: #待修復:同一時間點的直播 會造成前一占據的會被忽視
                v.toString()
                if v.start_time <= int((datetime.datetime.now() + datetime.timedelta(days=1)).timestamp()): #小於一天內開播
                    if watch_list.__contains__(v.title): #舊的直播
                        waiting_channels = watch_list[v.title].channels
                        print("waiting_channels_before:",waiting_channels)
                        for (id,guild) in value['channels'].items():
                            if not waiting_channels.__contains__(id): #新的頻道訂閱群
                                waiting_channels[id] = {
                                    "obj":guild
                                }
                                channel = await bot.fetch_channel(guild['obj'].text_id)
                                watch_list[v.title].message = await channel.send(embed = v.create_embed(),view = watch_list[v.title])
                        print("waiting_channels_after:",waiting_channels)
                    else: #新的直播加入
                        watch_list[v.title] = CheckView(v,dict(value['channels']),bot,node,watch_list,players,control_panels)
                        for (id,guild) in value['channels'].items():
                            channel = await bot.fetch_channel(guild['obj'].text_id)
                            watch_list[v.title].message = await channel.send(embed = v.create_embed(),view = watch_list[v.title])
                    pass

        
        video:Video = await get_latest_video(channel_url)
        if (c.latest_video != video.url) & (video is not None):
            print("原影片url:",c.latest_video)
            c.latest_video = video.url
            for (id,guild) in value['channels'].items():
                channel = await bot.fetch_channel(guild['obj'].text_id)
                await channel.send(embed = create_new_video_embed(c,video))
            ms.update_latest_video(c.title,video.url)
            print("新片上架")
        print("==========================下一個頻道==========================")
    print(f"----------------下次執行時間:{datetime.datetime.fromtimestamp(int(datetime.datetime.now().timestamp())) + datetime.timedelta(seconds = settings['notification']['interval'])}----------------")
