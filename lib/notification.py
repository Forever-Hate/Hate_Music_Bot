import asyncio
import requests
import datetime
import json
import re
import wavelink
import commands.music as Music
import lib.sql as sql
from bs4 import BeautifulSoup
from discord import ButtonStyle, Colour, Embed, Interaction, WebhookMessage
from discord.ext import commands,tasks 
from typing import Dict, List, Tuple, Union
from discord.ui import Button
from lib.common import Channel, CustomView, Guild, Live, Playlist, YTSong , Platform

with open('./config/settings.json', "r", encoding='utf-8') as f:
    settings = json.load(f)

class CheckView(CustomView):

    def __init__(self, live: Live, channels: dict, bot: commands.bot, watch_list: dict, players: dict, control_panels: dict):
        super().__init__(timeout = None)
        self.live = live
        self.bot = bot
        self.channels = channels #該直播訂閱的guild
        self.already_joined_channels = {} #已經加入隊列的guild
        self.watch_list = watch_list #正在被觀察的直播dict
        self.players = players
        self.control_panels = control_panels
        self.message = None
        self.add_base_button()
        self.time_to_start.start()

    def toEmbed(self, index: int = 0) -> Embed:
        miko = Embed(colour=Colour.random())
        miko.set_thumbnail(url = self.live.thumbnail)
        miko.set_author(name=f"📢第 {index+1} 個觀察目標:")
        miko.add_field(name="🎯標題:", value=self.live.title , inline=False)
        miko.add_field(name = "👑頻道名稱:", value = self.live.channel_title, inline = False)
        miko.add_field(name = "🔗url:", value = self.live.url, inline = False)
        miko.add_field(name = "⌛開始時間:", value = datetime.datetime.fromtimestamp(self.live.start_time).strftime('%Y年%m月%d日 %H點%M分%S秒'), inline = False)
        miko.add_field(name = "⏰距離開始還有:", value = f"{self.live.start_time - int(datetime.datetime.now().timestamp())}秒", inline = False)
        miko.add_field(name = "🔔訂閱頻道數:", value = f"{len(self.channels)}個", inline = False)
        miko.add_field(name = "👀已加入隊列頻道數:", value = f"{len(self.already_joined_channels)}個", inline = False)
        return miko

    def add_base_button(self):
        self.add(Button(style = ButtonStyle.green,label = "新增至隊列", emoji = "✅"), self.__add_in_query)
        self.add(Button(style = ButtonStyle.red, label = "移除通知",emoji = "❌"), self.__remove_notification)

    def ui_control(self):
        pass

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
            song = YTSong(self.live.url)
            result = await song.init()
            if isinstance(result,tuple):
                self.live.reconnection_times += 1
                print(f"        嘗試取得{self.live.title}串流{self.live.reconnection_times}次")
                return
            else: # 取的直播串流後執行
                self.join.cancel()
                control_panels = self.control_panels
                for key in self.already_joined_channels.keys():
                    history = control_panels[key].history_song
                    for index, item in enumerate(history):
                        #確認是否已在隊列中
                        if not isinstance(item, Music.HistorySong) and item.title == song.title:
                            history[index] = Music.HistorySong(song, self.bot.user) #把先前加入的live物件替換
                            if index == control_panels[key].position - 1:  # 當前正在等待
                                await control_panels[key].player.play(song.track)
                            else:
                                control_panels[key].player.queue.put_at_index(index, song.track)
                self.watch_list.pop(self.live.title) #已取得直播後就從觀察清單移除
                print(f"          已取得{self.live.title}串流")
                print(f"~~~~~~~~~~結束監測直播:{self.live.title}~~~~~~~~~~")
        except Exception:  # 先暫時不修理
            print("會員限定直播")
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
        for key, value in self.channels.items():
            if key not in players:
                players[key] = await self.bot.get_channel(value['obj'].voice_id).connect(cls = wavelink.Player)
                await asyncio.sleep(1)
                if players[key].is_connected():
                    control_panels[key] = Music.ControlView(players.get(key))
                    control_panels[key].channel = self.bot.get_channel(value['obj'].text_id)
                    control_panels[key].history_song.append(self.live)
                    control_panels[key].history_thumbnails.append(self.live.thumbnail)
                    control_panels[key].message: WebhookMessage = await control_panels[key].channel.send(embed=control_panels[key].create_embed(), view=control_panels[key])
                    control_panels[key].message_id = control_panels[key].message.id
                    if not control_panels[key].refresh_webhook.is_running():
                        control_panels[key].refresh_webhook.start()
                    if not control_panels[key].refresh_panel.is_running():
                        control_panels[key].refresh_panel.start()
                else:
                    players.pop(key)
            else:
                control_panel: Music.ControlView = control_panels.get(key)
                control_panel.history_song.append(self.live)
                control_panel.history_thumbnails.append(self.live.thumbnail)
                await control_panel.message.edit(content = f"<@{self.bot.user.id}>已新增等待 {self.live.channel_title} 直播開始至隊列中", embed = control_panel.create_embed(), view = control_panel)
            await self.message.delete()
        self.already_joined_channels.update(self.channels) #將B值更新至A

    async def __add_in_query(self, interaction: Interaction):
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
                control_panels[key].message: WebhookMessage = await control_panels[key].channel.send(embed=control_panels[key].create_embed(), view=control_panels[key])
                control_panels[key].message_id = control_panels[key].message.id
                if not control_panels[key].refresh_webhook.is_running():
                        control_panels[key].refresh_webhook.start()
                if not control_panels[key].refresh_panel.is_running():
                    control_panels[key].refresh_panel.start()
                await interaction.followup.send(f"已新增等待 {self.live.channel_title} 直播開始至隊列中", ephemeral=True)
            else:
                players.pop(key)
        else:
            control_panel: Music.ControlView = control_panels.get(key)
            control_panel.history_song.append(self.live)
            control_panel.history_thumbnails.append(self.live.thumbnail)
            await control_panel.message.edit(content=f"<@{interaction.user.id}>已新增等待 {self.live.channel_title} 直播開始至隊列中", embed=control_panel.create_embed(), view=control_panel)
            await interaction.followup.send(f"已新增等待 {self.live.channel_title} 直播開始至隊列中", ephemeral=True)
        self.already_joined_channels[interaction.guild_id] = self.channels.pop(interaction.guild_id)

    async def __remove_notification(self, interaction: Interaction):
        await self.message.delete()
        self.channels.pop(interaction.guild_id)
        if not self.channels and not self.already_joined_channels:  # 當等待直播隊列與已加入頻道隊列為空時
            self.time_to_start.cancel()
            self.watch_list.pop(self.live.title)
        await interaction.response.send_message(f"已移除 {self.live.title} 直播通知", ephemeral=True)

