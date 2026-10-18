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
                data = json.loads(path.read_text(encoding="utf-8"))
                if data: return data
            except: pass
    return []

def save(d):
    for path in PATHS:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            break
        except: pass

def status(p):
    if not p.get("sold"): return "active"
    return "expired" if time.time()-(p.get("sold_at")or 0) > 10*3600 else "sold_recent"

class Add(StatesGroup):
    photos=State(); name=State(); brand=State(); price=State(); size=State(); desc=State(); tag=State()

@dp.message(Command("start"))
async def start(m:Message):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    url = WEBAPP_URL or f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME','')}"
    kb=InlineKeyboardBuilder()
    if url:
        kb.button(text="📦 ОТКРЫТЬ КОРОБКУ", web_app=WebAppInfo(url=url))
    await m.answer(f"Goofy BOX • {len(load())} товара\n\nWebApp URL: {url or 'не задан (добавь WEBAPP_URL в Render)'}", reply_markup=kb.as_markup() if url else None)

@dp.message(Command("add"))
async def a0(m:Message, state:FSMContext):
    if m.from_user.id!=ADMIN_ID: return
    await state.set_state(Add.photos); await state.update_data(photos=[])
    await m.answer("📸 Кидай фото (до 10). Напиши ГОТОВО когда хватит")
@dp.message(Add.photos, F.photo)
async def a_photo(m:Message, state:FSMContext):
    d=await state.get_data(); ph=d.get("photos",[]); ph.append(m.photo[-1].file_id)
    await state.update_data(photos=ph); await m.answer(f"✅ {len(ph)} фото. Еще? → ГОТОВО")
@dp.message(Add.photos)
async def a_photos_text(m:Message, state:FSMContext):
    if m.text.lower() not in ["готово","готов","done","ok","все"]: return
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
    await state.update_data(desc=txt); await state.set_state(Add.tag); await m.answer("Тэг?")
@dp.message(Add.tag)
async def a7(m:Message, state:FSMContext):
    d=await state.get_data(); ps=load()
    tag="" if m.text.strip()=="-" else m.text.strip()
    ps.insert(0, {"id":int(time.time()*1000),"name":d["name"],"brand":d["brand"],"price":d["price"],"size":d["size"],"sizes":[d["size"]],"tag":tag,"tags":[tag] if tag else [],"description":d.get("desc",""),"img":d["photos"][0],"images":d["photos"],"sold":False,"sold_at":0})
    save(ps); await state.clear(); await m.answer(f"✅ Добавил! Всего: {len(ps)}")

@dp.message(Command("list"))
async def lst(m:Message):
    if m.from_user.id!=ADMIN_ID: return
    for p in load()[:10]:
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔴 Продано" if not p.get("sold") else "↩️ Вернуть", callback_data=f"{'sold' if not p.get('sold') else 'unsold'}_{p['id']}"), InlineKeyboardButton(text="🗑️", callback_data=f"del_{p['id']}")]])
        await m.answer(f"{p['brand']} {p['name']} {p['price']}₽", reply_markup=kb)
@dp.callback_query(F.data.startswith("unsold_"))
async def cu(c):
    pid=int(c.data.split("_")[1]); ps=load()
    for p in ps:
        if p['id']==pid: p['sold']=False; p['sold_at']=0
    save(ps); await c.message.edit_text("✅ Вернул"); await c.answer
