IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'discord_music_bot')
BEGIN
    CREATE DATABASE discord_music_bot;
END
GO
USE [discord_music_bot]
GO
/****** 新增資料表dc_server ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'dc_server' AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[dc_server](
        [id] [int] NOT NULL,
        [server_id] [varchar](200) NOT NULL,
        [text_id] [varchar](200) NOT NULL,
        [voice_id] [varchar](200) NOT NULL,
     CONSTRAINT [PK_dc_server] PRIMARY KEY CLUSTERED 
    (
        [id] ASC,
        [server_id] ASC
    )WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
    ) ON [PRIMARY]
END
GO
/****** 新增資料表latest_video ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'latest_video' AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[latest_video](
        [id] [int] NOT NULL,
        [video_url] [varchar](1000) NOT NULL,
     CONSTRAINT [PK_latest_video] PRIMARY KEY CLUSTERED 
    (
        [id] ASC
    )WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
    ) ON [PRIMARY]
END
GO
/****** 新增資料表playlist ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'playlist' AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[playlist](
        [id] [int] IDENTITY(1,1) NOT NULL,
        [playlist_title] [nvarchar](1000) NOT NULL,
        [user] [varchar](50) NOT NULL,
     CONSTRAINT [PK_playlist] PRIMARY KEY CLUSTERED 
    (
        [id] ASC
    )WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
    ) ON [PRIMARY]
END
GO
/****** 新增資料表 playlist_song ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'playlist_song' AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[playlist_song](
        [id] [int] NOT NULL,
        [no] [int] NOT NULL,
        [song_url] [nvarchar](1000) NOT NULL,
        [user] [varchar](50) NOT NULL,
     CONSTRAINT [PK_playlist_song] PRIMARY KEY CLUSTERED 
    (
        [id] ASC,
        [no] ASC
    )WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
    ) ON [PRIMARY]
END
GO
/****** 新增資料表yt_channel ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'yt_channel' AND type = 'U')
BEGIN
    CREATE TABLE [dbo].[yt_channel](
        [id] [int] IDENTITY(1,1) NOT NULL,
        [channel_id] [varchar](200) NOT NULL,
        [title] [nvarchar](200) NOT NULL,
        [thumbnail] [varchar](1000) NOT NULL,
        [type] [varchar](20) NOT NULL,
     CONSTRAINT [PK_yt_channel] PRIMARY KEY CLUSTERED 
    (
        [id] ASC
    )WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
    ) ON [PRIMARY]
END
GO
/****** 新增索引 ******/
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE object_id = OBJECT_ID(N'[dbo].[FK_yt_id]') AND parent_object_id = OBJECT_ID(N'[dbo].[dc_server]'))
BEGIN
    ALTER TABLE [dbo].[dc_server]  WITH CHECK ADD  CONSTRAINT [FK_yt_id] FOREIGN KEY([id])
    REFERENCES [dbo].[yt_channel] ([id])
    ON UPDATE CASCADE
    ON DELETE CASCADE
END
GO
/****** 新增索引 ******/
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE object_id = OBJECT_ID(N'[dbo].[latest_video_ibfk_1]') AND parent_object_id = OBJECT_ID(N'[dbo].[latest_video]'))
BEGIN
    ALTER TABLE [dbo].[latest_video]  WITH CHECK ADD  CONSTRAINT [latest_video_ibfk_1] FOREIGN KEY([id])
    REFERENCES [dbo].[yt_channel] ([id])
    ON UPDATE CASCADE
    ON DELETE CASCADE
END
GO
/****** 新增索引 ******/
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE object_id = OBJECT_ID(N'[dbo].[FK_id]') AND parent_object_id = OBJECT_ID(N'[dbo].[playlist_song]'))
BEGIN
    ALTER TABLE [dbo].[playlist_song]  WITH CHECK ADD  CONSTRAINT [FK_id] FOREIGN KEY([id])
    REFERENCES [dbo].[playlist] ([id])
    ON UPDATE CASCADE
    ON DELETE CASCADE
END
GO
