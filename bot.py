import discord
from discord.ext import commands
import openpyxl
import os
import asyncio
from datetime import timedelta

# Record function: Adds or updates a record in the Excel file.
# The discord_id is converted to a string to prevent scientific notation.
def record_play(discord_id, discord_username, in_game_username, event_name):
    file_name = f"{event_name}_play_records.xlsx"
    if os.path.exists(file_name):
        workbook = openpyxl.load_workbook(file_name)
        sheet = workbook.active
        
        # Check if user already exists in the sheet
        user_row = None
        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if str(row[0]) == str(discord_id):
                user_row = row_idx
                break
        
        if user_row:
            # Update existing record
            sheet.cell(row=user_row, column=1, value=str(discord_id))
            sheet.cell(row=user_row, column=2, value=discord_username)
            sheet.cell(row=user_row, column=3, value=in_game_username)
        else:
            # Add new record
            sheet.append([str(discord_id), discord_username, in_game_username])
    else:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(["Discord ID", "Discord Username", "In-Game Username"])
        # Save the discord_id as a string.
        sheet.append([str(discord_id), discord_username, in_game_username])
    
    workbook.save(file_name)

# Intent settings
intents = discord.Intents.default()
intents.members = True  # Required for member join events
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Global variables
events = {}
usage_counts = {}
event_nickname_counts = {}
event_nickname_limit = {}  # For same nickname limit

# Security Authorization
security_authorized_role_id = 1234567889   # Your security manager role ID
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

# Play Event Authorization
play_authorized_role_id = 1325134141414  # Your event manager role ID
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

# Role IDs allowed to use the button
allowed_role_ids = [12314155125511255515151]   # The role ID defined for button usage

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
                print("No-avatar filter error:", e)
    if account_age_filter_enabled:
        account_age = (discord.utils.utcnow() - member.created_at).days
        if account_age < account_age_min_days:
            try:
                if account_age_action == "ban":
                    await member.ban(reason="Account age insufficient")
                elif account_age_action == "kick":
                    await member.kick(reason="Account age insufficient")
                elif account_age_action == "timeout":
                    timeout_duration = timedelta(minutes=account_age_timeout_duration)
                    until = discord.utils.utcnow() + timeout_duration
                    await member.edit(timeout=until, reason="Account age insufficient")
            except Exception as e:
                print("Account age filter error:", e)

# !noavatarfilter command
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
                await ctx.send("Please enter a valid mode: ban, kick or timeout")
                return
            no_avatar_action = mode
            if mode == "timeout":
                if duration is None:
                    await ctx.send("In timeout mode, please specify a duration (in minutes).")
                    return
                no_avatar_timeout_duration = duration
        await ctx.send(f"No-avatar filter enabled. Mode: {no_avatar_action}" +
                       (f", Timeout: {no_avatar_timeout_duration} minutes" if no_avatar_action == "timeout" else ""))
    elif state == "off":
        no_avatar_filter_enabled = False
        await ctx.send("No-avatar filter disabled.")
    else:
        await ctx.send("Please type 'on' or 'off'.")

# !accountagefilter command
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
            await ctx.send("Please specify the minimum account age (in days) and a mode. Example: `!accountagefilter on 7 timeout 60`")
            return
        account_age_filter_enabled = True
        account_age_min_days = min_age
        mode = mode.lower()
        if mode not in ["ban", "kick", "timeout"]:
            await ctx.send("Please enter a valid mode: ban, kick or timeout")
            return
        account_age_action = mode
        if mode == "timeout":
            if duration is None:
                await ctx.send("In timeout mode, please specify a duration (in minutes).")
                return
            account_age_timeout_duration = duration
            await ctx.send(f"Account age filter enabled: Accounts younger than {min_age} days will be timed out for {duration} minutes.")
        else:
            await ctx.send(f"Account age filter enabled: Accounts younger than {min_age} days will be {mode}ned.")
    else:
        await ctx.send("Please type 'on' or 'off'.")

