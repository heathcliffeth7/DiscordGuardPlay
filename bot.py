import discord
from discord.ext import commands
import openpyxl
import os
import asyncio
from datetime import timedelta

# Record function
def record_play(discord_id, discord_username, in_game_username, event_name):
    file_name = f"{event_name}_play_records.xlsx"
    if os.path.exists(file_name):
        workbook = openpyxl.load_workbook(file_name)
        sheet = workbook.active
    else:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(["Discord ID", "Discord Username", "In-Game Username"])
    sheet.append([discord_id, discord_username, in_game_username])
    workbook.save(file_name)

# Intent settings
intents = discord.Intents.default()
intents.members = True  # Required to receive member join events
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Global variables
events = {}
usage_counts = {}
event_nickname_counts = {}
event_nickname_limit = {}  # To store same nickname limits for events

# Security authorization
security_authorized_role_id = 1234567889   # Your server's Security Manager role ID
security_authorized_ids = set()

def is_security_authorized(ctx):
    if security_authorized_role_id in [role.id for role in ctx.author.roles]:
        return True
    if ctx.author.id in security_authorized_ids:
        return True
    for role in ctx.author.roles:
        if role.id in security_authorized_ids:
            return True
    return False

# Play Event authorization
play_authorized_role_id = 1325134141414  # Your server's Event Manager role ID
play_authorized_ids = set()

def is_play_authorized(ctx):
    if play_authorized_role_id in [role.id for role in ctx.author.roles]:
        return True
    if ctx.author.id in play_authorized_ids:
        return True
    for role in ctx.author.roles:
        if role.id in play_authorized_ids:
            return True
    return False

# Allowed role IDs for button usage
allowed_role_ids = [12314155125511255515151]   # Your server's designated role ID

# Global Security Filter Variables
no_avatar_filter_enabled = False
no_avatar_action = None
no_avatar_timeout_duration = None

account_age_filter_enabled = False
account_age_min_days = None
account_age_action = None
account_age_timeout_duration = None

# on_member_join event (Security Filters)
@bot.event
async def on_member_join(member):
    if no_avatar_filter_enabled:
        if member.avatar is None:
            try:
                if no_avatar_action == "ban":
                    await member.ban(reason="No avatar provided")
                elif no_avatar_action == "kick":
                    await member.kick(reason="No avatar provided")
                elif no_avatar_action == "timeout":
                    timeout_duration = timedelta(minutes=no_avatar_timeout_duration)
                    until = discord.utils.utcnow() + timeout_duration
                    await member.edit(timeout=until, reason="No avatar provided")
            except Exception as e:
                print("Error applying no-avatar filter:", e)
    if account_age_filter_enabled:
        account_age = (discord.utils.utcnow() - member.created_at).days
        if account_age < account_age_min_days:
            try:
                if account_age_action == "ban":
                    await member.ban(reason="Account age too low")
                elif account_age_action == "kick":
                    await member.kick(reason="Account age too low")
                elif account_age_action == "timeout":
                    timeout_duration = timedelta(minutes=account_age_timeout_duration)
                    until = discord.utils.utcnow() + timeout_duration
                    await member.edit(timeout=until, reason="Account age too low")
            except Exception as e:
                print("Error applying account age filter:", e)

# !noavatarfilter Command
@bot.command(name="noavatarfilter")
async def noavatarfilter_command(ctx, state: str, mode: str = None, duration: int = None):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    global no_avatar_filter_enabled, no_avatar_action, no_avatar_timeout_duration
    state = state.lower()
    if state == "on":
        no_avatar_filter_enabled = True
        if mode is not None:
            mode = mode.lower()
            if mode not in ["ban", "kick", "timeout"]:
                await ctx.send("Please provide a valid mode: ban, kick, or timeout")
                return
            no_avatar_action = mode
            if mode == "timeout":
                if duration is None:
                    await ctx.send("In timeout mode, please provide a timeout duration (in minutes).")
                    return
                no_avatar_timeout_duration = duration
        await ctx.send(f"No-avatar filter enabled. Mode: {no_avatar_action}" +
                       (f", Timeout: {no_avatar_timeout_duration} minutes" if no_avatar_action == "timeout" else ""))
    elif state == "off":
        no_avatar_filter_enabled = False
        await ctx.send("No-avatar filter disabled.")
    else:
        await ctx.send("Please type 'on' or 'off'.")

