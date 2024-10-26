from typing import Dict
from lib.common import Channel, Guild, Playlist,Song,get_platform_info_by_string,get_string_by_platform
import pyodbc
import os

DRIVER_NAME = os.getenv('DRIVER_NAME')
SERVER_NAME = os.getenv("SERVER_NAME")
DB_NAME = os.getenv('DB_NAME')
TB_LATEST_VIDEO = os.getenv('TB_LATEST_VIDEO')
TB_YT_CHANNEL = os.getenv('TB_YT_CHANNEL')
TB_DC_SERVER = os.getenv('TB_DC_SERVER')
TB_PLAYLIST = os.getenv('TB_PLAYLIST')
TB_PLAYLIST_SONG = os.getenv('TB_PLAYLIST_SONG')
USER = os.getenv('DB_USER')
PASSWORD = os.getenv('DB_PASSWORD')

def get_connection() -> pyodbc.Connection: #取得資料庫連線
    return pyodbc.connect(f'DRIVER={{{DRIVER_NAME}}};SERVER={SERVER_NAME};DATABASE={DB_NAME};Trust_Connection=yes;UID={USER};PWD={PASSWORD}')

def update_latest_video(title:str,url:str): #更新最新影片的資料
    conn = get_connection()

    with conn.cursor() as cursor:
        # 執行預存程序
        cursor.execute("exec usp_UpdateLatestVideo @title = ?, @url = ?", (title, url))
        
        #提交 SQL 變更
        conn.commit()

    # 關閉 SQL 連線
    conn.close()

async def get_channels() -> Dict[str,Dict[Channel,Dict[int,Guild]]]: #取的所有群的訂閱資料 
    conn = get_connection()

    with conn.cursor() as cursor:
        # 執行預存程序
        cursor.execute(f"exec usp_SelectChannels")
        data = cursor.fetchall()

        cursor.nextset()
        data2 = cursor.fetchall()

        cursor.nextset()
        data3 = cursor.fetchall()

        videos = {}
        guilds = {}
        for (server_id,text_id,voice_id) in data3:
            guilds[server_id] = Guild(int(server_id),int(text_id),int(voice_id))
        for (key,(id,title,thumbnail,latest_video,platform)) in enumerate(data):
            temp_channel = Channel(id,title,thumbnail,latest_video,get_platform_info_by_string(platform))
            videos[id] = {
                "obj":temp_channel,
                "channels":{

                }
            }
            guild = list(data2[key])[0]
            for g in guild.split(','):
                videos[id]['channels'][int(g)] = {
                    "obj":guilds.get(g)
                }
        print("notification_channels:",videos)

    # 關閉 SQL 連線
    conn.close()
    return videos

def subscribe_channel(channel:Channel,g:Guild): #新增群的訂閱資料
    conn = get_connection()

    with conn.cursor() as cursor:
        # 執行預存程序
        cursor.execute("exec usp_InsertSubscribeChannel @channel_id = ?, @title = ?, @thumbnail = ?, @type = ?, @server_id = ?, @text_id = ?, @voice_id = ?, @video_url = ?", 
                       (channel.id, channel.title, channel.thumbnail, get_string_by_platform(channel.platform), g.guild_id, g.text_id, g.voice_id, channel.latest_video))
        
        #提交 SQL 變更
        conn.commit()

    # 關閉 SQL 連線
    conn.close() 

def unsubscribe_channel(channel:Channel,guild_id): #移除群的訂閱資料
    conn = get_connection()

    with conn.cursor() as cursor: 
        # 執行預存程序
        cursor.execute("EXEC usp_DeleteSubscribeChannel @server_id = ?, @channel_id = ?", (guild_id, channel.id))
        
        # 提交 SQL 變更
        conn.commit()

    # 關閉 SQL 連線
    conn.close()  

