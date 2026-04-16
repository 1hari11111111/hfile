"""
Core helper functions.
Multi Force-Subscribe replaces the old single-channel FORCE_SUB_CHANNEL logic.
"""
import base64
import re
import asyncio

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMINS
from helpers.fsub import get_all_channels


# ─── Multi Force Subscribe ─────────────────────────────────────────────────────

async def is_subscribed(filter, client, update):
    """
    Check if the user is subscribed to ALL registered fsub channels.
    Returns True immediately for admins or if no channels are configured.
    """
    user_id = update.from_user.id
    if user_id in ADMINS:
        return True

    channels = await get_all_channels()
    if not channels:
        return True  # No channels configured → open access

    for ch in channels:
        chat_id = ch["chat_id"]
        try:
            member = await client.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status not in [
                ChatMemberStatus.OWNER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.MEMBER,
            ]:
                return False
        except UserNotParticipant:
            return False
        except Exception:
            # If we can't check (bot not in channel etc.) → allow through
            pass

    return True


async def build_fsub_buttons(client, command_arg: str = None) -> InlineKeyboardMarkup:
    """
    Build an InlineKeyboardMarkup with join buttons for every unjoined channel
    plus a 'Try Again' button at the bottom.
    """
    channels = await get_all_channels()
    buttons = []

    for ch in channels:
        chat_id = ch["chat_id"]
        title = ch.get("title", "Channel")
        try:
            invite_link = (await client.get_chat(chat_id)).invite_link
            if not invite_link:
                invite_link = await client.export_chat_invite_link(chat_id)
        except Exception:
            invite_link = "https://t.me"

        buttons.append([InlineKeyboardButton(f"➕ Join {title}", url=invite_link)])

    # Try Again button
    if command_arg:
        try_url = f"https://t.me/{client.username}?start={command_arg}"
    else:
        try_url = f"https://t.me/{client.username}"
    buttons.append([InlineKeyboardButton("🔄 Try Again", url=try_url)])

    return InlineKeyboardMarkup(buttons)


subscribed = filters.create(is_subscribed)


# ─── Encoding / Decoding ───────────────────────────────────────────────────────

async def encode(string: str) -> str:
    string_bytes = string.encode("ascii")
    base64_bytes = base64.urlsafe_b64encode(string_bytes)
    return (base64_bytes.decode("ascii")).strip("=")


async def decode(base64_string: str) -> str:
    base64_string = base64_string.strip("=")
    base64_bytes = (base64_string + "=" * (-len(base64_string) % 4)).encode("ascii")
    string_bytes = base64.urlsafe_b64decode(base64_bytes)
    return string_bytes.decode("ascii")


# ─── Message Fetching ──────────────────────────────────────────────────────────

async def get_messages(client, message_ids: list) -> list:
    messages = []
    total_messages = 0
    while total_messages != len(message_ids):
        temp_ids = message_ids[total_messages: total_messages + 200]
        try:
            msgs = await client.get_messages(
                chat_id=client.db_channel.id,
                message_ids=temp_ids
            )
        except FloodWait as e:
            await asyncio.sleep(e.x)
            msgs = await client.get_messages(
                chat_id=client.db_channel.id,
                message_ids=temp_ids
            )
        except Exception:
            msgs = []
        total_messages += len(temp_ids)
        messages.extend(msgs)
    return messages


async def get_message_id(client, message) -> int:
    if message.forward_from_chat:
        if message.forward_from_chat.id == client.db_channel.id:
            return message.forward_from_message_id
        return 0
    elif message.forward_sender_name:
        return 0
    elif message.text:
        pattern = r"https://t.me/(?:c/)?(.*)/(\\d+)"
        matches = re.match(pattern, message.text)
        if not matches:
            return 0
        channel_id = matches.group(1)
        msg_id = int(matches.group(2))
        if channel_id.isdigit():
            if f"-100{channel_id}" == str(client.db_channel.id):
                return msg_id
        else:
            if channel_id == client.db_channel.username:
                return msg_id
    return 0


# ─── Utility ───────────────────────────────────────────────────────────────────

def get_readable_time(seconds: int) -> str:
    count = 0
    up_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    hmm = len(time_list)
    for x in range(hmm):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        up_time += f"{time_list.pop()}, "
    time_list.reverse()
    up_time += ":".join(time_list)
    return up_time
