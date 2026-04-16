"""
Admin Panel Plugin
Button-based UI for managing: Shortener, Premium, Force Subscribe, Stats.
Uses helpers/state.py for multi-step input flows.

Shortener changes vs original:
  - Multiple shorteners can be active at once (random selection per link).
  - Toggle button activates/deactivates without affecting others.
  - Inline Edit button lets admin update API URL or API Key without re-adding.
  - Back buttons added to every view.
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
    add_shortener, toggle_shortener, remove_shortener,
    list_shorteners, get_shortener_by_name, update_shortener_field
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
        [InlineKeyboardButton("🔗 Manage Shorteners", callback_data="adm:shortener")],
        [InlineKeyboardButton("⭐ Premium Users",      callback_data="adm:premium")],
        [InlineKeyboardButton("📢 Force Subscribe",    callback_data="adm:fsub")],
        [InlineKeyboardButton("📊 Stats",              callback_data="adm:stats")],
        [InlineKeyboardButton("❌ Close",              callback_data="adm:close")],
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
            "<b>🔗 Shortener Management</b>\n\n"
            "ℹ️ <i>Multiple shorteners can be active at once. "
            "A random one is chosen for each link.</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Shortener",  callback_data="adm:srt_add")],
                [InlineKeyboardButton("📋 List Shorteners", callback_data="adm:srt_list")],
                [InlineKeyboardButton("🔙 Back",            callback_data="adm:back")],
            ])
        )

    elif data == "adm:premium":
        await query.message.edit_text(
            "<b>⭐ Premium Management</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Premium",    callback_data="adm:prm_add")],
                [InlineKeyboardButton("➖ Remove Premium", callback_data="adm:prm_remove")],
                [InlineKeyboardButton("📋 List Premium",   callback_data="adm:prm_list")],
                [InlineKeyboardButton("🔙 Back",           callback_data="adm:back")],
            ])
        )

    elif data == "adm:fsub":
        await query.message.edit_text(
            "<b>📢 Force Subscribe Management</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Channel",    callback_data="adm:fsub_add")],
                [InlineKeyboardButton("➖ Remove Channel", callback_data="adm:fsub_remove")],
                [InlineKeyboardButton("📋 List Channels",  callback_data="adm:fsub_list")],
                [InlineKeyboardButton("🔙 Back",           callback_data="adm:back")],
            ])
        )

    elif data == "adm:back":
        clear_state(user_id)
        await query.message.edit_text(
            "<b>🛠 Admin Panel</b>\n\nChoose a section:",
            reply_markup=_main_menu()
        )

    # ── Shortener: add flow ────────────────────────────────────────────────────
    elif data == "adm:srt_add":
        set_state(user_id, "srt_wait_url")
        await query.message.edit_text(
            "<b>➕ Add Shortener — Step 1/2</b>\n\n"
            "Send the <b>API URL</b> of the shortener.\n"
            "<i>Example: https://shortx.app</i>\n\n"
            "Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="adm:shortener")]
            ])
        )

    # ── Shortener: list with toggle / edit / delete ───────────────────────────
    elif data == "adm:srt_list":
        await _show_shortener_list(query)

    elif data.startswith("adm:srt_toggle:"):
        name = data.split(":", 2)[2]
        result = await toggle_shortener(name)
        if result["ok"]:
            state_label = "✅ activated" if result["active"] else "⛔ deactivated"
            await query.answer(f"'{name}' {state_label}!", show_alert=False)
        else:
            await query.answer(f"❌ {result['error']}", show_alert=True)
        await _show_shortener_list(query)

    elif data.startswith("adm:srt_edit:"):
        name = data.split(":", 2)[2]
        set_state(user_id, "srt_edit_choose", {"edit_name": name})
        shortener = await get_shortener_by_name(name)
        await query.message.edit_text(
            f"<b>✏️ Edit Shortener: {name}</b>\n\n"
            f"<b>Current URL:</b> <code>{shortener['api_url']}</code>\n"
            f"<b>API Key:</b> <code>{shortener['api_key']}</code>\n\n"
            "What do you want to update?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Change API URL", callback_data=f"adm:srt_edit_url:{name}")],
                [InlineKeyboardButton("🔑 Change API Key", callback_data=f"adm:srt_edit_key:{name}")],
                [InlineKeyboardButton("🔙 Back",           callback_data="adm:srt_list")],
            ])
        )

    elif data.startswith("adm:srt_edit_url:"):
        name = data.split(":", 2)[2]
        set_state(user_id, "srt_wait_edit_url", {"edit_name": name})
        await query.message.edit_text(
            f"<b>✏️ Edit URL — {name}</b>\n\n"
            "Send the new <b>API URL</b>:\n\n"
            "Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data=f"adm:srt_edit:{name}")]
            ])
        )

    elif data.startswith("adm:srt_edit_key:"):
        name = data.split(":", 2)[2]
        set_state(user_id, "srt_wait_edit_key", {"edit_name": name})
        await query.message.edit_text(
            f"<b>✏️ Edit API Key — {name}</b>\n\n"
            "Send the new <b>API Key</b>:\n\n"
            "Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data=f"adm:srt_edit:{name}")]
            ])
        )

    elif data.startswith("adm:srt_delete:"):
        name = data.split(":", 2)[2]
        # Show confirmation prompt
        await query.message.edit_text(
            f"<b>🗑 Delete Shortener</b>\n\n"
            f"Are you sure you want to delete <b>{name}</b>?",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Yes, Delete", callback_data=f"adm:srt_confirm_del:{name}"),
                    InlineKeyboardButton("❌ Cancel",      callback_data="adm:srt_list"),
                ]
            ])
        )

    elif data.startswith("adm:srt_confirm_del:"):
        name = data.split(":", 2)[2]
        result = await remove_shortener(name)
        if result["ok"]:
            await query.answer(f"🗑 '{name}' deleted.", show_alert=False)
        else:
            await query.answer(f"❌ {result['error']}", show_alert=True)
        await _show_shortener_list(query)

    # ── Premium flows ──────────────────────────────────────────────────────────
    elif data == "adm:prm_add":
        set_state(user_id, "prm_wait_id")
        await query.message.edit_text(
            "<b>➕ Add Premium — Step 1/2</b>\n\n"
            "Send the <b>User ID</b> to grant premium.\n\n"
            "Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="adm:premium")]
            ])
        )

    elif data.startswith("adm:prm_days:"):
        parts = data.split(":")
        target_uid = int(parts[2])
        days = int(parts[3])
        expiry = await add_premium(target_uid, days)
        clear_state(user_id)
        await query.message.edit_text(
            f"✅ Premium granted to <code>{target_uid}</code> for <b>{days} days</b>.\n"
            f"Expires: <b>{expiry.strftime('%Y-%m-%d %H:%M UTC')}</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="adm:premium")]
            ])
        )

    elif data == "adm:prm_custom_days":
        state = get_state(user_id)
        if state:
            target_uid = state["data"].get("target_uid")
            set_state(user_id, "prm_wait_custom_days", {"target_uid": target_uid})
            await query.message.edit_text(
                "<b>Custom Days</b>\n\nSend the number of days to grant:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="adm:premium")]
                ])
            )

    elif data == "adm:prm_remove":
        set_state(user_id, "prm_wait_remove_id")
        await query.message.edit_text(
            "<b>➖ Remove Premium</b>\n\n"
            "Send the <b>User ID</b> to revoke premium.\n\n"
            "Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="adm:premium")]
            ])
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
            "<b>📢 Add Force Subscribe Channel</b>\n\n"
            "Forward any message from the channel OR send the channel ID "
            "(e.g. <code>-100xxxxxxxxxx</code>).\n\n"
            "Send /cancel to abort.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="adm:fsub")]
            ])
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
            await query.answer("✅ Channel removed.", show_alert=False)
        else:
            await query.answer(f"❌ {result['error']}", show_alert=True)
        await admin_callback(client, _fake_query(query, "adm:fsub_list"))

    elif data == "adm:fsub_remove":
        await admin_callback(client, _fake_query(query, "adm:fsub_list"))


# ─── Shortener list view (shared helper) ──────────────────────────────────────

async def _show_shortener_list(query: CallbackQuery):
    shorteners = await list_shorteners()
    if not shorteners:
        text = (
            "<b>📋 Shorteners</b>\n\n"
            "No shorteners added yet.\nUse ➕ Add to get started."
        )
        buttons = []
    else:
        active_names = [s["name"] for s in shorteners if s.get("active")]
        active_count = len(active_names)
        status_note = (
            f"✅ <b>{active_count} active</b> shortener(s) — chosen randomly per link."
            if active_count else
            "⚠️ <b>No active shorteners</b> — links won't be shortened."
        )

        lines = []
        for s in shorteners:
            status = "✅" if s.get("active") else "⛔"
            lines.append(
                f"{status} <b>{s['name']}</b>\n"
                f"   <code>{s['api_url']}</code>"
            )
        text = f"<b>📋 Shorteners</b>\n\n{status_note}\n\n" + "\n\n".join(lines)

        buttons = []
        for s in shorteners:
            toggle_label = "✅ ON" if s.get("active") else "⛔ OFF"
            buttons.append([
                InlineKeyboardButton(
                    f"{toggle_label}  {s['name']}",
                    callback_data=f"adm:srt_toggle:{s['name']}"
                ),
                InlineKeyboardButton("✏️", callback_data=f"adm:srt_edit:{s['name']}"),
                InlineKeyboardButton("🗑", callback_data=f"adm:srt_delete:{s['name']}"),
            ])

    buttons.append([
        InlineKeyboardButton("➕ Add New", callback_data="adm:srt_add"),
        InlineKeyboardButton("🔙 Back",    callback_data="adm:shortener"),
    ])
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# ─── Message handler for multi-step state inputs ──────────────────────────────

@Bot.on_message(
    filters.private & filters.user(ADMINS) &
    ~filters.command(['start', 'admin', 'users', 'broadcast', 'batch', 'genlink'])
)
async def admin_state_handler(client: Client, message: Message):
    user_id = message.from_user.id
    state_info = get_state(user_id)

    if not state_info:
        return

    state = state_info["state"]
    data  = state_info["data"]
    text  = message.text or ""

    # Cancel
    if text.strip() == "/cancel":
        clear_state(user_id)
        await message.reply(
            "❌ Action cancelled.",
            quote=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="adm:back")]
            ])
        )
        return

    # ── Shortener: add step 1 — API URL ───────────────────────────────────────
    if state == "srt_wait_url":
        update_data(user_id, "api_url", text.strip())
        set_state(user_id, "srt_wait_key", {"api_url": text.strip()})
        await message.reply(
            "<b>➕ Add Shortener — Step 2/2</b>\n\nNow send the <b>API Key</b>:",
            quote=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Cancel", callback_data="adm:shortener")]
            ])
        )

    # ── Shortener: add step 2 — API Key ───────────────────────────────────────
    elif state == "srt_wait_key":
        api_url = data.get("api_url", "")
        api_key = text.strip()
        try:
            from urllib.parse import urlparse
            name = urlparse(api_url).netloc.replace("www.", "").split(".")[0]
        except Exception:
            name = "custom"

        result = await add_shortener(name, api_url, api_key)
        clear_state(user_id)
        await message.reply(
            f"✅ Shortener <b>{name}</b> {result['action']} successfully!\n"
            "Use the list to toggle it active.",
            quote=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View Shorteners", callback_data="adm:srt_list")],
                [InlineKeyboardButton("🔙 Back to Admin",   callback_data="adm:back")],
            ])
        )

    # ── Shortener: edit API URL ────────────────────────────────────────────────
    elif state == "srt_wait_edit_url":
        name = data.get("edit_name")
        result = await update_shortener_field(name, "api_url", text.strip())
        clear_state(user_id)
        if result["ok"]:
            await message.reply(
                f"✅ API URL for <b>{name}</b> updated.",
                quote=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Shorteners", callback_data="adm:srt_list")],
                    [InlineKeyboardButton("🔙 Back to Admin",   callback_data="adm:back")],
                ])
            )
        else:
            await message.reply(f"❌ {result['error']}", quote=True)

    # ── Shortener: edit API Key ────────────────────────────────────────────────
    elif state == "srt_wait_edit_key":
        name = data.get("edit_name")
        result = await update_shortener_field(name, "api_key", text.strip())
        clear_state(user_id)
        if result["ok"]:
            await message.reply(
                f"✅ API Key for <b>{name}</b> updated.",
                quote=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Shorteners", callback_data="adm:srt_list")],
                    [InlineKeyboardButton("🔙 Back to Admin",   callback_data="adm:back")],
                ])
            )
        else:
            await message.reply(f"❌ {result['error']}", quote=True)

    # ── Premium: step 1 — User ID ─────────────────────────────────────────────
    elif state == "prm_wait_id":
        try:
            target_uid = int(text.strip())
        except ValueError:
            await message.reply("❌ Invalid User ID. Send a numeric ID.", quote=True)
            return

        set_state(user_id, "prm_wait_days", {"target_uid": target_uid})
        await message.reply(
            f"<b>➕ Grant Premium — Step 2/2</b>\n\nUser: <code>{target_uid}</code>\n\nSelect duration:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("7 Days",  callback_data=f"adm:prm_days:{target_uid}:7"),
                    InlineKeyboardButton("30 Days", callback_data=f"adm:prm_days:{target_uid}:30"),
                ],
                [
                    InlineKeyboardButton("90 Days", callback_data=f"adm:prm_days:{target_uid}:90"),
                    InlineKeyboardButton("Custom",  callback_data="adm:prm_custom_days"),
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="adm:premium")],
            ]),
            quote=True
        )

    # ── Premium: custom days ──────────────────────────────────────────────────
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
            quote=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="adm:back")]
            ])
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
        msg = (
            f"✅ Premium removed from <code>{target_uid}</code>."
            if removed else
            f"ℹ️ User <code>{target_uid}</code> had no active premium."
        )
        await message.reply(
            msg, quote=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Admin", callback_data="adm:back")]
            ])
        )

    # ── ForceSub: add channel ─────────────────────────────────────────────────
    elif state == "fsub_wait_channel":
        chat_id = None
        title = "Unknown"

        if message.forward_from_chat:
            chat_id = message.forward_from_chat.id
            title = message.forward_from_chat.title or "Channel"
        else:
            try:
                chat_id = int(text.strip())
                chat = await client.get_chat(chat_id)
                title = chat.title or "Channel"
            except Exception:
                await message.reply(
                    "❌ Could not resolve channel. Forward a message from it or send its numeric ID.",
                    quote=True,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Back", callback_data="adm:fsub")]
                    ])
                )
                return

        result = await add_channel(chat_id, title)
        clear_state(user_id)
        if result["ok"]:
            await message.reply(
                f"✅ Channel <b>{title}</b> (<code>{chat_id}</code>) added to Force Subscribe!",
                quote=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Channels", callback_data="adm:fsub_list")],
                    [InlineKeyboardButton("🔙 Back to Admin", callback_data="adm:back")],
                ])
            )
        else:
            await message.reply(
                f"❌ {result['error']}", quote=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="adm:fsub")]
                ])
            )


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
    """Shallow copy of a CallbackQuery with different data for re-routing."""
    original.data = new_data
    return original
