import asyncio, json, os, time, pathlib
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID","5020382411"))
WEBAPP_URL = os.getenv("WEBAPP_URL","").rstrip("/")
NPOINT_ID = os.getenv("NPOINT_ID","")  # создашь на npoint.io - бесплатно вечно

if not TOKEN:
    raise RuntimeError("Нет TOKEN")

bot = Bot(TOKEN)
dp = Dispatcher()
app = FastAPI()

DATA_PATH = pathlib.Path(os.getenv("DATA_PATH", "data/products.json"))
PATHS = [
    DATA_PATH,
    pathlib.Path("products.json"),
    pathlib.Path("/tmp/products.json"),
    pathlib.Path("data/products.json"),
    pathlib.Path("/data/products.json"),
]

# --- CLOUD PERSISTENCE ---
async def cloud_load():
    if not NPOINT_ID:
        return None
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.npoint.io/{NPOINT_ID}", timeout=10) as r:
                if r.status==200:
                    data = await r.json()
                    # npoint возвращает либо {"products":[...]} либо [...]
                    if isinstance(data, dict) and "products" in data:
                        return data["products"]
                    if isinstance(data, list):
                        return data
                    return data
    except Exception as e:
        print(f"cloud load fail {e}")
    return None

async def cloud_save(products):
    if not NPOINT_ID:
        return
    try:
        async with aiohttp.ClientSession() as s:
            # npoint требует POST весь объект
            payload = {"products": products}
            async with s.post(f"https://api.npoint.io/{NPOINT_ID}", json=payload, timeout=10) as r:
                print(f"cloud save {r.status}")
    except Exception as e:
        print(f"cloud save fail {e}")

def load_local():
    for path in PATHS:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    return data
            except: pass
    return []

def save_local(d):
    for path in PATHS:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            break
        except: pass

# память
MEMORY = []

async def load_all():
    global MEMORY
    # 1. пробуем локально
    local = load_local()
    if local:
        MEMORY = local
        print(f"Loaded local {len(local)}")
        return local
    # 2. пробуем облако
    cloud = await cloud_load()
    if cloud:
        MEMORY = cloud
        save_local(cloud)
        print(f"Loaded cloud {len(cloud)}")
        return cloud
    print("No data")
    return []

def get_products():
    return MEMORY

def save_products(d):
    global MEMORY
    MEMORY = d
    save_local(d)
    asyncio.create_task(cloud_save(d))

def status(p):
    if not p.get("sold"): return "active"
    return "expired" if time.time()-(p.get("sold_at") or 0) > 10*3600 else "sold_recent"

class Add(StatesGroup):
    photos=State(); name=State(); brand=State(); price=State(); size=State(); desc=State(); tag=State()

async def setup_commands():
    try:
        await bot.set_my_commands([BotCommand(command="start", description="📦 Открыть коробку")], scope=BotCommandScopeDefault())
        await bot.set_my_commands([
            BotCommand(command="start", description="📦 Открыть коробку"),
            BotCommand(command="add", description="➕ Добавить товар"),
            BotCommand(command="list", description="📋 Список товаров"),
            BotCommand(command="sold", description="🔥 /sold ID"),
            BotCommand(command="del", description="❌ /del ID"),
        ], scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    except Exception as e:
        print(e)

@dp.message(Command("start"))
async def start(m:Message):
    await load_all()
    url = WEBAPP_URL or f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME','')}"
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    # Делаем как на втором фото - дерзкий текст + большая кнопка снизу
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📦 ОТКРЫТЬ КОРОБКУ", web_app=WebAppInfo(url=url))]] if url else [[KeyboardButton(text="📦 ОТКРЫТЬ КОРОБКУ")]],
        resize_keyboard=True
    )
    # Текст как на втором фото
    text = (
        "ЙОУ! Это GOOFY CULTURE SHOP\n\n"
        "Жми кнопку ниже чтобы открыть коробку 👇\n\n"
        "Аху*нный товар, только оригинал."
    )
    await m.answer(text, reply_markup=kb)

@dp.message(Command("add"))
async def a0(m:Message, state:FSMContext):
    if m.from_user.id!=ADMIN_ID: return
    await state.set_state(Add.photos); await state.update_data(photos=[])
    await m.answer("📸 Кидай фото (до 10). Напиши ГОТОВО")

