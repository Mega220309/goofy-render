import asyncio, json, os, time, pathlib
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiohttp import web

# --- RENDER FIX: читаем оба варианта переменных ---
TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID","5020382411"))
# RENDER FIX: теперь берется из переменной окружения Render, а не Railway
WEBAPP_URL = os.getenv("WEBAPP_URL","").rstrip("/")

bot = Bot(TOKEN)
dp = Dispatcher()

# RENDER FIX: на Render нет /data по умолчанию, используем./data + fallback
DATA_PATH = pathlib.Path(os.getenv("DATA_PATH", "data/products.json"))
PATHS = [
    DATA_PATH,
    pathlib.Path("products.json"),
    pathlib.Path("/tmp/products.json"),
    pathlib.Path("data/products.json"),
    pathlib.Path("/data/products.json"),
]

def load():
    for path in PATHS:
        if path.exists():
            try:
