import discord
from discord.ext import commands
import openpyxl
import os
import asyncio
from datetime import timedelta
from playwright.async_api import async_playwright
import difflib  # For fuzzy matching
import dotenv   # For .env file support
import re
import random
import string
import io
from collections import defaultdict
import time
import json
_PIL_AVAILABLE = False
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    _PIL_AVAILABLE = True
    print("[PIL] Successfully imported PIL modules")
except ImportError as e:
    print(f"[PIL] Import failed - ImportError: {e}")
except Exception as e:
    print(f"[PIL] Import failed - Other error: {e}")

print(f"[PIL] Final status: _PIL_AVAILABLE = {_PIL_AVAILABLE}")
try:
    import regex as _advanced_regex_engine  # third-party 'regex' module (if available)
    _REGEX_ENGINE = _advanced_regex_engine
    _REGEX_ENGINE_NAME = "regex"
except Exception:  # pragma: no cover
    _REGEX_ENGINE = re
    _REGEX_ENGINE_NAME = "re"

# Load environment variables from .env file
dotenv.load_dotenv()

# Settings file path
SETTINGS_FILE = "bot_settings.json"

# Settings save/load functions
def save_settings():
    """Save all bot settings to JSON file"""
    settings = {
        "captcha_verify_role_id": captcha_verify_role_id,
        "captcha_panel_texts": captcha_panel_texts,
        "regex_settings_by_guild": {},
        "security_authorized_ids": list(security_authorized_ids),
        "play_authorized_ids": list(play_authorized_ids),
        "allowed_role_ids": allowed_role_ids,
        "no_avatar_filter_enabled": no_avatar_filter_enabled,
        "no_avatar_action": no_avatar_action,
        "no_avatar_timeout_duration": no_avatar_timeout_duration,
        "account_age_filter_enabled": account_age_filter_enabled,
        "account_age_min_days": account_age_min_days,
        "account_age_action": account_age_action,
        "account_age_timeout_duration": account_age_timeout_duration,
        "events": events,
        "event_nickname_limit": event_nickname_limit
    }
    
    # Convert regex settings to serializable format
    for guild_id, guild_rules in regex_settings_by_guild.items():
        settings["regex_settings_by_guild"][str(guild_id)] = {}
        for rule_name, rule_data in guild_rules.items():
            settings["regex_settings_by_guild"][str(guild_id)][rule_name] = {
                "pattern": rule_data.get("pattern", ""),
                "channels": list(rule_data.get("channels", set())),
                "exempt_users": list(rule_data.get("exempt_users", set())),
                "exempt_roles": list(rule_data.get("exempt_roles", set()))
            }
    
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        print(f"[SETTINGS] Settings saved to {SETTINGS_FILE}")
    except Exception as e:
        print(f"[SETTINGS] Error saving settings: {e}")

def load_settings():
    """Load all bot settings from JSON file"""
    global captcha_verify_role_id, captcha_panel_texts, regex_settings_by_guild
    global security_authorized_ids, play_authorized_ids, allowed_role_ids
    global no_avatar_filter_enabled, no_avatar_action, no_avatar_timeout_duration
    global account_age_filter_enabled, account_age_min_days, account_age_action, account_age_timeout_duration
    global events, event_nickname_limit
    
    if not os.path.exists(SETTINGS_FILE):
        print(f"[SETTINGS] Settings file {SETTINGS_FILE} not found, using defaults")
        return
    
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        
        # Load basic settings
        captcha_verify_role_id = settings.get("captcha_verify_role_id")
        captcha_panel_texts.update(settings.get("captcha_panel_texts", {}))
        security_authorized_ids.update(settings.get("security_authorized_ids", []))
        play_authorized_ids.update(settings.get("play_authorized_ids", []))
        allowed_role_ids[:] = settings.get("allowed_role_ids", [])
        
        # Load security filter settings
        no_avatar_filter_enabled = settings.get("no_avatar_filter_enabled", False)
        no_avatar_action = settings.get("no_avatar_action")
        no_avatar_timeout_duration = settings.get("no_avatar_timeout_duration")
        account_age_filter_enabled = settings.get("account_age_filter_enabled", False)
        account_age_min_days = settings.get("account_age_min_days")
        account_age_action = settings.get("account_age_action")
        account_age_timeout_duration = settings.get("account_age_timeout_duration")
        
        # Load play events
        events.update(settings.get("events", {}))
        event_nickname_limit.update(settings.get("event_nickname_limit", {}))
        
        # Load regex settings and recompile patterns
        regex_data = settings.get("regex_settings_by_guild", {})
        for guild_id_str, guild_rules in regex_data.items():
            guild_id = int(guild_id_str)
            regex_settings_by_guild[guild_id] = {}
            for rule_name, rule_data in guild_rules.items():
                pattern = rule_data.get("pattern", "")
                if pattern:
                    try:
                        pattern_text, flags_letters = _parse_pattern_and_flags(pattern)
                        compiled = _compile_with_flags(pattern_text, flags_letters)
                        regex_settings_by_guild[guild_id][rule_name] = {
                            "pattern": pattern,
                            "compiled": compiled,
                            "channels": set(rule_data.get("channels", [])),
                            "exempt_users": set(rule_data.get("exempt_users", [])),
                            "exempt_roles": set(rule_data.get("exempt_roles", []))
                        }
                    except Exception as e:
                        print(f"[SETTINGS] Error recompiling regex pattern '{pattern}': {e}")
        
        print(f"[SETTINGS] Settings loaded successfully from {SETTINGS_FILE}")
        
    except Exception as e:
        print(f"[SETTINGS] Error loading settings: {e}")

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

# Function to calculate string similarity for fuzzy matching
def _parse_pattern_and_flags(raw_text):
    text = (raw_text or "").strip()
    flags_letters_parts = []

    # Support trailing --flags imsx style
    m = re.search(r"\s--flags\s+([A-Za-z]+)\s*$", text)
    if m:
        flags_letters_parts.append(m.group(1))
        text = text[: m.start()].strip()

    # Support /pattern/flags style
    if len(text) >= 2 and text[0] == "/" and "/" in text[1:]:
        last_slash = text.rfind("/")
        body = text[1:last_slash]
        trailing = text[last_slash + 1 :].strip()
        if trailing and re.fullmatch(r"[A-Za-z]+", trailing):
            flags_letters_parts.append(trailing)
            # Unescape \/ to /
            body = body.replace("\\/", "/")
            text = body

    # Merge letters while preserving order and uniqueness
    seen = set()
    letters = ""
    for part in flags_letters_parts:
        for ch in part:
            cl = ch.lower()
            if cl not in seen:
                seen.add(cl)
                letters += cl

    return text, letters


def _compile_with_flags(pattern_text, flags_letters):
    flag_map = {
        "i": re.IGNORECASE,
        "m": re.MULTILINE,
        "s": re.DOTALL,
        "x": re.VERBOSE,
        "a": re.ASCII,
        "u": re.UNICODE,
        "l": re.LOCALE,
    }
    flags_value = 0
    for ch in flags_letters or "":
        flags_value |= flag_map.get(ch.lower(), 0)
    return _REGEX_ENGINE.compile(pattern_text, flags_value)

def string_similarity(s1, s2):
    # Convert both strings to lowercase for case-insensitive comparison
    s1 = s1.lower()
    s2 = s2.lower()
    
    # Calculate similarity ratio using difflib
    similarity = difflib.SequenceMatcher(None, s1, s2).ratio()
    return similarity

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

# Captcha verification settings
captcha_verify_role_id = None  # Role to grant upon successful captcha

# Customizable verification panel text per guild
captcha_panel_texts = {}  # guild_id -> {"title": str, "description": str, "image": str}

