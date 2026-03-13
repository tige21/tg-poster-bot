import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
DB_PATH = os.environ.get("DB_PATH", "data/bot.db")
MEDIA_DIR = os.environ.get("MEDIA_DIR", "data/media")