class Video():

    def __init__(self, title: str, url: str, thumbnail: str, date: datetime.datetime, type: str):
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

async def get_video_datetime(video_id) -> datetime.datetime:
    videos_html = requests.get(
        f"https://www.youtube.com/watch?v={video_id}").text
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

#取得最新影片(影片)
async def get_latest_video_from_videos(url) -> Union[Video,None]:
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
    return Video(title, url, thumbnail, await get_video_datetime(video_id), "videos")

#取得最新影片(直播)
async def get_latest_video_from_streams(url) -> Union[Video,None]:
    videos_html = requests.get(f"{url}/streams").text
    soup = BeautifulSoup(videos_html, "html.parser")
    data = re.search(r"var ytInitialData = ({.*});", str(soup)).group(1)
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        data = re.search(r"(.*);</script>", data).group(1)
        data = json.loads(data)
    title = ""
    thumbnail = ""
    video_id = ""
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
        #表示只有一個直播影片而且是待播中或直播中
        if title == "" or thumbnail == "" or video_id == "":
            return None
    except KeyError as e:
        print("get_latest_video_from_streams 取得失敗:",e)
        return None
    return Video(title, url, thumbnail, await get_video_datetime(video_id), "streams")

#取得最新影片(short)
async def get_latest_video_from_Shorts(url) -> Union[Video,None]:
    videos_html = requests.get(f"{url}/shorts").text
    soup = BeautifulSoup(videos_html, "html.parser")
    data = re.search(
        r"var ytInitialData = ({.*});", str(soup)).group(1)
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        data = re.search(r"(.*);</script>", data).group(1)
        data = json.loads(data)
    video_id = ""
    thumbnail = ""
    title = ""
    try:
        for tab_item in data['contents']['twoColumnBrowseResultsRenderer']['tabs']:
            if tab_item['tabRenderer']['title'] == "Shorts":
                for item in tab_item['tabRenderer']['content']['richGridRenderer']['contents'][:1]:
                    video_id = item['richItemRenderer']['content']['reelItemRenderer']['videoId']
                    thumbnail = item['richItemRenderer']['content']['reelItemRenderer']['thumbnail']['thumbnails'][0]['url']
                    title = item['richItemRenderer']['content']['reelItemRenderer']['headline']['simpleText']
                    url = f"https://www.youtube.com/shorts/{video_id}"
                break
        if video_id == "" or thumbnail == "" or title == "":
            return None
    except KeyError as e:
        return None
    return Video(title, url, thumbnail, await get_video_datetime(video_id), "Shorts")