# !accountagefilter Command
@bot.command(name="accountagefilter")
async def accountagefilter_command(ctx, state: str, min_age: int = None, mode: str = None, duration: int = None):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    global account_age_filter_enabled, account_age_min_days, account_age_action, account_age_timeout_duration
    state = state.lower()
    if state == "off":
        account_age_filter_enabled = False
        await ctx.send("Account age filter disabled.")
        return
    elif state == "on":
        if min_age is None or mode is None:
            await ctx.send("Please provide a minimum account age (in days) and a mode. Example: `!accountagefilter on 7 timeout 60`")
            return
        account_age_filter_enabled = True
        account_age_min_days = min_age
        mode = mode.lower()
        if mode not in ["ban", "kick", "timeout"]:
            await ctx.send("Please provide a valid mode: ban, kick, or timeout")
            return
        account_age_action = mode
        if mode == "timeout":
            if duration is None:
                await ctx.send("In timeout mode, please provide a timeout duration (in minutes).")
                return
            account_age_timeout_duration = duration
            await ctx.send(f"Account age filter enabled: Accounts younger than {min_age} days will receive {duration} minutes timeout.")
        else:
            await ctx.send(f"Account age filter enabled: Accounts younger than {min_age} days will be {mode}ned.")
    else:
        await ctx.send("Please type 'on' or 'off'.")

# !samenicknamefilter Command
@bot.command(name="samenicknamefilter")
async def samenicknamefilter_command(ctx, event_name: str, state: str, limit: int = None):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    state = state.lower()
    if state == "off":
        event_nickname_limit.pop(event_name, None)
        await ctx.send(f"Same Nickname Filter disabled for {event_name}. Users can now enter the same nickname unlimited times.")
    elif state == "on":
        if limit is None:
            await ctx.send("Please provide a limit value. Example: `!samenicknamefilter Tournament2025 on 1`")
            return
        event_nickname_limit[event_name] = limit
        await ctx.send(f"Same Nickname Filter enabled for {event_name}. Each username can be entered a maximum of {limit} times.")
    else:
        await ctx.send("Please type 'on' or 'off'.")

# ---------------- Other Security Commands ----------------
@bot.command(name="securityauthorizedadd")
async def securityauthorizedadd(ctx, identifier: str):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    try:
        id_val = int(identifier.strip("<@&>"))
    except ValueError:
        await ctx.send("Please provide a valid user or role ID.")
        return
    security_authorized_ids.add(id_val)
    await ctx.send(f"{identifier} is now authorized to use security commands.")

@bot.command(name="securityauthorizedremove")
async def securityauthorizedremove(ctx, identifier: str):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    try:
        id_val = int(identifier.strip("<@&>"))
    except ValueError:
        await ctx.send("Please provide a valid user or role ID.")
        return
    if id_val in security_authorized_ids:
        security_authorized_ids.remove(id_val)
        await ctx.send(f"{identifier} has been removed from the security authorized list.")
    else:
        await ctx.send("The specified ID was not found in the security authorized list.")

@bot.command(name="securitysettings")
async def securitysettings(ctx):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    embed = discord.Embed(title="Security Settings", color=discord.Color.orange())
    noavatar_status = "Enabled" if no_avatar_filter_enabled else "Disabled"
    embed.add_field(name="No-Avatar Filter", value=f"Status: {noavatar_status}\nAction: {no_avatar_action}", inline=False)
    if no_avatar_action == "timeout" and no_avatar_filter_enabled:
        embed.add_field(name="No-Avatar Timeout", value=f"{no_avatar_timeout_duration} minutes", inline=False)
    accountage_status = "Enabled" if account_age_filter_enabled else "Disabled"
    embed.add_field(name="Account Age Filter", value=f"Status: {accountage_status}", inline=False)
    if account_age_filter_enabled:
        embed.add_field(name="Minimum Account Age", value=f"{account_age_min_days} days", inline=False)
        embed.add_field(name="Account Age Action", value=f"{account_age_action}", inline=False)
        if account_age_action == "timeout":
            embed.add_field(name="Account Age Timeout", value=f"{account_age_timeout_duration} minutes", inline=False)
    if security_authorized_ids:
        ids_str = ", ".join(str(i) for i in security_authorized_ids)
    else:
        ids_str = "None added"
    embed.add_field(name="Security Authorized IDs", value=ids_str, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="securityhelp")
