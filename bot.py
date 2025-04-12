import discord
from discord.ext import commands
import openpyxl
import os
import asyncio
from datetime import timedelta
from playwright.async_api import async_playwright

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
        await ctx.send(f"Removed roles from allowed list: {removed}")
    else:
        await ctx.send("No roles were removed from the allowed list.")

@bot.command(name="playauthorizedadd")
async def playauthorizedadd(ctx, identifier: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    try:
        id_val = int(identifier.strip("<@&>"))
    except ValueError:
        await ctx.send("Please provide a valid user or role ID.")
        return
    play_authorized_ids.add(id_val)
    await ctx.send(f"{identifier} is now authorized for play event commands.")

@bot.command(name="playauthorizedremove")
async def playauthorizedremove(ctx, identifier: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    try:
        id_val = int(identifier.strip("<@&>"))
    except ValueError:
        await ctx.send("Please provide a valid user or role ID.")
        return
    if id_val in play_authorized_ids:
        play_authorized_ids.remove(id_val)
        await ctx.send(f"{identifier} has been removed from the play authorized list.")
    else:
        await ctx.send("The specified ID was not found in the play authorized list.")

@bot.command(name="sendplaylimit")
async def sendplaylimit(ctx, event_name: str, role_input: str, limit: int):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("Please create the event first using !createplayevent.")
        return
    try:
        role_id = int(role_input.strip("<@&>"))
    except ValueError:
        await ctx.send("Please provide a valid role ID or role mention.")
        return
    role = ctx.guild.get_role(role_id)
    if role is None:
        await ctx.send("No role found with the provided ID.")
        return
    events[event_name]["limits"][role.id] = limit
    await ctx.send(f"Interaction limit for {role.mention} in {event_name} event set to {limit}.")

@bot.command(name="sendplaysettings")
async def sendplaysettings(ctx, event_name: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("Event not found.")
        return
    event_data = events[event_name]
    embed = discord.Embed(title=f"{event_name} Event Settings", color=discord.Color.blue())
    embed.add_field(name="Link", value=event_data["link"] or "Not set", inline=False)
    channel_id = event_data["channel_id"]
    channel_mention = f"<#{channel_id}>" if channel_id else "Not set"
    embed.add_field(name="Channel", value=channel_mention, inline=False)
    embed.add_field(name="Excel File", value=event_data["excel_file"], inline=False)
    limits_text = ""
    for role_id, limit in event_data["limits"].items():
        role = ctx.guild.get_role(role_id)
        role_name = role.name if role else f"Unknown Role ({role_id})"
        limits_text += f"{role_name}: {limit}\n"
    embed.add_field(name="Interaction Limits", value=limits_text or "No limits set", inline=False)
    same_nickname_limit_text = str(event_nickname_limit.get(event_name, "No limit")) if event_name in event_nickname_limit else "No limit"
    embed.add_field(name="Same Nickname Limit", value=same_nickname_limit_text, inline=False)
    await ctx.send(embed=embed)

@bot.command(name="getplayexcel")
async def getplayexcel(ctx, event_name: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    excel_file_name = f"{event_name}_play_records.xlsx"
    if not os.path.exists(excel_file_name):
        await ctx.send("Excel file for the specified event not found.")
        return
    await ctx.send(file=discord.File(excel_file_name))

@bot.command(name="deletesendplay")
async def deletesendplay(ctx, event_name: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("Event not found.")
        return
    events.pop(event_name)
    event_nickname_counts.pop(event_name, None)
    event_nickname_limit.pop(event_name, None)
    excel_file_name = f"{event_name}_play_records.xlsx"
    if os.path.exists(excel_file_name):
        try:
            os.remove(excel_file_name)
            await ctx.send(f"{event_name} event and its Excel file have been deleted.")
        except Exception as e:
            await ctx.send(f"Event deleted, but could not delete Excel file: {e}")
    else:
        await ctx.send(f"{event_name} event has been deleted. No Excel file was found.")

@bot.command(name="playlistid")
async def playlistid(ctx, event_name: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
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
    discord_ids = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        value = row[0]  # Discord ID is in the first column
        if value is None:
            continue
        if isinstance(value, (int, float)):
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

# Specialized command: !getusername - Optimized for Lepoker.io
@bot.command(name="getusername")
async def getusername(ctx, url: str, selector: str):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    
    await ctx.send("Extracting player names from the Lepoker.io webpage. This may take a moment...")
    
    try:
        # Extract player names using the specialized Lepoker.io function
        player_names = await extract_lepoker_player_names(url, selector)
        
        if not player_names:
            await ctx.send("No player names found on the webpage with the provided selector.")
            return
        
        # Create a text file with the player names
        output_file_name = "player_names.txt"
        with open(output_file_name, "w", encoding="utf-8") as f:
            for name in player_names:
                f.write(f"{name}\n")
        
        # Send the results
        await ctx.send(f"Found {len(player_names)} player names.", file=discord.File(output_file_name))
    
    except Exception as e:
        # Truncate error message if it's too long to avoid Discord's 2000 character limit
        error_msg = str(e)
        if len(error_msg) > 1500:
            error_msg = error_msg[:1500] + "... (error message truncated)"
        
        await ctx.send(f"Error extracting player names: {error_msg}")

# Specialized function for Lepoker.io player extraction
async def extract_lepoker_player_names(url, selector):
    async with async_playwright() as p:
        # Launch browser with optimized settings for Lepoker.io
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials'
            ]
        )
        
        # Create context with larger viewport and mobile emulation (sometimes helps with lazy loading)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        
        # Create a new page with longer timeouts
        page = await context.new_page()
        page.set_default_timeout(180000)  # 3 minutes timeout
        
        try:
            print(f"Navigating to {url}")
            # Navigate to the URL with a longer timeout and wait until network is idle
            await page.goto(url, timeout=120000, wait_until="networkidle")
            
            # Wait for the page to be fully loaded
            await page.wait_for_load_state("networkidle", timeout=60000)
            await page.wait_for_timeout(5000)  # Additional 5 seconds wait
            
            # Check if we're on the correct page
            print("Checking if we're on the correct page...")
            page_title = await page.title()
            print(f"Page title: {page_title}")
            
            # Set to store unique player names
            player_names = set()
            
            # First try the provided selector
            print(f"Trying provided selector: {selector}")
            try:
                count = await page.locator(selector).count()
                print(f"Found {count} elements with provided selector")
            except Exception as e:
                print(f"Error with provided selector: {str(e)}")
                count = 0
            
            # If the provided selector doesn't work well, try these Lepoker.io specific selectors
            if count < 10:
                print("Provided selector found few elements, trying Lepoker.io specific selectors")
                lepoker_selectors = [
                    "div.truncate",
                    ".player-name",
                    ".player-username",
                    ".player-list div.truncate",
                    "tr td div.truncate",
                    "tr td:nth-child(2)",
                    ".players-table tr td:nth-child(2)",
                    ".players-list div.truncate"
                ]
                
                for current_selector in lepoker_selectors:
                    try:
                        count = await page.locator(current_selector).count()
                        if count > 0:
                            print(f"Found {count} elements with selector: {current_selector}")
                            selector = current_selector
                            break
                    except Exception:
                        continue
            
            # Initial extraction
            print("Performing initial extraction...")
            try:
                elements = await page.locator(selector).all()
                for element in elements:
                    try:
                        text = await element.text_content()
                        text = text.strip()
                        if text and len(text) > 0:
                            player_names.add(text)
                    except Exception:
                        continue
            except Exception as e:
                print(f"Error in initial extraction: {str(e)}")
            
            print(f"Initial extraction found {len(player_names)} players")
            
            # Specialized scrolling for Lepoker.io
            print("Starting specialized scrolling for Lepoker.io...")
            
            # First, try to find and click any "Show All" or similar buttons
            show_all_selectors = [
                "button:has-text('Show All')",
                "button:has-text('All Players')",
                "button:has-text('View All')",
                ".show-all-button",
                ".view-all-button"
            ]
            
            for show_selector in show_all_selectors:
                try:
                    if await page.locator(show_selector).count() > 0:
                        print(f"Found 'Show All' button with selector: {show_selector}")
                        await page.click(show_selector)
                        await page.wait_for_timeout(5000)  # Wait for content to load
                        break
                except Exception:
                    continue
            
            # Function to extract player names after each action
            async def extract_names():
                try:
                    elements = await page.locator(selector).all()
                    count_before = len(player_names)
                    for element in elements:
                        try:
                            text = await element.text_content()
                            text = text.strip()
                            if text and len(text) > 0:
                                player_names.add(text)
                        except Exception:
                            continue
                    return len(player_names) - count_before
                except Exception as e:
                    print(f"Error in extract_names: {str(e)}")
                    return 0
            
            # Specialized scrolling approach for Lepoker.io
            # 1. First try continuous small scrolls
            print("Performing continuous small scrolls...")
            for i in range(50):
                try:
                    # Scroll down a small amount
                    await page.evaluate(f"window.scrollBy(0, 300)")
                    await page.wait_for_timeout(500)  # Short wait
                    
                    # Every 5 scrolls, check for new names
                    if i % 5 == 0:
                        new_names = await extract_names()
                        print(f"Scroll group {i//5+1}: Found {new_names} new players, total: {len(player_names)}")
                        
                        # If we've found all 635 players or more, we can stop
                        if len(player_names) >= 635:
                            print(f"Found {len(player_names)} players, which is >= 635, stopping scrolling")
                            break
                except Exception as e:
                    print(f"Error during small scroll {i+1}: {str(e)}")
            
            # 2. If we don't have enough players yet, try larger jumps
            if len(player_names) < 635:
                print("Trying larger scroll jumps...")
                for i in range(20):
                    try:
                        # Larger scroll jump
                        await page.evaluate(f"window.scrollBy(0, 1000)")
                        await page.wait_for_timeout(1000)  # Longer wait
                        
                        new_names = await extract_names()
                        print(f"Large scroll {i+1}: Found {new_names} new players, total: {len(player_names)}")
                        
                        # If we've found all 635 players or more, we can stop
                        if len(player_names) >= 635:
                            print(f"Found {len(player_names)} players, which is >= 635, stopping scrolling")
                            break
                    except Exception as e:
                        print(f"Error during large scroll {i+1}: {str(e)}")
            
            # 3. If we still don't have enough, try scrolling to specific positions
            if len(player_names) < 635:
                print("Trying scrolling to specific positions...")
                scroll_positions = [0.2, 0.4, 0.6, 0.8, 1.0]  # Percentage of page height
                
                for pos in scroll_positions:
                    try:
                        # Scroll to percentage of page height
                        await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {pos})")
                        await page.wait_for_timeout(2000)  # Longer wait
                        
                        new_names = await extract_names()
                        print(f"Position scroll {pos*100}%: Found {new_names} new players, total: {len(player_names)}")
                    except Exception as e:
                        print(f"Error during position scroll {pos*100}%: {str(e)}")
            
            # 4. Try clicking pagination elements if they exist
            if len(player_names) < 635:
                print("Looking for pagination elements...")
                pagination_selectors = [
                    ".pagination button",
                    ".pagination a",
                    "button.pagination-next",
                    "a.pagination-next",
                    ".next-page",
                    "button:has-text('Next')",
                    "a:has-text('Next')"
                ]
                
                for pagination_selector in pagination_selectors:
                    try:
                        pagination_elements = await page.locator(pagination_selector).all()
                        if len(pagination_elements) > 0:
                            print(f"Found {len(pagination_elements)} pagination elements with selector: {pagination_selector}")
                            
                            # Click each pagination element
                            for i, element in enumerate(pagination_elements):
                                try:
                                    await element.click()
                                    await page.wait_for_timeout(2000)  # Wait for content to load
                                    
                                    new_names = await extract_names()
                                    print(f"Pagination click {i+1}: Found {new_names} new players, total: {len(player_names)}")
                                except Exception:
                                    continue
                            
                            break
                    except Exception:
                        continue
            
            # 5. Try a specialized approach for Lepoker.io - force load all players with JavaScript
            if len(player_names) < 635:
                print("Trying specialized JavaScript approach for Lepoker.io...")
                try:
                    # This JavaScript tries to trigger the loading of all players
                    await page.evaluate("""() => {
                        // Try to find and click any "load more" buttons
                        const buttons = Array.from(document.querySelectorAll('button'));
                        for (const button of buttons) {
                            if (button.textContent.toLowerCase().includes('more') || 
                                button.textContent.toLowerCase().includes('all') ||
                                button.textContent.toLowerCase().includes('show')) {
                                button.click();
                            }
                        }
                        
                        // Scroll to various positions to trigger lazy loading
                        const scrollPositions = [0.2, 0.4, 0.6, 0.8, 1.0];
                        for (const pos of scrollPositions) {
                            window.scrollTo(0, document.body.scrollHeight * pos);
                        }
                        
                        // Try to find the player container and force display
                        const containers = document.querySelectorAll('div');
                        for (const container of containers) {
                            if (container.querySelectorAll('div.truncate').length > 10) {
                                container.style.maxHeight = 'none';
                                container.style.overflow = 'visible';
                            }
                        }
                    }""")
                    
                    await page.wait_for_timeout(3000)  # Wait for changes to take effect
                    new_names = await extract_names()
                    print(f"JavaScript approach: Found {new_names} new players, total: {len(player_names)}")
                except Exception as e:
                    print(f"Error in JavaScript approach: {str(e)}")
            
            # 6. Final extraction using JavaScript to get all elements
            print("Performing final extraction with JavaScript...")
            try:
                # This JavaScript tries to extract all player names directly from the DOM
                all_texts = await page.evaluate(f"""() => {{
                    // Try the specified selector first
                    let elements = Array.from(document.querySelectorAll('{selector}'));
                    
                    // If that doesn't work well, try other common selectors
                    if (elements.length < 10) {{
                        const selectors = [
                            'div.truncate',
                            '.player-name',
                            '.player-username',
                            '.player-list div.truncate',
                            'tr td div.truncate',
                            'tr td:nth-child(2)',
                            '.players-table tr td:nth-child(2)',
                            '.players-list div.truncate'
                        ];
                        
                        for (const sel of selectors) {{
                            const newElements = Array.from(document.querySelectorAll(sel));
                            if (newElements.length > elements.length) {{
                                elements = newElements;
                            }}
                        }}
                    }}
                    
                    // Extract text content from elements
                    return elements
                        .map(el => el.textContent.trim())
                        .filter(text => text.length > 0);
                }}""")
                
                for text in all_texts:
                    player_names.add(text)
                
                print(f"Final JavaScript extraction found {len(player_names)} total players")
            except Exception as e:
                print(f"Error in final JavaScript extraction: {str(e)}")
            
            # 7. Try one more approach - get all text content from the page and parse it
            if len(player_names) < 635:
                print("Trying to extract from full page content...")
                try:
                    full_page_text = await page.evaluate("""() => {
                        return document.body.innerText;
                    }""")
                    
                    # Split by newlines and process each line
                    lines = full_page_text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and len(line) > 0 and len(line) < 50:  # Likely a username if not too long
                            player_names.add(line)
                    
                    print(f"Full page content extraction found {len(player_names)} total players")
                except Exception as e:
                    print(f"Error extracting from full page: {str(e)}")
            
            # Convert set back to list
            result = list(player_names)
            
            # Filter out non-player entries
            filtered_result = [
                name for name in result 
                if not name.isdigit() and 
                name not in ["Players", "Rank", "Clan", "Chips", "Tables", "Finished", "-", "Name", "Player", "Username"] and
                len(name) > 1  # Exclude single characters
            ]
            
            print(f"Final result: {len(filtered_result)} players after filtering")
            return filtered_result if filtered_result else result
        
        finally:
            await browser.close()

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
            "18. **!getusername <url> <selector>**\n"
            "    - Description: Extracts player names from a webpage using the specified selector and saves them to a text file.\n"
            "    - Example: `!getusername https://app.lepoker.io/m/lj2Dxdy/players \"div.truncate\"`\n\n"
            "19. **!playhelp**\n"
            "    - Description: Shows this help menu.\n"
        ),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

bot.run("BOTTOKENHERE")
