
import os, json, time, asyncio, uuid
from pathlib import Path
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5020382411"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://goofy-render.onrender.com")
DATA_DIR = Path(os.getenv("DATA_DIR", "/data" if Path("/data").exists() else "."))
DATA_DIR.mkdir(parents=True, exist_ok=True)
PRODUCTS_FILE = DATA_DIR / "products.json"
IMAGES_DIR = DATA_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)

# migrate if old products.json in cwd
if not PRODUCTS_FILE.exists() and Path("products.json").exists():
    try:
        PRODUCTS_FILE.write_text(Path("products.json").read_text(encoding="utf-8"), encoding="utf-8")
    except: pass

if not PRODUCTS_FILE.exists():
    PRODUCTS_FILE.write_text("[]", encoding="utf-8")

def load_products():
    try:
        return json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
    except:
        return []

def save_products(data):
    PRODUCTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

class AddState(StatesGroup):
    photos = State()
    name = State()
    brand = State()
    price = State()
    sizes = State()

# --- Admin commands setup ---
async def setup_commands():
    # For all users - only start
    await bot.set_my_commands(
        [BotCommand(command="start", description="📦 Открыть коробку")],
        scope=BotCommandScopeDefault()
    )
    # For admin - full list
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="📦 Открыть коробку"),
            BotCommand(command="add", description="➕ Добавить товар (много фото)"),
            BotCommand(command="list", description="📋 Список товаров"),
            BotCommand(command="sold", description="🔥 Пометить как спиздили /sold ID"),
            BotCommand(command="del", description="❌ Удалить /del ID"),
            BotCommand(command="discount", description="🎁 Секретная скидка"),
        ],
        scope=BotCommandScopeChat(chat_id=ADMIN_ID)
    )

def is_admin(m: types.Message):
    return m.from_user.id == ADMIN_ID

def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📦 ОТКРЫТЬ КОРОБКУ", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await setup_commands()
    await m.answer(
        "ЙОУ! Это GOOFY CULTURE SHOP\n\nЖми кнопку ниже чтобы открыть коробку 👇\n\nАху*нный товар, только оригинал.",
        reply_markup=main_kb()
    )

@dp.message(Command("add"))
async def cmd_add(m: types.Message, state: FSMContext):
    if not is_admin(m): return
    await state.clear()
    await state.set_state(AddState.photos)
    await state.update_data(photos=[])
    await m.answer("Кидай ФОТО товара. Можно до 6 штук одним альбомом или по одному. Когда все — напиши /done")

