"""
Start plugin — handles /start, file delivery, force-subscribe, shortener, analytics.

Payload prefix convention (encoded in base64 start param):
  "file-XXXX"      → original shared link (first visit)
  "file-XXXX-YYYY" → original shared batch link (first visit)
  "get-XXXX"       → verified link after passing shortener (free user, deliver file)
  "get-XXXX-YYYY"  → verified batch link after passing shortener

Flow for free users:
  1. User clicks shared link  → payload starts with "file-"
     → show shortener button; shortener URL points to a "get-" encoded link
  2. User completes shortener, clicks bot link → payload starts with "get-"
     → deliver file directly

Premium / Admin users skip the shortener entirely on the "file-" payload.
"""
import asyncio
import humanize

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
)
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated

from bot import Bot
from config import (
    ADMINS, FORCE_MSG, START_MSG, CUSTOM_CAPTION,
    DISABLE_CHANNEL_BUTTON, PROTECT_CONTENT, FILE_AUTO_DELETE
)
from helper_func import subscribed, encode, decode, get_messages, build_fsub_buttons
from database.database import add_user, del_user, full_userbase, present_user
from helpers.premium import is_premium
from helpers.shortner import get_shortlink
from helpers.analytics import save_click

file_auto_delete_readable = humanize.naturaldelta(FILE_AUTO_DELETE)


def _parse_ids(argument: list, db_channel_id: int) -> list | None:
    """
    Parse message IDs from a decoded payload argument list.
    argument[0] is the prefix ("file" or "get"), argument[1] (and optionally [2]) are encoded IDs.
    Returns a list of message IDs, or None on parse failure.
    """
    try:
        if len(argument) == 3:
            start = int(int(argument[1]) / abs(db_channel_id))
            end   = int(int(argument[2]) / abs(db_channel_id))
            return list(range(start, end + 1)) if start <= end else list(range(start, end - 1, -1))
        elif len(argument) == 2:
            return [int(int(argument[1]) / abs(db_channel_id))]
    except Exception:
        pass
    return None


# ─── /start (subscribed) ───────────────────────────────────────────────────────

@Bot.on_message(filters.command('start') & filters.private & subscribed)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id

    # Register user
    if not await present_user(user_id):
        try:
            await add_user(user_id)
        except Exception:
            pass

    text = message.text
    if len(text) > 7:
        # ── Has a payload ──────────────────────────────────────────────────────
        try:
            base64_string = text.split(" ", 1)[1]
        except IndexError:
            return

        try:
            string = await decode(base64_string)
        except Exception:
            return

        argument = string.split("-")
        if len(argument) < 2:
            return

        prefix = argument[0]   # "file" or "get"
        ids = _parse_ids(argument, client.db_channel.id)
        if ids is None:
            return

        premium = await is_premium(user_id)
        is_admin = user_id in ADMINS

        # ── "get-" payload: always deliver the file (shortener already passed) ─
        if prefix == "get":
            await _send_files(client, message, ids, premium=premium or is_admin)
            return

        # ── "file-" payload ────────────────────────────────────────────────────
        # Premium / Admin → deliver directly, no shortener
        if premium or is_admin:
            await _send_files(client, message, ids, premium=True)
            return

        # Free user → build a "get-" payload for the post-shortener link
        # Re-encode argument[1] (and optionally [2]) under the "get" prefix
        if len(argument) == 3:
            get_string = f"get-{argument[1]}-{argument[2]}"
        else:
            get_string = f"get-{argument[1]}"

        get_base64 = await encode(get_string)
        verified_link = f"https://t.me/{client.username}?start={get_base64}"

        # Wrap verified_link through the active shortener
        short_link = await get_shortlink(verified_link)

        await message.reply(
            text=(
                "🔗 <b>Access Your File</b>\n\n"
                "YOU ARE NOT A PREMIUM USER.\n"
                "<i>Complete the shortner steps, then you'll get ur link.</i>"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Get File Now", url=short_link)],
            ]),
            quote=True,
            disable_web_page_preview=True
        )

    else:
        # No payload → welcome message
        reply_markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("😊 About Me", callback_data="about"),
                InlineKeyboardButton("🔒 Close", callback_data="close")
            ]
        ])
        await message.reply_text(
            text=START_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            quote=True
        )


# ─── /start (not subscribed) ──────────────────────────────────────────────────

@Bot.on_message(filters.command('start') & filters.private)
async def not_joined(client: Client, message: Message):
    command_arg = message.command[1] if len(message.command) > 1 else None
    reply_markup = await build_fsub_buttons(client, command_arg)

    await message.reply(
        text=FORCE_MSG.format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=None if not message.from_user.username else '@' + message.from_user.username,
            mention=message.from_user.mention,
            id=message.from_user.id
        ),
        reply_markup=reply_markup,
        quote=True,
        disable_web_page_preview=True
    )