async def securityhelp(ctx):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    help_text = (
        "**Security Commands Help Menu**\n\n"
        "1. **!noavatarfilter on [mode] [duration] / off**\n"
        "   - Description: Checks new members for an avatar. Mode options: `ban`, `kick`, `timeout`.\n"
        "   - Example: `!noavatarfilter on timeout 60` → Applies 60 minutes timeout to users without an avatar.\n\n"
        "2. **!accountagefilter on <min_days> <mode> [duration] / off**\n"
        "   - Description: Checks new members for account age. Mode options: `ban`, `kick`, `timeout`.\n"
        "   - Example: `!accountagefilter on 7 timeout 60` → Applies 60 minutes timeout to accounts younger than 7 days.\n\n"
        "3. **!securityauthorizedadd <id>**\n"
        "   - Description: Adds the provided user or role ID to the security authorized list.\n"
        "   - Example: `!securityauthorizedadd <@&123456789012345678>`\n\n"
        "4. **!securityauthorizedremove <id>**\n"
        "   - Description: Removes the provided user or role ID from the security authorized list.\n"
        "   - Example: `!securityauthorizedremove <@&123456789012345678>`\n\n"
        "5. **!playauthorizedremove <id>**\n"
        "   - Description: (For Play commands) Removes the provided user or role ID from the play authorized list.\n"
        "   - Example: `!playauthorizedremove <@&123456789012345678>`\n\n"
        "6. **!securitysettings**\n"
        "   - Description: Displays the current security settings (filter statuses, actions, timeout durations, etc.).\n\n"
        "7. **!securityhelp**\n"
        "   - Description: Shows this help menu.\n"
    )
    await ctx.send(help_text)

# ---------------- End of Security Section ------------------