@dp.message(Add.photos, F.photo)
async def a_photo(m:Message, state:FSMContext):
    d=await state.get_data(); ph=d.get("photos",[]); ph.append(m.photo[-1].file_id)
    await state.update_data(photos=ph); await m.answer(f"✅ {len(ph)} фото → ГОТОВО")

@dp.message(Add.photos)
async def a_photos_text(m:Message, state:FSMContext):
    if not m.text or m.text.lower() not in ["готово","готов","done","ok","все","всё"]: return
    d=await state.get_data()
    if not d.get("photos"): return await m.answer("Кинь фото")
    await state.set_state(Add.name); await m.answer("Название?")

@dp.message(Add.name)
async def a2(m:Message, state:FSMContext):
    await state.update_data(name=m.text.strip()); await state.set_state(Add.brand); await m.answer("Бренд?")

@dp.message(Add.brand)
async def a3(m:Message, state:FSMContext):
    await state.update_data(brand=m.text.strip()); await state.set_state(Add.price); await m.answer("Цена?")

@dp.message(Add.price)
async def a4(m:Message, state:FSMContext):
    try: p=int(''.join(filter(str.isdigit, m.text)))
    except: return await m.answer("Цифры")
    await state.update_data(price=p); await state.set_state(Add.size); await m.answer("Размер?")

@dp.message(Add.size)
async def a5(m:Message, state:FSMContext):
    await state.update_data(size=m.text.strip().upper()); await state.set_state(Add.desc); await m.answer("Описание? - если без")

@dp.message(Add.desc)
async def a6(m:Message, state:FSMContext):
    txt="" if m.text.strip()=="-" else m.text.strip()
    await state.update_data(desc=txt); await state.set_state(Add.tag); await m.answer("Тэг? - если без")

@dp.message(Add.tag)
async def a7(m:Message, state:FSMContext):
    d=await state.get_data(); ps=get_products()
    tag="" if m.text.strip()=="-" else m.text.strip()
    ps.insert(0, {
        "id":int(time.time()*1000),
        "name":d["name"],"brand":d["brand"],"price":d["price"],
        "size":d["size"],"sizes":[d["size"]],
        "tag":tag,"tags":[tag] if tag else [],
        "description":d.get("desc",""),"desc":d.get("desc",""),
        "img":d["photos"][0],"images":d["photos"],
        "sold":False,"sold_at":0,"status":"available"
    })
    save_products(ps); await state.clear(); await m.answer(f"✅ Добавил! Всего: {len(ps)} (в облаке)")

@dp.message(Command("list"))
async def lst(m:Message):
    if m.from_user.id!=ADMIN_ID: return
    await load_all()
    ps=get_products()
    if not ps:
        await m.answer("Пусто"); return
    for p in ps[:10]:
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔴 Продано" if not p.get("sold") else "↩️ Вернуть", callback_data=f"{'sold' if not p.get('sold') else 'unsold'}_{p['id']}"), InlineKeyboardButton(text="🗑️", callback_data=f"del_{p['id']}")]])
        await m.answer(f"{p['brand']} {p['name']} {p['price']}₽", reply_markup=kb)

@dp.message(Command("sold"))
async def cmd_sold(m:Message):
    if m.from_user.id!=ADMIN_ID: return
    try: pid=int(m.text.split()[1])
    except: return await m.answer("Пиши /sold ID")
    ps=get_products()
    for p in ps:
        if p['id']==pid: p['sold']=True; p['status']='sold'; p['sold_at']=int(time.time())
    save_products(ps); await m.answer(f"ID {pid} — СПИЗДИЛИ")

@dp.message(Command("del"))
async def cmd_del(m:Message):
    if m.from_user.id!=ADMIN_ID: return
    try: pid=int(m.text.split()[1])
    except: return await m.answer("Пиши /del ID")
    ps=[p for p in get_products() if p['id']!=pid]
    save_products(ps); await m.answer(f"ID {pid} удален")

@dp.callback_query(F.data.startswith("sold_"))
async def cb_sold(c):
    pid=int(c.data.split("_")[1]); ps=get_products()
    for p in ps:
        if p['id']==pid: p['sold']=True; p['status']='sold'; p['sold_at']=int(time.time())
    save_products(ps); await c.message.edit_text("✅ СПИЗДИЛИ"); await c.answer()