async def get_playlists(bot) -> Dict[str , Playlist]: #取得所有播放清單 
    conn = get_connection()
    with conn.cursor() as cursor:
        
        # 執行預存程序
        cursor.execute("EXEC usp_SelectPlaylists")
        data = cursor.fetchall()
        
        playlists:Dict[str,Playlist] = {}
        songlists:Dict[str,Song] = {}
        for (playlist_title,creater_id,song_url,joiner_id,play_count) in data:
            song = None
            if song_url is not None:
                if not songlists.__contains__(song_url):
                    song = Song(song_url)
                    await song.init()
                    if joiner_id is not None:
                        song.setExtras({"joiner":joiner_id})
                    songlists[song_url] = song

            if not playlists.__contains__(playlist_title):
                creater = await bot.fetch_user(int(creater_id))
                if songlists.__contains__(song_url):
                    playlists[playlist_title] = Playlist([songlists[song_url]],creater,play_count)
                else:
                    playlists[playlist_title] = Playlist([],creater,play_count)
            else:
                if songlists.__contains__(song_url):
                    playlists[playlist_title].song_list.append(songlists[song_url])
        
        print("playlists:",playlists)
    # 關閉 SQL 連線
    conn.close() 
    return playlists

def create_new_playlist(name:str,user:str): #新增新的播放清單 
    conn = get_connection()

    with conn.cursor() as cursor: 
        # 執行預存程序
        cursor.execute("exec usp_InsertNewPlaylist @name = ?, @user = ?,@play_count = ?", (name, user, 0))
        
        # 提交 SQL 變更
        conn.commit()

    # 關閉 SQL 連線
    conn.close()

def update_playlist_play_count(name: str, play_count: int):  # 更新播放清單的播放次數
    conn = get_connection()

    with conn.cursor() as cursor:
        # 執行預存程序
        cursor.execute("exec usp_UpdatePlaylistPlayCount @name = ?, @play_count = ?", (name, play_count))

        # 提交 SQL 變更
        conn.commit()

    # 關閉 SQL 連線
    conn.close()

def delete_playlist(name:str): #刪除歌單 
    conn = get_connection()

    with conn.cursor() as cursor: 
        # 執行預存程序
        cursor.execute("EXEC usp_DeletePlaylist @name = ?", (name))
        
        # 提交 SQL 變更
        conn.commit()

    # 關閉 SQL 連線
    conn.close()

def update_playlist_name(old_name:str,new_name:str): #更新歌單名稱 
    conn = get_connection()

    with conn.cursor() as cursor:
        # 執行預存程序
        cursor.execute("exec usp_UpdatePlaylistName @old_name = ?, @new_name = ?", (old_name, new_name))
        
        #提交 SQL 變更
        conn.commit()

    # 關閉 SQL 連線
    conn.close()  

def update_playlist_song_order(name:str,old_no:int,new_no:int): #更新歌曲順序(交換) 
    conn = get_connection()

    with conn.cursor() as cursor:
        # 執行預存程序
        cursor.execute("exec usp_UpdatePlaylistSongOrder @name = ?, @old_no = ?, @new_no = ?", (name, old_no, new_no))
        
        #提交 SQL 變更
        conn.commit()

    # 關閉 SQL 連線
    conn.close()  

def insert_playlist_song(name:str,no:int,url:str,user:str): #新增歌曲
    conn = get_connection()

    with conn.cursor() as cursor: 
        # 執行預存程序
        cursor.execute("EXEC usp_InsertPlaylistSong @name = ?, @no = ?, @url = ?, @user = ?", (name, no, url, user))
        
        # 提交 SQL 變更
        conn.commit()

    # 關閉 SQL 連線
    conn.close()  

def delete_playlist_song(name:str,no:int): #刪除歌曲 
    conn = get_connection()

    with conn.cursor() as cursor: 
        # 執行預存程序
        cursor.execute("exec usp_DeletePlaylistSong @name = ?, @no = ?", (name, no))
        
        # 提交 SQL 變更
        conn.commit()

    # 關閉 SQL 連線
    conn.close()  