# Default panel text
DEFAULT_PANEL_TITLE = "Verification Panel"
DEFAULT_PANEL_DESCRIPTION = (
    "Server access requires verification.\n"
    "Click 'Verify' to receive a visual CAPTCHA challenge.\n"
    "Enter the displayed code using the 'Enter Code' button to complete verification."
)

# Rate limiting for captcha requests
captcha_rate_limits = defaultdict(list)  # user_id -> [timestamp, timestamp, ...]
CAPTCHA_RATE_LIMIT = 3  # Max 3 requests per minute
CAPTCHA_RATE_WINDOW = 60  # 60 seconds window

# Active captcha sessions to prevent spam
active_captcha_sessions = set()  # Set of user_ids currently processing captcha

# Verify button usage tracking (user_id -> interaction_count)
verify_button_usage = defaultdict(int)  # Tracks how many times each user clicked verify
VERIFY_MAX_ATTEMPTS = 10  # Maximum verify attempts per user

# Rate limit message tracking for CAPTCHA rate limits (user_id -> last_message_time)
captcha_rate_limit_messages = defaultdict(float)  # Tracks when captcha rate limit message was last sent
CAPTCHA_RATE_LIMIT_MESSAGE_COOLDOWN = 60  # Show captcha rate limit message once per minute

# Regex moderation settings per guild
# Structure: { guild_id: { name: {"pattern": str, "compiled": Pattern, "channels": set[int], "exempt_users": set[int], "exempt_roles": set[int]} } }
regex_settings_by_guild = {}

# Security Authorization
security_authorized_role_id = 1346562716680192012  # Your security manager role ID
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
play_authorized_role_id = 1346562716680192012  # Your event manager role ID
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
allowed_role_ids = [1346571303657930804]   # The role ID defined for button usage

# Global Security Filter Variables
no_avatar_filter_enabled = False
no_avatar_action = None
no_avatar_timeout_duration = None

account_age_filter_enabled = False
account_age_min_days = None
account_age_action = None
account_age_timeout_duration = None

# Helper function for regex moderation
async def check_and_moderate_message(message: discord.Message):
    """Check message content against regex rules and delete if matches"""
    if message.author.bot:
        return
    if message.guild is None:
        return
    guild_rules = regex_settings_by_guild.get(message.guild.id)
    if not guild_rules:
        return
    channel_id = message.channel.id
    for rule in guild_rules.values():
        channels = rule.get("channels", set())
        compiled = rule.get("compiled")
        if not compiled or not channels:
            continue
        if channel_id in channels and compiled.search(message.content or ""):
            # Exemptions: users or roles
            exempt_users = rule.get("exempt_users", set())
            exempt_roles = rule.get("exempt_roles", set())
            if message.author.id in exempt_users:
                continue
            author_roles = getattr(message.author, "roles", [])
            if any(r.id in exempt_roles for r in author_roles):
                continue
            try:
                await message.delete()
            except Exception:
                pass
            break

# Message moderation via regex
@bot.event
async def on_message(message: discord.Message):
    if isinstance(bot.command_prefix, str) and message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return
    await check_and_moderate_message(message)

# Message edit moderation via regex
@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """Handle message edits - check edited message against regex rules"""
    await check_and_moderate_message(after)

# Button interaction handler - Add this to fix the interaction failed issue
@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id", "")
        
        # Handle CAPTCHA verification button
        if custom_id == "captcha_verify_button":
            user_id = interaction.user.id
            
            # Check if user has exceeded verify attempts - COMPLETELY SILENT
            if verify_button_usage[user_id] >= VERIFY_MAX_ATTEMPTS:
                # Silently ignore - no response at all
                return
            
            # Check if verification role is set
            if captcha_verify_role_id is None:
                await interaction.response.send_message(
                    "Verification role is not set. Please contact an administrator.",
                    ephemeral=True,
                )
                return

            # Check rate limiting BEFORE incrementing usage count
            if not _check_captcha_rate_limit(user_id):
                current_time = time.time()
                last_rate_limit_message = captcha_rate_limit_messages[user_id]
                
                # Show rate limit message only once per minute
                if current_time - last_rate_limit_message >= CAPTCHA_RATE_LIMIT_MESSAGE_COOLDOWN:
                    captcha_rate_limit_messages[user_id] = current_time
                    await interaction.response.send_message(
                        f"⏰ Rate limit exceeded. You can only request {CAPTCHA_RATE_LIMIT} captchas per minute. Please wait and try again.",
                        ephemeral=True,
                    )
                # If rate limit message was sent recently, silently ignore
                # IMPORTANT: Don't increment usage count when rate limited
                return
            
            # Only increment usage count AFTER passing rate limit check
            verify_button_usage[user_id] += 1

            # Remove any existing active session to allow fresh captcha
            if user_id in active_captcha_sessions:
                active_captcha_sessions.discard(user_id)
                print(f"[captcha] Removed existing session for user {user_id} to generate fresh captcha")

            # Already has role?
            member = interaction.user
            if isinstance(member, discord.Member):
                if any(r.id == captcha_verify_role_id for r in getattr(member, "roles", [])):
                    await interaction.response.send_message(
                        "You are already verified.", ephemeral=True
                    )
                    return

            # Add to active sessions
            active_captcha_sessions.add(user_id)

            try:
                # Generate fresh captcha code each time
                code = _generate_captcha_code()
                print(f"[captcha] Generated FRESH code: {code} for user {user_id} (attempt #{verify_button_usage[user_id]}), PIL available: {_PIL_AVAILABLE}")

                # Add to rate limit tracker only when captcha is successfully generated
                _add_captcha_rate_limit_request(user_id)

                # Defer first, then send image
                await interaction.response.defer(ephemeral=True)
                
                # Text image CAPTCHA
                if _PIL_AVAILABLE:
                    try:
                        img_bytes = _create_text_image(code)
                        file = discord.File(io.BytesIO(img_bytes), filename="captcha.png")
                        embed = discord.Embed(
                            title="🔐 Security Verification",
                            description=f"Please read the code from the image below and click 'Enter Code' to input it.\n\n**Attempt: {verify_button_usage[user_id]}/{VERIFY_MAX_ATTEMPTS}**",
                            color=discord.Color.blue()
                        )
                        embed.set_image(url="attachment://captcha.png")
                        view = CaptchaCodeEntryView(expected_code=code, verify_role_id=captcha_verify_role_id, user_id=user_id)
                        await interaction.followup.send(embed=embed, file=file, view=view, ephemeral=True)
                        return
                    except Exception as e:
                        print(f"[captcha] Text image creation failed: {e}")

                # Fallback: Simple text
                embed = discord.Embed(
                    title="🔐 Security Verification",
                    description=f"**Code: `{code}`**\n\nPlease enter the code above by clicking 'Enter Code'.\n\n**Attempt: {verify_button_usage[user_id]}/{VERIFY_MAX_ATTEMPTS}**",
                    color=discord.Color.green()
                )
                view = CaptchaCodeEntryView(expected_code=code, verify_role_id=captcha_verify_role_id, user_id=user_id)
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)

            except Exception as e:
                print(f"[captcha] Error in verify_button: {e}")
                # Remove from active sessions on error
                active_captcha_sessions.discard(user_id)
                try:
                    await interaction.followup.send("An error occurred while generating captcha. Please try again.", ephemeral=True)
                except Exception:
                    pass
            return
            
        # Handle CAPTCHA code entry button  
        if custom_id == "captcha_enter_code":
            # This should be handled by the CaptchaCodeEntryView
            return
            
        if custom_id.startswith("play_button_"):
            event_name = custom_id.replace("play_button_", "")
            
            # Check if event exists
            if event_name not in events:
                await interaction.response.send_message("This event no longer exists.", ephemeral=True)
                return
            
            # Check if user has allowed role
            has_allowed_role = False
            if not allowed_role_ids:  # If no roles are specified, allow all
                has_allowed_role = True
            else:
                for role in interaction.user.roles:
                    if role.id in allowed_role_ids:
                        has_allowed_role = True
                        break
            
            if not has_allowed_role:
                await interaction.response.send_message("You don't have the required role to use this button.", ephemeral=True)
                return
            
            # Check user limit if set
            user_limit = None
            for role in interaction.user.roles:
                if role.id in events[event_name]["limits"]:
                    user_limit = events[event_name]["limits"][role.id]
                    break
            
            if user_limit is not None:
                usage_key = f"{event_name}_{interaction.user.id}"
                if usage_counts.get(usage_key, 0) >= user_limit:
                    await interaction.response.send_message(
                        f"You've reached your limit of {user_limit} interactions for this event.",
                        ephemeral=True
                    )
                    return
            
            # Create and send the modal
            class NicknameModal(discord.ui.Modal):
                def __init__(self, event_name, nickname_limit):
                    super().__init__(title=f"Register for {event_name}")
                    self.event_name = event_name
                    self.nickname_limit = nickname_limit
                    
                    self.nickname = discord.ui.TextInput(
                        label="Your In-Game Username",
                        placeholder="Enter your in-game username here...",
                        min_length=3,
                        max_length=32
                    )
                    self.add_item(self.nickname)
                
                async def on_submit(self, interaction):
                    in_game_username = self.nickname.value.strip()
                    
                    # Check same nickname limit if enabled
                    if self.nickname_limit is not None:
                        if in_game_username in event_nickname_counts.get(self.event_name, {}):
                            if event_nickname_counts[self.event_name][in_game_username] >= self.nickname_limit:
                                await interaction.response.send_message(
                                    f"This in-game username has already been registered {self.nickname_limit} times.",
                                    ephemeral=True
                                )
                                return
                        
                        # Update nickname count
                        if self.event_name not in event_nickname_counts:
                            event_nickname_counts[self.event_name] = {}
                        event_nickname_counts[self.event_name][in_game_username] = event_nickname_counts[self.event_name].get(in_game_username, 0) + 1
                    
                    # Record the play
                    record_play(interaction.user.id, str(interaction.user), in_game_username, self.event_name)
                    
                    # Update usage count if limits are set
                    if events[self.event_name]["limits"]:
                        usage_key = f"{self.event_name}_{interaction.user.id}"
                        usage_counts[usage_key] = usage_counts.get(usage_key, 0) + 1
                    
                    # Send confirmation message
                    await interaction.response.send_message(
                        f"Successfully registered for {self.event_name} with username: {in_game_username}",
                        ephemeral=True
                    )
                    
                    # Send link if available
                    event_link = events[self.event_name].get("link")
                    event_password = events[self.event_name].get("password")
                    
                    if event_link:
                        try:
                            link_message = f"Link for {self.event_name}: {event_link}"
                            if event_password:
                                link_message += f"\nPassword: {event_password}"
                            
                            await interaction.followup.send(link_message, ephemeral=True)
                        except Exception as e:
                            print(f"Error sending link: {e}")
            
            # Send the modal
            if event_name in event_nickname_limit:
                modal = NicknameModal(event_name, event_nickname_limit[event_name])
            else:
                modal = NicknameModal(event_name, None)
            
            await interaction.response.send_modal(modal)

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
        save_settings()
        await ctx.send(f"No-avatar filter enabled. Mode: {no_avatar_action}" +
                       (f", Timeout: {no_avatar_timeout_duration} minutes" if no_avatar_action == "timeout" else ""))
    elif state == "off":
        no_avatar_filter_enabled = False
        save_settings()
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
        save_settings()
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
            save_settings()
            await ctx.send(f"Account age filter enabled: Accounts younger than {min_age} days will be timed out for {duration} minutes.")
        else:
            save_settings()
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
        save_settings()
        await ctx.send(f"Same nickname filter for {event_name} disabled. Users can now enter unlimited entries.")
    elif state == "on":
        if limit is None:
            await ctx.send("Please provide a limit value. Example: `!samenicknamefilter Tournament2025 on 1`")
            return
        event_nickname_limit[event_name] = limit
        save_settings()
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
    save_settings()
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
        save_settings()
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

