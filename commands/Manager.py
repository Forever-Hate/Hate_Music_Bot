import os
from discord.ext import commands
from discord import app_commands,Interaction, Object
from lib.common import ObjectEmbedView

MANAGE_SERVER_ID = os.getenv('MANAGE_SERVER_ID')

class Manager(commands.GroupCog, name = 'admin', description = '管理指令'):
    def __init__(self, bot:commands.Bot):
        super().__init__()
        self.bot = bot

    @app_commands.command(name = "search", description = "查詢物件")
    async def search(self, interaction: Interaction, module: str, obj: str):
        await interaction.response.defer(ephemeral=True)
        embed_list = []

        cog = self.bot.get_cog(module).__dict__[obj]

        if obj == "notification_channels":
            for index, value in enumerate(cog.values()):
                embed_list.append(value['obj'].toEmbed(index))
                for number, guild in enumerate(value['channels'].values()):
                    embed_list.append(guild['obj'].toEmbed(self.bot, index, number))
        elif obj == "control_panels":
            for index, (id, value) in enumerate(cog.items()):
                embed_list.append(value.toEmbed(self.bot, id, index))
        elif obj == "watch_list":
            for index, (title, value) in enumerate(cog.items()):
                embed_list.append(value.toEmbed(index))

        if embed_list:
            await interaction.followup.send(embeds=embed_list[:10], view=ObjectEmbedView(embed_list))
        else:
            await interaction.followup.send("None")

    @search.autocomplete('module')
    async def search_module_autocomplete_callback(self, interaction: Interaction, current: str):
        module_list = []
        module_list.append(app_commands.Choice(name = f'Music', value = f'Music'))
        return module_list

    @search.autocomplete('obj')
    async def search_obj_autocomplete_callback(self, interaction: Interaction, current: str):
        obj_list = [app_commands.Choice(name = 'notification_channels', value = 'notification_channels'),
                    app_commands.Choice(name = 'control_panels', value = 'control_panels'),
                    app_commands.Choice(name = 'watch_list', value = 'watch_list')]
        return obj_list

async def setup(bot: commands.Bot):
    await bot.add_cog(Manager(bot), guilds = [Object(id = MANAGE_SERVER_ID)])
