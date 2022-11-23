import datetime
import os
import json
from discord.ext import commands
from discord import ButtonStyle, Interaction, app_commands,Object
from discord.ui import Button
import commands.Music as Music

with open('./config/settings.json',"r",encoding='utf-8') as f:
    settings = json.load(f)

class ObjectEmbedView(Music.CustomView):

    def __init__(self,embed_list):
        super().__init__(timeout = None)
        self.embed_list = embed_list
        self.start = 0
        self.end = 10
        self.add_base_button()
    
    async def next(self,interaction:Interaction):
        await interaction.response.defer(ephemeral=True)
        self.start += int(interaction.data.get('custom_id'))
        self.end += int(interaction.data.get('custom_id'))
        self.ui_control()
        await interaction.followup.edit_message(interaction.message.id,embeds = self.embed_list[self.start:self.end],view=self)

    def add_base_button(self):
        self.add(Button(style = ButtonStyle.green,label = "上十項",emoji="⏮️",custom_id="-10"),self.next)
        self.add(Button(style = ButtonStyle.green,label = "下十項",emoji="⏭️",custom_id="10"),self.next)
        self.ui_control()

    def ui_control(self):
        self.children[0].disabled = False
        self.children[1].disabled = False
        if self.start == 0:
            self.children[0].disabled = True
        if len(self.embed_list) <= self.end:
            self.children[1].disabled = True

class Manager(commands.GroupCog,name='admin',description='管理指令'):
    def __init__(self,bot):
        self.bot = bot
        super().__init__()
    
    @app_commands.command(name = "search", description="查詢物件")
    async def search(self,interaction: Interaction,module:str,obj:str):
        await interaction.response.defer(ephemeral=True)
        embed_list = []
        if obj == "notification_channels":
           notification = interaction.client.get_cog(module).__dict__[obj]
           for (index,value) in enumerate(notification.values()):
            embed_list.append(value['obj'].toEmbed(index))
            for (number,guild) in enumerate(value['channels'].values()):
                embed_list.append(guild['obj'].toEmbed(self.bot,index,number))
        elif obj == "control_panels":
            control_panels = interaction.client.get_cog(module).__dict__[obj]
            for (index,(id,value)) in enumerate(control_panels.items()):
                embed_list.append(value.toEmbed(self.bot,id,index))
        elif obj == "watch_list":
            watch_list = interaction.client.get_cog(module).__dict__[obj]
            for (index,(title,value)) in enumerate(watch_list.items()):
                embed_list.append(value.toEmbed(index))
            

        if len(embed_list) != 0:
            await interaction.followup.send(embeds=embed_list[0:10],view=ObjectEmbedView(embed_list))
        else:
            await interaction.followup.send("None")
        
    @search.autocomplete('module')
    async def search_module_autocomplete_callback(self,interaction:Interaction, current: str):
        module_list = []
        for filename in os.listdir('./commands'):
            if filename.endswith('.py'):
                module_list.append(app_commands.Choice(name=f'{filename[:-3]}', value=f'{filename[:-3]}'))
        return module_list

    @search.autocomplete('obj')
    async def search_obj_autocomplete_callback(self,interaction:Interaction, current: str):
        obj_list = [app_commands.Choice(name = 'notification_channels', value = 'notification_channels'),
                    app_commands.Choice(name = 'control_panels', value = 'control_panels'),
                    app_commands.Choice(name = 'watch_list', value = 'watch_list')]
        # for variable in interaction.client.get_cog(f"{interaction.namespace['module']}").__dict__.keys():
        #     if not variable.startswith("_"):
        #         obj_list.append(app_commands.Choice(name=f'{variable}', value=f'{variable}'))
        return obj_list 

async def setup(bot:commands.Bot):
    await bot.add_cog(Manager(bot),guilds = [Object(id = settings['manage_server_id'])])