#取得最新影片(總)
async def get_latest_video(channel_url: str) -> Union[Video,None]:
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

                latest_video: Video = videos[0]
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


async def create_channel(platform: Platform, URL: str) -> Channel:
    if platform == Platform.YOUTUBE:
        soup = BeautifulSoup(requests.get(URL).content, "html.parser")
        data = re.search(r"var ytInitialData = ({.*});", str(soup)).group(1)
        try:
            json_data = json.loads(data)
            channel_id = json_data['header']['c4TabbedHeaderRenderer']['channelId']
            channel_title = json_data['header']['c4TabbedHeaderRenderer']['title']
            channel_thumbnail = json_data['header']['c4TabbedHeaderRenderer']['avatar']['thumbnails'][2]['url']
        except json.JSONDecodeError:
            json_data = re.search(
                r"\"header\":(.*),\"metadata\"", data).group(1)
            json_data = json.loads(json_data)
            channel_id = json_data['c4TabbedHeaderRenderer']['channelId']
            channel_title = json_data['c4TabbedHeaderRenderer']['title']
            channel_thumbnail = json_data['c4TabbedHeaderRenderer']['avatar']['thumbnails'][2]['url']
        video: Video = await get_latest_video(URL)
    else:
        pass

    return Channel(channel_id, channel_title, channel_thumbnail, video.url, platform)


async def init(bot: commands.Bot) -> Tuple[Dict[str,Playlist],Dict[str,Dict[Channel,Dict[int,Guild]]]]:
    return await sql.get_playlists(bot), await sql.get_channels()


