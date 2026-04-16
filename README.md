# FileStore Bot — Upgraded

## New Features
- **Multi Force Subscribe** (up to 6 channels) via `/admin` → Force Subscribe
- **Premium Users** with expiry-based access via `/admin` → Premium Users
- **Shortener Monetization** — dynamic URL shortener via `/admin` → Manage Shortener
- **Analytics Tracking** — file clicks, premium vs free stats
- **Admin Panel** — full button UI via `/admin`

## Removed
- `FORCE_SUB_CHANNEL` env var (replaced by DB-driven multi-fsub)

## Environment Variables
| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram Bot Token |
| `API_ID` | Telegram API ID |
| `API_HASH` | Telegram API Hash |
| `OWNER_ID` | Bot owner Telegram user ID |
| `DB_URL` | MongoDB connection string |
| `DB_NAME` | MongoDB database name (default: `madflixbotz`) |
| `CHANNEL_ID` | DB storage channel ID |
| `FILE_AUTO_DELETE` | Seconds before file deletion (default: 600) |
| `ADMINS` | Space-separated additional admin user IDs |
| `PROTECT_CONTENT` | True/False |
| `DISABLE_CHANNEL_BUTTON` | True/False |
| `CUSTOM_CAPTION` | Optional custom file caption |

## Admin Commands
- `/admin` — Open admin panel
- `/users` — Total user count
- `/broadcast` — Broadcast message (reply to a message)
- `/batch` — Generate batch link
- `/genlink` — Generate single file link

## Admin Panel Flow
1. `/admin` → buttons for each section
2. **Shortener**: Add (API URL → API Key) → List → Activate/Delete
3. **Premium**: Add (User ID → days: 7/30/90/Custom) | Remove | List
4. **Force Sub**: Add (forward msg or ID) | Remove | List (max 6 channels)
5. **Stats**: Total users, premium count, click analytics