# ─── File delivery helper ─────────────────────────────────────────────────────

async def _send_files(client: Client, message: Message, ids: list, premium: bool):
    """Fetch files from DB channel and forward them to the user."""
    user_id = message.from_user.id
    temp_msg = await message.reply("Please Wait...")

    try:
        messages = await get_messages(client, ids)
    except Exception:
        await message.reply_text("Something Went Wrong..!")
        return
    await temp_msg.delete()

    sent_msgs = []
    for msg in messages:
        if bool(CUSTOM_CAPTION) and bool(msg.document):
            caption = CUSTOM_CAPTION.format(
                previouscaption="" if not msg.caption else msg.caption.html,
                filename=msg.document.file_name
            )
        else:
            caption = "" if not msg.caption else msg.caption.html

        reply_markup = msg.reply_markup if DISABLE_CHANNEL_BUTTON else None

        try:
            sent = await msg.copy(
                chat_id=user_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
                protect_content=PROTECT_CONTENT
            )
            sent_msgs.append(sent)
        except FloodWait as e:
            await asyncio.sleep(e.x)
            try:
                sent = await msg.copy(
                    chat_id=user_id,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    protect_content=PROTECT_CONTENT
                )
                sent_msgs.append(sent)
            except Exception:
                pass
        except Exception:
            pass

        # Analytics: log each file access
        try:
            await save_click(user_id=user_id, file_id=msg.id, is_premium=premium)
        except Exception:
            pass

    # Auto-delete notice
    notice = await client.send_message(
        chat_id=user_id,
        text=(
            f"<b>❗️ <u>IMPORTANT</u> ❗️</b>\n\n"
            f"This File Will Be Deleted In <b>{file_auto_delete_readable}</b> "
            f"(Due To Copyright Issues).\n\n"
            f"📌 Please Forward It Somewhere Else And Start Downloading There."
        )
    )

    asyncio.create_task(delete_files(sent_msgs, client, notice))


# ─── Auto-delete task ─────────────────────────────────────────────────────────

async def delete_files(messages: list, client: Client, notice_msg):
    await asyncio.sleep(FILE_AUTO_DELETE)
    for msg in messages:
        try:
            await client.delete_messages(chat_id=msg.chat.id, message_ids=[msg.id])
        except Exception as e:
            print(f"[AutoDelete] Failed to delete {msg.id}: {e}")
    try:
        await notice_msg.edit_text("Your File Has Been Successfully Deleted ✅")
    except Exception:
        pass


# ─── Admin commands ───────────────────────────────────────────────────────────

@Bot.on_message(filters.command('users') & filters.private & filters.user(ADMINS))
async def get_users(client: Bot, message: Message):
    msg = await client.send_message(chat_id=message.chat.id, text="Processing...")
    users = await full_userbase()
    await msg.edit(f"<b>{len(users)}</b> Users Are Using This Bot")


@Bot.on_message(filters.private & filters.command('broadcast') & filters.user(ADMINS))
async def send_text(client: Bot, message: Message):
    if not message.reply_to_message:
        msg = await message.reply("Use this command as a reply to any Telegram message.")
        await asyncio.sleep(8)
        await msg.delete()
        return

    query = await full_userbase()
    broadcast_msg = message.reply_to_message
    total = successful = blocked = deleted = unsuccessful = 0

    pls_wait = await message.reply("<i>Broadcasting Message... This Will Take Some Time</i>")
    for chat_id in query:
        try:
            await broadcast_msg.copy(chat_id)
            successful += 1
        except FloodWait as e:
            await asyncio.sleep(e.x)
            await broadcast_msg.copy(chat_id)
            successful += 1
        except UserIsBlocked:
            await del_user(chat_id)
            blocked += 1
        except InputUserDeactivated:
            await del_user(chat_id)
            deleted += 1
        except Exception:
            unsuccessful += 1
        total += 1

    status = (
        f"<b><u>Broadcast Completed</u></b>\n\n"
        f"<b>Total Users:</b> <code>{total}</code>\n"
        f"<b>Successful:</b> <code>{successful}</code>\n"
        f"<b>Blocked Users:</b> <code>{blocked}</code>\n"
        f"<b>Deleted Accounts:</b> <code>{deleted}</code>\n"
        f"<b>Unsuccessful:</b> <code>{unsuccessful}</code>"
    )
    await pls_wait.edit(status)
