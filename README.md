# Auction Bot

A Discord bot for running live and scheduled auctions, with a mystery crate system.

## Table of contents

<!-- toc -->

- [Development](#development)
  - [Setup](#setup)
  - [Type Checking](#type-checking)
  - [Project Structure](#project-structure)
- [Features](#features)
  - [Auctions](#auctions)
  - [Scheduled Auctions](#scheduled-auctions)
  - [Mystery Crates](#mystery-crates)
- [Commands](#commands)

<!-- tocstop -->

## Development

### Setup

1. Create a `.env` file with your Discord bot token:

   ```
   DISCORD_TOKEN=your_token_here
   ```

2. Install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Run the bot:
   ```bash
   python main.py
   ```

The SQLite database (`data.db`) is created automatically on first run.

### Type Checking

The project uses [mypy](https://mypy.readthedocs.io/) for static type checking. It is already installed in the virtual environment.

Run it from the project root:

```bash
.venv/bin/mypy .
```

Configuration is in `mypy.ini`. The most important settings:

- `explicit_package_bases = True` — required because the project uses `src.` prefixed imports without a top-level package
- `ignore_missing_imports = True` — suppresses errors for third-party libraries (discord.py, etc.) that don't ship type stubs

Mypy will not check the bodies of untyped functions by default. To enable stricter checking, add `check_untyped_defs = True` to `mypy.ini`.

### Project Structure

```
main.py                         # Entry point
database.py                     # SQLite wrapper
src/
  AuctionBot.py                 # Bot subclass, in-memory state, scheduled auction loop
  Auction.py                    # Live auction data class
  ItemDropdownView.py           # Mystery crate item browser UI
  auctionFunctions/             # Shared auction logic (trigger, bid, finalize, reminders)
  commands/
    auctionCommands/            # Slash commands for auctions
    mysteryCrateCommands/       # Slash commands for mystery crates
  helperFunctions/              # Parsers, formatters, Discord lookup helpers
```

## Features

### Auctions

- Start a live auction immediately or schedule one for a future date/time
- Live auction embed that updates on each bid
- Minimum increment enforcement and anti-snipe protection (extends by 1 minute if a bid is placed in the last 2 minutes)
- Quick-bid command to auto-bid current price + increment
- Timed reminders at 1 hour and 5 minutes before end
- Early termination by the seller or an admin
- Winner announcement and seller DM on completion
- Outbid DM notifications (opt-in via 🔔 reaction)

### Scheduled Auctions

- Schedule auctions with a specific start date and time
- Background task checks every 60 seconds and auto-starts when the time arrives
- Subscribe for a DM notification when an auction starts via the "Notify Me" button
- `/upcoming` command lists all scheduled auctions for the current channel

### Mystery Crates

- Admins manage an item pool with names and images
- Users spend points to draw a random item
- Browse available items via interactive dropdown
- Point balance management per user

## Commands

| Command         | Description                             | Role Required    |
| --------------- | --------------------------------------- | ---------------- |
| `/startauction` | Start or schedule an auction            | Cryysys          |
| `/bid`          | Place a bid with a custom amount        | —                |
| `/quickbid`     | Bid current price + minimum increment   | —                |
| `/status`       | Show the current auction status embed   | —                |
| `/endauction`   | End the current auction early           | Seller / Cryysys |
| `/upcoming`     | List scheduled auctions in this channel | —                |
| `/additem`      | Add an item to the mystery crate pool   | Cryysys          |
| `/removeitem`   | Remove an item from the pool            | Cryysys          |
| `/items`        | Browse available items                  | —                |
| `/addpoints`    | Add points to a user                    | Cryysys          |
| `/removepoints` | Remove points from a user               | Cryysys          |
| `/setdrawcost`  | Set the points cost per draw            | Cryysys          |
| `/points`       | Check your own point balance            | —                |
| `/draw`         | Spend points to draw a random item      | —                |