@bot.command(name="savesettings")
async def savesettings_command(ctx):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    save_settings()
    await ctx.send("✅ All settings have been manually saved to bot_settings.json")

@bot.command(name="loadsettings")
async def loadsettings_command(ctx):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    load_settings()
    await ctx.send("✅ All settings have been reloaded from bot_settings.json")

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
        "   - Description: Checks new members for minimum account age. Mode options: `ban`, `kick`, `timeout`.\n"
        "   - Example: `!accountagefilter on 7 timeout 60` → Applies a 60-minute timeout to accounts younger than 7 days.\n\n"
        "3. **!securityauthorizedadd <id>**\n"
        "   - Description: Authorizes the specified user or role ID for security commands.\n\n"
        "4. **!securityauthorizedremove <id>**\n"
        "   - Description: Removes the specified user or role ID from the security authorized list.\n\n"
        "5. **!securitysettings**\n"
        "   - Description: Displays current security settings (filter statuses, actions, timeout durations, etc.).\n\n"
        "6. **!regex <regexsettingsname> <regex>**\n"
        "   - Description: Defines/updates a regex rule with the given name. Supports `/pattern/flags` or `pattern --flags imsx`. If the advanced `regex` engine is installed it is used; otherwise Python's built-in `re` is used.\n\n"
        "7. **!setregexsettings <regexsettingsname> <channels>**\n"
        "   - Description: Assigns which channels the regex rule applies to. You can specify multiple channels by ID or #mention.\n"
        "   - Also supported: `!setregexsettings <name> allchannel notchannel <channels_to_exclude>` → apply to all text channels except the ones listed after `notchannel`.\n\n"
        "8. **!setregexexempt <regexsettingsname> users|roles <targets>**\n"
        "   - Description: Sets users or roles exempt from the rule.\n\n"
        "9. **!regexsettings [regexsettingsname]**\n"
        "   - Description: Shows active regex rules and their details (channels and exemptions). Provide a name to see only that rule.\n\n"
        "10. **!delregexsettings <regexsettingsname>**\n"
        "   - Description: Deletes the specified regex setting from this server.\n\n"
        "11. **!setverifyrole <role_id|@role>**\n"
        "   - Description: Sets the role to be assigned after successful CAPTCHA verification.\n"
        "   - Example: `!setverifyrole @Verified` → Sets the Verified role as the verification reward.\n\n"
        "12. **!sendverifypanel [#channel|channel_id]**\n"
        "   - Description: Sends a verification panel with CAPTCHA button to the specified channel (or current channel).\n"
        "   - Example: `!sendverifypanel #verification` → Sends verification panel to the verification channel.\n\n"
        "13. **!setverifypaneltext <title|description|image> <text|url>**\n"
        "   - Description: Customizes the verification panel title, description text, or image.\n"
        "   - Examples: `!setverifypaneltext title Welcome to Our Server` → Changes panel title.\n"
        "   - `!setverifypaneltext image https://example.com/logo.png` → Adds panel image.\n\n"
        "14. **!showverifypaneltext**\n"
        "   - Description: Shows the current verification panel text settings.\n\n"
        "15. **!resetverifypaneltext**\n"
        "   - Description: Resets verification panel text to default values.\n\n"
        "16. **!savesettings**\n"
        "   - Description: Manually saves all bot settings to JSON file.\n\n"
        "17. **!loadsettings**\n"
        "   - Description: Reloads all bot settings from JSON file.\n\n"
        "18. **!securityhelp**\n"
        "   - Description: Shows this help menu.\n"
    )
    # Split into chunks to respect Discord 2000-char message limit
    parts = []
    buffer = []
    current_len = 0
    for para in help_text.split("\n\n"):
        block = para + "\n\n"
        if current_len + len(block) > 1900:
            if buffer:
                parts.append("".join(buffer).rstrip())
                buffer = [block]
                current_len = len(block)
            else:
                # Hard-split if single block is too long
                for i in range(0, len(block), 1900):
                    parts.append(block[i:i+1900])
                buffer = []
                current_len = 0
        else:
            buffer.append(block)
            current_len += len(block)
    if buffer:
        parts.append("".join(buffer).rstrip())
    for part in parts:
        await ctx.send(part)

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
        "password": None,  # Added password field
        "channel_id": None,
        "excel_file": f"{event_name}_play_records.xlsx",
        "limits": {}
    }
    event_nickname_counts[event_name] = {}  # Initialize same nickname counter.
    save_settings()
    await ctx.send(f"{event_name} event has been created.")

