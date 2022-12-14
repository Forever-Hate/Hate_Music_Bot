import asyncio
from bs4 import BeautifulSoup
import commands.Music as Music
import datetime
from discord import ButtonStyle, Colour, Embed, Interaction, WebhookMessage
from discord.ext import commands,tasks 
from discord.ui import Button
import json
from lib.common import Channel, CustomView, Guild, Live, Playlist, Song
import lib.sql as sql
import re
import requests
from typing import Dict, List, Tuple, Union
import wavelink

with open('./config/settings.json', "r", encoding='utf-8') as f:
    settings = json.load(f)

class CheckView(CustomView):

    def __init__(self, live: Live, channels: dict, bot: commands.bot, watch_list: dict, players: dict, control_panels: dict):
        super().__init__(timeout = None)
        self.live = live
        self.bot = bot
        self.channels = channels
        self.already_joined_channels = {}
        self.watch_list = watch_list
        self.players = players
        self.control_panels = control_panels
        self.message = None
        self.add_base_button()
        self.time_to_start.start()

    def toEmbed(self, index: int = 0) -> Embed:
        miko = Embed(colour=Colour.random())
        miko.set_thumbnail(url = self.live.thumbnail)
        miko.set_author(name=f"๐ข็ฌฌ {index+1} ๅ่งๅฏ็ฎๆจ:")
        miko.add_field(name = "๐ฏๆจ้ก:", value = self.live.title , inline = False)
        miko.add_field(name = "๐้ ป้ๅ็จฑ:", value = self.live.channel_title, inline = False)
        miko.add_field(name = "๐url:", value = self.live.url, inline = False)
        miko.add_field(name = "โ้ๅงๆ้:", value = datetime.datetime.fromtimestamp(self.live.start_time).strftime('%Yๅนด%mๆ%dๆฅ %H้ป%Mๅ%S็ง'), inline = False)
        miko.add_field(name = "โฐ่ท้ข้ๅง้ๆ:", value = f"{self.live.start_time - int(datetime.datetime.now().timestamp())}็ง", inline = False)
        miko.add_field(name = "๐่จ้ฑ้ ป้ๆธ:", value = f"{len(self.channels)}ๅ", inline = False)
        miko.add_field(name = "๐ๅทฒๅ ๅฅ้ๅ้ ป้ๆธ:", value = f"{len(self.already_joined_channels)}ๅ", inline = False)
        return miko

    def add_base_button(self):
        self.add(Button(style = ButtonStyle.green,label = "ๆฐๅข่ณ้ๅ", emoji = "โ"), self.add_in_query)
        self.add(Button(style = ButtonStyle.red, label = "็งป้ค้็ฅ",emoji = "โ"), self.remove_notification)

    def ui_control(self):
        pass

    @tasks.loop(count = 1)
    async def time_to_start(self):
        self.join.start()
        print(f"~~~~~~~~~~็พๆญฃ้ๅง็ดๆญ:{self.live.title}~~~~~~~~~~")

    @time_to_start.before_loop
    async def before_time_to_start(self):
        await asyncio.sleep(float(self.live.start_time - int(datetime.datetime.now().timestamp())))

    @tasks.loop(seconds = settings['notification']['refresh_live_interval'])
    async def join(self):
        try:
            song = Song(self.live.url)
            result = await song.init()
            if isinstance(result,tuple):
                self.live.reconnection_times += 1
                print(f"        ๅ่ฉฆๅๅพ{self.live.title}ไธฒๆต{self.live.reconnection_times}ๆฌก")
                return
            else: # ๅ็็ดๆญไธฒๆตๅพๅท่ก
                self.join.cancel()
                control_panels = self.control_panels
                for key in self.already_joined_channels.keys():
                    history = control_panels[key].history_song
                    for index, song in enumerate(history):
                        if not isinstance(song, Music.HistorySong) and song.title == song.title:
                            history[index] = Music.HistorySong(song, self.bot.user)
                            if index == control_panels[key].position - 1:  # ็ถๅๆญฃๅจ็ญๅพ
                                await control_panels[key].player.play(song.track)
                            else:
                                control_panels[key].player.queue.put_at_index(index, song.track)
                self.watch_list.pop(self.live.title)
                print(f"          ๅทฒๅๅพ{self.live.title}ไธฒๆต")
                print(f"~~~~~~~~~~็ตๆ็ฃๆธฌ็ดๆญ:{self.live.title}~~~~~~~~~~")
        finally:  # ๅๆซๆไธไฟฎ็
            pass
            # if "members-only" in str(e):
            #     self.join.cancel()
            #     control_panels = self.control_panels
            #     for key in self.already_joined_channels.keys():
            #         history = control_panels[key].history_song
            #         for index,song in enumerate(history):
            #             if not isinstance(song,Music.HistorySong) and song.title == search.title:
            #                 if index == control_panels[key].position - 1: #็ถๅๆญฃๅจ็ญๅพ
            #                     await control_panels[key].player.play(search)
            #                 else:
            #                     control_panels[key].player.queue.put_at_index(index,search)

            #     self.watch_list.pop(self.live.title)
            #     print(f"        ๅทฒๅผทๅถ็ตๆ็ฃๆธฌ๏ผๅๅ :ๆๅก้ๅฎ็ดๆญ")
            #     print(f"~~~~~~~~~~็ตๆ็ฃๆธฌ็ดๆญ:{self.live.title}~~~~~~~~~~")

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
                await control_panel.message.edit(content = f"<@{self.bot.user.id}>ๅทฒๆฐๅข็ญๅพ {self.live.channel_title} ็ดๆญ้ๅง่ณ้ๅไธญ", embed = control_panel.create_embed(), view = control_panel)
            await self.message.delete()
        self.already_joined_channels.update(self.channels)

    async def add_in_query(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.message.delete()
        players = self.players
        control_panels = self.control_panels
        key = interaction.guild_id
        if key not in players:
            players[key] = await self.bot.get_channel(self.channels[interaction.guild_id]['obj'].voice_id).connect(cls=wavelink.Player)
            if players[key].is_connected():
                control_panels[key] = Music.ControlView(players.get(key))
                control_panels[key].channel = self.bot.get_channel(
                    self.channels[interaction.guild_id]['obj'].text_id)
                control_panels[key].history_song.append(self.live)
                control_panels[key].history_thumbnails.append(
                    self.live.thumbnail)
                control_panels[key].length += 1
                control_panels[key].message: WebhookMessage = await control_panels[key].channel.send(embed=control_panels[key].create_embed(), view=control_panels[key])
                control_panels[key].message_id = control_panels[key].message.id
                control_panels[key].refresh_webhook.start()
                control_panels[key].refresh_panel.start()
                await interaction.followup.send(f"ๅทฒๆฐๅข็ญๅพ {self.live.channel_title} ็ดๆญ้ๅง่ณ้ๅไธญ", ephemeral=True)
            else:
                players.pop(key)
        else:
            control_panel: Music.ControlView = control_panels.get(key)
            control_panel.history_song.append(self.live)
            control_panel.history_thumbnails.append(self.live.thumbnail)
            control_panel.length += 1
            await control_panel.message.edit(content=f"<@{interaction.user.id}>ๅทฒๆฐๅข็ญๅพ {self.live.channel_title} ็ดๆญ้ๅง่ณ้ๅไธญ", embed=control_panel.create_embed(), view=control_panel)
            await interaction.followup.send(f"ๅทฒๆฐๅข็ญๅพ {self.live.channel_title} ็ดๆญ้ๅง่ณ้ๅไธญ", ephemeral=True)
        self.already_joined_channels[interaction.guild_id] = self.channels.pop(
            interaction.guild_id)

    async def remove_notification(self, interaction: Interaction):
        await self.message.delete()
        self.channels.pop(interaction.guild_id)
        if not self.channels and not self.already_joined_channels:  # ็ถ็ญๅพ็ดๆญ้ๅ่ๅทฒๅ ๅฅ้ ป้้ๅ็บ็ฉบๆ
            self.time_to_start.cancel()
            self.watch_list.pop(self.live.title)
        await interaction.response.send_message(f"ๅทฒ็งป้ค {self.live.title} ็ดๆญ้็ฅ", ephemeral=True)


class Video():

    def __init__(self, title: str, url: str, thumbnail: str, date: datetime.datetime, type: str):
        self.title = title
        self.thumbnail = thumbnail
        self.url = url
        self.date = date
        self.type = type

    def toString(self):
        print(f"===============ๆฐ{self.type}ๅฝฑ็===============")
        print("- ๆจ้ก:", self.title)
        print("- url:", self.url)
        print("- ็ธฎๅ:", self.thumbnail)
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
    datetime_str = datetime_str.split('๏ผ')
    if len(datetime_str) == 2:
        datetime_str = datetime_str[1]
    else:
        datetime_str = datetime_str[0]
    try:
        dateTime = datetime.datetime.strptime(datetime_str, '%Yๅนด%mๆ%dๆฅ')
    except ValueError:
        dateTime = datetime.datetime.today()

    return dateTime


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
            if tab_item['tabRenderer']['title'] == "ๅฝฑ็":
                for item in tab_item['tabRenderer']['content']['richGridRenderer']['contents']:
                    # print(item['gridVideoRenderer'])
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
    return Video(title, url, thumbnail, await get_video_datetime(video_id), "videos")


async def get_latest_video_from_streams(url) -> Union[Video,None]:
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
            if tab_item['tabRenderer']['title'] == "็ดๆญ":
                for item in tab_item['tabRenderer']['content']['richGridRenderer']['contents']:
                    style = item['richItemRenderer']['content']['videoRenderer'][
                        'thumbnailOverlays'][0]['thumbnailOverlayTimeStatusRenderer']['style']
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
    return Video(title, url, thumbnail, await get_video_datetime(video_id), "streams")


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
    return Video(title, url, thumbnail, await get_video_datetime(video_id), "Shorts")


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
            if tab_item['tabRenderer']['title'] == "้ฆ้ ":
                # for section_item in tab_item['tabRenderer']['content']['sectionListRenderer']['contents']:
                #     if section_item['itemSectionRenderer']['contents'][0].get('shelfRenderer') != None:
                #         if section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['title']['runs'][0]['text'] == "ๅฝฑ็":
                #             video_list = section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['content']['horizontalListRenderer']['items']
                #             for video in video_list[:5]:
                #                 style = video['gridVideoRenderer']['thumbnailOverlays'][0]['thumbnailOverlayTimeStatusRenderer']['style']
                #                 if style == "LIVE" or style == "UPCOMING":
                #                     continue
                #                 else:
                #                     title = video['gridVideoRenderer']['title']['simpleText']
                #                     url = f"https://www.youtube.com/watch?v={video['gridVideoRenderer']['videoId']}"
                #                     thumbnail = video['gridVideoRenderer']['thumbnail']['thumbnails'][3]['url']
                #                     print("----------ๆๆฐๅฝฑ็/็ดๆญ----------")
                #                     print("- ๆจ้ก:",title)
                #                     print("- ็ถฒๅ:",url)
                #                     print("- ็ธฎๅ:",thumbnail)
                #                     print("- ้กๅ:",style)
                #                     print("---------------------------------")
                #                     return Video(title,url,thumbnail,None,"videos")
                # else:
                for tab_item in data['contents']['twoColumnBrowseResultsRenderer']['tabs']:
                    if tab_item.get('tabRenderer') != None:
                        print(tab_item['tabRenderer']['title'])
                        if tab_item['tabRenderer']['title'] == "ๅฝฑ็":
                            video = await get_latest_video_from_videos(f"{channel_url}/videos")
                        elif tab_item['tabRenderer']['title'] == "็ดๆญ":
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
                    print("---------------ๆๆฐๅฝฑ็/็ดๆญ---------------")
                    latest_video.toString()
                    return latest_video
    except KeyError:
        print("----------ๆฐๅฝฑ็่ณ่จๅๅพๅคฑๆ----------")
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
        miko.set_author(name="๐งๆฐ็ๅฝฑ็็ผๅธ:")
        miko.set_thumbnail(url=channel.thumbnail)
        miko.add_field(name="<:yt:1032640435375583342>้ ป้:",
                       value=channel.title)
        miko.add_field(name="๐ฏๅ็จฑ:", value=video.title)
        miko.add_field(name="๐็ถฒๅ:", value=channel.latest_video, inline=False)
        miko.set_image(url=video.thumbnail)
        return miko

    print(
        f"------------------็พๅจๆ้:{datetime.datetime.fromtimestamp(int(datetime.datetime.now().timestamp()))}------------------")
    for key, value in notification_channels.items():
        channel_url = f"https://www.youtube.com/channel/{key}"
        index_html = requests.get(channel_url).text
        c: Channel = value['obj']
        print("้ ป้:", c.title)
        if re.search('(?<="startTime":").*?(?=")', index_html) is not None:
            soup = BeautifulSoup(index_html, "html.parser")
            data = re.search(
                r"var ytInitialData = ({.*});", str(soup)).group(1)
            videos: List[Live] = []
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = re.search(r"(.*);</script>", data).group(1)
                data = json.loads(data)
            try:
                # ๆๅก้ๅฎ็ดๆญ้้ๆฟพ
                for tab_item in data['contents']['twoColumnBrowseResultsRenderer']['tabs']:
                    if tab_item['tabRenderer']['title'] == "้ฆ้ ":
                        for section_item in tab_item['tabRenderer']['content']['sectionListRenderer']['contents']:
                            if section_item['itemSectionRenderer']['contents'][0].get('shelfRenderer') != None:
                                if section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['title']['runs'][0]['text'] == "ๅทฒๆๅฎ็็ดๆญๅฝฑ็":
                                    # ๅชๆไธๅๅฝฑ็ๆๅบ็พ
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
                                                    Live(title, c.title, url, start_time, thumbnail, c.platform))
                                    else:  # ไธๅไปฅไธๅฝฑ็ๆๅบ็พ
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
                                                    Live(title, c.title, url, start_time, thumbnail, c.platform))
                                    break
                                # ๅฝฑ็ๆชๅ้กๆๅบ็พ
                                elif section_item['itemSectionRenderer']['contents'][0]['shelfRenderer']['title']['runs'][0]['text'] == "ไธๅณ็ๅฝฑ็":
                                    video_list = section_item['itemSectionRenderer']['contents'][0][
                                        'shelfRenderer']['content']['horizontalListRenderer']['items']
                                    for video in video_list[:5]:
                                        if video['gridVideoRenderer'].get('upcomingEventData') != None:
                                            title = video['gridVideoRenderer']['title']['simpleText']
                                            url = f"https://www.youtube.com/watch?v={video['gridVideoRenderer']['videoId']}"
                                            start_time = int(
                                                video['gridVideoRenderer']['upcomingEventData']['startTime'])
                                            thumbnail = video['gridVideoRenderer']['thumbnail']['thumbnails'][3]['url']
                                            videos.append(
                                                Live(title, c.title, url, start_time, thumbnail, c.platform))
                                    break
                        break
            except KeyError:
                print("----------็ดๆญ่ณ่จๅๅพๅคฑๆ----------")
            for v in videos:  # ๅพไฟฎๅพฉ:ๅไธๆ้้ป็็ดๆญ ๆ้ ๆๅไธๅ ๆ็ๆ่ขซๅฟฝ่ฆ
                v.toString()
                # ๅฐๆผไธๅคฉๅง้ๆญ
                if v.start_time <= int((datetime.datetime.now() + datetime.timedelta(days=1)).timestamp()):
                    if watch_list.__contains__(v.title):  # ่็็ดๆญ
                        waiting_channels = watch_list[v.title].channels
                        print("waiting_channels_before:", waiting_channels)
                        for (id, guild) in value['channels'].items():
                            # ๆฐ็้ ป้่จ้ฑ็พค
                            if not waiting_channels.__contains__(id):
                                waiting_channels[id] = {
                                    "obj": guild
                                }
                                channel = await bot.fetch_channel(guild['obj'].text_id)
                                watch_list[v.title].message = await channel.send(embed=v.create_embed(), view=watch_list[v.title])
                        print("waiting_channels_after:", waiting_channels)
                    else:  # ๆฐ็็ดๆญๅ ๅฅ
                        watch_list[v.title] = CheckView(
                            v, dict(value['channels']), bot, watch_list, players, control_panels)
                        for (id, guild) in value['channels'].items():
                            channel = await bot.fetch_channel(guild['obj'].text_id)
                            watch_list[v.title].message = await channel.send(embed=v.create_embed(), view=watch_list[v.title])
                    pass

        video: Video = await get_latest_video(channel_url)
        if video is not None:
            if c.latest_video != video.url:
                print("ๅๅฝฑ็url:", c.latest_video)
                c.latest_video = video.url
                for (id, guild) in value['channels'].items():
                    channel = await bot.fetch_channel(guild['obj'].text_id)
                    await channel.send(embed=create_new_video_embed(c, video))
                sql.update_latest_video(c.title, video.url)
                print("ๆฐ็ไธๆถ")
        print("==========================ไธไธๅ้ ป้==========================")
    print(
        f"----------------ไธๆฌกๅท่กๆ้:{datetime.datetime.fromtimestamp(int(datetime.datetime.now().timestamp())) + datetime.timedelta(seconds = settings['notification']['interval'])}----------------")