@tasks.loop(seconds=settings['notification']['interval'])
async def checkforvideos(bot: commands.Bot, notification_channels: dict, players: dict, control_panels: dict, watch_list: dict):

    def create_new_video_embed(channel: Channel, video: Video):
        miko = Embed(colour=Colour.random())
        miko.set_author(name="🎧新的影片發布:")
        miko.set_thumbnail(url=channel.thumbnail)
        miko.add_field(name=f"{Platform.YOUTUBE.value}頻道:",
                       value=channel.title)
        miko.add_field(name="🎯名稱:", value=video.title)
        miko.add_field(name="🔗網址:", value=channel.latest_video, inline=False)
        miko.set_image(url=video.thumbnail)
        return miko
    print(f"------------------現在時間:{datetime.datetime.fromtimestamp(int(datetime.datetime.now().timestamp()))}------------------")
    for channel_id, value in notification_channels.items():
        channel_url = f"https://www.youtube.com/channel/{channel_id}"
        index_html = requests.get(channel_url).text
        live_channel: Channel = value['obj']
        subscribe_guilds:dict[int,Guild] = value['channels']
        print("頻道:", live_channel.title)
        if re.search('(?<="startTime":").*?(?=")', index_html) is not None:
            soup = BeautifulSoup(index_html, "html.parser")
            data = re.search(r"var ytInitialData = ({.*});", str(soup)).group(1)
            videos: List[Live] = []
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = re.search(r"(.*);</script>", data).group(1)
                data = json.loads(data)
            try:
                # 會員限定直播需過濾
                for tab_item in data['contents']['twoColumnBrowseResultsRenderer']['tabs']:
                    if tab_item['tabRenderer']['title'] == "首頁":
                        for section_item in tab_item['tabRenderer']['content']['sectionListRenderer']['contents']:
                            if section_item['itemSectionRenderer']['contents'][0].get('shelfRenderer') != None:
                                if section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['title']['runs'][0]['text'] == "已排定的直播影片":
                                    # 只有一個影片會出現
                                    if section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['content'].get('expandedShelfContentsRenderer') != None:
                                        video_list = section_item['itemSectionRenderer']['contents'][0][
                                            'shelfRenderer']['content']['expandedShelfContentsRenderer']['items']
                                        for video in video_list:
                                            if video['videoRenderer'].get('upcomingEventData') != None:
                                                title = video['videoRenderer']['title']['simpleText']
                                                url = f"https://www.youtube.com/watch?v={video['videoRenderer']['videoId']}"
                                                start_time = int(
                                                    video['videoRenderer']['upcomingEventData']['startTime'])
                                                thumbnail = video['videoRenderer']['thumbnail']['thumbnails'][3]['url']
                                                videos.append(
                                                    Live(title, live_channel.title, url, start_time, thumbnail, live_channel.platform))
                                    else:  # 一個以上影片會出現
                                        video_list = section_item['itemSectionRenderer']['contents'][0][
                                            'shelfRenderer']['content']['horizontalListRenderer']['items']
                                        for video in video_list:
                                            if video['gridVideoRenderer'].get('upcomingEventData') != None:
                                                title = video['gridVideoRenderer']['title']['simpleText']
                                                url = f"https://www.youtube.com/watch?v={video['gridVideoRenderer']['videoId']}"
                                                start_time = int(
                                                    video['gridVideoRenderer']['upcomingEventData']['startTime'])
                                                thumbnail = video['gridVideoRenderer']['thumbnail']['thumbnails'][3]['url']
                                                videos.append(
                                                    Live(title, live_channel.title, url, start_time, thumbnail, live_channel.platform))
                                    break
                                # 影片未分類時出現
                                elif section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['title']['runs'][0]['text'] == "上傳的影片":
                                    video_list = section_item['itemSectionRenderer']['contents'][0][
                                        'shelfRenderer']['content']['horizontalListRenderer']['items']
                                    for video in video_list[:5]:
                                        if video['gridVideoRenderer'].get('upcomingEventData') != None:
                                            title = video['gridVideoRenderer']['title']['simpleText']
                                            url = f"https://www.youtube.com/watch?v={video['gridVideoRenderer']['videoId']}"
                                            start_time = int(
                                                video['gridVideoRenderer']['upcomingEventData']['startTime'])
                                            thumbnail = video['gridVideoRenderer']['thumbnail']['thumbnails'][3]['url']
                                            videos.append(Live(title, live_channel.title, url, start_time, thumbnail, live_channel.platform))
                                    break
                        break
            except KeyError:
                print("----------直播資訊取得失敗----------")
            for video in videos:  # 待修復:同一時間點的直播 會造成前一占據的會被忽視
                video.toString()
                # 小於一天內開播
                if video.start_time <= int((datetime.datetime.now() + datetime.timedelta(days=1)).timestamp()):
                    if watch_list.__contains__(video.title):  # 舊的直播
                        waiting_channels = watch_list[video.title].channels
                        print("waiting_channels_before:", waiting_channels)
                        for id, guild in subscribe_guilds.items():
                            # 新的頻道訂閱群
                            if not waiting_channels.__contains__(id):
                                waiting_channels[id] = {
                                    "obj": guild
                                }
                                channel = await bot.fetch_channel(guild['obj'].text_id)
                                watch_list[video.title].message = await channel.send(embed=video.create_embed(), view=watch_list[video.title])
                        print("waiting_channels_after:", waiting_channels)
                    else:  # 新的直播加入
                        watch_list[video.title] = CheckView(video, subscribe_guilds, bot, watch_list, players, control_panels)
                        for id,guild in subscribe_guilds.items():
                            channel = await bot.fetch_channel(guild['obj'].text_id)
                            watch_list[video.title].message = await channel.send(embed=video.create_embed(), view=watch_list[video.title])
        





        #新影片上架
        video: Video = await get_latest_video(channel_url)
        if video is not None:
            if live_channel.latest_video != video.url:
                print("原影片url:", live_channel.latest_video)
                live_channel.latest_video = video.url
                for (id, guild) in value['channels'].items():
                    channel = await bot.fetch_channel(guild['obj'].text_id)
                    await channel.send(embed=create_new_video_embed(live_channel, video))
                sql.update_latest_video(live_channel.title, video.url)
                print("新片上架")
        print("==========================下一個頻道==========================")
    print(f"----------------下次執行時間:{datetime.datetime.fromtimestamp(int(datetime.datetime.now().timestamp())) + datetime.timedelta(seconds = settings['notification']['interval'])}----------------")