@bot.command(name="setplaylink")
async def setplaylink(ctx, event_name: str, link: str, *args):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    if event_name not in events:
        await ctx.send("Please create the event first using !createplayevent.")
        return
    
    # Set the link
    events[event_name]["link"] = link
    
    # Check for password in the arguments
    password = None
    for i, arg in enumerate(args):
        if arg.lower() == "password" and i+1 < len(args):
            password = args[i+1]
            break
    
    # If password is found, store it
    if password:
        events[event_name]["password"] = password
        save_settings()
        await ctx.send(f"Link set for {event_name} event: {link}\nPassword: {password}")
    else:
        events[event_name]["password"] = None
        save_settings()
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
    save_settings()
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

@bot.command(name="sendplay")
async def sendplay(ctx, event_name: str, channel_input: str = None):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    
    if event_name not in events:
        await ctx.send("Event not found. Please create the event first using !createplayevent.")
        return
    
    # Determine which channel to use
    target_channel = None
    if channel_input:
        try:
            channel_id = int(channel_input.strip("<#>"))
            target_channel = ctx.guild.get_channel(channel_id)
            if target_channel is None:
                await ctx.send("No channel found with the provided ID.")
                return
        except ValueError:
            await ctx.send("Please provide a valid channel ID or channel mention.")
            return
    else:
        # Use the channel set in the event if no channel is specified
        channel_id = events[event_name]["channel_id"]
        if channel_id:
            target_channel = ctx.guild.get_channel(channel_id)
        else:
            await ctx.send("No channel is set for this event. Please specify a channel.")
            return
    
    # Create a button for the event
    class PlayButton(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label="Play",
                custom_id=f"play_button_{event_name}"
            ))
    
    # Send the button
    try:
        await target_channel.send(
            f"Click the button below to register for **{event_name}**:",
            view=PlayButton()
        )
        await ctx.send(f"Play button for {event_name} has been sent to {target_channel.mention}")
    except Exception as e:
        await ctx.send(f"Failed to send play button: {str(e)}")

@bot.command(name="removeplaybutton")
async def removeplaybutton(ctx, event_name: str, channel_input: str = None):
    if not is_play_authorized(ctx):
        await ctx.message.delete()
        return
    
    if event_name not in events:
        await ctx.send("Event not found.")
        return
    
    # Determine which channel to use
    target_channel = None
    if channel_input:
        try:
            channel_id = int(channel_input.strip("<#>"))
            target_channel = ctx.guild.get_channel(channel_id)
            if target_channel is None:
                await ctx.send("No channel found with the provided ID.")
                return
        except ValueError:
            await ctx.send("Please provide a valid channel ID or channel mention.")
            return
    else:
        # Use the channel set in the event if no channel is specified
        channel_id = events[event_name]["channel_id"]
        if channel_id:
            target_channel = ctx.guild.get_channel(channel_id)
        else:
            await ctx.send("No channel is set for this event. Please specify a channel.")
            return
    
    # Try to find and delete the play button message
    try:
        async for message in target_channel.history(limit=100):
            if message.components and f"play_button_{event_name}" in str(message.components):
                await message.delete()
                await ctx.send(f"Play button for {event_name} has been removed from {target_channel.mention}")
                return
        await ctx.send(f"No play button found for {event_name} in {target_channel.mention}")
    except Exception as e:
        await ctx.send(f"Failed to remove play button: {str(e)}")

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
    save_settings()
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
        save_settings()
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
    save_settings()
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
        save_settings()
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
    save_settings()
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
    
    # Add password field if it exists
    if event_data.get("password"):
        embed.add_field(name="Password", value=event_data["password"], inline=False)
    
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
    save_settings()
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
# Now supports case-insensitive matching and fuzzy matching
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
        if in_game_username:
            username_to_discord[in_game_username.lower()] = discord_id  # Store lowercase for case-insensitive matching
    
    # Find matches (exact, case-insensitive, and fuzzy)
    exact_matches = []
    case_insensitive_matches = []
    fuzzy_matches = []
    
    for username in username_list:
        username_lower = username.lower()
        
        # Check for exact match
        if username in username_to_discord:
            exact_matches.append((username, username_to_discord[username]))
        # Check for case-insensitive match
        elif username_lower in username_to_discord:
            case_insensitive_matches.append((username, username_to_discord[username_lower]))
        else:
            # Check for fuzzy matches (allowing 2-3 character differences)
            best_match = None
            best_similarity = 0.7  # Threshold for fuzzy matching (adjust as needed)
            
            for db_username, discord_id in username_to_discord.items():
                similarity = string_similarity(username, db_username)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = (username, discord_id, db_username, similarity)
            
            if best_match:
                fuzzy_matches.append(best_match)
    
    # Combine all matches
    all_matches = exact_matches + case_insensitive_matches + fuzzy_matches
    
    # Create result message
    result_message = f"Checked {len(username_list)} game usernames for event '{event_name}'.\n"
    result_message += f"Found {len(all_matches)} matching Discord IDs (Exact: {len(exact_matches)}, Case-insensitive: {len(case_insensitive_matches)}, Fuzzy: {len(fuzzy_matches)})."
    
    # Create a text file with the results
    output_file_name = f"{event_name}_username_matches.txt"
    with open(output_file_name, "w", encoding="utf-8") as f:
        f.write(f"Event: {event_name}\n")
        f.write(f"Total usernames checked: {len(username_list)}\n")
        f.write(f"Total matches found: {len(all_matches)}\n")
        f.write(f"- Exact matches: {len(exact_matches)}\n")
        f.write(f"- Case-insensitive matches: {len(case_insensitive_matches)}\n")
        f.write(f"- Fuzzy matches: {len(fuzzy_matches)}\n\n")
        
        if id_only_mode:
            # In ID-only mode, just list the Discord IDs
            f.write("Discord IDs:\n")
            for match in exact_matches:
                f.write(f"{match[1]}\n")
            for match in case_insensitive_matches:
                f.write(f"{match[1]}\n")
            for match in fuzzy_matches:
                f.write(f"{match[1]}\n")
        else:
            # In normal mode, list both username and Discord ID
            if exact_matches:
                f.write("Exact Matches (Game Username : Discord ID):\n")
                for username, discord_id in exact_matches:
                    f.write(f"{username} : {discord_id}\n")
                f.write("\n")
            
            if case_insensitive_matches:
                f.write("Case-Insensitive Matches (Game Username : Discord ID):\n")
                for username, discord_id in case_insensitive_matches:
                    f.write(f"{username} : {discord_id}\n")
                f.write("\n")
            
            if fuzzy_matches:
                f.write("Fuzzy Matches (Game Username : Discord ID : Database Username : Similarity):\n")
                for username, discord_id, db_username, similarity in fuzzy_matches:
                    f.write(f"{username} : {discord_id} : {db_username} : {similarity:.2f}\n")
    
    # Send the results
    await ctx.send(result_message, file=discord.File(output_file_name))

