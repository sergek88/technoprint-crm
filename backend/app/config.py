import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://technoprint:technoprint@localhost:5432/technoprint")
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY не задан — пропишите его в backend/.env перед запуском (резервируйте .env!)")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

BANK_COMMISSION = float(os.getenv("BANK_COMMISSION", "0"))
CARD_COMMISSION = float(os.getenv("CARD_COMMISSION", "0"))

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_ADMIN_CHAT_ID = os.getenv("TG_ADMIN_CHAT_ID", "")

INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "")
