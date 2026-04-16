"""
Admin Panel Plugin
Button-based UI for managing: Shortener, Premium, Force Subscribe, Stats.
Uses helpers/state.py for multi-step input flows.
"""
import asyncio
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)

from bot import Bot
from config import ADMINS
from helpers.state import set_state, get_state, clear_state, update_data
from helpers.premium import add_premium, remove_premium, get_premium_info, list_premium_users
from helpers.fsub import add_channel, remove_channel, get_all_channels
from helpers.shortner_manage import (
    add_shortener, set_active_shortener, remove_shortener,
    list_shorteners, get_shortener_by_name
)
from helpers.analytics import get_stats


# ─── /admin command ───────────────────────────────────────────────────────────

@Bot.on_message(filters.command('admin') & filters.private & filters.user(ADMINS))
async def admin_panel(client: Client, message: Message):
    clear_state(message.from_user.id)
    await message.reply(
        text="<b>🛠 Admin Panel</b>\n\nChoose a section:",
        reply_markup=_main_menu()
    )


def _main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Manage Shortener", callback_data="adm:shortener")],
        [InlineKeyboardButton("⭐ Premium Users", callback_data="adm:premium")],
        [InlineKeyboardButton("📢 Force Subscribe", callback_data="adm:fsub")],
        [InlineKeyboardButton("📊 Stats", callback_data="adm:stats")],
        [InlineKeyboardButton("❌ Close", callback_data="adm:close")],
    ])


# ─── Callback Router ──────────────────────────────────────────────────────────