# Alias for checkgameusername with id parameter
@bot.command(name="checkgameusernameid")
async def checkgameusernameid(ctx, event_name: str, *, usernames: str):
    # This is just a convenience alias that calls checkgameusername with the id parameter
    await checkgameusername(ctx, "id", event_name, usernames=usernames)

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
            print("Page loaded, checking content")
            
            # Set to store unique player names
            player_names = set()
            
            # Function to extract names and return how many new names were found
            async def extract_names():
                elements = await page.locator(selector).all()
                initial_count = len(player_names)
                
                for element in elements:
                    try:
                        text = await element.text_content()
                        text = text.strip()
                        if text and len(text) > 0:
                            player_names.add(text)
                    except Exception:
                        continue
                
                return len(player_names) - initial_count
            
            # Initial extraction
            await extract_names()
            print(f"Initial extraction found {len(player_names)} players")
            
            # 1. Try small scrolls first
            print("Starting small scrolls...")
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
            "2. **!setplaylink <event_name> <link> [password xxxxx]**\n"
            "   - Description: Sets the link and optional password for the event.\n"
            "   - Example: `!setplaylink Tournament2025 https://example.com/tournament password 12345`\n\n"
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
            "    - Description: Checks if the provided game usernames match with Discord IDs in the event records. Now supports case-insensitive and fuzzy matching.\n"
            "    - Example: `!checkgameusername Tournament2025 Player1 Player2 Player3`\n\n"
            "17. **!checkgameusername id <event_name> <username1 username2 ...>**\n"
            "    - Description: Same as above, but outputs only the Discord IDs in the text file.\n"
            "    - Example: `!checkgameusername id Tournament2025 Player1 Player2 Player3`\n\n"
            "18. **!checkgameusernameid <event_name> <username1 username2 ...>**\n"
            "    - Description: Alias for the above command, outputs only Discord IDs.\n"
            "    - Example: `!checkgameusernameid Tournament2025 Player1 Player2 Player3`\n\n"
            "19. **!getusername <url> <selector>**\n"
            "    - Description: Extracts player names from a webpage using the specified selector and saves them to a text file.\n"
            "    - Example: `!getusername https://app.lepoker.io/m/lj2Dxdy/players \"div.truncate\"`\n\n"
            "20. **!playhelp**\n"
            "    - Description: Shows this help menu.\n"
        ),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

# ---------------- CAPTCHA Verification Functions ----------------

def _check_captcha_rate_limit(user_id: int) -> bool:
    """Check if user is within rate limit for captcha requests"""
    current_time = time.time()
    user_requests = captcha_rate_limits[user_id]
    
    # Remove old requests outside the window
    user_requests[:] = [req_time for req_time in user_requests if current_time - req_time < CAPTCHA_RATE_WINDOW]
    
    # Check if user has exceeded rate limit
    if len(user_requests) >= CAPTCHA_RATE_LIMIT:
        return False
    
    return True

def _add_captcha_rate_limit_request(user_id: int):
    """Add a request to the rate limit tracker"""
    current_time = time.time()
    captcha_rate_limits[user_id].append(current_time)


def _generate_captcha_code(length: int = 6) -> str:
    # Avoid ambiguous characters like 0/O and 1/I
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(alphabet) for _ in range(length))


def _create_text_image(code: str) -> bytes:
    """Creates simple text image"""
    width, height = 300, 100
    # Light background
    bg_color = (245, 245, 245)
    text_color = (30, 30, 30)
    
    image = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(image)
    
    # Font loading
    font = None
    possible_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for fp in possible_fonts:
        try:
            font = ImageFont.truetype(fp, 48)
            break
        except Exception:
            pass
    if font is None:
        font = ImageFont.load_default()
    
    # Center text
    try:
        bbox = draw.textbbox((0, 0), code, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        # Old PIL version
        text_width, text_height = draw.textsize(code, font=font)
    
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    # Draw text
    draw.text((x, y), code, font=font, fill=text_color)
    
    # Add light noise
    for _ in range(50):
        x_noise = random.randint(0, width - 1)
        y_noise = random.randint(0, height - 1)
        image.putpixel((x_noise, y_noise), (
            random.randint(200, 240),
            random.randint(200, 240), 
            random.randint(200, 240)
        ))
    
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class CaptchaModal(discord.ui.Modal):
    def __init__(self, expected_code: str, verify_role_id: int, user_id: int = None, show_code_hint: bool = False):
        super().__init__(title="Captcha Verification")
        self.expected_code = expected_code
        self.verify_role_id = verify_role_id
        self.user_id = user_id
        self.answer_input = discord.ui.TextInput(
            label=(f"Enter code: {expected_code}" if show_code_hint else "Enter code"),
            placeholder="Type the code here",
            min_length=1,
            max_length=12,
            required=True,
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction):
        provided = (self.answer_input.value or "").strip()
        if provided != self.expected_code:
            await interaction.response.send_message(
                "Incorrect code. Please click the verification button again to retry.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This action can only be performed within a server.", ephemeral=True
            )
            return

        role = guild.get_role(self.verify_role_id)
        if role is None:
            await interaction.response.send_message(
                "Verification role not found. Please contact an administrator.",
                ephemeral=True,
            )
            return

        # Ensure we have a Member object
        member = interaction.user
        if not isinstance(member, discord.Member):
            try:
                member = await guild.fetch_member(interaction.user.id)
            except Exception:
                member = None

        if member is None:
            await interaction.response.send_message(
                "Unable to retrieve member information.", ephemeral=True
            )
            return

        # If already verified
        if any(r.id == role.id for r in getattr(member, "roles", [])):
            await interaction.response.send_message(
                "You are already verified.", ephemeral=True
            )
            return

        try:
            await member.add_roles(role, reason="Captcha verified")
        except discord.Forbidden:
            await interaction.response.send_message(
                "Unable to assign role: Bot lacks permissions or role hierarchy prevents this action.",
                ephemeral=True,
            )
            return
        except Exception:
            await interaction.response.send_message(
                "An error occurred while assigning the role.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Success! {role.mention} role has been assigned.", ephemeral=True
        )
        
        # Clean up session after successful verification
        if self.user_id:
            active_captcha_sessions.discard(self.user_id)
            print(f"[captcha] Successfully verified user {self.user_id}")


class CaptchaVerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify",
        style=discord.ButtonStyle.success,
        custom_id="captcha_verify_button",
    )
    async def verify_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # This method is now handled by the on_interaction event handler
        # to prevent double acknowledgment issues
        pass


class CaptchaCodeEntryView(discord.ui.View):
    def __init__(self, expected_code: str, verify_role_id: int, user_id: int):
        super().__init__(timeout=180)
        self.expected_code = expected_code
        self.verify_role_id = verify_role_id
        self.user_id = user_id

    @discord.ui.button(label="Enter Code", style=discord.ButtonStyle.primary, custom_id="captcha_enter_code")
    async def enter_code(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # Only allow the original user to use this button
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This captcha is not for you.", ephemeral=True
            )
            return
            
        await interaction.response.send_modal(CaptchaModal(self.expected_code, self.verify_role_id, self.user_id))

    async def on_timeout(self):
        # Clean up session when view times out
        active_captcha_sessions.discard(self.user_id)
        print(f"[captcha] Session timeout for user {self.user_id}")

# ---------------- Regex Moderation Commands ----------------

