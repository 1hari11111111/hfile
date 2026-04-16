from pyrogram import __version__
from bot import Bot
from config import OWNER_ID
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


@Bot.on_callback_query()
async def cb_handler(client: Bot, query: CallbackQuery):
    data = query.data

    # Admin panel callbacks are handled in admin.py
    if data.startswith("adm:"):
        return

    if data == "about":
        await query.message.edit_text(
            text=(
                f"<b>🤖 My Name :</b> <a href='https://t.me/FileSharingXProBot'>File Sharing Bot</a>\n"
                f"<b>📝 Language :</b> <a href='https://python.org'>Python 3</a>\n"
                f"<b>📚 Library :</b> <a href='https://pyrogram.org'>Pyrogram {__version__}</a>\n"
                f"<b>🚀 Server :</b> <a href='https://heroku.com'>Heroku</a>\n"
                f"<b>📢 Channel :</b> <a href='https://t.me/Madflix_Bots'>Madflix Botz</a>\n"
                f"<b>🧑‍💻 Developer :</b> <a href='tg://user?id={OWNER_ID}'>Jishu Developer</a>"
            ),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔒 Close", callback_data="close")]
            ])
        )
    elif data == "close":
        await query.message.delete()
        try:
            await query.message.reply_to_message.delete()
        except Exception:
            pass