@dp.callback_query(F.data.startswith("unsold_"))
async def cb_unsold(c):
    pid=int(c.data.split("_")[1]); ps=get_products()
    for p in ps:
        if p['id']==pid: p['sold']=False; p['status']='available'; p['sold_at']=0
    save_products(ps); await c.message.edit_text("✅ Вернул"); await c.answer()

@dp.callback_query(F.data.startswith("del_"))
async def cb_del(c):
    pid=int(c.data.split("_")[1]); ps=[p for p in get_products() if p['id']!=pid]
    save_products(ps); await c.message.edit_text("🗑️ Удален"); await c.answer()

async def autoclean():
    while True:
        try:
            ps=get_products(); now=time.time(); new=[]
            for p in ps:
                if p.get("sold") and now - (p.get("sold_at") or 0) > 10*3600: continue
                new.append(p)
            if len(new)!=len(ps): save_products(new)
        except: pass
        await asyncio.sleep(600)

@dp.message(F.web_app_data)
async def webapp_data(m:Message):
    try:
        raw = json.loads(m.web_app_data.data)
        items_ids = raw.get("items") or raw.get("cart") or raw.get("order") or []
        if isinstance(items_ids, list) and len(items_ids)>0 and isinstance(items_ids[0], dict):
            items_ids = [x.get("id") or x for x in items_ids]
        total = raw.get("total", 0)
        discount = raw.get("discount", 0)
        promo = raw.get("promo") or ("GOOFY10" if discount else None)
        
        ps = get_products()
        prods = []
        for pid in items_ids:
            p = next((x for x in ps if str(x["id"])==str(pid) or x["id"]==pid), None)
            if p:
                prods.append(p)
        
        if not total and prods:
            total = sum(p["price"] for p in prods)
            if discount:
                total = round(total*0.9)

        user = m.from_user
        username = f"@{user.username}" if user.username else "без юзера"
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Гость"
        
        lines = []
        lines.append("📦 <b>НОВЫЙ ЗАКАЗ — GOOFY BOX</b>")
        lines.append("")
        lines.append(f"👤 <b>Клиент:</b> {name} {username}")
        lines.append(f"🆔 ID: <code>{user.id}</code>")
        lines.append(f"🔗 <a href='tg://user?id={user.id}'>Открыть профиль клиента</a>")
        if user.username:
            lines.append(f"✉️ <a href='https://t.me/{user.username}'>@{user.username}</a>")
        lines.append("")
        lines.append("🛒 <b>Товары:</b>")
        for i,p in enumerate(prods,1):
            lines.append(f"{i}. <b>{p.get('brand','')} {p.get('name','')}</b>")
            lines.append(f"   Размер: {p.get('size','?')} | Цена: {p.get('price',0)}₽")
        if not prods:
            lines.append(f"ID товаров: {items_ids}")
        lines.append("")
        lines.append(f"💰 <b>Итого:</b> {total}₽")
        if discount or promo:
            lines.append(f"🎁 <b>Скидка:</b> {discount}% {f'({promo})' if promo else ''} — ПРИМЕНЕНА")
        else:
            lines.append(f"🎁 <b>Скидка:</b> нет")
        lines.append("")
        lines.append(f"⏰ {time.strftime('%d.%m.%Y %H:%M')}")

        txt = "
".join(lines)
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Написать клиенту", url=f"tg://user?id={user.id}")]])
        await bot.send_message(ADMIN_ID, txt, parse_mode="HTML", reply_markup=kb)
        if prods:
            from aiogram.types import InputMediaPhoto
            media = []
            for p in prods[:10]:
                fid = p.get("img") or (p.get("images",[None])[0] if p.get("images") else None)
                if fid:
                    media.append(InputMediaPhoto(media=fid, caption=f"{p.get('brand','')} {p.get('name','')} {p.get('price',0)}₽"))
            if media:
                try:
                    await bot.send_media_group(ADMIN_ID, media)
                except Exception as e:
                    print(f"media group fail {e}")
        await m.answer("✅ Заказ улетел! Я напишу тебе в личку 👟")
    except Exception as e:
        print(f"webapp_data error {e}")
        import traceback; traceback.print_exc()
        await m.answer("Ошибка заказа")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/api/products")