# Define or update a regex rule
@bot.command(name="regex")
async def define_regex(ctx, regexsettingsname: str, *, regexcommand: str):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    name_key = regexsettingsname.strip().lower()
    # Accept extended syntaxes: /pattern/flags or plain pattern with optional --flags i m s x ...
    pattern_text, flags_letters = _parse_pattern_and_flags(regexcommand)
    try:
        compiled = _compile_with_flags(pattern_text, flags_letters)
    except re.error as e:
        await ctx.send(f"Invalid regex: {e}")
        return
    guild_id = ctx.guild.id
    if guild_id not in regex_settings_by_guild:
        regex_settings_by_guild[guild_id] = {}
    settings = regex_settings_by_guild[guild_id].get(name_key, {"channels": set(), "exempt_users": set(), "exempt_roles": set()})
    settings["pattern"] = regexcommand
    settings["compiled"] = compiled
    regex_settings_by_guild[guild_id][name_key] = settings
    save_settings()
    if settings["channels"]:
        ch_mentions = ", ".join(f"<#{cid}>" for cid in settings["channels"])
        await ctx.send(
            f"Regex setting updated: `{regexsettingsname}`\n"
            f"Pattern: `{regexcommand}`\n"
            f"Engine: `{_REGEX_ENGINE_NAME}`  Flags: `{flags_letters or '-'}`\n"
            f"Applied channels: {ch_mentions}"
        )
    else:
        await ctx.send(
            f"Regex setting saved: `{regexsettingsname}`\n"
            f"Pattern: `{regexcommand}`\n"
            f"Engine: `{_REGEX_ENGINE_NAME}`  Flags: `{flags_letters or '-'}`\n"
            f"No channels assigned yet. Use `!setregexsettings {regexsettingsname} <channels>` to assign."
        )

# Assign channels to a regex rule
@bot.command(name="setregexsettings")
async def set_regex_settings(ctx, regexsettingsname: str, *, channels: str):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    guild_id = ctx.guild.id
    name_key = regexsettingsname.strip().lower()
    guild_rules = regex_settings_by_guild.get(guild_id)
    if not guild_rules or name_key not in guild_rules:
        await ctx.send("Please create the regex rule first: `!regex <regexsettingsname> <regex>`")
        return
    tokens = channels.replace(",", " ").split()
    lower_tokens = [t.lower() for t in tokens]
    selected: set[int] = set()
    invalid: list[str] = []

    # Helper: parse channel-like token into channel id (if valid)
    def _parse_channel_token(token: str):
        raw = token.strip()
        if raw.startswith("<#") and raw.endswith(">"):
            raw = raw[2:-1]
        try:
            cid_local = int(raw)
        except ValueError:
            return None
        channel_local = ctx.guild.get_channel(cid_local)
        if channel_local is None:
            return None
        return cid_local

    if "allchannel" in lower_tokens:
        # Start with all text channels
        for ch in ctx.guild.text_channels:
            selected.add(ch.id)

        if "notchannel" in lower_tokens:
            idx = lower_tokens.index("notchannel")
            exclude_tokens = tokens[idx + 1 :]
            if not exclude_tokens:
                # No exclusions provided; proceed with all text channels
                pass
            else:
                exclude_ids: set[int] = set()
                for tok in exclude_tokens:
                    cid = _parse_channel_token(tok)
                    if cid is None:
                        invalid.append(tok)
                    else:
                        exclude_ids.add(cid)
                selected -= exclude_ids
    else:
        if "notchannel" in lower_tokens:
            await ctx.send("Use `notchannel` only together with `allchannel`. Example: `!setregexsettings spamRule allchannel notchannel #channel1 #channel2`")
            return
        for tok in tokens:
            cid = _parse_channel_token(tok)
            if cid is None:
                invalid.append(tok)
                continue
            selected.add(cid)

    if not selected:
        await ctx.send("Please specify valid channels. Examples: `!setregexsettings spamRule #general #chat` or `!setregexsettings spamRule allchannel notchannel #log #mod`")
        return

    guild_rules[name_key]["channels"] = selected
    save_settings()
    ch_mentions = ", ".join(f"<#{cid}>" for cid in selected)
    msg = f"Applied channels updated for `{regexsettingsname}`: {ch_mentions}"
    if invalid:
        msg += f"\nIgnored/Invalid: {' '.join(invalid)}"
    await ctx.send(msg)

# Set exemptions (users or roles) for a regex rule
@bot.command(name="setregexexempt")
async def set_regex_exempt(ctx, regexsettingsname: str, kind: str, *, targets: str):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    guild_id = ctx.guild.id
    name_key = regexsettingsname.strip().lower()
    guild_rules = regex_settings_by_guild.get(guild_id)
    if not guild_rules or name_key not in guild_rules:
        await ctx.send("Please create the regex rule first: `!regex <regexsettingsname> <regex>`")
        return
    kind_l = kind.strip().lower()
    if kind_l not in ("users", "roles"):
        await ctx.send("Please specify a type: `users` or `roles`. Example: `!setregexexempt spam users @u1 @u2` or `!setregexexempt spam roles @role1 @role2`")
        return
    tokens = targets.replace(",", " ").split()
    selected: set[int] = set()
    invalid = []
    for tok in tokens:
        raw = tok.strip()
        # Normalize mentions
        if kind_l == "roles":
            if raw.startswith("<@&") and raw.endswith(">"):
                raw = raw[3:-1]
        else:  # users
            if raw.startswith("<@!") and raw.endswith(">"):
                raw = raw[3:-1]
            elif raw.startswith("<@") and raw.endswith(">"):
                raw = raw[2:-1]
        try:
            _id = int(raw)
        except ValueError:
            invalid.append(tok)
            continue
        if kind_l == "roles":
            role = ctx.guild.get_role(_id)
            if role is None:
                invalid.append(tok)
                continue
        else:
            member = ctx.guild.get_member(_id)
            if member is None:
                invalid.append(tok)
                continue
        selected.add(_id)
    if not selected:
        await ctx.send("Please specify valid targets. Examples:\n- `!setregexexempt spam users @alice @bob`\n- `!setregexexempt spam roles @Admin 123456789012345678`")
        return
    if kind_l == "roles":
        guild_rules[name_key]["exempt_roles"] = selected
        save_settings()
        mentions = ", ".join(f"<@&{i}>" for i in selected)
        msg = f"Exempt roles updated for `{regexsettingsname}`: {mentions}"
    else:
        guild_rules[name_key]["exempt_users"] = selected
        save_settings()
        mentions = ", ".join(f"<@{i}>" for i in selected)
        msg = f"Exempt users updated for `{regexsettingsname}`: {mentions}"
    if invalid:
        msg += f"\nIgnored/Invalid: {' '.join(invalid)}"
    await ctx.send(msg)

