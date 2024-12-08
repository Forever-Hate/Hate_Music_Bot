import aiohttp
from discord.ext import commands,tasks
from discord import Activity, ActivityType, Intents
from dotenv import load_dotenv
import os
from os.path import dirname, realpath, join

load_dotenv() #讀取.env檔案
APPLICATION_ID = os.getenv('APPLICATION_ID')
TOKEN = os.getenv('TOKEN')
ANNOUNCE_INTERVAL = int(os.getenv('ANNOUNCE_INTERVAL'))
ANNOUNCE_CONTENTS = os.getenv('ANNOUNCE_CONTENTS').split(',')

class client(commands.Bot):
    def __init__(self,**options):
        self.index = -1
        super().__init__(
            command_prefix = "-",
            intents = Intents.all(),
            application_id = APPLICATION_ID,
            **options
        )
    
    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        # 獲取當前檔案的目錄
        current_dir = dirname(realpath(__file__))
        # 建立 commands 目錄的路徑
        commands_dir = join(current_dir, 'commands')
        
        for filename in os.listdir(commands_dir):
            if filename.endswith('.py'):
                await bot.load_extension(f'commands.{filename[:-3]}')


    async def on_ready(self):
        print('Music bot已上線 上線ID為:{0.user}'.format(bot))
        if not self.change_announcement.is_running():
            self.change_announcement.start()
        
    @tasks.loop(seconds = ANNOUNCE_INTERVAL)
    async def change_announcement(self):
        if len(ANNOUNCE_CONTENTS) == 0:
            activities = Activity(type = ActivityType.playing, name = "")
        else:
            self.index += 1
            if self.index == len(ANNOUNCE_CONTENTS):
                self.index = 0        
            activities = Activity(type = ActivityType.playing, name = ANNOUNCE_CONTENTS[self.index].format(server_count = len(bot.guilds)))
        await bot.change_presence(activity = activities)

    # @app_commands.command(name = "load", description="載入插件")
    # @app_commands.guilds(Object(id = 469507920808116234))
    # async def load(self,interaction:Interaction,extension:str):
    #     bot.load_extension(f'commands.{extension}')
    #     await interaction.response.send_message(f'讀入{extension}完成',ephemeral=True)

    # @app_commands.command(name = "unload", description="卸載插件")
    # @app_commands.guilds(Object(id = 469507920808116234))
    # async def unload(self,interaction:Interaction,extension:str):
    #     bot.unload_extension(f'commands.{extension}')
    #     await interaction.response.send_message(f'卸載{extension}完成',ephemeral=True)

    # @app_commands.command(name = "reload", description="重新讀取插件")
    # @app_commands.guilds(Object(id = 469507920808116234))
    # async def reload(self,interaction:Interaction,extension:str):
    #     bot.reload_extension(f'commands.{extension}')
    #     await interaction.response.send_message(f'重新讀入{extension}完成',ephemeral=True)

if __name__ == "__main__":
   bot = client()
   bot.run(TOKEN)