@Bot.on_callback_query(filters.user(ADMINS) & filters.regex(r"^adm:"))
async def admin_callback(client: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    # ── Main sections ──────────────────────────────────────────────────────────
    if data == "adm:close":
        await query.message.delete()

    elif data == "adm:stats":
        await _show_stats(query)

    elif data == "adm:shortener":
        await query.message.edit_text(
            "<b>🔗 Shortener Management</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Shortener", callback_data="adm:srt_add")],
                [InlineKeyboardButton("📋 List Shorteners", callback_data="adm:srt_list")],
                [InlineKeyboardButton("🔙 Back", callback_data="adm:back")],
            ])
        )

    elif data == "adm:premium":
        await query.message.edit_text(
            "<b>⭐ Premium Management</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Premium", callback_data="adm:prm_add")],
                [InlineKeyboardButton("➖ Remove Premium", callback_data="adm:prm_remove")],
                [InlineKeyboardButton("📋 List Premium", callback_data="adm:prm_list")],
                [InlineKeyboardButton("🔙 Back", callback_data="adm:back")],
            ])
        )

    elif data == "adm:fsub":
        await query.message.edit_text(
            "<b>📢 Force Subscribe Management</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Channel", callback_data="adm:fsub_add")],
                [InlineKeyboardButton("➖ Remove Channel", callback_data="adm:fsub_remove")],
                [InlineKeyboardButton("📋 List Channels", callback_data="adm:fsub_list")],
                [InlineKeyboardButton("🔙 Back", callback_data="adm:back")],
            ])
        )

    elif data == "adm:back":
        clear_state(user_id)
        await query.message.edit_text(
            "<b>🛠 Admin Panel</b>\n\nChoose a section:",
            reply_markup=_main_menu()
        )

    # ── Shortener flows ────────────────────────────────────────────────────────
    elif data == "adm:srt_add":
        set_state(user_id, "srt_wait_url")
        await query.message.edit_text(
            "<b>Step 1/2 — Add Shortener</b>\n\nSend the <b>API URL</b> of the shortener.\n"
            "<i>Example: https://shortx.app</i>\n\nSend /cancel to abort."
        )

    elif data == "adm:srt_list":
        shorteners = await list_shorteners()
        if not shorteners:
            text = "No shorteners added yet."
        else:
            lines = []
            for s in shorteners:
                status = "✅ Active" if s.get("active") else "❌ Inactive"
                lines.append(f"• <b>{s['name']}</b> — {status}\n  <code>{s['api_url']}</code>")
            text = "<b>📋 Shorteners</b>\n\n" + "\n\n".join(lines)

        # Build activate/delete buttons per shortener
        buttons = []
        for s in shorteners:
            row = [
                InlineKeyboardButton(
                    f"{'🔘' if s.get('active') else '⚪'} {s['name']}",
                    callback_data=f"adm:srt_activate:{s['name']}"
                ),
                InlineKeyboardButton("🗑", callback_data=f"adm:srt_delete:{s['name']}")
            ]
            buttons.append(row)
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="adm:shortener")])

        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("adm:srt_activate:"):
        name = data.split(":", 2)[2]
        result = await set_active_shortener(name)
        if result["ok"]:
            await query.answer(f"✅ '{name}' is now active!", show_alert=True)
        else:
            await query.answer(f"❌ {result['error']}", show_alert=True)
        # Refresh list
        await admin_callback(client, _fake_query(query, "adm:srt_list"))

    elif data.startswith("adm:srt_delete:"):
        name = data.split(":", 2)[2]
        result = await remove_shortener(name)
        if result["ok"]:
            await query.answer(f"🗑 '{name}' removed.", show_alert=True)
        else:
            await query.answer(f"❌ {result['error']}", show_alert=True)
        await admin_callback(client, _fake_query(query, "adm:srt_list"))

    # ── Premium flows ──────────────────────────────────────────────────────────
    elif data == "adm:prm_add":
        set_state(user_id, "prm_wait_id")
        await query.message.edit_text(
            "<b>Step 1/2 — Add Premium</b>\n\nSend the <b>User ID</b> to grant premium.\n\nSend /cancel to abort."
        )

    elif data.startswith("adm:prm_days:"):
        # Format: adm:prm_days:USER_ID:DAYS
        parts = data.split(":")
        target_uid = int(parts[2])
        days = int(parts[3])
        expiry = await add_premium(target_uid, days)
        await query.message.edit_text(
            f"✅ Premium granted to <code>{target_uid}</code> for <b>{days} days</b>.\n"
            f"Expires: <b>{expiry.strftime('%Y-%m-%d %H:%M UTC')}</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="adm:premium")]
            ])
        )
        clear_state(user_id)

    elif data == "adm:prm_custom_days":
        state = get_state(user_id)
        if state:
            target_uid = state["data"].get("target_uid")
            set_state(user_id, "prm_wait_custom_days", {"target_uid": target_uid})
            await query.message.edit_text(
                "<b>Custom Days</b>\n\nSend the number of days to grant:"
            )

    elif data == "adm:prm_remove":
        set_state(user_id, "prm_wait_remove_id")
        await query.message.edit_text(
            "<b>Remove Premium</b>\n\nSend the <b>User ID</b> to revoke premium.\n\nSend /cancel to abort."
        )

    elif data == "adm:prm_list":
        users = await list_premium_users()
        if not users:
            text = "No active premium users."
        else:
            lines = [
                f"• <code>{u['user_id']}</code> — expires {u['expiry'].strftime('%Y-%m-%d')}"
                for u in users
            ]
            text = "<b>⭐ Active Premium Users</b>\n\n" + "\n".join(lines)
        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="adm:premium")]
            ])
        )

    # ── ForceSub flows ─────────────────────────────────────────────────────────
    elif data == "adm:fsub_add":
        set_state(user_id, "fsub_wait_channel")
        await query.message.edit_text(
            "<b>Add Force Subscribe Channel</b>\n\n"
            "Forward any message from the channel OR send the channel ID (e.g. <code>-100xxxxxxxxxx</code>).\n\n"
            "Send /cancel to abort."
        )

    elif data == "adm:fsub_list":
        channels = await get_all_channels()
        if not channels:
            text = "No channels added."
        else:
            lines = [f"• <b>{c['title']}</b> — <code>{c['chat_id']}</code>" for c in channels]
            text = "<b>📢 Force Sub Channels</b>\n\n" + "\n".join(lines)

        buttons = [
            [InlineKeyboardButton(f"🗑 {c['title']}", callback_data=f"adm:fsub_del:{c['chat_id']}")]
            for c in channels
        ]
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="adm:fsub")])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("adm:fsub_del:"):
        chat_id = int(data.split(":")[2])
        result = await remove_channel(chat_id)
        if result["ok"]:
            await query.answer("✅ Channel removed.", show_alert=True)
        else:
            await query.answer(f"❌ {result['error']}", show_alert=True)
        await admin_callback(client, _fake_query(query, "adm:fsub_list"))

    elif data == "adm:fsub_remove":
        await admin_callback(client, _fake_query(query, "adm:fsub_list"))


# ─── Message handler for multi-step state inputs ──────────────────────────────

