import json
import os
from discord.ext import commands
from discord import app_commands,Interaction, Object
from lib.common import ObjectEmbedView

with open('./config/settings.json', "r", encoding='utf-8') as f:
    settings = json.load(f)

class Manager(commands.GroupCog, name = 'admin', description = '管理指令'):
    def __init__(self, bot:commands.Bot):
        super().__init__()
        self.bot = bot

    @app_commands.command(name = "search", description = "查詢物件")
    async def search(self, interaction: Interaction, module: str, obj: str):
        await interaction.response.defer(ephemeral=True)
        embed_list = []
        if obj == "notification_channels":
            notification = interaction.client.get_cog(module).__dict__[obj]
            for (index, value) in enumerate(notification.values()):
                embed_list.append(value['obj'].toEmbed(index))
                for (number, guild) in enumerate(value['channels'].values()):
                    embed_list.append(guild['obj'].toEmbed(
                        self.bot, index, number))
        elif obj == "control_panels":
            control_panels = interaction.client.get_cog(module).__dict__[obj]
            for (index, (id, value)) in enumerate(control_panels.items()):
                embed_list.append(value.toEmbed(self.bot, id, index))
        elif obj == "watch_list":
            watch_list = interaction.client.get_cog(module).__dict__[obj]
            for (index, (title, value)) in enumerate(watch_list.items()):
                embed_list.append(value.toEmbed(index))

        if len(embed_list) != 0:
            await interaction.followup.send(embeds=embed_list[0:10], view=ObjectEmbedView(embed_list))
        else:
            await interaction.followup.send("None")

    @search.autocomplete('module')
    async def search_module_autocomplete_callback(self, interaction: Interaction, current: str):
        module_list = []
        for filename in os.listdir('./commands'):
            if filename.endswith('.py'):
                module_list.append(app_commands.Choice(name = f'{filename[:-3]}', value = f'{filename[:-3].capitalize()}'))
        return module_list

    @search.autocomplete('obj')
    async def search_obj_autocomplete_callback(self, interaction: Interaction, current: str):
        obj_list = [app_commands.Choice(name = 'notification_channels', value = 'notification_channels'),
                    app_commands.Choice(name = 'control_panels', value = 'control_panels'),
                    app_commands.Choice(name = 'watch_list', value = 'watch_list')]
        # for variable in interaction.client.get_cog(f"{interaction.namespace['module']}").__dict__.keys():
        #     if not variable.startswith("_"):
        #         obj_list.append(app_commands.Choice(name=f'{variable}', value=f'{variable}'))
        return obj_list

async def setup(bot: commands.Bot):
    await bot.add_cog(Manager(bot), guilds = [Object(id = settings['manage_server_id'])])
