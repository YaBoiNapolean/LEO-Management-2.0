import sys

# Trick discord.py into finding the audioop module if it's missing in Python 3.13
try:
    import audioop
except ImportError:
    try:
        from pip._internal import main as pipmain
        pipmain(['install', 'audioop-lts'])
        import audioop
    except Exception:
        # If automatic installation fails, manually mock the module so discord.py stops crashing
        import types
        mock_audioop = types.ModuleType('audioop')
        mock_audioop.error = Exception
        sys.modules['audioop'] = mock_audioop
import os
import discord
import asyncio
import aiosqlite
import aiohttp
import random
import string
import resource
import time
from discord.ext import commands
from discord import app_commands, ui
from datetime import datetime, timedelta, timezone

# --- CONFIGURATION ---
DATABASE = '/data/gsp_bot.db' 

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)
bot_start_time = time.monotonic()

# Visual Identity (embed colors)
GSP_CUSTOM_ORANGE = discord.Color.from_str("#0f13ff")
GSP_RED = discord.Color.red()
GSP_YELLOW = 0xFFFF00
SEPARATOR = "~~━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━~~"

# Restrict commands only to GSP and FBI command channels
ALLOWED_CMD_CHANNELS = [
    1491403907329556630,  # GSP Commands
    1513513472938475530   # FBI Commands
]

# --- GUILD REGISTRY ---
# Stores settings, channels, and roles for each department.
# Add or update Guild IDs and Channel IDs here.
GUILD_SETTINGS = {
    1471660122035195916: {  # Georgia State Patrol (GSP)
        'name': 'GSP',
        'cmd_channel': 1491403907329556630,
        'channels': {
            'arrest_logs': 1491396788287045784,
            'citation_logs': 1491401885280637031,
            'infractions': 1491402935341678634,
            'strike_confirm': 1491893789952835584,
            'bolo_logs': 1491403907329556630,       # Local cmd channel fallback
            'warrant_logs': 1491403907329556630     # Local cmd channel fallback
        },
        'roles': {
            'strike_1': 1489800614098505858,
            'strike_2': 1489800660978499727,
            'up_for_ban': 1489800716452102255,
            'strike_confirmer': 1491765593639096351,
            'supervisor': 1491916962861940947
        }
    },
    1511837991503401031: {  # Federal Bureau of Investigation (FBI)
        'name': 'FBI',
        'cmd_channel': 1513513472938475530,
        'channels': {
            'arrest_logs': 1513513057576419349,
            'citation_logs': 1513513121527107715,
            'infractions': 1513513221519048816,
            'strike_confirm': 1513513274849886398,
            'bolo_logs': 1513513472938475530,       # Local cmd channel fallback
            'warrant_logs': 1513513472938475530     # Local cmd channel fallback
        },
        'roles': {
            'strike_1': 1513563614932631642,
            'strike_2': 1513563652719120505,
            'up_for_ban': 1513563721832599623,
            'strike_confirmer': 1513563799075164322,
            'supervisor': 1513563836379168788
        }
    },
    # --- Placeholders for other servers (fill in IDs when ready) ---
    111111111111111111: {  # Fulton County Sheriff’s Office (FCSO) - Example Guild ID
        'name': 'FCSO',
        'cmd_channel': 0,
        'channels': {
            'arrest_logs': 0,
            'citation_logs': 0,
            'infractions': 0,
            'strike_confirm': 0,
            'bolo_logs': 0,
            'warrant_logs': 0
        },
        'roles': {
            'strike_1': 0,
            'strike_2': 0,
            'up_for_ban': 0,
            'strike_confirmer': 0,
            'supervisor': 0
        }
    },
    222222222222222222: {  # Department of Homeland Security (DHS) - Example Guild ID
        'name': 'DHS',
        'cmd_channel': 0,
        'channels': {
            'arrest_logs': 0,
            'citation_logs': 0,
            'infractions': 0,
            'strike_confirm': 0,
            'bolo_logs': 0,
            'warrant_logs': 0
        },
        'roles': {
            'strike_1': 0,
            'strike_2': 0,
            'up_for_ban': 0,
            'strike_confirmer': 0,
            'supervisor': 0
        }
    },
    333333333333333333: {  # United States Marshals Service (USMS) - Example Guild ID
        'name': 'USMS',
        'cmd_channel': 0,
        'channels': {
            'arrest_logs': 0,
            'citation_logs': 0,
            'infractions': 0,
            'strike_confirm': 0,
            'bolo_logs': 0,
            'warrant_logs': 0
        },
        'roles': {
            'strike_1': 0,
            'strike_2': 0,
            'up_for_ban': 0,
            'strike_confirmer': 0,
            'supervisor': 0
        }
    },
    444444444444444444: {  # Atlanta Police Department (APD) - Example Guild ID
        'name': 'APD',
        'cmd_channel': 0,
        'channels': {
            'arrest_logs': 0,
            'citation_logs': 0,
            'infractions': 0,
            'strike_confirm': 0,
            'bolo_logs': 0,
            'warrant_logs': 0
        },
        'roles': {
            'strike_1': 0,
            'strike_2': 0,
            'up_for_ban': 0,
            'strike_confirmer': 0,
            'supervisor': 0
        }
    }
}

# --- DATABASE & UTILITIES ---

def get_setting(guild_id, key, subkey=None):
    """Safely retrieves channel/role settings, falling back to GSP if guild is missing."""
    config = GUILD_SETTINGS.get(guild_id)
    if not config:
        config = GUILD_SETTINGS[1471660122035195916] # Fallback to GSP
    if subkey:
        return config.get(key, {}).get(subkey)
    return config.get(key)

def get_pst_time():
    utc_now = datetime.now(timezone.utc)
    pst_now = utc_now - timedelta(hours=8)
    return pst_now.strftime('%B %d, %Y at %H:%M')

def format_time_ago(ts_string):
    try:
        past = datetime.strptime(ts_string, '%B %d, %Y at %H:%M')
        now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=8)
        diff = now - past
        if diff.days > 0: return f"{diff.days} days ago"
        hours = diff.seconds // 3600
        if hours > 0: return f"{hours} hours ago"
        return f"{diff.seconds // 60} minutes ago"
    except:
        return "Unknown"
    
def get_separator(color_hex: str) -> str:
    """Return the registered blue-line emoji or the standard text separator."""
    if isinstance(color_hex, discord.Color):
        clean_hex = str(color_hex).replace('#', '').lower()
    else:
        clean_hex = str(color_hex).replace('#', '').lower()

    # If the embed is your specific blue, use your new emoji line
    if clean_hex == "0f13ff":
        return "<:blue_line:1515792202377203753>" * 12

    # Otherwise, fall back to your original text line string
    return "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