@Bot.on_message(filters.private & filters.user(ADMINS) & ~filters.command(['start', 'admin', 'users', 'broadcast', 'batch', 'genlink']))
async def admin_state_handler(client: Client, message: Message):
    user_id = message.from_user.id
    state_info = get_state(user_id)

    if not state_info:
        return  # Not in an admin flow; let other handlers deal with it

    state = state_info["state"]
    data = state_info["data"]
    text = message.text or ""

    # Cancel
    if text.strip() == "/cancel":
        clear_state(user_id)
        await message.reply("❌ Action cancelled.", quote=True)
        return

    # ── Shortener: step 1 — API URL ───────────────────────────────────────────
    if state == "srt_wait_url":
        update_data(user_id, "api_url", text.strip())
        set_state(user_id, "srt_wait_key", {"api_url": text.strip()})
        await message.reply(
            "<b>Step 2/2 — Add Shortener</b>\n\nNow send the <b>API Key</b>:",
            quote=True
        )

    # ── Shortener: step 2 — API Key ──────────────────────────────────────────
    elif state == "srt_wait_key":
        api_url = data.get("api_url", "")
        api_key = text.strip()
        # Derive name from domain
        try:
            from urllib.parse import urlparse
            name = urlparse(api_url).netloc.replace("www.", "").split(".")[0]
        except Exception:
            name = "custom"

        result = await add_shortener(name, api_url, api_key)
        clear_state(user_id)
        await message.reply(
            f"✅ Shortener <b>{name}</b> {result['action']} successfully!\n"
            "Use the List Shorteners menu to activate it.",
            quote=True
        )

    # ── Premium: step 1 — User ID ─────────────────────────────────────────────
    elif state == "prm_wait_id":
        try:
            target_uid = int(text.strip())
        except ValueError:
            await message.reply("❌ Invalid User ID. Send a numeric ID.", quote=True)
            return

        set_state(user_id, "prm_wait_days", {"target_uid": target_uid})
        await message.reply(
            f"<b>Step 2/2 — Grant Premium</b>\n\nUser: <code>{target_uid}</code>\n\nSelect duration:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("7 Days", callback_data=f"adm:prm_days:{target_uid}:7"),
                    InlineKeyboardButton("30 Days", callback_data=f"adm:prm_days:{target_uid}:30"),
                ],
                [
                    InlineKeyboardButton("90 Days", callback_data=f"adm:prm_days:{target_uid}:90"),
                    InlineKeyboardButton("Custom", callback_data="adm:prm_custom_days"),
                ],
            ]),
            quote=True
        )

    # ── Premium: custom days input ────────────────────────────────────────────
    elif state == "prm_wait_custom_days":
        try:
            days = int(text.strip())
            if days <= 0:
                raise ValueError
        except ValueError:
            await message.reply("❌ Send a positive integer (number of days).", quote=True)
            return

        target_uid = data.get("target_uid")
        expiry = await add_premium(target_uid, days)
        clear_state(user_id)
        await message.reply(
            f"✅ Premium granted to <code>{target_uid}</code> for <b>{days} days</b>.\n"
            f"Expires: <b>{expiry.strftime('%Y-%m-%d %H:%M UTC')}</b>",
            quote=True
        )

    # ── Premium: remove ───────────────────────────────────────────────────────
    elif state == "prm_wait_remove_id":
        try:
            target_uid = int(text.strip())
        except ValueError:
            await message.reply("❌ Invalid User ID.", quote=True)
            return

        removed = await remove_premium(target_uid)
        clear_state(user_id)
        if removed:
            await message.reply(f"✅ Premium removed from <code>{target_uid}</code>.", quote=True)
        else:
            await message.reply(f"ℹ️ User <code>{target_uid}</code> had no active premium.", quote=True)

    # ── ForceSub: add channel ─────────────────────────────────────────────────
    elif state == "fsub_wait_channel":
        chat_id = None
        title = "Unknown"

        # Try forwarded message
        if message.forward_from_chat:
            chat_id = message.forward_from_chat.id
            title = message.forward_from_chat.title or "Channel"
        else:
            # Try plain chat_id text
            try:
                chat_id = int(text.strip())
                chat = await client.get_chat(chat_id)
                title = chat.title or "Channel"
            except Exception:
                await message.reply(
                    "❌ Could not resolve channel. Forward a message from it or send its numeric ID.",
                    quote=True
                )
                return

        result = await add_channel(chat_id, title)
        clear_state(user_id)
        if result["ok"]:
            await message.reply(
                f"✅ Channel <b>{title}</b> (<code>{chat_id}</code>) added to Force Subscribe!",
                quote=True
            )
        else:
            await message.reply(f"❌ {result['error']}", quote=True)


# ─── Stats ────────────────────────────────────────────────────────────────────

async def _show_stats(query: CallbackQuery):
    stats = await get_stats()
    top = "\n".join(
        [f"  • File <code>{f['_id']}</code>: {f['count']} clicks" for f in stats["top_files"]]
    ) or "  None yet"

    text = (
        f"<b>📊 Bot Statistics</b>\n\n"
        f"👥 <b>Total Users:</b> {stats['total_users']}\n"
        f"⭐ <b>Active Premium:</b> {stats['active_premium_users']}\n\n"
        f"📥 <b>Total File Clicks:</b> {stats['total_clicks']}\n"
        f"⭐ <b>Premium Clicks:</b> {stats['premium_clicks']}\n"
        f"🆓 <b>Free Clicks:</b> {stats['free_clicks']}\n\n"
        f"🏆 <b>Top Files:</b>\n{top}"
    )
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="adm:back")]
        ])
    )


# ─── Utility ──────────────────────────────────────────────────────────────────

def _fake_query(original: CallbackQuery, new_data: str) -> CallbackQuery:
    """Create a shallow copy of a CallbackQuery with different data for re-routing."""
    original.data = new_data
    return original