# Show regex settings (all or specific)
@bot.command(name="regexsettings")
async def regexsettings(ctx, regexsettingsname: str = None):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    guild_id = ctx.guild.id
    guild_rules = regex_settings_by_guild.get(guild_id)
    if not guild_rules:
        await ctx.send("There are no regex settings defined in this server.")
        return

    def _mentions_list(ids: set[int], kind: str, max_items: int = 10) -> str:
        if not ids:
            return "None"
        ids_list = list(ids)
        if len(ids_list) > max_items:
            # Show first few items and count
            if kind == "channel":
                shown = ", ".join(f"<#{i}>" for i in ids_list[:max_items])
                return f"{shown} ... (+{len(ids_list) - max_items} more)"
            elif kind == "user":
                shown = ", ".join(f"<@{i}>" for i in ids_list[:max_items])
                return f"{shown} ... (+{len(ids_list) - max_items} more)"
            elif kind == "role":
                shown = ", ".join(f"<@&{i}>" for i in ids_list[:max_items])
                return f"{shown} ... (+{len(ids_list) - max_items} more)"
        else:
            if kind == "channel":
                return ", ".join(f"<#{i}>" for i in ids_list)
            elif kind == "user":
                return ", ".join(f"<@{i}>" for i in ids_list)
            elif kind == "role":
                return ", ".join(f"<@&{i}>" for i in ids_list)
        return "None"

    if regexsettingsname:
        name_key = regexsettingsname.strip().lower()
        rule = guild_rules.get(name_key)
        if not rule:
            await ctx.send("No regex setting found with the specified name.")
            return
        pattern_text = rule.get("pattern", "-")
        # Truncate very long patterns
        if len(pattern_text) > 100:
            pattern_text = pattern_text[:97] + "..."
            
        channels = rule.get("channels", set())
        exempt_users = rule.get("exempt_users", set())
        exempt_roles = rule.get("exempt_roles", set())
        status = "Active" if channels else "Inactive"

        embed = discord.Embed(title=f"Regex Settings - {regexsettingsname}", color=discord.Color.blue())
        embed.add_field(name="Status", value=status, inline=False)
        embed.add_field(name="Pattern", value=f"`{pattern_text}`", inline=False)
        embed.add_field(name="Applied Channels", value=_mentions_list(channels, "channel"), inline=False)
        embed.add_field(name="Exempt Users", value=_mentions_list(exempt_users, "user"), inline=False)
        embed.add_field(name="Exempt Roles", value=_mentions_list(exempt_roles, "role"), inline=False)
        await ctx.send(embed=embed)
        return

    # List all rules - Split into multiple embeds if needed
    rules_list = list(guild_rules.items())
    if not rules_list:
        await ctx.send("No regex settings found in this server.")
        return
    
    # Split rules into chunks to avoid embed limits
    chunk_size = 5  # Max 5 rules per embed
    for i in range(0, len(rules_list), chunk_size):
        chunk = rules_list[i:i + chunk_size]
        
        if i == 0:
            embed = discord.Embed(title="Regex Settings", color=discord.Color.blue())
        else:
            embed = discord.Embed(title=f"Regex Settings (Page {i//chunk_size + 1})", color=discord.Color.blue())
        
        for name_key, rule in chunk:
            pattern_text = rule.get("pattern", "-")
            # Truncate very long patterns
            if len(pattern_text) > 50:
                pattern_text = pattern_text[:47] + "..."
                
            channels = rule.get("channels", set())
            exempt_users = rule.get("exempt_users", set())
            exempt_roles = rule.get("exempt_roles", set())
            status = "Active" if channels else "Inactive"
            
            # Create shorter field values
            channels_text = _mentions_list(channels, "channel", 3)
            users_text = _mentions_list(exempt_users, "user", 3)
            roles_text = _mentions_list(exempt_roles, "role", 3)
            
            value = (
                f"**Status:** {status}\n"
                f"**Pattern:** `{pattern_text}`\n"
                f"**Channels:** {channels_text}\n"
                f"**Exempt Users:** {users_text}\n"
                f"**Exempt Roles:** {roles_text}"
            )
            
            # Ensure field value doesn't exceed 1024 characters
            if len(value) > 1020:
                value = value[:1017] + "..."
            
            embed.add_field(name=name_key, value=value, inline=False)
        
        # Check if embed is getting too large
        if len(embed) > 5500:  # Leave some buffer
            # Remove last field and send
            embed.remove_field(-1)
            await ctx.send(embed=embed)
            # Create new embed with the removed field
            embed = discord.Embed(title=f"Regex Settings (Continued)", color=discord.Color.blue())
            name_key, rule = chunk[-1]
            pattern_text = rule.get("pattern", "-")
            if len(pattern_text) > 50:
                pattern_text = pattern_text[:47] + "..."
            channels = rule.get("channels", set())
            exempt_users = rule.get("exempt_users", set())
            exempt_roles = rule.get("exempt_roles", set())
            status = "Active" if channels else "Inactive"
            channels_text = _mentions_list(channels, "channel", 3)
            users_text = _mentions_list(exempt_users, "user", 3)
            roles_text = _mentions_list(exempt_roles, "role", 3)
            value = (
                f"**Status:** {status}\n"
                f"**Pattern:** `{pattern_text}`\n"
                f"**Channels:** {channels_text}\n"
                f"**Exempt Users:** {users_text}\n"
                f"**Exempt Roles:** {roles_text}"
            )
            if len(value) > 1020:
                value = value[:1017] + "..."
            embed.add_field(name=name_key, value=value, inline=False)
        
        await ctx.send(embed=embed)

# Delete a regex setting by name
@bot.command(name="delregexsettings")
async def delregexsettings(ctx, regexsettingsname: str):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    guild_id = ctx.guild.id
    guild_rules = regex_settings_by_guild.get(guild_id)
    if not guild_rules:
        await ctx.send("There are no regex settings defined in this server.")
        return
    name_key = regexsettingsname.strip().lower()
    if name_key not in guild_rules:
        await ctx.send("No regex setting found with the specified name.")
        return
    del guild_rules[name_key]
    if not guild_rules:
        try:
            del regex_settings_by_guild[guild_id]
        except KeyError:
            pass
    save_settings()
    await ctx.send(f"Regex setting deleted: `{regexsettingsname}`")

# ---------------- CAPTCHA Verification Commands ----------------

@bot.event
async def on_ready():
    # Load settings from file
    load_settings()
    
    # Register persistent view so button keeps working after restart
    try:
        bot.add_view(CaptchaVerifyView())
    except Exception:
        pass
    print(f"Logged in as {bot.user} (ID: {getattr(bot.user, 'id', '-')})")
    print("[SETTINGS] Bot ready with loaded settings")


@bot.command(name="setverifyrole")
async def setverifyrole(ctx, role_identifier: str):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    global captcha_verify_role_id

    raw = role_identifier.strip()
    if raw.startswith("<@&") and raw.endswith(">"):
        raw = raw[3:-1]
    try:
        rid = int(raw)
    except ValueError:
        await ctx.send("Please enter a valid role ID or role mention.")
        return
    role = ctx.guild.get_role(rid)
    if role is None:
        await ctx.send("No role found with this ID.")
        return
    captcha_verify_role_id = rid
    save_settings()
    await ctx.send(f"Verification role set: {role.mention} ({rid})")