async def api_products():
    ps = await load_all() if not get_products() else get_products()
    for p in ps:
        p["status_calc"]=status(p)
        if p.get("sold"): p["status"]="sold"
    return ps

@app.get("/api/file/{file_id}")
async def api_file(file_id: str):
    try:
        file = await bot.get_file(file_id)
        url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"
        return JSONResponse({"url": url})
    except Exception as e:
        return JSONResponse({"error": str(e), "url": ""}, status_code=404)

@app.post("/api/order")
async def api_order(req: Request):
    try:
        data = await req.json()
        user = data.get("user",{}) or {}
        items_ids = data.get("items") or data.get("cart") or []
        total = data.get("total",0)
        discount = data.get("discount",0)
        promo = data.get("promo") or (f"GOOFY{discount}" if discount else None)

        ps = get_products()
        prods = []
        for pid in items_ids:
            p = next((x for x in ps if str(x["id"])==str(pid) or x["id"]==pid), None)
            if p:
                prods.append(p)

        uid = user.get("id",0) or data.get("from_id",0) or 0
        uname = user.get("username") or ""
        first = user.get("first_name","") or user.get("firstName","")
        last = user.get("last_name","") or ""
        photo_url = user.get("photo_url","")

        name = f"{first} {last}".strip() or user.get("name","") or "Гость"
        username = f"@{uname}" if uname else "без юзера"

        # Build pretty text
        lines = []
        lines.append("📦 <b>НОВЫЙ ЗАКАЗ — GOOFY BOX</b>")
        lines.append("")
        if uid and uid!=0:
            lines.append(f"👤 <b>Клиент:</b> {name} {username}")
            lines.append(f"🆔 ID: <code>{uid}</code>")
            # ссылка работает даже без юзера!
            lines.append(f"🔗 <a href='tg://user?id={uid}'>Открыть профиль клиента</a>")
            if uname:
                lines.append(f"✉️ <a href='https://t.me/{uname}'>@{uname} в ТГ</a>")
        else:
            lines.append(f"👤 <b>Клиент:</b> {name} ({username})")
            lines.append(f"🆔 ID: неизвестен — открыл вне Телеги?")
        lines.append("")
        lines.append("🛒 <b>Товары:</b>")
        for i,p in enumerate(prods,1):
            lines.append(f"{i}. <b>{p.get('brand','')} {p.get('name','')}</b> — {p.get('price',0)}₽ (Размер: {p.get('size','?')})")
        if not prods:
            lines.append(f"ID: {items_ids}")
        lines.append("")
        lines.append(f"💰 <b>Итого:</b> {total}₽")
        if discount or promo:
            lines.append(f"🎁 <b>Скидка:</b> {discount}% {promo or ''} — ПРИМЕНЕНА")
        else:
            lines.append("🎁 <b>Скидка:</b> нет")
        lines.append(f"⏰ {time.strftime('%d.%m.%Y %H:%M')}")
        txt = "
".join(lines)

        # Кнопка Написать клиенту даже без юзера
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = None
        if uid and uid!=0:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Написать клиенту", url=f"tg://user?id={uid}")]])

        await bot.send_message(ADMIN_ID, txt, parse_mode="HTML", reply_markup=kb)
        if prods:
            from aiogram.types import InputMediaPhoto
            media=[]
            for p in prods[:10]:
                fid=p.get("img") or (p.get("images",[None])[0] if p.get("images") else None)
                if fid:
                    media.append(InputMediaPhoto(media=fid, caption=f"{p.get('brand','')} {p.get('name','')}"))
            if media:
                try:
                    await bot.send_media_group(ADMIN_ID, media)
                except: pass
    except Exception as e:
        print(f"api_order error {e}")
        import traceback; traceback.print_exc()
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    await load_all()
    asyncio.create_task(autoclean())
    asyncio.create_task(setup_commands())
    asyncio.create_task(dp.start_polling(bot))
    print(f"Goofy BOX started, cloud={'ON' if NPOINT_ID else 'OFF'}")

if __name__ == "__main__":
    port = int(os.getenv("PORT","10000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
