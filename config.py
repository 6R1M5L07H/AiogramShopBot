from dotenv import load_dotenv
import os
from enums.currency import Currency
from ngrok_executor import start_ngrok

load_dotenv(".env")

WEBHOOK_HOST = start_ngrok()
WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH")
WEBAPP_HOST = os.environ.get("WEBAPP_HOST")
WEBAPP_PORT = int(os.environ.get("WEBAPP_PORT"))
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
TOKEN = os.environ.get("TOKEN")
ADMIN_ID_LIST = os.environ.get("ADMIN_ID_LIST").split(',')
ADMIN_ID_LIST = [int(admin_id) for admin_id in ADMIN_ID_LIST]
SUPPORT_LINK = os.environ.get("SUPPORT_LINK")
DB_ENCRYPTION = os.environ.get("DB_ENCRYPTION", False) == 'true'
DB_NAME = os.environ.get("DB_NAME")
DB_PASS = os.environ.get("DB_PASS")
PAGE_ENTRIES = int(os.environ.get("PAGE_ENTRIES"))
BOT_LANGUAGE = os.environ.get("BOT_LANGUAGE")
MULTIBOT = os.environ.get("MULTIBOT", False) == 'true'
ETHPLORER_API_KEY = os.environ.get("ETHPLORER_API_KEY")
CURRENCY = Currency(os.environ.get("CURRENCY"))

# Order and Background Task Configuration
ORDER_TIMEOUT_MINUTES = int(os.environ.get("ORDER_TIMEOUT_MINUTES", "30"))
BACKGROUND_TASK_INTERVAL_SECONDS = int(os.environ.get("BACKGROUND_TASK_INTERVAL_SECONDS", "60"))
MAX_USER_TIMEOUTS = int(os.environ.get("MAX_USER_TIMEOUTS", "3"))
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", None)
