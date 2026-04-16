import os
import logging
from logging.handlers import RotatingFileHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API_ID = int(os.environ.get("API_ID", "38570926"))
API_HASH = os.environ.get("API_HASH", "0d7285e5fc1fce2c152e41ec069bf6bc")


OWNER_ID = int(os.environ.get("OWNER_ID", "8204618290"))
DB_URL = os.environ.get("DB_URL", "mongodb+srv://ranigupta24753y_db_user:hari813142@cluster0.n5hqign.mongodb.net/?appName=Cluster0")
DB_NAME = os.environ.get("DB_NAME", "kmbotz")


CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003972912715"))

FILE_AUTO_DELETE = int(os.getenv("FILE_AUTO_DELETE", "300"))  # auto delete in seconds

PORT = os.environ.get("PORT", "8080")
TG_BOT_WORKERS = int(os.environ.get("TG_BOT_WORKERS", "4"))

try:
    ADMINS = [OWNER_ID]
    for x in (os.environ.get("ADMINS", "8327243105").split()):
        val = int(x)
        if val not in ADMINS:
            ADMINS.append(val)
except ValueError:
    raise Exception("Your Admins list does not contain valid integers.")

CUSTOM_CAPTION = os.environ.get("CUSTOM_CAPTION", None)
PROTECT_CONTENT = True if os.environ.get('PROTECT_CONTENT', "False") == "True" else False
DISABLE_CHANNEL_BUTTON = True if os.environ.get('DISABLE_CHANNEL_BUTTON', "True") == "True" else False

BOT_STATS_TEXT = "<b>BOT UPTIME :</b>\n{uptime}"
USER_REPLY_TEXT = "❌ Don't Send Me Messages Directly, I'm Only A File Share Bot!"
START_MSG = os.environ.get(
    "START_MESSAGE",
    "Hello {mention}\n\nI Can Store Private Files In Specified Channel And Other Users Can Access It From Special Link."
)
FORCE_MSG = os.environ.get(
    "FORCE_SUB_MESSAGE",
    "Hello {mention}\n\n<b>You Need To Join My Channel/Group To Use Me\n\nKindly Please Join The Channels Below</b>"
)

LOG_FILE_NAME = "filesharingbot.txt"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt='%d-%b-%y %H:%M:%S',
    handlers=[
        RotatingFileHandler(LOG_FILE_NAME, maxBytes=50000000, backupCount=10),
        logging.StreamHandler()
    ]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