# ---------------- Event (Play Event) Section ------------------
@bot.command(name="createplayevent")
async def createplayevent(ctx, event_name: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name in events:
        await ctx.send(f"{event_name} event already exists.")
        return
    events[event_name] = {
        "link": None,
        "channel_id": None,
        "excel_file": f"{event_name}_play_records.xlsx",
        "limits": {}
    }
    event_nickname_counts[event_name] = {}  # Initialize same nickname counter.
    await ctx.send(f"{event_name} event has been created.")

@bot.command(name="setplaylink")
async def setplaylink(ctx, event_name: str, link: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("Event not found. Please create it first with !createplayevent.")
        return
    events[event_name]["link"] = link
    await ctx.send(f"Event-specific link set for {event_name}: {link}")

@bot.command(name="setplaychannel")
async def setplaychannel(ctx, event_name: str, channel_input: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("Event not found. Please create it first with !createplayevent.")
        return
    try:
        channel_id = int(channel_input.strip("<#>"))
    except ValueError:
        await ctx.send("Please provide a valid channel ID or mention.")
        return
    channel = ctx.guild.get_channel(channel_id)
    if channel is None:
        await ctx.send("No channel found with the provided ID.")
        return
    events[event_name]["channel_id"] = channel.id
    await ctx.send(f"Channel for the event {event_name} has been set to: {channel.mention}")

@bot.command(name="setauthorizedrole")
async def setauthorizedrole(ctx, role_input: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    global authorized_role_id
    try:
        role_id = int(role_input.strip("<@&>"))
    except ValueError:
        await ctx.send("Please provide a valid role ID or mention.")
        return
    role = ctx.guild.get_role(role_id)
    if role is None:
        await ctx.send("No role found with the provided ID.")
        return
    authorized_role_id = role.id
    await ctx.send(f"Play event authorized role set to: {role.mention}")

@bot.command(name="setallowedrole")
async def setallowedrole(ctx, *, roles: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    global allowed_role_ids
    role_ids = []
    for role_str in roles.split(","):
        role_str = role_str.strip()
        if role_str.startswith("<@&") and role_str.endswith(">"):
            role_str = role_str[3:-1]
        try:
            role_id = int(role_str)
            role_ids.append(role_id)
        except ValueError:
            continue
    allowed_role_ids = role_ids
    await ctx.send(f"Roles required to use the button have been set: {allowed_role_ids}")

@bot.command(name="removeallowedrole")
async def removeallowedrole(ctx, *, roles: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    global allowed_role_ids
    removed = []
    for role_str in roles.split(","):
        role_str = role_str.strip()
        if role_str.startswith("<@&") and role_str.endswith(">"):
            role_str = role_str[3:-1]
        try:
            role_id = int(role_str)
            if role_id in allowed_role_ids:
                allowed_role_ids.remove(role_id)
                removed.append(role_id)
        except ValueError:
            continue
    if removed:
        await ctx.send(f"Allowed role(s) {removed} have been removed.")
    else:
        await ctx.send("The specified roles were not found in the allowed list.")

# ---------------- Play Event Modal ----------------
class PlayModal(discord.ui.Modal, title="Enter Your In-Game Username"):
    player = discord.ui.TextInput(
        label="In-Game Username",
        placeholder="Enter your in-game username",
        required=True
    )
    def __init__(self, event_name: str, *args, **kwargs):
        self.event_name = event_name
        self.processed = False  # Flag to prevent double submission.
        super().__init__(*args, **kwargs)
    async def on_submit(self, interaction: discord.Interaction):
        if self.processed:
            return
        self.processed = True
        nickname = self.player.value.strip()
        if not nickname:
            await interaction.response.send_message("Please enter a valid username.", ephemeral=True)
            return
        if self.event_name in event_nickname_limit:
            limit = event_nickname_limit[self.event_name]
            if self.event_name not in event_nickname_counts:
                event_nickname_counts[self.event_name] = {}
            count = event_nickname_counts[self.event_name].get(nickname, 0)
            if count >= limit:
                await interaction.response.send_message("You have exceeded the limit for this username, please use a different one.", ephemeral=True)
                return
            event_nickname_counts[self.event_name][nickname] = count + 1
        asyncio.create_task(asyncio.to_thread(record_play, interaction.user.id, interaction.user.name, nickname, self.event_name))
        key = (self.event_name, interaction.user.id)
        usage_counts[key] = usage_counts.get(key, 0) + 1
        ev = events.get(self.event_name, {})
        link = ev.get("link", "Link not set")
        await interaction.response.send_message(f"Hello {nickname}, here is the link: {link}", ephemeral=True)

# ---------------- Play Event View ----------------
class PlayView(discord.ui.View):
    def __init__(self, event_name: str, *, timeout=180):
        self.event_name = event_name
        super().__init__(timeout=timeout)
    @discord.ui.button(label="Play", style=discord.ButtonStyle.primary)
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        ev = events.get(self.event_name, {})
        if ev.get("channel_id") and interaction.channel.id != ev["channel_id"]:
            await interaction.response.send_message("This button cannot be used in this channel.", ephemeral=True)
            return
        if allowed_role_ids:
            user_role_ids = [role.id for role in interaction.user.roles]
            if not any(role_id in user_role_ids for role_id in allowed_role_ids):
                await interaction.response.send_message("You are not authorized to use this button.", ephemeral=True)
                return
        if "limits" in ev and ev["limits"]:
            limits = ev["limits"]
            user_role_ids = [role.id for role in interaction.user.roles]
            applicable_limits = [limits[rid] for rid in limits if rid in user_role_ids]
            if applicable_limits:
                min_limit = min(applicable_limits)
                key = (self.event_name, interaction.user.id)
                current = usage_counts.get(key, 0)
                if current >= min_limit:
                    await interaction.response.send_message("You have reached your interaction limit.", ephemeral=True)
                    return
        await interaction.response.send_modal(PlayModal(self.event_name))

@bot.command(name="sendplay")
async def sendplay(ctx, event_name: str, channel_id_input: str = None):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("Event not found. Please create it first with !createplayevent.")
        return
    if channel_id_input:
        try:
            channel_id = int(channel_id_input.strip("<#>"))
        except ValueError:
            await ctx.send("Please provide a valid channel ID.")
            return
        channel = ctx.guild.get_channel(channel_id)
        if channel is None:
            await ctx.send("No channel found with the provided ID.")
            return
        events[event_name]["channel_id"] = channel.id
    else:
        if not events[event_name].get("channel_id"):
            await ctx.send("No event-specific channel is set. Please use !setplaychannel or provide a channel ID.")
            return
        channel_id = events[event_name]["channel_id"]
        channel = ctx.guild.get_channel(channel_id)
    msg = await channel.send(f"Play button for {event_name} event:", view=PlayView(event_name))
    events[event_name]["message_id"] = msg.id
    await ctx.send(f"{event_name} event created. Button sent to channel: {channel.mention}")

@bot.command(name="sendplaylimit")
async def sendplaylimit(ctx, event_name: str, role_input: str, limit: int):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    try:
        role_id = int(role_input.strip("<@&>"))
    except ValueError:
        await ctx.send("Please provide a valid role ID or mention.")
        return
    if event_name not in events:
        await ctx.send("The specified event was not found.")
        return
    if "limits" not in events[event_name]:
        events[event_name]["limits"] = {}
    events[event_name]["limits"][role_id] = limit
    await ctx.send(f"Interaction limit for role <@&{role_id}> set to {limit} for event {event_name}.")

@bot.command(name="sendplaysettings")
async def sendplaysettings(ctx, event_name: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("The specified event was not found.")
        return
    ev = events[event_name]
    embed = discord.Embed(title=f"{event_name} Event Settings", color=discord.Color.green())
    embed.add_field(name="Link", value=ev.get("link", "Not set"), inline=False)
    if ev.get("channel_id"):
        channel = ctx.guild.get_channel(ev["channel_id"])
        embed.add_field(name="Channel", value=channel.mention if channel else "Unknown", inline=False)
    else:
        embed.add_field(name="Channel", value="Not set", inline=False)
    if ev.get("limits"):
        limits_str = "\n".join([f"<@&{rid}>: {limit}" for rid, limit in ev["limits"].items()])
    else:
        limits_str = "Not set"
    embed.add_field(name="Interaction Limits", value=limits_str, inline=False)
    excel = ev.get("excel_file", "Not specified")
    embed.add_field(name="Excel File", value=excel, inline=False)
    if event_name in event_nickname_limit:
        embed.add_field(name="Same Nickname Limit", value=f"{event_nickname_limit[event_name]} times", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="getplayexcel")
async def getplayexcel(ctx, event_name: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    file_name = f"{event_name}_play_records.xlsx"
    if not os.path.exists(file_name):
        await ctx.send("Excel file not found.")
        return
    await ctx.send(file=discord.File(file_name))

@bot.command(name="allplaylist")
async def allplaylist(ctx):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if not events:
        await ctx.send("No events found.")
        return
    event_names = "\n".join(events.keys())
    await ctx.send(f"List of created events:\n{event_names}")

@bot.command(name="deletesendplay")
async def deletesendplay(ctx, event_name: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("The specified event was not found.")
        return
    info = events.pop(event_name)
    if event_name in event_nickname_counts:
        event_nickname_counts.pop(event_name)
    channel = ctx.guild.get_channel(info.get("channel_id"))
    if channel:
        try:
            msg = await channel.fetch_message(info["message_id"])
            await msg.delete()
        except Exception:
            await ctx.send("Failed to delete event message.")
    file_name = info.get("excel_file")
    if file_name and os.path.exists(file_name):
        os.remove(file_name)
        await ctx.send(f"{event_name} event and Excel file deleted.")
    else:
        await ctx.send(f"{event_name} event deleted, Excel file not found.")

@bot.command(name="playhelp")
async def playhelp(ctx):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    embed = discord.Embed(
        title="Play Bot Help Menu - Detailed Guide",
        description=(
            "**Event Creation and Settings Management**\n"
            "With this bot, you can create different events (e.g., tournaments, competitions, etc.) in your server, "
            "set event-specific links, channels, interaction limits, same nickname limits, and maintain a record Excel file.\n\n"
            "**Commands and Example Usage:**\n\n"
            "1. **!createplayevent <eventname>**\n"
            "   - Description: Creates a new event.\n"
            "   - Example: `!createplayevent Tournament2025`\n\n"
            "2. **!setplaylink <eventname> <link>**\n"
            "   - Description: Sets the link to be sent for the event.\n"
            "   - Example: `!setplaylink Tournament2025 https://example.com/tournament`\n\n"
            "3. **!setplaychannel <eventname> <channelid>**\n"
            "   - Description: Sets the channel where the event's button will be sent.\n"
            "   - Example: `!setplaychannel Tournament2025 123456789012345678` or `!setplaychannel Tournament2025 <#123456789012345678>`\n\n"
            "4. **!setauthorizedrole <roleID or @role>**\n"
            "   - Description: Sets the base authorized role for using play event commands.\n"
            "   - Example: `!setauthorizedrole 987654321098765432` or `!setauthorizedrole <@&987654321098765432>`\n\n"
            "5. **!setallowedrole <roleID1,roleID2,...>**\n"
            "   - Description: Specifies which roles are allowed to use the button.\n"
            "   - Example: `!setallowedrole 112233445566778899,223344556677889900`\n\n"
            "6. **!removeallowedrole <roleID1,roleID2,...>**\n"
            "   - Description: Removes the specified allowed roles.\n"
            "   - Example: `!removeallowedrole 112233445566778899`\n\n"
            "7. **!samenicknamefilter <eventname> on <limit> / off**\n"
            "   - Description: Sets the maximum number of times the same in-game username can be entered in the specified event.\n"
            "   - Example: `!samenicknamefilter Tournament2025 on 1` → In this event, each username can only be entered once.\n"
            "             `!samenicknamefilter Tournament2025 on 2` → The same username can be entered twice.\n"
            "             `!samenicknamefilter Tournament2025 off` → Filter disabled, users can enter the same username unlimited times.\n\n"
            "8. **!sendplay <eventname> [channelid]**\n"
            "   - Description: Sends a 'Play' message with a button for the event. If the event's channel is not set, it can be updated with a provided channel ID.\n"
            "   - Example: `!sendplay Tournament2025 <#123456789012345678>` or `!sendplay Tournament2025`\n\n"
            "9. **!sendplaylimit <eventname> <roleID or @role> <limit>**\n"
            "   - Description: Sets the interaction limit for users with the specified role for the event.\n"
            "   - Example: `!sendplaylimit Tournament2025 <@&112233445566778899> 3`\n\n"
            "10. **!sendplaysettings <eventname>**\n"
            "    - Description: Shows all settings for the event (link, channel, limits, same nickname limit, Excel file) in detail.\n"
            "    - Example: `!sendplaysettings Tournament2025`\n\n"
            "11. **!getplayexcel <eventname>**\n"
            "    - Description: Sends the Excel file where the event records are maintained.\n"
            "    - Example: `!getplayexcel Tournament2025`\n\n"
            "12. **!allplaylist**\n"
            "    - Description: Lists all created event names.\n"
            "    - Example: `!allplaylist`\n\n"
            "13. **!deletesendplay <eventname>**\n"
            "    - Description: Deletes the specified event and its associated Excel file.\n"
            "    - Example: `!deletesendplay Tournament2025`\n\n"
            "14. **!securityauthorizedremove <id>** / **!playauthorizedremove <id>**\n"
            "    - Description: Removes the provided user or role ID from the security or play authorized list.\n"
            "    - Example: `!securityauthorizedremove <@&123456789012345678>` or `!playauthorizedremove <@&123456789012345678>`\n\n"
            "Note: All these commands can only be used by authorized users. Unauthorized users will have their command messages automatically deleted."
        ),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

bot.run("BOTTOKENHERE")