@bot.command(name="setverifypaneltext")
async def setverifypaneltext(ctx, text_type: str, *, content: str):
    # Debug: Command triggered
    print(f"[DEBUG] setverifypaneltext command triggered by {ctx.author} with type: {text_type}")
    
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        print(f"[DEBUG] User {ctx.author} not authorized")
        return
    
    print(f"[DEBUG] User authorized, processing...")
    
    guild_id = ctx.guild.id
    text_type = text_type.lower().strip()
    
    print(f"[DEBUG] Text type: {text_type}, Content length: {len(content)}")
    
    if text_type not in ["title", "description", "image"]:
        await ctx.send("Please specify either `title`, `description`, or `image`. Examples:\n• `!setverifypaneltext title Welcome to Our Server`\n• `!setverifypaneltext image https://example.com/image.png`")
        print(f"[DEBUG] Invalid text type: {text_type}")
        return
    
    if text_type == "image":
        print(f"[DEBUG] Processing image URL: {content[:100]}...")
        
        # Validate URL format (expanded check for various platforms)
        content_lower = content.lower()
        
        # Check for valid URL protocols
        valid_protocols = [
            "http://", "https://", "blob:", "data:"
        ]
        
        print(f"[DEBUG] Checking protocols...")
        if not any(content.startswith(protocol) for protocol in valid_protocols):
            await ctx.send("Image must be a valid URL starting with http://, https://, blob:, or data:")
            print(f"[DEBUG] Invalid protocol in URL: {content[:50]}")
            return
        
        print(f"[DEBUG] Protocol check passed")
        
        # Special handling for different URL types
        print(f"[DEBUG] Starting platform validation...")
        is_discord_cdn = ("cdn.discordapp.com" in content_lower or 
                         "media.discordapp.net" in content_lower or
                         "images-ext-1.discordapp.net" in content_lower or
                         "images-ext-2.discordapp.net" in content_lower or
                         "discordapp.com/attachments" in content_lower or
                         "discord.com/attachments" in content_lower)
        print(f"[DEBUG] Discord CDN check: {is_discord_cdn}")
        is_whatsapp = "web.whatsapp.com" in content_lower or "whatsapp" in content_lower
        is_blob_url = content.startswith("blob:")
        is_data_url = content.startswith("data:image/")
        is_gif_platform = any(platform in content_lower for platform in [
            "giphy.com", "tenor.com", "gfycat.com", "reddit.com", "redgifs.com"
        ])
        is_video_platform = any(platform in content_lower for platform in [
            "youtube.com", "youtu.be", "vimeo.com", "streamable.com", "twitch.tv", "tiktok.com"
        ])
        is_special_platform = any(platform in content_lower for platform in [
            "imgur.com", "gyazo.com", "prntscr.com", "lightshot.com", 
            "github.com", "githubusercontent.com", "telegram.org", "steamcommunity.com"
        ])
        
        # Check file extensions for regular URLs (images and videos)
        valid_extensions = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".mp4", ".mov", ".avi", ".webm", ".mkv"]
        has_valid_extension = any(content_lower.endswith(ext) for ext in valid_extensions)
        
        # Debug: Show which validations passed/failed
        print(f"[DEBUG] All platform checks completed")
        print(f"[DEBUG] Final validation results:")
        print(f"[DEBUG] - Discord CDN: {is_discord_cdn}")
        print(f"[DEBUG] - WhatsApp: {is_whatsapp}")
        print(f"[DEBUG] - Blob URL: {is_blob_url}")
        print(f"[DEBUG] - Data URL: {is_data_url}")
        print(f"[DEBUG] - GIF Platform: {is_gif_platform}")
        print(f"[DEBUG] - Video Platform: {is_video_platform}")
        print(f"[DEBUG] - Special Platform: {is_special_platform}")
        print(f"[DEBUG] - Valid Extension: {has_valid_extension}")
        
        debug_info = f"🔍 **URL Validation Debug:**\n"
        debug_info += f"URL: `{content[:100]}{'...' if len(content) > 100 else ''}`\n"
        debug_info += f"Discord CDN: {'✅' if is_discord_cdn else '❌'}\n"
        debug_info += f"WhatsApp: {'✅' if is_whatsapp else '❌'}\n"
        debug_info += f"Blob URL: {'✅' if is_blob_url else '❌'}\n"
        debug_info += f"Data URL: {'✅' if is_data_url else '❌'}\n"
        debug_info += f"GIF Platform: {'✅' if is_gif_platform else '❌'}\n"
        debug_info += f"Video Platform: {'✅' if is_video_platform else '❌'}\n"
        debug_info += f"Special Platform: {'✅' if is_special_platform else '❌'}\n"
        debug_info += f"Valid Extension: {'✅' if has_valid_extension else '❌'}\n"
        
        # Allow URL if it meets any of these criteria
        validation_passed = (is_discord_cdn or is_whatsapp or is_blob_url or is_data_url or 
                            is_gif_platform or is_video_platform or is_special_platform or has_valid_extension)
        print(f"[DEBUG] Overall validation result: {validation_passed}")
        
        if not validation_passed:
            
            embed = discord.Embed(
                title="❌ Image URL Validation Failed",
                description=debug_info,
                color=discord.Color.red()
            )
            embed.add_field(
                name="Supported URL Types",
                value=(
                    "• End with a valid image/video extension (.png, .jpg, .jpeg, .gif, .webp, .bmp, .svg, .mp4, .mov, .avi, .webm, .mkv)\n"
                    "• Be a Discord CDN link (cdn.discordapp.com, discord.com/attachments)\n"
                    "• Be a WhatsApp Web link\n"
                    "• Be a blob: or data: URL\n"
                    "• Be from a GIF platform (Giphy, Tenor, Gfycat, Reddit)\n"
                    "• Be from a video platform (YouTube, Vimeo, Streamable, TikTok)\n"
                    "• Be from a supported platform (Imgur, GitHub, Steam, etc.)"
                ),
                inline=False
            )
            await ctx.send(embed=embed)
            return
        else:
            # Success - show which validation passed
            print(f"[DEBUG] Validation passed! Sending success message...")
            success_embed = discord.Embed(
                title="✅ Image URL Validation Passed",
                description=debug_info,
                color=discord.Color.green()
            )
            await ctx.send(embed=success_embed)
            print(f"[DEBUG] Success message sent")
    
    if len(content) > 256 and text_type == "title":
        await ctx.send("Title must be 256 characters or less.")
        return
    
    if len(content) > 2048 and text_type == "description":
        await ctx.send("Description must be 2048 characters or less.")
        return
    
    if guild_id not in captcha_panel_texts:
        captcha_panel_texts[guild_id] = {
            "title": DEFAULT_PANEL_TITLE,
            "description": DEFAULT_PANEL_DESCRIPTION,
            "image": None
        }
    
    captcha_panel_texts[guild_id][text_type] = content
    save_settings()
    
    if text_type == "image":
        await ctx.send(f"Verification panel image updated successfully!\nImage URL: {content}")
    else:
        await ctx.send(f"Verification panel {text_type} updated successfully!")


@bot.command(name="showverifypaneltext")
async def showverifypaneltext(ctx):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    
    guild_id = ctx.guild.id
    panel_text = captcha_panel_texts.get(guild_id, {
        "title": DEFAULT_PANEL_TITLE,
        "description": DEFAULT_PANEL_DESCRIPTION,
        "image": None
    })
    
    embed = discord.Embed(
        title="Current Verification Panel Text",
        color=discord.Color.blue()
    )
    embed.add_field(name="Title", value=f"```{panel_text['title']}```", inline=False)
    embed.add_field(name="Description", value=f"```{panel_text['description']}```", inline=False)
    
    image_url = panel_text.get('image')
    if image_url:
        embed.add_field(name="Image URL", value=f"```{image_url}```", inline=False)
    else:
        embed.add_field(name="Image URL", value="```Not set```", inline=False)
    
    embed.add_field(
        name="Usage", 
        value="• `!setverifypaneltext title <new title>`\n• `!setverifypaneltext description <new description>`\n• `!setverifypaneltext image <image_url>`", 
        inline=False
    )
    
    await ctx.send(embed=embed)


@bot.command(name="resetverifypaneltext")
async def resetverifypaneltext(ctx):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return
    
    guild_id = ctx.guild.id
    if guild_id in captcha_panel_texts:
        del captcha_panel_texts[guild_id]
    save_settings()
    
    await ctx.send("Verification panel text reset to default values.")


@bot.command(name="sendverifypanel")
async def sendverifypanel(ctx, channel: str = None):
    if not is_security_authorized(ctx):
        await ctx.message.delete()
        return

    target_channel = ctx.channel
    if channel:
        raw = channel.strip()
        if raw.startswith("<#") and raw.endswith(">"):
            raw = raw[2:-1]
        try:
            cid = int(raw)
            ch = ctx.guild.get_channel(cid)
            if ch is not None:
                target_channel = ch
        except ValueError:
            pass

    # Get custom panel text for this guild or use defaults
    guild_id = ctx.guild.id
    panel_text = captcha_panel_texts.get(guild_id, {
        "title": DEFAULT_PANEL_TITLE,
        "description": DEFAULT_PANEL_DESCRIPTION,
        "image": None
    })

    embed = discord.Embed(
        title=panel_text["title"],
        description=panel_text["description"],
        color=discord.Color.green(),
    )
    
    # Add image if set
    image_url = panel_text.get("image")
    if image_url:
        embed.set_image(url=image_url)
    try:
        await target_channel.send(embed=embed, view=CaptchaVerifyView())
        await ctx.send(f"Verification panel sent to: {target_channel.mention}")
    except Exception as e:
        await ctx.send("Failed to send verification panel.")

# Get bot token from environment variable
bot_token = os.getenv("PLAYBOT")
if not bot_token:
    bot_token = "BOTTOKENHERE"  # Fallback to hardcoded token if env var not set

bot.run(bot_token)