# !samenicknamefilter command
@bot.command(name="samenicknamefilter")
async def samenicknamefilter_command(ctx, event_name: str, state: str, limit: int = None):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    state = state.lower()
    if state == "off":
        event_nickname_limit.pop(event_name, None)
        await ctx.send(f"Same nickname filter for {event_name} disabled. Users can now enter unlimited entries.")
    elif state == "on":
        if limit is None:
            await ctx.send("Please provide a limit value. Example: `!samenicknamefilter Tournament2025 on 1`")
            return
        event_nickname_limit[event_name] = limit
        await ctx.send(f"Same nickname filter enabled for {event_name}. Each user can enter {limit} times.")
    else:
        await ctx.send("Please type 'on' or 'off'.")

# ---------------- Security Commands ----------------
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
    await ctx.send(f"{identifier} is now authorized for security commands.")

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
        ids_str = "No authorized IDs added"
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
        "   - Example: `!noavatarfilter on timeout 60` → Applies a 60-minute timeout to users without an avatar.\n\n"
        "2. **!accountagefilter on <min_days> <mode> [duration] / off**\n"
        "   - Description: Checks new members for account age. Mode options: `ban`, `kick`, `timeout`.\n"
        "   - Example: `!accountagefilter on 7 timeout 60` → Applies a 60-minute timeout to accounts younger than 7 days.\n\n"
        "3. **!securityauthorizedadd <id>**\n"
        "   - Description: Authorizes the specified user or role ID for security commands.\n\n"
        "4. **!securityauthorizedremove <id>**\n"
        "   - Description: Removes the specified user or role ID from the security authorized list.\n\n"
        "5. **!securitysettings**\n"
        "   - Description: Displays current security settings (filter statuses, actions, timeout durations, etc.).\n\n"
        "6. **!securityhelp**\n"
        "   - Description: Shows this help menu.\n"
    )
    await ctx.send(help_text)

