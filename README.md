# 🕶 Mafia Baku Black Telegram Bot (Pro Multi-Language Edition)

A high-performance, asynchronous Telegram Mafia game bot modeled after **@MafiaBakuBlack1Bot** and regional Mafia favorites. Built with **Python 3.12+**, **aiogram 3.x**, and **SQLAlchemy 2.0**.

---

## 🌟 Key Features

* **🎭 Rich Role Mechanics:**
  * **Town (Dinc Sakinlər / Tinch Fuqarolar):** Citizen, Doctor, Detective/Sheriff, Bodyguard, Kamikaze.
  * **Mafia (Klan / Mafiozi):** Don (Godfather), Mafioso, Lawyer.
  * **Neutrals (Təkçilər / Yolg'izlar):** Serial Killer/Maniac, Mistress/Courtesan (Leva/Kamilla).
* **🌐 5 Languages Supported:**
  * 🇦🇿 **Azerbaijani (`az`)** (Authentic Baku Black phrasing)
  * 🇺🇿 **Uzbek (`uz`)** (Complete O'zbekcha translation)
  * 🇷🇺 **Russian (`ru`)**
  * 🇬🇧 **English (`en`)**
  * 🇹🇷 **Turkish (`tr`)**
* **🔇 Group Auto-Moderation:**
  * Automatically sets **Night Mute Mode** so players cannot talk during the night cycle.
  * Automatically **mutes eliminated/dead players** so they cannot ghost or spoil the game.
  * Automatically restores permissions when the match concludes.
* **🛒 In-Game Store & Economy:**
  * Dual currency: **Coins (Qızıl / Tanga)** & **Diamonds (Almaz / Olmos)**.
  * **Role Cards**: Increase the probability of obtaining Don, Detective, or Doctor.
  * **Titles & VIP Passes**: Custom prestige ranks displayed on profile cards.
  * **Daily Rewards**: `/daily` streak bonus with cooldown timer.
* **🏆 Tournaments & Ranked Seasons (Turnirlər):**
  * Automated tournament scheduler and enrollment (`/tournament`).
  * Prize pool accumulation and championship recognition.
* **🛡 Mafia Families / Clans (Klanlar):**
  * Establish your clan: `/clan create [TAG] [Clan Name]`.
  * Clan treasury, rating points, and member management.

---

## 🚀 Quick Setup & Installation

### 1. Clone or Open Project
```bash
cd /Users/macbook/.gemini/antigravity/scratch/mafia-telegram-bot
```

### 2. Activate Virtual Environment
```bash
source venv/bin/activate
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` and fill in your details:
```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_IDS=123456789
DB_URL=sqlite+aiosqlite:///mafia_bot.db
DEFAULT_LANGUAGE=az
```

> [!TIP]
> Get your `BOT_TOKEN` from [@BotFather](https://t.me/BotFather) on Telegram.

### 4. Run the Bot
```bash
python main.py
```

### 5. Run Automated Tests
```bash
venv/bin/pytest
```

---

## 🤖 Telegram Bot Permissions

When adding the bot to a group chat, promote it to **Administrator** with the following permissions:
1. **Delete Messages**
2. **Restrict Users / Ban Users** (Needed to silence chat at night and mute eliminated players)

---

## 📜 Commands Reference

### Group Chat Commands
| Command | Description |
| :--- | :--- |
| `/game`, `/oyun`, `/mafia` | Create a new game lobby with interactive join buttons |
| `/start` | Force-start the game early (if minimum players met) |
| `/stop` | Forcefully abort the current game (Creator/Admin) |
| `/setlang` | Set the group chat language (`az`, `uz`, `ru`, `en`, `tr`) |

### Private Chat Commands
| Command | Description |
| :--- | :--- |
| `/profile` | View player profile, win rate, coins, diamonds, and signature role |
| `/shop` | Open the in-game store (Role cards, Titles, VIP passes) |
| `/daily` | Claim daily coin bonus |
| `/top` | View the global leaderboard |
| `/clan` | Mafia Family (Clan) management |
| `/tournament` | View and register for tournaments |
| `/lang` | Select your personal language preference |
| `/help` | Detailed help guide |

---

## 📁 Project Structure

```
mafia-telegram-bot/
├── config/
│   ├── __init__.py
│   └── settings.py          # App settings & timeouts
├── database/
│   ├── __init__.py
│   ├── models.py            # User, GroupChat, Inventory, Clan, Tournament
│   ├── database.py          # Async SQLAlchemy engine
│   └── crud.py              # Queries and business logic
├── locales/
│   ├── az.json              # Azerbaijani localization
│   ├── uz.json              # Uzbek localization
│   ├── ru.json              # Russian localization
│   ├── en.json              # English localization
│   ├── tr.json              # Turkish localization
│   └── i18n.py              # Dynamic i18n engine
├── game/
│   ├── enums.py             # Game phases, roles, teams
│   ├── role_models.py       # Role distributions & Player state
│   ├── room.py              # GameRoom Day/Night state machine
│   └── manager.py           # Multi-group room manager
├── handlers/
│   ├── common.py            # /start, /profile, /lang, /daily, /top
│   ├── game_group.py        # /game, join/leave, voting
│   ├── game_private.py      # Secret PM night action buttons
│   ├── store.py             # /shop and item purchase
│   ├── clans.py             # Clan creation and management
│   └── tournaments.py       # Tournament enrollment
├── services/
│   ├── auto_moderator.py    # Group night-muting and dead-player muting
│   ├── economy_service.py   # Shop catalog and transactions
│   └── tournament_engine.py # Tournaments & prize pools
├── tests/
│   ├── test_game.py         # Role balance & win condition tests
│   └── test_i18n.py         # Multi-language integrity tests
├── .env.example
├── pytest.ini
├── requirements.txt
├── README.md
└── main.py                  # Bot entrypoint
```
