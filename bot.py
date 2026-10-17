
import asyncio, json, os, time, pathlib
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiohttp import web
import aiohttp
import pathlib as pl

TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5020382411"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://goofy-culture.onrender.com/")
SOLD_HOURS = 10

if not TOKEN:
    raise RuntimeError("Нет TOKEN в Environment Render")

bot = Bot(TOKEN)
dp = Dispatcher()

# Для Render используем папку с диском /data если есть, иначе локально
DATA_DIR = pl.Path(os.getenv("DATA_DIR", "."))
DB_FILE = DATA_DIR / "products.json"
if not DB_FILE.exists():
    DB_FILE.write_text("[]", encoding="utf-8")

def get_products():
    try:
        return json.loads(DB_FILE.read_text(encoding="utf-8"))
    except:
        return []

def save_products(d):
    DB_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def get_status(p):
    if not p.get("sold"):
        return "active"
    sold_at = p.get("sold_at", 0) or 0
    if time.time() - sold_at > SOLD_HOURS * 3600:
        return "expired"
    return "sold_recent"

class Add(StatesGroup):
    photo = State()
    name = State()
    brand = State()
    price = State()
    size = State()
    tag = State()

@dp.message(Command("start"))
async def start(m: Message):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="📦 ОТКРЫТЬ КОРОБКУ", web_app=WebAppInfo(url=WEBAPP_URL))
    await m.answer("Goofy Culture BOX открыт.\nТОЛЬКО ОРИГИНАЛ\n\nЖми кнопку ниже 👇\n\nАдмин: /add /list /sold 1 /del 1", reply_markup=kb.as_markup())

@dp.message(Command("add"))
async def add_start(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    await state.set_state(Add.photo)
    await m.answer("📦 Кидай фото шмотки")

@dp.message(Add.photo, F.photo)
async def add_photo(m: Message, state: FSMContext):
    await state.update_data(photo=m.photo[-1].file_id)
    await state.set_state(Add.name)
    await m.answer("Название?")

@dp.message(Add.name)
async def add_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await state.set_state(Add.brand)
    await m.answer("Бренд?")

@dp.message(Add.brand)
async def add_brand(m: Message, state: FSMContext):
    await state.update_data(brand=m.text)
    await state.set_state(Add.price)
    await m.answer("Цена? Только цифры")

@dp.message(Add.price)
async def add_price(m: Message, state: FSMContext):
    try:
        p = int(m.text)
    except:
        return await m.answer("Только цифры бро")
    await state.update_data(price=p)
    await state.set_state(Add.size)
    await m.answer("Размер? M/L/S/ONE SIZE")

@dp.message(Add.size)
async def add_size(m: Message, state: FSMContext):
    await state.update_data(size=m.text.upper())
    await state.set_state(Add.tag)
    await m.answer("Тэг? FRAGILE / USED / 1 ШТ или -")

@dp.message(Add.tag)
async def add_tag(m: Message, state: FSMContext):
    data = await state.get_data()
    products = get_products()
    new = {
        "id": int(time.time()*1000),
        "name": data.get("name"),
        "brand": data.get("brand"),
        "price": data.get("price"),
        "size": data.get("size"),
        "tag": m.text if m.text != "-" else "",
        "img": data.get("photo"),
        "sold": False,
        "sold_at": 0
    }
    products.append(new)
    save_products(products)
    await state.clear()
    await m.answer(f"✅ Добавил в коробку: {new['name']} — {new['price']}₽\nСейчас в каталоге {len(products)} вещей")

@dp.message(Command("list"))
async def list_cmd(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    ps = get_products()
    if not ps:
        return await m.answer("Пусто бро")
    txt = ""
    for i, p in enumerate(ps, 1):
        st = "🔴 ПРОДАНО" if p.get("sold") else "🟢"
        txt += f"{i}. {st} {p.get('brand')} {p.get('name')} {p.get('price')}₽\n"
    await m.answer(txt)

@dp.message(Command("sold"))
async def sold_cmd(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    try:
        idx = int(m.text.split()[1]) - 1
        ps = get_products()
        ps[idx]["sold"] = True
        ps[idx]["sold_at"] = int(time.time())
        ps[idx]["tag"] = "СПИЗДИЛИ"
        save_products(ps)
        await m.answer(f"✅ Теперь: {ps[idx]['name']} — СПИЗДИЛИ? САМ ВИНОВАТ! Исчезнет через 10ч")
    except:
        await m.answer("Пиши: /sold 1")

@dp.message(Command("del"))
async def del_cmd(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    try:
        idx = int(m.text.split()[1]) - 1
        ps = get_products()
        name = ps[idx]["name"]
        ps.pop(idx)
        save_products(ps)
        await m.answer(f"🗑 Удалил: {name}")
    except:
        await m.answer("Пиши: /del 1")

# --- WEB PART FOR RENDER ---
async def api_products(request):
    ps = get_products()
    res = []
    for p in ps:
        st = get_status(p)
        if st == "expired":
            continue
        cp = p.copy()
        cp["status"] = st
        res.append(cp)
    return web.json_response(res)

async def api_file(request):
    file_id = request.match_info["file_id"]
    try:
        file = await bot.get_file(file_id)
        url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"
        return web.json_response({"url": url})
    except Exception as e:
        return web.json_response({"url": "", "error": str(e)})

async def api_order(request):
    try:
        data = await request.json()
        user = data.get("user", {})
        items = data.get("items", [])
        total = data.get("total", 0)
        ps = get_products()
        ordered = [p for p in ps if p["id"] in items]

        username = user.get("username")
        name = f"{user.get('first_name','')} {user.get('last_name','')}".strip()
        uid = user.get("id")
        mention = f"@{username} ({name})" if username else f"{name} [ID {uid}]"

        text = f"📦 НОВЫЙ ЗАКАЗ!\n\n👤 Клиент: {mention}\n🆔 ID: {uid}\n\n📋 Товары ({len(ordered)}):\n"
        for o in ordered:
            text += f"• {o.get('brand')} {o.get('name')} {o.get('price')}₽\n"
        text += f"\n💰 Итого: {total}₽\n\nНапиши ему: @{username}" if username else f"\nНапиши: tg://user?id={uid}"

        await bot.send_message(ADMIN_ID, text)
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)

async def index(request):
    return web.FileResponse(pathlib.Path(__file__).parent / "static" / "index.html")

app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/api/products", api_products)
app.router.add_get("/api/file/{file_id}", api_file)
app.router.add_post("/api/order", api_order)
app.router.add_static("/static/", path=pathlib.Path(__file__).parent / "static")

async def main():
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web running on {port}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
