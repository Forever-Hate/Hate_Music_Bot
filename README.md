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
- ~~[X] 顯示歌詞(僅支援spotify)~~
- [X] 訂閱youtube頻道追蹤最新影片、~~直播~~
- [ ] 訂閱twitch頻道追蹤直播

## 🔧技術
- [discord.py](https://github.com/Rapptz/discord.py)
- [docker](https://www.docker.com/)
- [python](https://www.python.org/)
- [wavelink](https://github.com/PythonistaGuild/Wavelink)

## 📖開始使用

### Docker(推薦)
如想要使用Docker版本，請查看 [這裡](https://github.com/Forever-Hate/Hate_Music_Bot_Docker)

### 本地

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
1. 下載本專案後，請打開終端機執行以下指令(請先確保本機具有python執行環境，以及執行目錄在本專案底下`~/Hate_Music_Bot`)
```
pip install --no-cache-dir -r requirements.txt
```
2. 請到 [discord develop portal](https://discord.com/developers/applications) 註冊一個應用程式(Bot)

3. 請下載安裝 [下載資料庫](https://www.microsoft.com/zh-tw/sql-server/sql-server-downloads) 及 [下載管理介面ssms](https://learn.microsoft.com/zh-tw/sql/ssms/download-sql-server-management-studio-ssms?view=sql-server-ver16) (已有sql server資料庫可跳過此步驟)
   <br>註:安裝過程中會設定sa的密碼，請務必記住

4. 開啟SSMS，建立資料庫與資料表(請先下載此專案的[Docker MSSQL Image](https://hub.docker.com/r/karylpudding/music-bot-mssql)，找到在image裡的`script.sql`)

5. 安裝 lavalink (請確保具有`jdk17 or 以上的執行環境`)
- 請到 [lavalink](https://github.com/lavalink-devs/Lavalink/releases) 下載`lavalink.jar`
- 新增檔案`application.yml`
- 新增檔案`start.bat`
### application.yml(如何取得 refreshToken 請參考 [這裡](https://github.com/Forever-Hate/Hate_Music_Bot_Docker?tab=readme-ov-file#%E5%A6%82%E4%BD%95%E5%8F%96%E5%BE%97-oauth-%E7%9A%84-refreshtoken))
```yaml
server: # REST and WS server
  port: 2333
  address: 0.0.0.0
  http2:
    enabled: false # Whether to enable HTTP/2 support

plugins:
  youtube:
    enabled: true
    allowSearch: true
    allowDirectVideoIds: true
    allowDirectPlaylistIds: true
    clients:
      - ANDROID_MUSIC
      - MUSIC
      - TVHTML5EMBEDDED
      - WEB
      - WEBEMBEDDED
    oauth:
      enabled: true
      #skipInitialization: true
      #refreshToken: "your refresh token"
    clientOptions:
      ANDROID_MUSIC:
        playback: false
        playlistLoading: false
        searching: false
        videoLoading: true
      MUSIC:
        playback: false
        playlistLoading: false
        searching: true
        videoLoading: false
      TVHTML5EMBEDDED:
        playback: true
        playlistLoading: false
        searching: false
        videoLoading: true
      WEB:
        playback: false
        playlistLoading: true
        searching: true
        videoLoading: false
      WEBEMBEDDED:
        playback: false
        playlistLoading: false
        searching: false
        videoLoading: false

  lavasrc:
    providers: # Custom providers for track loading. This is the default
      # - "dzisrc:%ISRC%" # Deezer ISRC provider
      # - "dzsearch:%QUERY%" # Deezer search provider
      - "ytsearch:\"%ISRC%\"" # Will be ignored if track does not have an ISRC. See https://en.wikipedia.org/wiki/International_Standard_Recording_Code
      - "ytsearch:%QUERY%" # Will be used if track has no ISRC or no track could be found for the ISRC
      #  you can add multiple other fallback sources here
    sources:
      spotify: true # Enable Spotify source
      applemusic: false # Enable Apple Music source
      deezer: false # Enable Deezer source
      yandexmusic: false # Enable Yandex Music source
      flowerytts: false # Enable Flowery TTS source
      youtube: false # Enable YouTube search source (https://github.com/topi314/LavaSearch)
    lyrics-sources:
      spotify: true # Enable Spotify lyrics source
      deezer: false # Enable Deezer lyrics source
      youtube: true # Enable YouTube lyrics source
      yandexmusic: false # Enable Yandex Music lyrics source
    spotify:
      clientId: "your spotify client id"
      clientSecret: "your spotify client secret"
      # spDc: "your sp dc cookie" # the sp dc cookie used for accessing the spotify lyrics api
      countryCode: "TW" # the country code you want to use for filtering the artists top tracks. See https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2
      playlistLoadLimit: 6 # The number of pages at 100 tracks each
      albumLoadLimit: 6 # The number of pages at 50 tracks each
      localFiles: false # Enable local files support with Spotify playlists. Please note `uri` & `isrc` will be `null` & `identifier` will be `"local"`
    applemusic:
      countryCode: "US" # the country code you want to use for filtering the artists top tracks and language. See https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2
      mediaAPIToken: "your apple music api token" # apple music api token
      # or specify an apple music key
      keyID: "your key id"
      teamID: "your team id"
      musicKitKey: |
        -----BEGIN PRIVATE KEY-----
        your key
        -----END PRIVATE KEY-----      
      playlistLoadLimit: 6 # The number of pages at 300 tracks each
      albumLoadLimit: 6 # The number of pages at 300 tracks each
    deezer:
      masterDecryptionKey: "your master decryption key" # the master key used for decrypting the deezer tracks. (yes this is not here you need to get it from somewhere else)
    yandexmusic:
      accessToken: "your access token" # the token used for accessing the yandex music api. See https://github.com/TopiSenpai/LavaSrc#yandex-music
      playlistLoadLimit: 1 # The number of pages at 100 tracks each
      albumLoadLimit: 1 # The number of pages at 50 tracks each
      artistLoadLimit: 1 # The number of pages at 10 tracks each
    flowerytts:
      voice: "default voice" # (case-sensitive) get default voice from here https://api.flowery.pw/v1/tts/voices
      translate: false # whether to translate the text to the native language of voice
      silence: 0 # the silence parameter is in milliseconds. Range is 0 to 10000. The default is 0.
      speed: 1.0 # the speed parameter is a float between 0.5 and 10. The default is 1.0. (0.5 is half speed, 2.0 is double speed, etc.)
      audioFormat: "mp3" # supported formats are: mp3, ogg_opus, ogg_vorbis, aac, wav, and flac. Default format is mp3
    youtube:
      countryCode: "TW" # the country code you want to use for searching lyrics via ISRC. See https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2

lavalink:
  plugins:
    - dependency: "dev.lavalink.youtube:youtube-plugin:1.11.1"
      snapshot: false 

    - dependency: "com.github.topi314.lavasrc:lavasrc-plugin:4.3.0"
      repository: "https://maven.lavalink.dev/releases" 
      snapshot: false 

#    - dependency: "com.github.example:example-plugin:1.0.0" # required, the coordinates of your plugin
#      repository: "https://maven.example.com/releases" # optional, defaults to the Lavalink releases repository by default
#      snapshot: false # optional, defaults to false, used to tell Lavalink to use the snapshot repository instead of the release repository
#  pluginsDir: "./plugins" # optional, defaults to "./plugins"
#  defaultPluginRepository: "https://maven.lavalink.dev/releases" # optional, defaults to the Lavalink release repository
#  defaultPluginSnapshotRepository: "https://maven.lavalink.dev/snapshots" # optional, defaults to the Lavalink snapshot repository
  server:
    password: "youshallnotpass"
    sources:
      # The default Youtube source is now deprecated and won't receive further updates. Please use https://github.com/lavalink-devs/youtube-source#plugin instead.
      youtube: false
      bandcamp: true
      soundcloud: true
      twitch: true
      vimeo: true
      nico: true
      http: true # warning: keeping HTTP enabled without a proxy configured could expose your server's IP address.
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
    resamplingQuality: LOW # Quality of resampling operations. Valid values are LOW, MEDIUM and HIGH, where HIGH uses the most CPU.
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

7. 開啟終端機，前往至專案目錄底下`~/Hate_Music_Bot`，輸入下列指令，開啟Bot
```txt
python main.py
```





