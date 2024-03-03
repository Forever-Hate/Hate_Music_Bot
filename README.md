# Hate_Music_Bot
## 🎵簡單容易使用的DC音樂bot
透過 `wavelink` 串流音樂，並使用 `discord.py` 串接Discord:
- 單一斜槓指令
- UI控制面板
- 無前綴指令
- 播放歌曲不會造成洗版
- 播完歌曲自動離開並刪除控制面板
- 可以訂閱頻道來獲取直播/新影片通知

TodoList
- [X] 支援播放youtube影片及播放清單
- [X] 支援播放spotify歌曲及播放清單
- [X] 自訂歌單
- [X] 歌單可從隨機、指定位置播放
- [X] 顯示歌詞(僅支援spotify)
- [X] 訂閱youtube頻道追蹤最新影片、直播
- [ ] 訂閱twitch頻道追蹤直播

## 🔧技術
- [discord.py](https://github.com/Rapptz/discord.py)
- [docker](https://www.docker.com/)
- [python](https://www.python.org/)
- [wavelink](https://github.com/PythonistaGuild/Wavelink)

## 📖開始使用
### 檔案結構
```txt
root(任意資料夾)
 |__lavalink(資料夾)
      |__application.yml
      |__lavalink.jar
      |__start.bat
 |__Hate_Music_Bot(專案資料夾)
      |__ ...

```
### 本地
1. 下載本專案後，請打開終端機執行以下指令(請先確保本機具有python執行環境，以及執行目錄在本專案底下`~/Hate_Music_Bot`)
```
pip install --no-cache-dir -r requirements.txt
```
2. 請到 [discord develop portal](https://discord.com/developers/applications) 註冊一個應用程式(Bot)

3. 請下載安裝 [下載資料庫](https://www.microsoft.com/zh-tw/sql-server/sql-server-downloads) 及 [下載管理介面ssms](https://learn.microsoft.com/zh-tw/sql/ssms/download-sql-server-management-studio-ssms?view=sql-server-ver16) (已有sql server資料庫可跳過此步驟)
   <br>註:安裝過程中會設定sa的密碼，請務必記住

4. 開啟SSMS，執行專案內的`script.sql`腳本，建立資料庫與資料表

5. 安裝 lavalink (請確保具有`jdk17 or 以上的執行環境`)
- 請到 [lavalink](https://github.com/lavalink-devs/Lavalink/releases/tag/3.7.8) 下載`lavalink.jar`
- 新增檔案`application.yml`
- 新增檔案`start.bat`
### application.yml
```yaml
server: # REST and WS server
  port: 2333
  address: 0.0.0.0
lavalink:
  server:
    password: "youshallnotpass"
    sources:
      youtube: true
      bandcamp: true
      soundcloud: true
      twitch: true
      vimeo: true
      http: true
      local: false
    filters: # All filters are enabled by default
      volume: true
      equalizer: true
      karaoke: true
      timescale: true
      tremolo: true
      vibrato: true
      distortion: true
      rotation: true
      channelMix: true
      lowPass: true
    bufferDurationMs: 400 # The duration of the NAS buffer. Higher values fare better against longer GC pauses. Duration <= 0 to disable JDA-NAS. Minimum of 40ms, lower values may introduce pauses.
    frameBufferDurationMs: 5000 # How many milliseconds of audio to keep buffered
    opusEncodingQuality: 10 # Opus encoder quality. Valid values range from 0 to 10, where 10 is best quality but is the most expensive on the CPU.
    resamplingQuality: HIGH # Quality of resampling operations. Valid values are LOW, MEDIUM and HIGH, where HIGH uses the most CPU.
    trackStuckThresholdMs: 10000 # The threshold for how long a track can be stuck. A track is stuck if does not return any audio data.
    useSeekGhosting: true # Seek ghosting is the effect where whilst a seek is in progress, the audio buffer is read from until empty, or until seek is ready.
    youtubePlaylistLoadLimit: 6 # Number of pages at 100 each
    playerUpdateInterval: 5 # How frequently to send player updates to clients, in seconds
    youtubeSearchEnabled: true
    soundcloudSearchEnabled: true
    gc-warnings: true
    #ratelimit:
      #ipBlocks: ["1.0.0.0/8", "..."] # list of ip blocks
      #excludedIps: ["...", "..."] # ips which should be explicit excluded from usage by lavalink
      #strategy: "RotateOnBan" # RotateOnBan | LoadBalance | NanoSwitch | RotatingNanoSwitch
      #searchTriggersFail: true # Whether a search 429 should trigger marking the ip as failing
      #retryLimit: -1 # -1 = use default lavaplayer value | 0 = infinity | >0 = retry will happen this numbers times
    #youtubeConfig: # Required for avoiding all age restrictions by YouTube, some restricted videos still can be played without.
      #email: "" # Email of Google account
      #password: "" # Password of Google account
    #httpConfig: # Useful for blocking bad-actors from ip-grabbing your music node and attacking it, this way only the http proxy will be attacked
      #proxyHost: "localhost" # Hostname of the proxy, (ip or domain)
      #proxyPort: 3128 # Proxy port, 3128 is the default for squidProxy
      #proxyUser: "" # Optional user for basic authentication fields, leave blank if you don't use basic auth
      #proxyPassword: "" # Password for basic authentication

metrics:
  prometheus:
    enabled: false
    endpoint: /metrics

sentry:
  dsn: ""
  environment: ""
#  tags:
#    some_key: some_value
#    another_key: another_value

logging:
  file:
    path: ./logs/

  level:
    root: INFO
    lavalink: INFO

  request:
    enabled: true
    includeClientInfo: true
    includeHeaders: false
    includeQueryString: true
    includePayload: true
    maxPayloadLength: 10000


  logback:
    rollingpolicy:
      max-file-size: 1GB
      max-history: 30
```
### start.bat
```bat
java -jar Lavalink.jar pause
```

6. 填寫 .env檔案
### .env
```env
# Discord Bot 應用程式ID
APPLICATION_ID=<your application id>
# Discord Bot Token
TOKEN=<your bot token>
# Discord Bot 管理伺服器ID
MANAGE_SERVER_ID=<your manage discord server id>
# Discord Bot 管理者User ID
MANAGE_USER_ID=<your manage user id>
# Spotify Client ID
SPOTIFY_CLIENT_ID=<your spotify client id>
# Spotify Client Secret
SPOTIFY_CLIENT_SECRET=<your spotify client secret>


# Lavalink Server IP(預設為docker image內的設定，如需本地啟動，請修改為localhost:2333)
WL_HOST=lavalink:${LAVALINK_SERVER_PORT}
# Lavalink Server 密碼(預設為docker image內的設定，如需本地啟動，請修改為youshallnotpass) 
WL_PASSWORD=${LAVALINK_SERVER_PASSWORD} 

# 資料庫連線字串設定
# 驅動器名稱(預設為docker image內的驅動器名稱，如需本地啟動，請修改為SQL Server)
DRIVER_NAME=ODBC Driver 17 for SQL Server
# 伺服器名稱(預設為docker image內的伺服器名稱，如需本地啟動，請修改為本地伺服器名稱)
# 請在ssms內->新增查詢->輸入查詢`select @@SERVERNAME`取得本地伺服器名稱 
SERVER_NAME=mssql
# 資料庫User(預設為sa)
DB_USER=sa
# 資料庫密碼(預設為Aa123456)
DB_PASSWORD=Aa123456  

# 資料庫設定
# -------------勿修改----------------
DB_NAME=discord_music_bot
TB_LATEST_VIDEO=latest_video
TB_YT_CHANNEL=yt_channel
TB_DC_SERVER=dc_server
TB_PLAYLIST=playlist
TB_PLAYLIST_SONG=playlist_song
# -------------勿修改----------------

# 宣傳內容(會出現在Bot名稱下面) {server_count} 會顯示該Bot所在伺服器數量
# 例如: "在 {server_count} 個伺服器上"
# 會顯示為 "在 10 個伺服器上"
# 如有多個宣傳內容，請用 , 分隔
ANNOUNCE_CONTENTS=<your announce contents>
# 宣傳間隔(秒)
ANNOUNCE_INTERVAL=300
# 新影片搜尋間隔(秒)
NOTIFICATION_INTERVAL=300
# 直播狀態刷新間隔(秒)
NOTIFICATION_REFRESH_LIVE_INTERVAL=10
```
7. 開啟終端機，前往至專案目錄底下`~/Hate_Music_Bot`，輸入下列指令，開啟Bot
```txt
python main.py
```

---
## Docker
### 檔案結構
```txt
root(任意資料夾)
 |__envs(資料夾)
      |__app.env
      |__lavalink.env
      |__mssql.env
 |__docker-compose.yml
 |__application.yml(lavalink的設定檔)
 |__.env

```
1. 安裝 [docker](https://www.docker.com/products/docker-desktop/)
2. 新增檔案`docker-compose.yml`
3. 新增資料夾`envs`，並新增3個檔案`app.env`、`lavalink.env`、`mssql.env`
4. 新增檔案`.env`
6. 設定`app.env`
### docker-compose.yml
```yaml
version: '3'
services:
  mssql:
    container_name: mssql
    # 測試是否有檔案，如果有檔案就代表已經設定完成
    healthcheck:
      test: ["CMD", "sh", "-c", "test -f /tmp/configure-db-finished"]
      interval: 5s
      timeout: 10s
      retries: 6
      start_period: 10s
    image: karylpudding/music-bot-mssql:latest
    restart: always
    env_file:
      - envs/mssql.env
    ports:
      - 0.0.0.0:${MSSQL_HOST_PORT}:1433
    networks:
      - mssql
    volumes:
      - ./data:/var/opt/mssql/data
  
  lavalink:
    image: fredboat/lavalink:439f122
    container_name: lavalink
    healthcheck:
      test: 'echo lavalink'
      interval: 10s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    volumes:
      - ./application.yml:/opt/Lavalink/application.yml
      - ./plugins/:/opt/Lavalink/plugins/
    networks:
      - lavalink
    expose:
      - ${LAVALINK_SERVER_PORT}
    ports:
      - "${LAVALINK_SERVER_PORT}:${LAVALINK_SERVER_PORT}"
    env_file:
      - ./envs/lavalink.env
    depends_on:
      mssql:
        condition: service_healthy

  app:
    container_name: app
    image: karylpudding/music-bot-app:latest
    restart: always
    env_file:
      - ./envs/app.env
    networks:
      - lavalink
      - mssql
    depends_on:
      lavalink:
        condition: service_healthy

networks:
  lavalink:
    name: lavalink

  mssql:
    name: mssql
```
### lavalink.env(請不要修改其參數)
```env
#JAVA環境啟動參數
_JAVA_OPTIONS=-Xmx6G
#伺服器port
SERVER_PORT=${LAVALINK_SERVER_PORT}
#密碼
LAVALINK_SERVER_PASSWORD=${LAVALINK_SERVER_PASSWORD}
```
### mssql.env(請不要修改其參數)
```env
#是否同意eula
ACCEPT_EULA=Y
#SA的密碼
MSSQL_SA_PASSWORD=Aa123456
```
### app.env
```env
# Discord Bot 應用程式ID
APPLICATION_ID=<your application id>
# Discord Bot Token
TOKEN=<your bot token>
# Discord Bot 管理伺服器ID
MANAGE_SERVER_ID=<your manage discord server id>
# Discord Bot 管理者User ID
MANAGE_USER_ID=<your manage user id>
# Spotify Client ID
SPOTIFY_CLIENT_ID=<your spotify client id>
# Spotify Client Secret
SPOTIFY_CLIENT_SECRET=<your spotify client secret>


# Lavalink Server IP(預設為docker image內的設定，如需本地啟動，請修改為localhost:2333)
WL_HOST=lavalink:${LAVALINK_SERVER_PORT}
# Lavalink Server 密碼(預設為docker image內的設定，如需本地啟動，請修改為youshallnotpass) 
WL_PASSWORD=${LAVALINK_SERVER_PASSWORD} 

# 資料庫連線字串設定
# 驅動器名稱(預設為docker image內的驅動器名稱，如需本地啟動，請修改為SQL Server)
DRIVER_NAME=ODBC Driver 17 for SQL Server
# 伺服器名稱(預設為docker image內的伺服器名稱，如需本地啟動，請修改為本地伺服器名稱)
# 請在ssms內->新增查詢->輸入查詢`select @@SERVERNAME`取得本地伺服器名稱 
SERVER_NAME=mssql
# 資料庫User(預設為sa)
DB_USER=sa
# 資料庫密碼(預設為Aa123456)
DB_PASSWORD=Aa123456  

# 資料庫設定
# -------------勿修改----------------
DB_NAME=discord_music_bot
TB_LATEST_VIDEO=latest_video
TB_YT_CHANNEL=yt_channel
TB_DC_SERVER=dc_server
TB_PLAYLIST=playlist
TB_PLAYLIST_SONG=playlist_song
# -------------勿修改----------------

# 宣傳內容(會出現在Bot名稱下面) {server_count} 會顯示該Bot所在伺服器數量
# 例如: "在 {server_count} 個伺服器上"
# 會顯示為 "在 10 個伺服器上"
# 如有多個宣傳內容，請用 , 分隔
ANNOUNCE_CONTENTS=<your announce contents>
# 宣傳間隔(秒)
ANNOUNCE_INTERVAL=300
# 新影片搜尋間隔(秒)
NOTIFICATION_INTERVAL=300
# 直播狀態刷新間隔(秒)
NOTIFICATION_REFRESH_LIVE_INTERVAL=10
```
### .env
```env
# MSSQL port
MSSQL_HOST_PORT=1957
#--------勿動--------
# lavalink服務port
LAVALINK_SERVER_PORT=2333
# lavalink密碼
LAVALINK_SERVER_PASSWORD=youshallnotpass
#--------勿動--------
```
7. 開啟終端機，前往至資料夾目錄底下`~/XXX`，輸入下列指令，啟動容器
```txt
docker compose up -d
```