# ---------------- Play Event Section ----------------
@bot.command(name="createplayevent")
async def createplayevent(ctx, event_name: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name in events:
        await ctx.send(f"{event_name} event already exists. Recreating with the same name will reset usage counts.")
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
        await ctx.send("Please create the event first using !createplayevent.")
        return
    events[event_name]["link"] = link
    await ctx.send(f"Link set for {event_name} event: {link}")

@bot.command(name="setplaychannel")
async def setplaychannel(ctx, event_name: str, channel_input: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("Please create the event first using !createplayevent.")
        return
    try:
        channel_id = int(channel_input.strip("<#>"))
    except ValueError:
        await ctx.send("Please provide a valid channel ID or channel mention.")
        return
    channel = ctx.guild.get_channel(channel_id)
    if channel is None:
        await ctx.send("No channel found with the provided ID.")
        return
    events[event_name]["channel_id"] = channel.id
    await ctx.send(f"Channel set for {event_name} event: {channel.mention}")

@bot.command(name="setauthorizedrole")
async def setauthorizedrole(ctx, role_input: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    global authorized_role_id
    try:
        role_id = int(role_input.strip("<@&>"))
    except ValueError:
        await ctx.send("Please provide a valid role ID or role mention.")
        return
    role = ctx.guild.get_role(role_id)
    if role is None:
        await ctx.send("No role found with the provided ID.")
        return
    authorized_role_id = role.id
    await ctx.send(f"Authorized role for play event commands set to: {role.mention}")

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
    await ctx.send(f"Roles allowed for button usage set to: {allowed_role_ids}")

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
        await ctx.send(f"Removed roles: {removed}")
    else:
        await ctx.send("The specified roles were not found in the allowed list.")

# New command: !removeplaybutton – Removes the Play button message for the specified event.
@bot.command(name="removeplaybutton")
async def removeplaybutton(ctx, event_name: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("Specified event not found.")
        return
    if "message_id" not in events[event_name] or "channel_id" not in events[event_name]:
        await ctx.send("No button message found for this event.")
        return
    channel = ctx.guild.get_channel(events[event_name]["channel_id"])
    if channel is None:
        await ctx.send("Channel not found.")
        return
    try:
        msg = await channel.fetch_message(events[event_name]["message_id"])
        await msg.delete()
        await ctx.send(f"Play button for {event_name} event has been removed.")
    except Exception as e:
        await ctx.send(f"Failed to remove button: {e}")

@bot.command(name="sendplay")
async def sendplay(ctx, event_name: str, channel_input: str = None):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("Please create the event first using !createplayevent.")
        return
    if channel_input:
        try:
            channel_id = int(channel_input.strip("<#>"))
        except ValueError:
            await ctx.send("Please provide a valid channel ID or channel mention.")
            return
        channel = ctx.guild.get_channel(channel_id)
    else:
        if events[event_name]["channel_id"] is None:
            await ctx.send("No channel set for this event. Please use !setplaychannel or provide a channel.")
            return
        channel = ctx.guild.get_channel(events[event_name]["channel_id"])
    if channel is None:
        await ctx.send("Channel not found.")
        return
    if events[event_name]["link"] is None:
        await ctx.send("No link set for this event. Please use !setplaylink first.")
        return
    view = discord.ui.View()
    button = discord.ui.Button(label="Play", style=discord.ButtonStyle.green)
    async def button_callback(interaction):
        user = interaction.user
        user_roles = [role.id for role in user.roles]
        if not any(role_id in allowed_role_ids for role_id in user_roles):
            await interaction.response.send_message("You don't have permission to use this button.", ephemeral=True)
            return
        key = (event_name, user.id)
        if key in usage_counts:
            usage_counts[key] += 1
        else:
            usage_counts[key] = 1
        limit_exceeded = False
        for role_id, limit in events[event_name].get("limits", {}).items():
            if role_id in user_roles and usage_counts[key] > limit:
                limit_exceeded = True
                break
        if limit_exceeded:
            await interaction.response.send_message(f"You've reached your interaction limit for {event_name}.", ephemeral=True)
            return
        modal = discord.ui.Modal(title=f"Enter your in-game username for {event_name}")
        username_input = discord.ui.TextInput(
            label="In-Game Username",
            placeholder="Enter your in-game username here...",
            required=True
        )
        modal.add_item(username_input)
        async def modal_submit(modal_interaction):
            in_game_username = username_input.value
            if event_name in event_nickname_limit:
                limit = event_nickname_limit[event_name]
                if event_name not in event_nickname_counts:
                    event_nickname_counts[event_name] = {}
                if in_game_username in event_nickname_counts[event_name]:
                    event_nickname_counts[event_name][in_game_username] += 1
                else:
                    event_nickname_counts[event_name][in_game_username] = 1
                if event_nickname_counts[event_name][in_game_username] > limit:
                    await modal_interaction.response.send_message(f"The in-game username '{in_game_username}' has reached its limit for {event_name}.", ephemeral=True)
                    return
            record_play(user.id, user.name, in_game_username, event_name)
            await modal_interaction.response.send_message(f"Your in-game username '{in_game_username}' has been recorded for {event_name}. You can now access the event at {events[event_name]['link']}", ephemeral=True)
        modal.on_submit = modal_submit
        await interaction.response.send_modal(modal)
    button.callback = button_callback
    view.add_item(button)
    message = await channel.send(f"Click the button below to participate in {event_name}:", view=view)
    events[event_name]["message_id"] = message.id
    await ctx.send(f"{event_name} event created. Button sent to {channel.mention} channel.")

@bot.command(name="sendplaylimit")
async def sendplaylimit(ctx, event_name: str, role_input: str, limit: int):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    try:
        role_id = int(role_input.strip("<@&>"))
    except ValueError:
        await ctx.send("Please provide a valid role ID or role mention.")
        return
    if event_name not in events:
        await ctx.send("Specified event not found.")
        return
    if "limits" not in events[event_name]:
        events[event_name]["limits"] = {}
    events[event_name]["limits"][role_id] = limit
    await ctx.send(f"Interaction limit for <@&{role_id}> set to {limit} for {event_name} event.")

@bot.command(name="sendplaysettings")
async def sendplaysettings(ctx, event_name: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("Specified event not found.")
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

# !getplayexcel command – Sends the Excel file for the event.
@bot.command(name="getplayexcel")
async def getplayexcel(ctx, event_name: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    file_name = f"{event_name}_play_records.xlsx"
    if not os.path.exists(file_name):
        await ctx.send("Excel file not found for this event.")
        return
    await ctx.send(file=discord.File(file_name))

# !deletesendplay command – Deletes the event and clears usage_counts and event_nickname_counts.
@bot.command(name="deletesendplay")
async def deletesendplay(ctx, event_name: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("Specified event not found.")
        return
    info = events.pop(event_name)
    # Clear event_nickname_counts for the event
    if event_name in event_nickname_counts:
        event_nickname_counts.pop(event_name)
    # Clear all usage_counts entries that start with the event_name
    keys_to_remove = [key for key in usage_counts if key[0] == event_name]
    for key in keys_to_remove:
        usage_counts.pop(key)
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
        await ctx.send(f"{event_name} event deleted, but Excel file not found.")

# !playlistid command – Gathers unique participant IDs from the Excel file and writes them to a text file.
# In the file, the IDs are arranged side by side (separated by a space) with every 150 IDs starting a new paragraph.
@bot.command(name="playlistid")
async def playlistid(ctx, event_name: str):
    excel_file_name = f"{event_name}_play_records.xlsx"
    if not os.path.exists(excel_file_name):
        await ctx.send("Excel file for the specified event not found.")
        return
    try:
        workbook = openpyxl.load_workbook(excel_file_name)
        sheet = workbook.active
    except Exception as e:
        await ctx.send("Error reading the Excel file.")
        return
    discord_ids = []
    # Skip the header row; read Discord IDs starting from row 2.
    for row in sheet.iter_rows(min_row=2, values_only=True):
        value = row[0]
        # If the value is a float, convert it to an int and then to a string.
        if isinstance(value, float):
            value_str = str(int(value))
        else:
            value_str = str(value)
        discord_ids.append(value_str)
    # Remove duplicate IDs while preserving order.
    unique_ids = list(dict.fromkeys(discord_ids))
    if not unique_ids:
        await ctx.send("No participants found for the event.")
        return
    chunk_size = 150
    paragraphs = []
    for i in range(0, len(unique_ids), chunk_size):
        chunk = unique_ids[i:i+chunk_size]
        # Join IDs with a space.
        paragraph = " ".join(chunk)
        paragraphs.append(paragraph)
    # Each group of 150 IDs starts on a new paragraph (separated by two newlines).
    txt_content = "\n\n".join(paragraphs)
    output_file_name = f"{event_name}_playlist.txt"
    with open(output_file_name, "w", encoding="utf-8") as f:
        f.write(txt_content)
    # Send the text file as an attachment.
    await ctx.send(file=discord.File(output_file_name))

# Updated command: !checkgameusername - Checks if game usernames match with Discord IDs
# Now supports "id" parameter to output only Discord IDs
@bot.command(name="checkgameusername")
async def checkgameusername(ctx, first_param: str, event_name: str = None, *, usernames: str = None):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    
    # Check if the first parameter is "id"
    id_only_mode = False
    if first_param.lower() == "id":
        id_only_mode = True
        if event_name is None or usernames is None:
            await ctx.send("Usage: !checkgameusername id <event_name> <username1 username2 ...>")
            return
    else:
        # If first parameter is not "id", then it's the event_name
        if usernames is None:
            usernames = event_name
            event_name = first_param
    
    excel_file_name = f"{event_name}_play_records.xlsx"
    if not os.path.exists(excel_file_name):
        await ctx.send("Excel file for the specified event not found.")
        return
    
    try:
        workbook = openpyxl.load_workbook(excel_file_name)
        sheet = workbook.active
    except Exception as e:
        await ctx.send(f"Error reading the Excel file: {e}")
        return
    
    # Parse the usernames from the input
    username_list = [name.strip() for name in usernames.split()]
    
    # Create a dictionary to store in-game username to Discord ID mappings
    username_to_discord = {}
    
    # Read the Excel file and populate the dictionary
    for row in sheet.iter_rows(min_row=2, values_only=True):
        discord_id = str(row[0])
        in_game_username = row[2]
        username_to_discord[in_game_username] = discord_id
    
    # Find matches
    matches = []
    for username in username_list:
        if username in username_to_discord:
            matches.append((username, username_to_discord[username]))
    
    # Create result message
    result_message = f"Checked {len(username_list)} game usernames for event '{event_name}'.\n"
    result_message += f"Found {len(matches)} matching Discord IDs."
    
    # Create a text file with the results
    output_file_name = f"{event_name}_username_matches.txt"
    with open(output_file_name, "w", encoding="utf-8") as f:
        f.write(f"Event: {event_name}\n")
        f.write(f"Total usernames checked: {len(username_list)}\n")
        f.write(f"Total matches found: {len(matches)}\n\n")
        
        if id_only_mode:
            # In ID-only mode, just list the Discord IDs
            f.write("Discord IDs:\n")
            for _, discord_id in matches:
                f.write(f"{discord_id}\n")
        else:
            # In normal mode, list both username and Discord ID
            f.write("Matches (Game Username : Discord ID):\n")
            for username, discord_id in matches:
                f.write(f"{username} : {discord_id}\n")
    
    # Send the results
    await ctx.send(result_message, file=discord.File(output_file_name))

@bot.command(name="allplaylist")
async def allplaylist(ctx):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if not events:
        await ctx.send("No events found.")
        return
    event_names = "\n".join(events.keys())
    await ctx.send(f"Created events:\n{event_names}")

@bot.command(name="playhelp")
async def playhelp(ctx):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    embed = discord.Embed(
        title="Play Bot Help Menu - Detailed Guide",
        description=(
            "**Event Creation and Settings Management**\n"
            "With this bot, you can create various events (tournaments, competitions, etc.) in your server, "
            "set event-specific links, channels, interaction limits, same nickname limits, and maintain an Excel file.\n\n"
            "**Commands and Example Usage:**\n\n"
            "1. **!createplayevent <event_name>**\n"
            "   - Description: Creates a new event.\n"
            "   - Example: `!createplayevent Tournament2025`\n\n"
            "2. **!setplaylink <event_name> <link>**\n"
            "   - Description: Sets the link for the event.\n"
            "   - Example: `!setplaylink Tournament2025 https://example.com/tournament`\n\n"
            "3. **!setplaychannel <event_name> <channelID or #channel>**\n"
            "   - Description: Sets the channel where the event's button will be sent.\n\n"
            "4. **!setauthorizedrole <roleID or @role>**\n"
            "   - Description: Sets the authorized role for play event commands.\n\n"
            "5. **!setallowedrole <roleID1,roleID2,...>**\n"
            "   - Description: Specifies roles allowed to use the button.\n\n"
            "6. **!removeallowedrole <roleID1,roleID2,...>**\n"
            "   - Description: Removes the specified roles from the allowed list.\n\n"
            "7. **!samenicknamefilter <event_name> on <limit> / off**\n"
            "   - Description: Limits the number of times the same in-game username can be entered.\n\n"
            "8. **!sendplay <event_name> [channelID]**\n"
            "   - Description: Sends the Play button for the event.\n\n"
            "9. **!sendplaylimit <event_name> <roleID or @role> <limit>**\n"
            "   - Description: Sets the interaction limit for the specified role for the event.\n\n"
            "10. **!sendplaysettings <event_name>**\n"
            "    - Description: Displays all event settings.\n\n"
            "11. **!getplayexcel <event_name>**\n"
            "    - Description: Sends the Excel file.\n\n"
            "12. **!deletesendplay <event_name>**\n"
            "    - Description: Deletes the event and associated files (usage data is cleared).\n\n"
            "13. **!playlistid <event_name>**\n"
            "    - Description: Lists Discord IDs of event participants in a text file. The IDs are arranged side by side (separated by spaces), with every 150 IDs starting a new paragraph.\n\n"
            "14. **!removeplaybutton <event_name>**\n"
            "    - Description: Removes the Play button for the specified event.\n\n"
            "15. **!allplaylist**\n"
            "    - Description: Lists all created events.\n\n"
            "16. **!checkgameusername <event_name> <username1 username2 ...>**\n"
            "    - Description: Checks if the provided game usernames match with Discord IDs in the event records.\n"
            "    - Example: `!checkgameusername Tournament2025 Player1 Player2 Player3`\n\n"
            "17. **!checkgameusername id <event_name> <username1 username2 ...>**\n"
            "    - Description: Same as above, but outputs only the Discord IDs in the text file.\n"
            "    - Example: `!checkgameusername id Tournament2025 Player1 Player2 Player3`\n\n"
            "18. **!playhelp**\n"
            "    - Description: Shows this help menu.\n"
        ),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

bot.run("BOTTOKENHERE")
