import asyncio
import datetime
import json
import os
import requests
import re
import wavelink
import commands.music as Music
import lib.sql as sql
from bs4 import BeautifulSoup
from discord import ButtonStyle, Colour, Embed, Interaction, WebhookMessage
from discord.ext import commands,tasks 
from typing import Dict, List, Tuple, Union
from discord.ui import Button
from lib.common import Channel, CustomView, Guild, Playlist, Song , Platform

NOTIFICATION_REFRESH_LIVE_INTERVAL = int(os.getenv('NOTIFICATION_REFRESH_LIVE_INTERVAL'))
NOTIFICATION_INTERVAL = int(os.getenv('NOTIFICATION_INTERVAL'))
MANAGE_CHANNEL_ID = int(os.getenv('MANAGE_CHANNEL_ID'))

class Video():

    def __init__(self, title: str, url: str, thumbnail: str, date: Union[datetime.datetime,None], type: str):
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

async def get_video_datetime(video_id) -> Union[datetime.datetime,None]:
    try:
        videos_html = requests.get(f"https://www.youtube.com/watch?v={video_id}").text
    except requests.exceptions.Timeout:
        return None
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
    try:
        videos_html = requests.get(f"{url}/videos",timeout = 5).text
    except requests.exceptions.Timeout:
        return None
    soup = BeautifulSoup(videos_html, "html.parser")
    data = re.search(r"var ytInitialData = ({.*});", str(soup)).group(1)
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        data = re.search(r"(.*);</script>", data).group(1)
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None
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
    try:
        videos_html = requests.get(f"{url}/streams",timeout = 5).text
    except requests.exceptions.Timeout:
        return None
    soup = BeautifulSoup(videos_html, "html.parser")
    data = re.search(r"var ytInitialData = ({.*});", str(soup)).group(1)
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        data = re.search(r"(.*);</script>", data).group(1)
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None
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
    try:
        videos_html = requests.get(f"{url}/shorts",timeout = 5).text
    except requests.exceptions.Timeout:
        return None
    soup = BeautifulSoup(videos_html, "html.parser")
    data = re.search(r"var ytInitialData = ({.*});", str(soup)).group(1)
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        data = re.search(r"(.*);</script>", data).group(1)
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None
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
    try:
        videos_html = requests.get(channel_url,timeout = 5).text
    except requests.exceptions.Timeout:
        return None
    soup = BeautifulSoup(videos_html, "html.parser")
    data = re.search(r"var ytInitialData = ({.*});", str(soup)).group(1)
    try:
        data = json.loads(data)
    except json.JSONDecodeError:
        data = re.search(r"(.*);</script>", data).group(1)
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None
    videos:List[Video] = []
    try:
        for tab_item in data['contents']['twoColumnBrowseResultsRenderer']['tabs']:
            if tab_item['tabRenderer']['title'] == "首頁":
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
                    if latest_video.date != None:
                        if video.date != None:
                            if latest_video.date < video.date:
                                latest_video = video
                        else:
                            continue
                    else:
                        break
                print("---------------最新影片/直播---------------")
                latest_video.toString()
                return latest_video
    except (KeyError,IndexError):
        print("----------新影片資訊取得失敗----------")
        return None


async def create_channel(platform: Platform, URL: str) -> Union[Channel,None]:
    if platform == Platform.YOUTUBE:
        try:
            soup = BeautifulSoup(requests.get(URL,timeout = 5).content, "html.parser")
            data = re.search(r"var ytInitialData = ({.*});", str(soup)).group(1)
        except requests.exceptions.Timeout:
            return None
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
        video: Video = await get_latest_video(URL)
    else:
        pass

    return Channel(channel_id, channel_title, channel_thumbnail, video.url, platform)


async def init(bot: commands.Bot) -> Tuple[Dict[str,Playlist],Dict[str,Dict[Channel,Dict[int,Guild]]]]:
    return await sql.get_playlists(bot), await sql.get_channels()


@tasks.loop(seconds=NOTIFICATION_INTERVAL)
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
        live_channel: Channel = value['obj']
        #新影片上架
        video: Video = await get_latest_video(channel_url)
        if video is not None:
            if live_channel.latest_video != video.url:
                print("原影片url:", live_channel.latest_video)
                live_channel.latest_video = video.url
                for (id, item) in value['channels'].items():
                    try:
                        channel = await bot.fetch_channel(item['obj'].text_id)
                        await channel.send(embed=create_new_video_embed(live_channel, video))
                    except Exception:
                        print("新影片通知失敗")
                        try:
                            channel = await bot.fetch_channel(MANAGE_CHANNEL_ID)
                            guild = bot.get_guild(item['obj'].guild_id)
                            miko = Embed(colour=Colour.random())
                            miko.set_author(name="⚠️錯誤:")
                            miko.set_thumbnail(url=live_channel.thumbnail)
                            miko.add_field(name=f"{Platform.YOUTUBE.value}頻道:",value=live_channel.title)
                            miko.add_field(name="🔔伺服器:", value=guild.name)
                            miko.add_field(name="🔥狀態:",value="無法通知新影片",inline=False)
                            miko.add_field(name="🔗網址:", value=live_channel.latest_video, inline=False)
                            miko.set_image(url=video.thumbnail)
                            await channel.send(embed=miko)
                        except Exception as e:
                            print("無效的管理頻道") 
                sql.update_latest_video(live_channel.title, video.url)
                print("新片上架")
        print("==========================下一個頻道==========================")
    print(f"----------------下次執行時間:{datetime.datetime.fromtimestamp(int(datetime.datetime.now().timestamp())) + datetime.timedelta(seconds = NOTIFICATION_INTERVAL)}----------------")
