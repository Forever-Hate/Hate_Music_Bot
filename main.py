import aiohttp
from discord.ext import commands,tasks
from discord import Activity, ActivityType, Intents
import json
import os

with open('./config/settings.json',"r",encoding = 'utf-8') as f:
    settings = json.load(f)

class client(commands.Bot):
    def __init__(self,**options):
        self.index = -1
        super().__init__(
            command_prefix = "-",
            intents = Intents.all(),
            application_id = settings['application_id'],
            **options
        )
    
    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        for filename in os.listdir('./commands'):
            if filename.endswith('.py'):
                await bot.load_extension(f'commands.{filename[:-3]}')


    async def on_ready(self):
        print('Music bot已上線 上線ID為:{0.user}'.format(bot))
        if not self.change_announcement.is_running():
            self.change_announcement.start()
        
    @tasks.loop(seconds = settings['announcement']['interval'])
    async def change_announcement(self):
        self.index += 1
        if self.index == len(settings['announcement']['contents']):
            self.index = 0
        activities = Activity(type = ActivityType.playing, name = settings['announcement']['contents'][self.index].format(server_count = len(bot.guilds)))
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
   bot.run(settings['token'])





#@bot.command() #指令修飾詞
#async def play(ctx): #方法名稱即為指令 輸入指令後傳入discord.ext.commands.context.Context 物件
    #print(ctx)
    #await ctx.send("play")

#@bot.command() 
#async def ping(ctx): 
    #await ctx.send(f'延遲:{round(bot.latency*1000)}(ms)')

#@bot.command()
#async def 貓咪(ctx):
    #pic = discord.File('C:/Users/minec/Desktop/Music_bot/photo/cat.jpg') #透過discord.File()讀取檔案，讓send()傳送
    #await ctx.send(file = pic)