def format_uptime(seconds: float) -> str:
    total_seconds = int(seconds)
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)
async def init_db():
    db_dir = os.path.dirname(DATABASE)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS arrests (id_code TEXT PRIMARY KEY, suspect TEXT, officer_id INTEGER, secondaries TEXT, charges TEXT, mugshot TEXT, timestamp TEXT, guild_id INTEGER)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS citations (id_code TEXT PRIMARY KEY, suspect TEXT, officer_id INTEGER, vehicle TEXT, location TEXT, reason TEXT, timestamp TEXT, guild_id INTEGER)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS bolos (id_code TEXT PRIMARY KEY, suspect TEXT, officer_id INTEGER, reason TEXT, vehicle TEXT, plate TEXT, expiry_timestamp TEXT, timestamp TEXT, guild_id INTEGER)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS warrants (id_code TEXT PRIMARY KEY, suspect TEXT, officer_id INTEGER, reason TEXT, risk_level TEXT, expiry_timestamp TEXT, timestamp TEXT, guild_id INTEGER)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS infractions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, issuer_id INTEGER, reason TEXT, punishment TEXT, proof TEXT, msg_url TEXT, is_active INTEGER DEFAULT 1, is_processed INTEGER DEFAULT 0, expiry_timestamp TEXT, timestamp TEXT, guild_id INTEGER)''')
        
        # Migrates existing tables seamlessly
        for tbl in ["arrests", "citations", "bolos", "warrants", "infractions"]:
            try:
                await db.execute(f"ALTER TABLE {tbl} ADD COLUMN guild_id INTEGER")
            except aiosqlite.OperationalError:
                pass 
        await db.commit()

async def generate_unique_id():
    async with aiosqlite.connect(DATABASE) as db:
        while True:
            new_id = f"GSP{''.join(random.choices(string.digits, k=4))}"
            query = "SELECT 1 FROM arrests WHERE id_code = ? UNION SELECT 1 FROM citations WHERE id_code = ? UNION SELECT 1 FROM bolos WHERE id_code = ? UNION SELECT 1 FROM warrants WHERE id_code = ?"
            async with db.execute(query, (new_id, new_id, new_id, new_id)) as cursor:
                if not await cursor.fetchone(): return new_id

async def is_cmd_channel(itx: discord.Interaction):
    if itx.channel.id not in ALLOWED_CMD_CHANNELS:
        if not itx.response.is_done():
            await itx.response.send_message(f"❌ Commands restricted to authorized command channels.", ephemeral=True)
        return False
    return True

async def broadcast_log(bot, embed, log_type, origin_guild_id):
    """Broadcasts logging embeds to all other configured guilds besides the source guild."""
    for guild_id, config in GUILD_SETTINGS.items():
        if guild_id == origin_guild_id or guild_id in [0, 1, 2, 3, 111111111111111111, 222222222222222222, 333333333333333333, 444444444444444444]:
            continue # Don't send back to the origin, and skip unconfigured placeholders
            
        channel_id = config.get('channels', {}).get(log_type)
        if not channel_id or channel_id == 0:
            continue
            
        try:
            guild = bot.get_guild(guild_id) or await bot.fetch_guild(guild_id)
            if guild:
                channel = guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)
                if channel:
                    await channel.send(embed=embed)
        except Exception as e:
            print(f"Failed to broadcast log type '{log_type}' to Guild {guild_id}: {e}")

# --- UI COMPONENTS ---

class ClearAllDataView(ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @ui.button(label="Confirm Wipe", style=discord.ButtonStyle.success)
    async def confirm(self, itx: discord.Interaction, button: ui.Button):
        if not itx.user.guild_permissions.administrator:
            return await itx.response.send_message("❌ Only Administrators can confirm a database wipe.", ephemeral=True)
        async with aiosqlite.connect(DATABASE) as db:
            tables = ["arrests", "citations", "bolos", "warrants", "infractions"]
            for tbl in tables:
                await db.execute(f"DELETE FROM {tbl}")
            await db.commit()
        await itx.response.edit_message(content="⚠️ **DATABASE WIPE COMPLETE.** All tables have been cleared.", view=None)

    @ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, itx: discord.Interaction, button: ui.Button):
        await itx.message.delete()

class StrikeConfirmView(ui.View):
    def __init__(self, trooper: discord.Member, infraction_data: list, original_reason: str, guild_id: int):
        super().__init__(timeout=None)
        self.trooper = trooper
        self.infraction_data = infraction_data
        self.infraction_ids = [row[0] for row in infraction_data]
        self.original_reason = original_reason
        self.guild_id = guild_id

    @ui.button(label='Confirm Strike', style=discord.ButtonStyle.success)
    async def confirm_strike(self, itx: discord.Interaction, button: ui.Button):
        roles_config = GUILD_SETTINGS.get(self.guild_id, {}).get('roles', {})
        strike_confirmer_id = roles_config.get('strike_confirmer')
        
        if itx.guild.get_role(strike_confirmer_id) not in itx.user.roles:
            return await itx.response.send_message("❌ Unauthorized.", ephemeral=True)
            
        s1 = itx.guild.get_role(roles_config.get('strike_1'))
        s2 = itx.guild.get_role(roles_config.get('strike_2'))
        ub = itx.guild.get_role(roles_config.get('up_for_ban'))
        
        target_role, display_name = s1, "Strike 1"
        if ub in self.trooper.roles:
            return await itx.response.send_message("⚠️ Already Up For Termination.", ephemeral=True)
        elif s2 in self.trooper.roles:
            target_role, display_name = ub, "Up For Termination"
        elif s1 in self.trooper.roles:
            target_role, display_name = s2, "Strike 2"
            
        await self.trooper.add_roles(target_role)
        async with aiosqlite.connect(DATABASE) as db:
            for inf_id in self.infraction_ids:
                await db.execute("UPDATE infractions SET is_processed = 1 WHERE id = ?", (inf_id,))
            await db.commit()
            
        links = "\n".join([f"• [Infraction #{r[0]}]({r[1]})" for r in self.infraction_data])
        log_embed = discord.Embed(title="**STRIKE**", color=GSP_RED)
        log_embed.description = f"{SEPARATOR}\n**Trooper:** {self.trooper.mention}\n**Reason:** {self.original_reason}\n**Infractions:**\n{links}\n\n**Strike Level:** `{display_name}`\n{SEPARATOR}"
        log_embed.set_footer(text=f"Confirmed by {itx.user.display_name}")
        
        channels_config = GUILD_SETTINGS.get(self.guild_id, {}).get('channels', {})
        inf_channel_id = channels_config.get('infractions')
        inf_channel = bot.get_channel(inf_channel_id)
        if inf_channel: 
            await inf_channel.send(content=f"{self.trooper.mention}", embed=log_embed)
            
        await itx.response.edit_message(content=f"✅ Strike applied for {self.trooper.mention}.", embed=log_embed, view=None)

class RobloxMoreInfoView(ui.View):
    def __init__(self, user_id: int, username: str, author_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.username = username
        self.author_id = author_id

    async def interaction_check(self, itx: discord.Interaction) -> bool:
        """Restricts button clicks strictly to the command author."""
        if itx.user.id != self.author_id:
            await itx.response.send_message(
                "❌ Only the person who ran this command can use this button!",
                ephemeral=True
            )
            return False
        return True

    @ui.button(label="View Advanced Details", style=discord.ButtonStyle.primary, emoji="🔍")
    async def show_more_info(self, itx: discord.Interaction, button: discord.ui.Button):
        await itx.response.defer(ephemeral=True)

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    "https://presence.roblox.com/v1/presence/users",
                    json={"userIds": [self.user_id]}
                ) as resp:
                    resp.raise_for_status()
                    presence_data = await resp.json()

                async with session.get(f"https://badges.roblox.com/v1/users/{self.user_id}/badges") as resp:
                    resp.raise_for_status()
                    badges_data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return await itx.followup.send(
                "❌ Roblox advanced information is unavailable right now.",
                ephemeral=True,
            )

        presence_map = {0: "Offline 🔴", 1: "Online 🟢", 2: "In Game 🎮", 3: "In Studio 🛠️"}
        p_type = 0
        if presence_data.get("userPresences"):
            p_type = presence_data["userPresences"][0].get("userPresenceType", 0)
        presence_str = presence_map.get(p_type, "Offline 🔴")

        badge_count = len(badges_data.get("data", [])) if "data" in badges_data else 0

        adv_embed = discord.Embed(
            title=f"Roblox Advanced Info | {self.username}",
            color=GSP_CUSTOM_ORANGE
        )

        blue_line = get_separator("0f13ff")
        adv_embed.description = (
            f"{blue_line}\n"
            f"**Online Activity Status:** {presence_str}\n"
            f"**Public Badges Earned:** `{badge_count}`\n"
            f"**Direct Profile Link:** [Click Here](https://www.roblox.com/users/{self.user_id}/profile)\n"
            f"{blue_line}"
        )
        adv_embed.set_footer(text=f"Requested by {itx.user.display_name}")

        await itx.followup.send(embed=adv_embed, ephemeral=True)

class ClearRecordConfirm(ui.View):
    def __init__(self, original_user, owner_id, record_id, table):
        super().__init__(timeout=60)
        self.original_user = original_user
        self.owner_id = owner_id
        self.record_id = record_id
        self.table = table

    @ui.button(label="Permanently Delete", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, itx: discord.Interaction, button: ui.Button):
        if itx.user.id != self.original_user.id:
            return await itx.response.send_message("❌ This is not your menu.", ephemeral=True)
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute(f"DELETE FROM {self.table} WHERE id_code = ?", (self.record_id,))
            await db.commit()
        await itx.response.send_message(f"🗑️ Record `{self.record_id}` deleted from **{self.table}**.", ephemeral=True)
        await itx.message.delete()

class ExpiryDropdown(ui.Select):
    def __init__(self, callback_func):
        options = [discord.SelectOption(label="24 Hours", value="24"), discord.SelectOption(label="48 Hours", value="48"), discord.SelectOption(label="72 Hours", value="72"), discord.SelectOption(label="1 Week", value="168")]
        super().__init__(placeholder="Duration Selection", options=options)
        self.callback_func = callback_func
    async def callback(self, itx: discord.Interaction):
        await self.callback_func(itx, int(self.values[0]))

class InfractionExpiryDropdown(ui.Select):
    def __init__(self, callback_func):
        options = [
            discord.SelectOption(label="24 Hours", value="24"), discord.SelectOption(label="48 Hours", value="48"), discord.SelectOption(label="72 Hours", value="72"),
            discord.SelectOption(label="1 Week", value="168"), discord.SelectOption(label="2 Weeks", value="336"), discord.SelectOption(label="3 Weeks", value="504"),
            discord.SelectOption(label="1 Month", value="720"), discord.SelectOption(label="1.5 Months", value="1080"), discord.SelectOption(label="2 Months", value="1440")
        ]
        super().__init__(placeholder="Select Infraction Expiry", options=options)
        self.callback_func = callback_func
    async def callback(self, itx: discord.Interaction):
        await self.callback_func(itx, int(self.values[0]))

class ActiveSearchPaginator(discord.ui.View):
    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=180) # Buttons will time out after 3 minutes
        self.pages = pages
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        # Disable 'Back' if on the first page, disable 'Next' if on the last page
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == len(self.pages) - 1

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev_page(self, itx: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await itx.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.primary)
    async def next_page(self, itx: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await itx.response.edit_message(embed=self.pages[self.current_page], view=self)

# --- COMMANDS ---

@bot.tree.command(name='clear_all_data', description='WIPE ALL DATABASE TABLES (ADMIN ONLY)')
@app_commands.checks.has_permissions(administrator=True)
async def clear_all_data(itx: discord.Interaction):
    await itx.response.send_message("🚨 **Are you sure?**", view=ClearAllDataView(), ephemeral=True)

@bot.tree.command(name='info', description='Bot support information')
async def info(itx: discord.Interaction):
    if not await is_cmd_channel(itx): return
    e = discord.Embed(title="**INFORMATION**", description=f"{SEPARATOR}\nQuestions/Bugs: DM **<@1277234576426532894>**.\n{SEPARATOR}", color=GSP_CUSTOM_ORANGE)
    e.set_footer(text=f"Requested by {itx.user.display_name}")
    await itx.response.send_message(embed=e)

@bot.tree.command(name='clear_record', description='Permanently delete a record')
async def clear_record(itx: discord.Interaction, record_id: str):
    if not await is_cmd_channel(itx): return
    rid = record_id.upper()
    async with aiosqlite.connect(DATABASE) as db:
        found = False
        for tbl in ["arrests", "citations", "bolos", "warrants"]:
            async with db.execute(f"SELECT officer_id FROM {tbl} WHERE id_code = ?", (rid,)) as c:
                row = await c.fetchone()
                if row:
                    found, target_tbl, owner_id = True, tbl, row[0]
                    break
        if not found:
            return await itx.response.send_message(f"❌ Record `{rid}` not found.", ephemeral=True)
            
        supervisor_role_id = get_setting(itx.guild.id, 'roles', 'supervisor')
        if itx.user.id != owner_id and itx.guild.get_role(supervisor_role_id) not in itx.user.roles:
            return await itx.response.send_message("❌ Unauthorized.", ephemeral=True)
            
        await itx.response.send_message(f"⚠️ Delete `{rid}` from **{target_tbl}**?", view=ClearRecordConfirm(itx.user, owner_id, rid, target_tbl), ephemeral=True)

@bot.tree.command(name='trooper_performance', description='View advanced trooper statistics for this department')
async def trooper_performance(itx: discord.Interaction, trooper: discord.Member):
    if not await is_cmd_channel(itx): return
    await itx.response.defer()
    
    now_iso = datetime.now(timezone.utc).isoformat()
    current_dept_id = itx.guild.id
    dept_name = get_setting(current_dept_id, 'name') or "Department"
    
    async with aiosqlite.connect(DATABASE) as db:
        # Lifetime Counts isolated by current Guild ID
        async with db.execute("SELECT COUNT(*) FROM arrests WHERE officer_id = ? AND guild_id = ?", (trooper.id, current_dept_id)) as c:
            arr_cnt = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM citations WHERE officer_id = ? AND guild_id = ?", (trooper.id, current_dept_id)) as c:
            cit_cnt = (await c.fetchone())[0]
            
        # Active vs Lifetime BOLOs isolated by current Guild ID
        async with db.execute("SELECT COUNT(*) FROM bolos WHERE officer_id = ? AND guild_id = ?", (trooper.id, current_dept_id)) as c:
            bolo_total = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM bolos WHERE officer_id = ? AND expiry_timestamp > ? AND guild_id = ?", (trooper.id, now_iso, current_dept_id)) as c:
            bolo_active = (await c.fetchone())[0]
            
        # Active vs Lifetime Warrants isolated by current Guild ID
        async with db.execute("SELECT COUNT(*) FROM warrants WHERE officer_id = ? AND guild_id = ?", (trooper.id, current_dept_id)) as c:
            war_total = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM warrants WHERE officer_id = ? AND expiry_timestamp > ? AND guild_id = ?", (trooper.id, now_iso, current_dept_id)) as c:
            war_active = (await c.fetchone())[0]
            
        # Infraction Standing isolated by current Guild ID so roleplay profiles stay separate
        async with db.execute("SELECT COUNT(*) FROM infractions WHERE user_id = ? AND guild_id = ?", (trooper.id, current_dept_id)) as c:
            inf_lifetime = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM infractions WHERE user_id = ? AND is_processed = 0 AND guild_id = ?", (trooper.id, current_dept_id)) as c:
            inf_active = (await c.fetchone())[0]
            
    # Advanced Dynamic Calculations
    total_actions = arr_cnt + cit_cnt + bolo_total + war_total
    
    if (arr_cnt + cit_cnt) > 0:
        ratio = round((arr_cnt / (arr_cnt + cit_cnt)) * 100)
        ratio_display = f"{ratio}% Custody / {100 - ratio}% Citation"
    else:
        ratio_display = "No citation/arrest history"

    # Evaluate standing based on local role configurations
    roles_config = GUILD_SETTINGS.get(current_dept_id, {}).get('roles', {})
    s1 = itx.guild.get_role(roles_config.get('strike_1'))
    s2 = itx.guild.get_role(roles_config.get('strike_2'))
    ub = itx.guild.get_role(roles_config.get('up_for_ban'))
    
    if ub and ub in trooper.roles: 
        status_tier = "🔴 Up For Termination"
    elif s2 and s2 in trooper.roles: 
        status_tier = "🟠 Strike 2 (Final Warning)"
    elif s1 and s1 in trooper.roles: 
        status_tier = "🟡 Strike 1"
    else: 
        status_tier = "🟢 Good Standing"

    # Build clean, department-specific card layout
    e = discord.Embed(title=f"📊 **{dept_name} PERFORMANCE: {trooper.display_name.upper()}**", color=GSP_CUSTOM_ORANGE)
    
    if trooper.display_avatar:
        e.set_thumbnail(url=trooper.display_avatar.url)
        
    e.description = (
        f"{SEPARATOR}\n"
        f"📋 **{dept_name} Administrative Standing**\n"
        f"• **Local Status:** `{status_tier}`\n"
        f"• **Active Misconduct Points:** `{inf_active}/3`\n"
        f"• **Total Department Infractions:** `{inf_lifetime}`\n\n"
        
        f"📈 **Activity Overview**\n"
        f"• **Grand Total Actions (TEA):** `{total_actions}`\n"
        f"• **Enforcement Profile:** `{ratio_display}`\n\n"
        
        f"🗂️ **Detailed Ledger Counts**\n"
        f"• 🚨 **Arrests Secured:** `{arr_cnt}`\n"
        f"• 🎫 **Citations Issued:** `{cit_cnt}`\n"
        f"• 📡 **BOLOs Issued:** `{bolo_total}` *({bolo_active} active)*\n"
        f"• ⚖️ **Warrants Issued:** `{war_total}` *({war_active} active)*\n"
        f"{SEPARATOR}"
    )
    
    e.set_footer(text=f"Requested by {itx.user.display_name} in {itx.guild.name}")
    await itx.followup.send(embed=e)
    
@bot.tree.command(name='search_record', description='Search any GSP ID')
async def search_record(itx: discord.Interaction, record_id: str):
    if not await is_cmd_channel(itx): return
    await itx.response.defer()
    rid = record_id.upper()
    
    async with aiosqlite.connect(DATABASE) as db:
        for tbl, title, color in [("arrests", "**ARREST RECORD**", GSP_CUSTOM_ORANGE), ("citations", "**CITATION RECORD**", GSP_YELLOW), ("bolos", "**BOLO RECORD**", GSP_RED), ("warrants", "**WARRANT RECORD**", GSP_RED)]:
            async with db.execute(f"SELECT * FROM {tbl} WHERE id_code = ?", (rid,)) as c:
                row = await c.fetchone()
                if row:
                    off = await bot.fetch_user(row[2])
                    e = discord.Embed(title=title, color=color)
                    
                    # If it's an arrest, fetch the custom blue line emoji. Otherwise, use standard SEPARATOR.
                    current_line = get_separator("0f13ff") if tbl == "arrests" else SEPARATOR
                    
                    if tbl == "arrests":
                        e.description = f"{current_line}\n**ID:** {row[0]}\n**Officer:** {off.mention}\n**Suspect:** {row[1]}\n**Secondaries:** {row[3]}\n**Charges:** {row[4]}\n**Date:** {row[6]}\n{current_line}"
                        if row[5] != "N/A": e.set_image(url=row[5])
                    elif tbl == "citations":
                        e.description = f"{current_line}\n**ID:** {row[0]}\n**Officer:** {off.mention}\n**Suspect:** {row[1]}\n**Vehicle:** {row[3]}\n**Location:** {row[4]}\n**Reason:** {row[5]}\n**Date:** {row[6]}\n{current_line}"
                    elif tbl == "bolos":
                        e.description = f"{current_line}\n**ID:** {row[0]}\n**Officer:** {off.mention}\n**Suspect:** {row[1]}\n**Vehicle:** {row[4]}\n**Plate:** {row[5]}\n**Reason:** {row[3]}\n**Expires:** {row[6]}\n**Date:** {row[7]}\n{current_line}"
                    else: # warrants
                        e.description = f"{current_line}\n**ID:** {row[0]}\n**Officer:** {off.mention}\n**Suspect:** {row[1]}\n**Reason:** {row[3]}\n**Risk Level:** {row[4]}\n**Expires:** {row[5]}\n**Date:** {row[6]}\n{current_line}"
                    
                    e.set_footer(text=f"Logged by {off.display_name}")
                    return await itx.followup.send(embed=e)
                    
    await itx.followup.send(f"❌ `{rid}` not found.")

@bot.tree.command(name='infraction_log', description='Log misconduct')
async def infraction_log(itx: discord.Interaction, trooper: discord.Member, reason: str, punishment: str, proof: str = "None"):
    if not await is_cmd_channel(itx): return
    supervisor_role_id = get_setting(itx.guild.id, 'roles', 'supervisor')
    if itx.guild.get_role(supervisor_role_id) not in itx.user.roles: 
        return await itx.response.send_message("❌ Restricted.", ephemeral=True)
        
    async def complete_infraction(itx_select, hours):
        ts = get_pst_time()
        expire_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
        e = discord.Embed(title="**INFRACTION LOGGED**", color=GSP_RED)
        e.description = f"{SEPARATOR}\n**Trooper:** {trooper.mention}\n**Reason:** {reason}\n**Punishment:** {punishment}\n**Proof:** {proof}\n{SEPARATOR}"
        e.set_footer(text=f"Logged by {itx.user.display_name}")
        
        # Local Logging (Strictly local to origin server)
        infractions_channel_id = get_setting(itx.guild.id, 'channels', 'infractions')
        inf_channel = bot.get_channel(infractions_channel_id)
        log_msg = await inf_channel.send(content=f"{trooper.mention}", embed=e)
        
        async with aiosqlite.connect(DATABASE) as db:
            # Replace the database segment inside infraction_log with this:
            async with aiosqlite.connect(DATABASE) as db:
                await db.execute('''INSERT INTO infractions (user_id, issuer_id, reason, punishment, proof, msg_url, expiry_timestamp, timestamp, guild_id) VALUES (?,?,?,?,?,?,?,?,?)''', 
                             (trooper.id, itx.user.id, reason, punishment, proof, log_msg.jump_url, expire_at, ts, itx.guild.id))
                await db.commit()
            
            # Filters previous infractions to ensure they are checked strictly within the same server
                async with db.execute("SELECT id, msg_url FROM infractions WHERE user_id = ? AND is_processed = 0 AND guild_id = ?", (trooper.id, itx.guild.id)) as c:
                    rows = await c.fetchall()
                
        if len(rows) >= 3:
            roles_config = GUILD_SETTINGS.get(itx.guild.id, {}).get('roles', {})
            s1 = itx.guild.get_role(roles_config.get('strike_1'))
            s2 = itx.guild.get_role(roles_config.get('strike_2'))
            
            next_lvl = "Strike 1"
            if s2 in trooper.roles: next_lvl = "Up For Termination"
            elif s1 in trooper.roles: next_lvl = "Strike 2"
            
            links = "\n".join([f"• [Infraction #{r[0]}]({r[1]})" for r in rows])
            alert = discord.Embed(title="**⚖️ STRIKE ELIGIBILITY ALERT**", color=GSP_RED)
            alert.description = f"{SEPARATOR}\n**Trooper:** {trooper.mention}\n**Reason:** {reason}\n**Infractions:**\n{links}\n\n**Next Strike Level:** `{next_lvl}`\n{SEPARATOR}"
            alert.set_footer(text=f"{get_setting(itx.guild.id, 'name')} Central Notification")
            
            strike_confirm_channel_id = get_setting(itx.guild.id, 'channels', 'strike_confirm')
            strike_channel = bot.get_channel(strike_confirm_channel_id)
            await strike_channel.send(content=f"{trooper.mention}", embed=alert, view=StrikeConfirmView(trooper, rows, reason, itx.guild.id))
            
        await itx_select.response.send_message("✅ Infraction logged.", ephemeral=True)
        
    await itx.response.send_message("Select Duration:", view=ui.View().add_item(InfractionExpiryDropdown(complete_infraction)), ephemeral=True)

@bot.tree.command(name='search_user', description='NCIC Name Lookup')
async def search_user(itx: discord.Interaction, suspect_name: str):
    if not await is_cmd_channel(itx): return
    await itx.response.defer()
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute("SELECT id_code, reason FROM warrants WHERE suspect = ? AND expiry_timestamp > ?", (suspect_name, now)) as c: warrants = await c.fetchall()
        async with db.execute("SELECT id_code, reason FROM bolos WHERE suspect = ? AND expiry_timestamp > ?", (suspect_name, now)) as c: bolos = await c.fetchall()
        async with db.execute("SELECT timestamp FROM arrests WHERE suspect = ? ORDER BY timestamp DESC LIMIT 1", (suspect_name,)) as c: last_arrest = await c.fetchone()
    e = discord.Embed(title=f"**NCIC: {suspect_name}**", color=GSP_RED if (warrants or bolos) else discord.Color.green())
    w_t = "\n".join([f"• `{w[0]}`: {w[1]}" for w in warrants]) if warrants else "None"
    b_t = "\n".join([f"• `{b[0]}`: {b[1]}" for b in bolos]) if bolos else "None"
    e.description = f"{SEPARATOR}\n**Warrants:** {w_t}\n**BOLOs:** {b_t}\n**Last Arrest:** {format_time_ago(last_arrest[0]) if last_arrest else 'No priors.'}\n{SEPARATOR}"
    e.set_footer(text=f"Requested by {itx.user.display_name}")
    await itx.followup.send(embed=e)

@bot.tree.command(name='arrest_log', description='Record an arrest with a file upload')
async def arrest_log(
    itx: discord.Interaction, 
    suspect: str, 
    charges: str, 
    secondaries: str = "N/A", 
    # Change 'str' to 'discord.Attachment' here:
    mugshot: discord.Attachment = None 
):
    if not await is_cmd_channel(itx): return
    await itx.response.defer(ephemeral=True)
    
    id_code, ts = await generate_unique_id(), get_pst_time()
    
    # Extract the URL from the attachment object if an image was uploaded
    final_image_url = "N/A"
    if mugshot is not None:
        final_image_url = mugshot.url # Discord automatically hosts the uploaded file and gives you a URL!

    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("INSERT INTO arrests VALUES (?,?,?,?,?,?,?,?)", (id_code, suspect, itx.user.id, secondaries, charges, final_image_url, ts, itx.guild.id))
        await db.commit()
        
    blue_line = get_separator("0f13ff")
    
    e = discord.Embed(title="**ARREST RECORD**", color=GSP_CUSTOM_ORANGE)
    e.description = f"{blue_line}\n**ID:** {id_code}\n**Officer:** {itx.user.mention}\n**Suspect:** {suspect}\n**Secondaries:** {secondaries}\n**Charges:** {charges}\n**Date:** {ts}\n{blue_line}"
    
    # Attach the hosted image URL to the embed layout
    if final_image_url != "N/A": 
        e.set_image(url=final_image_url)
        
    e.set_footer(text=f"Logged by {itx.user.display_name} in {itx.guild.name}")
    
    local_channel_id = get_setting(itx.guild.id, 'channels', 'arrest_logs')
    local_channel = bot.get_channel(local_channel_id)
    if local_channel:
        await local_channel.send(embed=e)
        
    await broadcast_log(bot, e, 'arrest_logs', itx.guild.id)
    await itx.followup.send(f"✅ Logged `{id_code}` with file attachment.")

@bot.tree.command(name='citation_log', description='Record a citation')
async def citation_log(itx: discord.Interaction, suspect: str, vehicle: str, location: str, reason: str):
    if not await is_cmd_channel(itx): return
    await itx.response.defer(ephemeral=True)
    id_code, ts = await generate_unique_id(), get_pst_time()
    # Replace the database block inside citation_log with this:
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("INSERT INTO citations VALUES (?,?,?,?,?,?,?,?)", (id_code, suspect, itx.user.id, vehicle, location, reason, ts, itx.guild.id))
        await db.commit()

    e = discord.Embed(title="**CITATION RECORD**", color=GSP_YELLOW)
    e.description = f"{SEPARATOR}\n**ID:** {id_code}\n**Officer:** {itx.user.mention}\n**Suspect:** {suspect}\n**Vehicle:** {vehicle}\n**Location:** {location}\n**Reason:** {reason}\n**Date:** {ts}\n{SEPARATOR}"
    e.set_footer(text=f"Logged by {itx.user.display_name}")
    
    # 1. Log locally to origin server
    local_channel_id = get_setting(itx.guild.id, 'channels', 'citation_logs')
    local_channel = bot.get_channel(local_channel_id)
    if local_channel:
        await local_channel.send(embed=e)
        
    # 2. Broadcast log to all OTHER configured servers
    await broadcast_log(bot, e, 'citation_logs', itx.guild.id)
    
    await itx.followup.send(f"✅ Logged `{id_code}`")

@bot.tree.command(name='bolo_log', description='Issue a BOLO')
async def bolo_log(itx: discord.Interaction, suspect: str, vehicle: str, reason: str, plate: str = "Unknown"):
    if not await is_cmd_channel(itx): return
    async def post_bolo(itx_s, hours):
        id_code, ts, expire = await generate_unique_id(), get_pst_time(), (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
        # Replace the database block inside post_bolo with this:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute("INSERT INTO bolos VALUES (?,?,?,?,?,?,?,?,?)", (id_code, suspect, itx.user.id, reason, vehicle, plate, expire, ts, itx_s.guild.id))
            await db.commit()

        e = discord.Embed(title="**BOLO ACTIVE**", color=GSP_RED)
        e.description = f"{SEPARATOR}\n**ID:** {id_code}\n**Officer:** {itx.user.mention}\n**Suspect:** {suspect}\n**Vehicle:** {vehicle}\n**Plate:** {plate}\n**Reason:** {reason}\n**Date:** {ts}\n{SEPARATOR}"
        e.set_footer(text=f"Logged by {itx.user.display_name}")
        
        # 1. Log locally to command/logging channel
        await itx_s.channel.send(embed=e)
        
        # 2. Broadcast log to all OTHER configured servers
        await broadcast_log(bot, e, 'bolo_logs', itx_s.guild.id)
        
        await itx_s.response.send_message(f"✅ BOLO Issued.", ephemeral=True)
    await itx.response.send_message("Duration:", view=ui.View().add_item(ExpiryDropdown(post_bolo)), ephemeral=True)

@bot.tree.command(name='warrant_log', description='Issue a warrant')
async def warrant_log(itx: discord.Interaction, suspect: str, reason: str, risk: str = "Medium"):
    if not await is_cmd_channel(itx): return
    async def post_war(itx_s, hours):
        id_code, ts, expire = await generate_unique_id(), get_pst_time(), (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
        # Replace the database block inside post_war with this:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute("INSERT INTO warrants VALUES (?,?,?,?,?,?,?,?)", (id_code, suspect, itx.user.id, reason, risk, expire, ts, itx_s.guild.id))
            await db.commit()

        e = discord.Embed(title="**WARRANT ACTIVE**", color=GSP_RED)
        e.description = f"{SEPARATOR}\n**ID:** {id_code}\n**Officer:** {itx.user.mention}\n**Suspect:** {suspect}\n**Reason:** {reason}\n**Risk Level:** {risk}\n**Date:** {ts}\n{SEPARATOR}"
        e.set_footer(text=f"Logged by {itx.user.display_name}")
        
        # 1. Log locally to command/logging channel
        await itx_s.channel.send(embed=e)
        
        # 2. Broadcast log to all OTHER configured servers
        await broadcast_log(bot, e, 'warrant_logs', itx_s.guild.id)
        
        await itx_s.response.send_message(f"✅ Warrant Issued.", ephemeral=True)
    await itx.response.send_message("Duration:", view=ui.View().add_item(ExpiryDropdown(post_war)), ephemeral=True)

@bot.tree.command(name="search_active", description="Global search for all active Warrants and BOLOs across all departments")
async def search_active(itx: discord.Interaction):
    if not await is_cmd_channel(itx): return
    await itx.response.defer()
    
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # 1. Fetch Global Data (No guild_id filter)
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute("SELECT id_code, suspect, reason, risk_level FROM warrants WHERE expiry_timestamp > ?", (now_iso,)) as c:
            warrants = await c.fetchall()
        async with db.execute("SELECT id_code, suspect, reason, vehicle, plate FROM bolos WHERE expiry_timestamp > ?", (now_iso,)) as c:
            bolos = await c.fetchall()

    # 2. Categorize and Format Data
    high_w, med_w, low_w, active_b = [], [], [], []
    
    for w in warrants:
        id_code, suspect, reason, risk = w
        line = f"⚖️ **`{id_code}`** | **{suspect}** - *{reason}*"
        if risk.lower() == 'high': high_w.append(line)
        elif risk.lower() == 'medium': med_w.append(line)
        else: low_w.append(line)
            
    for b in bolos:
        id_code, suspect, reason, vehicle, plate = b
        active_b.append(f"📡 **`{id_code}`** | **{suspect}** - *{vehicle} ({plate})* - *{reason}*")

    # 3. Build the Display Layout Sequence
    lines = []
    if high_w:
        lines.append("### 🔴 High Risk Warrants")
        lines.extend(high_w)
    if med_w:
        lines.append("### 🟠 Medium Risk Warrants")
        lines.extend(med_w)
    if low_w:
        lines.append("### 🟡 Low Risk Warrants")
        lines.extend(low_w)
    if active_b:
        lines.append("### 🔵 Active BOLOs")
        lines.extend(active_b)
        
    if not lines:
        await itx.followup.send("✅ There are currently no active warrants or BOLOs in the global network.")
        return

    # 4. Chunking into Pages (Max ~2000 chars per page for clean formatting)
    pages = []
    current_page_text = ""
    for line in lines:
        if len(current_page_text) + len(line) > 2000:
            pages.append(current_page_text)
            current_page_text = line + "\n"
        else:
            current_page_text += line + "\n"
    if current_page_text:
        pages.append(current_page_text)

    # 5. Convert Text Pages into Discord Embeds
    embeds = []
    for i, page_content in enumerate(pages):
        e = discord.Embed(
            title="🌐 **GLOBAL ACTIVE WARRANTS & BOLOS**", 
            description=f"{SEPARATOR}\n{page_content}\n{SEPARATOR}",
            color=GSP_CUSTOM_ORANGE
        )
        e.set_footer(text=f"Page {i+1} of {len(pages)} | Requested by {itx.user.display_name}")
        embeds.append(e)

    # 6. Send the Response
    if len(embeds) == 1:
        # If everything fits on one page, don't bother attaching buttons
        await itx.followup.send(embed=embeds[0])
    else:
        # Attach the UI View if there are multiple pages
        view = ActiveSearchPaginator(embeds)
        await itx.followup.send(embed=embeds[0], view=view)

@bot.tree.command(name="user_info", description="Discord profile lookup")
async def user_info(itx: discord.Interaction, trooper: discord.Member):
    if not await is_cmd_channel(itx): return
    
    # Process dynamic activities/presence (since static connections are hidden by Discord)
    activities_list = []
    if trooper.activities:
        for act in trooper.activities:
            if act.type == discord.ActivityType.playing:
                activities_list.append(f"🎮 Playing: **{act.name}**")
            elif act.type == discord.ActivityType.streaming:
                activities_list.append(f"📺 Streaming: **{act.name}**")
            elif act.type == discord.ActivityType.listening:
                activities_list.append(f"🎵 Listening to: **{act.name}**")
            elif act.type == discord.ActivityType.custom:
                # Fallbacks if a custom status contains emojis or custom text attributes
                status_text = act.name if act.name else ""
                if act.emoji:
                    status_text = f"{act.emoji} {status_text}"
                if status_text:
                    activities_list.append(f"💬 Status: *\"{status_text}\"*")
                
    status_display = "\n".join(activities_list) if activities_list else "None (Offline or no active status layout)"

    # Build the enhanced profile embed
    e = discord.Embed(title=f"**PROFILE: {trooper.display_name}**", color=GSP_CUSTOM_ORANGE)
    
    # Feature: Add profile picture as a thumbnail
    if trooper.display_avatar:
        e.set_thumbnail(url=trooper.display_avatar.url)
        
    # Feature: Convert timestamps into Discord relative time markdown strings
    created_unix = int(trooper.created_at.timestamp())
    joined_unix = int(trooper.joined_at.timestamp()) if trooper.joined_at else None
    
    created_str = f"{trooper.created_at.strftime('%Y-%m-%d')} (<t:{created_unix}:R>)"
    joined_str = f"{trooper.joined_at.strftime('%Y-%m-%d')} (<t:{joined_unix}:R>)" if joined_unix else "N/A"

    e.description = (
        f"{SEPARATOR}\n"
        f"🆔 **User ID:** `{trooper.id}`\n"
        f"👤 **Type:** {'`Bot` 🤖' if trooper.bot else '`Trooper` 👥'}\n"
        f"👑 **Top Role:** {trooper.top_role.mention}\n\n"
        f"📅 **Account Created:** {created_str}\n"
        f"📥 **Joined Guild:** {joined_str}\n\n"
        f"✨ **Live Presence / Activity:**\n{status_display}\n"
        f"{SEPARATOR}"
    )
    
    # Keeping your uniform global logging footer format intact
    e.set_footer(text=f"Requested by {itx.user.display_name} in {itx.guild.name}")
    await itx.response.send_message(embed=e)

@bot.event
async def on_message(message):
    # Ignore messages sent by bots to avoid infinite loops
    if message.author.bot:
        return

    # Check if the bot was explicitly mentioned and it wasn't a mass ping (@everyone)
    if bot.user in message.mentions and not message.mention_everyone:
        # Dynamically fetch all registered slash commands from the tree
        slash_cmds = bot.tree.get_commands()
        total_cmds = len(slash_cmds)
        
        # Build the scannable directory list of commands and their descriptions
        cmd_directory = ""
        for cmd in slash_cmds:
            cmd_directory += f"• `/{cmd.name}`: *{cmd.description or 'No description available.'}*\n"
            
        # Set up the embed structure
        e = discord.Embed(
            title=f"🤖 **BOT PROFILE: {bot.user.name}**", 
            color=GSP_CUSTOM_ORANGE
        )
        
        # Feature: Set the bot's profile picture as the main large embed image
        if bot.user.display_avatar:
            e.set_thumbnail(url=bot.user.display_avatar.url)
            
        # Compile stats and directory layout
        e.description = (
            f"{SEPARATOR}\n"
            f"📊 **System Diagnostics:**\n"
            f"• **Total Registered Commands:** `{total_cmds}`\n"
            f"• **Guild Connections:** `{len(bot.guilds)} servers`\n"
            f"• **Network Latency:** `{round(bot.latency * 1000)}ms`\n"
            f"• **Engine Version:** `discord.py v{discord.__version__}`\n\n"
            f"🛠️ **Available Slash Commands:**\n{cmd_directory}"
            f"{SEPARATOR}"
        )
        
        # Matches your exact requested footer layout
        e.set_footer(text=f"Requested by {message.author.display_name} in {message.guild.name}")
        
        await message.channel.send(embed=e)

    # Process traditional prefix commands if any are ever added later
    await bot.process_commands(message)

@bot.tree.command(name="commands", description="View a directory of all available bot commands")
async def commands_directory(itx: discord.Interaction):
    if not await is_cmd_channel(itx): return
    
    # Dynamically fetch all registered slash commands from the tree
    slash_cmds = bot.tree.get_commands()
    total_cmds = len(slash_cmds)
    
    # Build the scannable directory list of commands and their descriptions
    cmd_directory = ""
    for cmd in slash_cmds:
        cmd_directory += f"• `/{cmd.name}`: *{cmd.description or 'No description available.'}*\n"
        
    # Set up the embed structure
    e = discord.Embed(
        title="📂 **COMMAND DIRECTORY**", 
        color=GSP_CUSTOM_ORANGE
    )
    
    # Keeps it consistent with the bot's avatar in the top right corner
    if bot.user.display_avatar:
        e.set_thumbnail(url=bot.user.display_avatar.url)
        
    # Compile stats and directory layout
    e.description = (
        f"{SEPARATOR}\n"
        f"📊 **Total Registered Commands:** `{total_cmds}`\n\n"
        f"🛠️ **Available Slash Commands:**\n{cmd_directory}"
        f"{SEPARATOR}"
    )
    
    # Uses your requested footer layout
    e.set_footer(text=f"Requested by {itx.user.display_name} in {itx.guild.name}")
    
    await itx.response.send_message(embed=e)

@bot.tree.command(name="status", description="Check the bot's live status")
async def status(itx: discord.Interaction):
    if not await is_cmd_channel(itx):
        return
    if itx.user.id != 1062166609931804702:
        return await itx.response.send_message("❌ Unauthorized.", ephemeral=True)

    started_at = time.monotonic()
    await itx.response.defer()
    response_time = round((time.monotonic() - started_at) * 1000)
    usage = resource.getrusage(resource.RUSAGE_SELF)

    embed = discord.Embed(title="Bot Status", color=discord.Color.green())
    embed.description = (
        f"{SEPARATOR}\n"
        f"**Uptime:** `{format_uptime(time.monotonic() - bot_start_time)}`\n"
        f"**Response Time:** `{response_time}ms`\n"
        f"**Memory Usage:** `{round(usage.ru_maxrss / 1024)} MB`\n"
        f"**CPU Time:** `{usage.ru_utime:.2f}s`\n"
        f"{SEPARATOR}"
    )
    embed.set_timestamp()
    embed.set_footer(text=f"Response time: {response_time}ms")
    await itx.followup.send(embed=embed)

@bot.tree.command(name="logs", description="Show recent PM2 error logs")
async def logs(itx: discord.Interaction, lines: app_commands.Range[int, 1, 100] = 20):
    if not await is_cmd_channel(itx):
        return
    if not itx.user.guild_permissions.administrator:
        return await itx.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )

    await itx.response.defer(ephemeral=True)
    try:
        process = await asyncio.create_subprocess_exec(
            "pm2", "logs", "Northside", "--err", "--lines", str(lines), "--nostream",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output_bytes, _ = await asyncio.wait_for(process.communicate(), timeout=15)
    except (FileNotFoundError, asyncio.TimeoutError):
        return await itx.followup.send("❌ Failed to retrieve PM2 logs.", ephemeral=True)

    output = output_bytes.decode("utf-8", errors="replace").strip()
    if not output:
        return await itx.followup.send("No recent error logs found.", ephemeral=True)

    embed = discord.Embed(title="Recent PM2 Errors", color=discord.Color.red())
    embed.description = f"```\n{output[:3900]}\n```"
    await itx.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name='dept_performance', description='View activity and log metrics for a specific department')
@app_commands.choices(department=[
    app_commands.Choice(name="Georgia State Patrol (GSP)", value="1471660122035195916"),
    app_commands.Choice(name="Federal Bureau of Investigation (FBI)", value="1511837991503401031"),
    app_commands.Choice(name="Fulton County Sheriff’s Office (FCSO)", value="111111111111111111"),
    app_commands.Choice(name="Department of Homeland Security (DHS)", value="222222222222222222"),
    app_commands.Choice(name="United States Marshals Service (USMS)", value="333333333333333333"),
    app_commands.Choice(name="Atlanta Police Department (APD)", value="444444444444444444")
])
async def dept_performance(itx: discord.Interaction, department: app_commands.Choice[str]):
    if not await is_cmd_channel(itx): return
    await itx.response.defer(ephemeral=True)
    
    # Extract the chosen Guild ID and the actual department configuration name
    target_guild_id = int(department.value)
    dept_name = GUILD_SETTINGS[target_guild_id]['name']
    
    # Query your database to calculate the live performance metrics
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute("SELECT COUNT(*) FROM arrests WHERE guild_id = ?", (target_guild_id,)) as c:
            arr_count = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM citations WHERE guild_id = ?", (target_guild_id,)) as c:
            cit_count = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM bolos WHERE guild_id = ?", (target_guild_id,)) as c:
            bolo_count = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM warrants WHERE guild_id = ?", (target_guild_id,)) as c:
            war_count = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM infractions WHERE guild_id = ?", (target_guild_id,)) as c:
            inf_count = (await c.fetchone())[0]

    total_actions = arr_count + cit_count + bolo_count + war_count + inf_count
    
    # Generate your custom blue line layout
    blue_line = get_separator("0f13ff")
    
    e = discord.Embed(
        title=f"📊 **DEPARTMENT PERFORMANCE REPORT: {dept_name}**",
        color=GSP_CUSTOM_ORANGE
    )
    
    e.description = (
        f"{blue_line}\n"
        f"📈 **Total Logs Filed:** `{total_actions}`\n\n"
        f"📂 **Breakdown by Category:**\n"
        f"🔹 **Arrests:** `{arr_count}`\n"
        f"🔹 **Citations:** `{cit_count}`\n"
        f"🔹 **BOLOs Issued:** `{bolo_count}`\n"
        f"🔹 **Warrants Issued:** `{war_count}`\n"
        f"🔹 **Internal Infractions:** `{inf_count}`\n"
        f"{blue_line}"
    )
    
    e.set_footer(text=f"Requested by {itx.user.display_name} • Data evaluated live")
    
    # Send the final generated report card directly as the follow-up response
    await itx.followup.send(embed=e)

@bot.tree.command(name='roblox_user', description='Lookup detailed Roblox account profile and statistics')
async def roblox_user(itx: discord.Interaction, username: str):
    """Fetches Roblox profile data, friends count, and top groups."""
    if not await is_cmd_channel(itx):
        return

    await itx.response.defer()

    async with aiohttp.ClientSession() as session:
        # 1. Username -> User ID
        async with session.post("https://users.roblox.com/v1/usernames/users", json={"usernames": [username]}) as resp:
            data = await resp.json()
            if not data.get("data"):
                return await itx.followup.send(f"❌ Roblox user `{username}` not found.")
            user_id = data["data"][0]["id"]

        # 2. User Profile
        async with session.get(f"https://users.roblox.com/v1/users/{user_id}") as resp:
            profile = await resp.json()

        # 3. Friends Count
        async with session.get(f"https://friends.roblox.com/v1/users/{user_id}/friends/count") as resp:
            friends_data = await resp.json()
            friends_count = friends_data.get("count", 0)

        # 4. Avatar Headshot
        thumb_url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=420x420&format=Png"
        async with session.get(thumb_url) as resp:
            thumb_data = await resp.json()
            avatar_url = thumb_data["data"][0]["imageUrl"] if thumb_data.get("data") else None

        # 5. Group Roles (Top 3)
        async with session.get(f"https://groups.roblox.com/v1/users/{user_id}/groups/roles") as resp:
            groups_data = await resp.json()
            groups_list = groups_data.get("data", [])
            group_summary = [f"• **{item['group']['name']}**: {item['role']['name']}" for item in groups_list[:3]]
            groups_formatted = "\n".join(group_summary) if group_summary else "No public groups"

    created_raw = profile.get("created", "")
    created_str = datetime.strptime(created_raw[:10], "%Y-%m-%d").strftime("%B %d, %Y") if created_raw else "Unknown"

    embed = discord.Embed(
        title=f"Roblox Profile | {profile.get('displayName')} (@{profile.get('name')})",
        url=f"https://www.roblox.com/users/{user_id}/profile",
        color=GSP_CUSTOM_ORANGE
    )

    if avatar_url:
        embed.set_thumbnail(url=avatar_url)

    blue_line = get_separator("0f13ff")
    desc = profile.get("description", "").strip() or "No profile description."

    embed.description = (
        f"{blue_line}\n"
        f"**User ID:** `{user_id}`\n"
        f"**Account Created:** {created_str}\n"
        f"**Banned:** {'Yes 🔴' if profile.get('isBanned') else 'No 🟢'}\n\n"
        f"**Bio:**\n```{desc[:300]}```\n"
        f"**Friends Count:** `{friends_count}`\n\n"
        f"**Groups ({len(groups_list)} Total):**\n"
        f"{groups_formatted}\n"
        f"{blue_line}"
    )

    embed.set_footer(text=f"Requested by {itx.user.display_name}")

    # Attach author-restricted button view
    view = RobloxMoreInfoView(
        user_id=user_id, 
        username=profile.get("name"), 
        author_id=itx.user.id  # Restricts interactions to command author
    )
    await itx.followup.send(embed=embed, view=view)

@bot.event
async def on_ready():
    # 1. Run your original startup tasks
    await init_db()

    # Sync commands to specific guilds (faster and more reliable than global sync)
    total_synced = 0
    for guild_id in GUILD_SETTINGS.keys():
        try:
            guild = discord.Object(id=guild_id)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} commands to guild {GUILD_SETTINGS[guild_id]['name']} ({guild_id})")
            total_synced += len(synced)
        except Exception as e:
            print(f"Failed to sync commands to guild {guild_id}: {e}")

    print(f"Startup complete. Total commands synced: {total_synced}. Waiting 30 seconds to announce status...")

    # 2. Wait 30 seconds
    await asyncio.sleep(30)

    # 3. Send the "Systems Online" message to your primary configured command channel
    cmd_channel_id = GUILD_SETTINGS.get(1471660122035195916, {}).get('cmd_channel') or ALLOWED_CMD_CHANNELS[0]
    channel = bot.get_channel(cmd_channel_id)
    if channel:
        await channel.send("Systems Online")
        print("Successfully sent 'Systems Online' to Discord!")
    else:
        print("Channel not found. Check your configured command channel IDs.")

bot.run(os.getenv("DISCORD_TOKEN"))