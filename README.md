# LEO Management 2.0

LEO Management 2.0 is a Discord bot for law-enforcement roleplay departments. It provides structured record keeping, department performance reports, Roblox account lookups, infraction and strike workflows, and administrator tooling from Discord slash commands.

The bot is currently configured for Georgia State Patrol (GSP) and Federal Bureau of Investigation (FBI) command channels. Additional departments can be enabled by completing their entry in `GUILD_SETTINGS` in `main.py`.

## Features

- Slash-command-only user workflow, with commands synced to configured guilds on startup.
- SQLite storage for arrests, citations, BOLOs, warrants, and infractions.
- Department-specific command channel restrictions.
- Cross-department broadcast of supported records.
- Strike confirmation workflow with role escalation.
- Roblox profile lookup with avatar, account age, friends, groups, presence, and badge information.
- Live rotating Discord presence, refreshed every three seconds.
- Administrator PM2 error-log lookup.
- Owner-only bot status diagnostics.
- Record search, deletion confirmation, active BOLO/warrant pagination, and performance reporting.

## Requirements

- Python 3.12 or newer.
- A Discord application and bot token.
- A Discord bot invite with the `bot` and `applications.commands` scopes.
- Bot permissions to view channels, send messages, embed links, attach files, manage roles, and manage messages where the configured workflows need them.
- PM2 installed on the host if `/logs` is expected to return PM2 logs.

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Configuration

Set the Discord token as an environment variable. Never commit the token to the repository.

```bash
export DISCORD_TOKEN="your-discord-bot-token"
python main.py
```

The following values in `main.py` are deployment-specific and should be reviewed before production use:

- `GUILD_SETTINGS`: guild IDs, command channels, log channels, and role IDs.
- `ALLOWED_CMD_CHANNELS`: channels where slash commands can be used.
- `DATABASE`: SQLite database location. The default is `/data/gsp_bot.db`.
- The owner ID in `/status`.
- The PM2 process name in `/logs`, currently `Northside`.

The Roblox APIs used by `/roblox_user` and its advanced information button do not require a Roblox API token. The advanced lookup has a ten-second request timeout and returns a user-facing error if Roblox is unavailable.

## Railway Deployment

### Do I need a Railway Volume?

Yes, if you want records to survive deploys, restarts, or container replacement. The bot stores its SQLite database at `/data/gsp_bot.db`. Without a mounted volume, `/data` is part of the temporary container filesystem and the database can be lost when Railway replaces the deployment.

Create a Railway Volume and mount it at:

```text
/data
```

Do not mount it at `/data/gsp_bot.db`; Railway volumes are directories and the application creates the database file inside the mount point.

Configure these Railway settings:

- **Start command:** `python main.py` (the included `Procfile` uses `worker: python main.py`).
- **Variable:** `DISCORD_TOKEN` set to the bot token.
- **Volume mount path:** `/data`.
- **Persistent volume backups:** enable the Railway option if available for your plan and recovery needs.

If persistence is not important for a temporary test deployment, a volume is optional, but all SQLite records should be treated as disposable.

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DISCORD_TOKEN="your-discord-bot-token"
python main.py
```

The default database path is `/data/gsp_bot.db`, so local development may require a writable `/data` directory. On systems where that is inconvenient, change `DATABASE` to a local path such as `./data/gsp_bot.db` before starting the bot.

## Slash Commands

| Command | Purpose | Access |
| --- | --- | --- |
| `/arrest_log` | Record an arrest and optional mugshot upload. | Authorized command channels |
| `/citation_log` | Record a citation. | Authorized command channels |
| `/bolo_log` | Issue a BOLO with vehicle and expiration data. | Authorized command channels |
| `/warrant_log` | Issue a warrant with risk and expiration data. | Authorized command channels |
| `/infraction_log` | Log misconduct and choose its expiration period. | Supervisor role |
| `/search_record` | Search a record by generated ID. | Authorized command channels |
| `/search_user` | Search records by suspect name. | Authorized command channels |
| `/search_active` | Browse active BOLOs and warrants across configured departments. | Authorized command channels |
| `/trooper_performance` | View a trooper's department performance and status. | Authorized command channels |
| `/dept_performance` | View aggregate department metrics. | Authorized command channels |
| `/user_info` | Display a Discord member profile and activity. | Authorized command channels |
| `/roblox_user` | Look up a Roblox account and show profile statistics. | Authorized command channels |
| `/commands` | Display the current slash-command directory. | Authorized command channels |
| `/clear_record` | Permanently delete a selected record after confirmation. | Authorized command channels |
| `/clear_all_data` | Wipe all database tables after confirmation. | Discord administrators |
| `/status` | Show uptime, response time, memory, and CPU diagnostics. | Bot owner |
| `/logs` | Show recent PM2 error output for the `Northside` process. | Discord administrators |
| `/info` | Display bot support information. | Authorized command channels |

Commands are synced to each guild listed in `GUILD_SETTINGS` by `on_ready`. Discord can take a short time to display newly synchronized commands after the bot starts.

## Stored Data

The SQLite database contains these tables:

- `arrests`: generated ID, suspect, officer, secondaries, charges, mugshot URL, timestamp, and guild.
- `citations`: generated ID, suspect, officer, vehicle, location, reason, timestamp, and guild.
- `bolos`: generated ID, suspect, officer, reason, vehicle, plate, expiration, timestamp, and guild.
- `warrants`: generated ID, suspect, officer, reason, risk level, expiration, timestamp, and guild.
- `infractions`: user, issuer, reason, punishment, proof, message URL, processing state, expiration, timestamp, and guild.

The rotating presence counts all rows across those five tables and displays the total as `watching N law enforcement records`.

## Presence Rotation

The bot changes its Discord activity every three seconds. Current activity sets include:

- Watching the total number of law-enforcement records.
- Watching the number of configured Discord departments currently connected.
- Listening to `/commands` for the command directory.
- Playing `LEO Management 2.0`.
- Watching the current bot uptime.

The record count is read from SQLite for each rotation, so it reflects new records without requiring a restart.

## Validation

Run the Python syntax check before deployment:

```bash
python -m py_compile main.py
```

Confirm that the Railway service has a healthy deployment, the bot appears online, slash commands are visible in configured guilds, and a test record remains after restarting the service.

## Security and Operations

- Keep `DISCORD_TOKEN` in Railway Variables or another secret manager.
- Replace example guild, channel, and role IDs before enabling additional departments.
- Limit the bot's permissions to the configured channels where practical.
- Back up the Railway volume before database maintenance.
- Treat `/clear_all_data` as destructive. It clears every supported SQLite table.
- PM2 must be installed and the process must be named `Northside` for `/logs` to work unchanged.
