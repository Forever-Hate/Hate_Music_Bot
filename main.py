import discord
import json
import os
import aiohttp
from discord.ext import commands

with open('./config/settings.json',"r",encoding='utf-8') as f:
    settings = json.load(f)

class client(commands.Bot):
    def __init__(self,**options):
        super().__init__(
            command_prefix="!",
            intents = discord.Intents.all(),
            application_id = settings['application_id'],
            **options
        )
    
    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        for filename in os.listdir('./commands'):
            if filename.endswith('.py'):
                await bot.load_extension(f'commands.{filename[:-3]}')
            await bot.tree.sync() #guild = discord.Object(id = 469507920808116234) #目前所有指令皆為全域指令(非特定伺服器)


    async def on_ready(self):
        print('Music bot已上線 上線ID為:{0.user}'.format(bot))

    @commands.command()
    async def load(self,ctx,extension):
        bot.load_extension(f'commands.{extension}')
        await ctx.send(f'讀入{extension}完成')

    @commands.command()
    async def unload(self,ctx,extension):
        bot.unload_extension(f'commands.{extension}')
        await ctx.send(f'卸載{extension}完成')

    @commands.command()
    async def reload(self,ctx,extension):
        bot.reload_extension(f'commands.{extension}')
        await ctx.send(f'重新讀入{extension}完成')



#bot = commands.Bot(command_prefix=settings['prefix'])
bot = client()
if __name__ == "__main__":
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
