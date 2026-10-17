
# Goofy Culture BOX - Render Edition

Готовый пак для переезда с Railway на Render.

## Файлы:
- bot.py - бот + сайт (aiohttp + aiogram)
- requirements.txt
- products.json - пустая база
- static/index.html - твой магазин с логикой СОЛД 1.8сек пульсация и прыжком коробки
- static/banner.jpg.WEBP - ЗАЛЕЙ СВОЮ ШАПКУ СЮДА (скопируй с Railway)

## Как залить на Render:

1. Создай новый репозиторий на GitHub `goofy-render`
2. Залей туда все файлы из этого архива (drag&drop)
3. Не забудь закинуть свою шапку banner.jpg.WEBP в static/
4. Иди на render.com -> New -> Web Service -> подключи GitHub репу
5. Build: pip install -r requirements.txt
   Start: python bot.py
6. В Environment добавь:
   TOKEN = твой токен от @BotFather
   ADMIN_ID = твой ID (узнай в @userinfobot)
   WEBAPP_URL = https://твое-имя.onrender.com/
   PORT = 10000

7. Deploy -> жди 2 мин -> открой https://твое-имя.onrender.com/

8. Чтобы товары не стирались после деплоя:
   Render Dashboard -> твой сервис -> Disks -> Add Disk
   Name: data, Mount Path: /data, Size: 1GB
   И в Variables добавь DATA_DIR = /data

9. В @BotFather -> /setmenubutton -> твой бот -> вставь WEBAPP_URL

Готово. Команды те же: /add /list /sold 1 /del 1