@dp.message(StateFilter(AddState.photos), F.photo)
async def add_photos(m: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    # save file_id and also download file for web
    for _ in range(1): # one photo per message, but album will trigger multiple messages
        file_id = m.photo[-1].file_id
        # download
        file = await bot.get_file(file_id)
        ext = ".jpg"
        fname = f"{uuid.uuid4().hex}{ext}"
        fpath = IMAGES_DIR / fname
        await bot.download_file(file.file_path, destination=fpath)
        photos.append({"file_id": file_id, "file": fname})
    await state.update_data(photos=photos)
    await m.answer(f"Принял {len(photos)}/6 фото. Кидай еще или /done")

@dp.message(StateFilter(AddState.photos), Command("done"))
async def add_done(m: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("photos"):
        await m.answer("Ты не кинул ни одного фото!")
        return
    await state.set_state(AddState.name)
    await m.answer("Как называется? (например: NOCTA GLOVE или ARC'TERYX JACKET)")

@dp.message(StateFilter(AddState.name))
async def add_name(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text)
    await state.set_state(AddState.brand)
    await m.answer("Бренд?")

@dp.message(StateFilter(AddState.brand))
async def add_brand(m: types.Message, state: FSMContext):
    await state.update_data(brand=m.text)
    await state.set_state(AddState.price)
    await m.answer("Цена? (число, например 6500)")

@dp.message(StateFilter(AddState.price))
async def add_price(m: types.Message, state: FSMContext):
    try:
        price = int(m.text.replace(" ", ""))
    except:
        await m.answer("Напиши числом")
        return
    await state.update_data(price=price)
    await state.set_state(AddState.sizes)
    await m.answer("Размеры? (например: M L XL или ONE SIZE)")

@dp.message(StateFilter(AddState.sizes))
async def add_sizes(m: types.Message, state: FSMContext):
    data = await state.get_data()
    products = load_products()
    new_id = max([p["id"] for p in products], default=0) + 1
    product = {
        "id": new_id,
        "name": data["name"],
        "brand": data["brand"],
        "price": data["price"],
        "sizes": m.text,
        "photos": data["photos"], # list of dicts
        "photo": data["photos"][0]["file"], # backward compat
        "status": "available",
        "created": int(time.time())
    }
    products.append(product)
    save_products(products)
    await state.clear()
    await m.answer(f"Готово! Добавил ID {new_id} — {product['name']} с {len(product['photos'])} фото", reply_markup=main_kb())

@dp.message(Command("list"))
async def cmd_list(m: types.Message):
    if not is_admin(m): return
    products = load_products()
    if not products:
        await m.answer("0 товара")
        return
    txt = "\n".join([f"{p['id']}. {p['brand']} {p['name']} — {p['price']}р [{len(p.get('photos',[]))} фото] — {p['status']}" for p in products[-20:]])
    await m.answer(txt)

@dp.message(Command("sold"))
async def cmd_sold(m: types.Message):
    if not is_admin(m): return
    try:
        pid = int(m.text.split()[1])
    except:
        await m.answer("Пиши /sold ID")
        return
    products = load_products()
    for p in products:
        if p["id"] == pid:
            p["status"] = "sold"
            p["sold_at"] = int(time.time())
    save_products(products)
    await m.answer(f"ID {pid} помечен как СПИЗДИЛИ. Висит 10 часов для FOMO")

@dp.message(Command("del"))
async def cmd_del(m: types.Message):
    if not is_admin(m): return
    try:
        pid = int(m.text.split()[1])
    except:
        await m.answer("Пиши /del ID")
        return
    products = load_products()
    products = [p for p in products if p["id"] != pid]
    save_products(products)
    await m.answer(f"ID {pid} удален")

@dp.message(Command("discount"))
async def cmd_discount(m: types.Message):
    if not is_admin(m): return
    await m.answer("🎁 СЕКРЕТНАЯ СКИДКА АКТИВНА: код GOOFY15 — скидка 15% на 24 часа. Ссылка с кодом: "+WEBAPP_URL+"?promo=GOOFY15")

# Auto-clean sold after 10h
async def autoclean():
    while True:
        try:
            products = load_products()
            now = int(time.time())
            new = []
            for p in products:
                if p.get("status")=="sold" and now - p.get("sold_at",0) > 36000: # 10h
                    continue
                new.append(p)
            if len(new)!=len(products):
                save_products(new)
        except: pass
        await asyncio.sleep(600)

@dp.message(F.web_app_data)
async def webapp_data(m: types.Message):
    try:
        data = json.loads(m.web_app_data.data)
        # order
        await bot.send_message(ADMIN_ID, f"📦 НОВЫЙ ЗАКАЗ!\nОт: @{m.from_user.username} {m.from_user.id}\nТовары: {json.dumps(data, ensure_ascii=False)[:1000]}")
        await m.answer("Заказ принят! Я напишу тебе в личку 👟")
    except Exception as e:
        print(e)

# FastAPI static + images
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/api/products")
async def api_products():
    products = load_products()
    # add image urls
    for p in products:
        urls = []
        for ph in p.get("photos", []):
            if isinstance(ph, dict):
                urls.append(f"/images/{ph['file']}")
            else:
                urls.append(f"/images/{ph}")
        if not urls and p.get("photo"):
            # backward
            if "/" in p["photo"]:
                urls=[p["photo"]]
            else:
                urls=[f"/images/{p['photo']}"]
        p["image_urls"] = urls
    return products

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(autoclean())
    asyncio.create_task(setup_commands())
    # start polling in background
    asyncio.create_task(dp.start_polling(bot))

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
