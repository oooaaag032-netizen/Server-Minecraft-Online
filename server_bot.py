import os
import json
import time
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Токен берем из переменных окружения (BOT2_TOKEN)
BOT_TOKEN = os.getenv('BOT2_TOKEN')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

DATA_FILE = 'server_data.json'

# --- БАЗА ДАННЫХ ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"servers": {"HayCraft": "haycraft.top"}, "admins": ["Admin1"], "history": {}}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

data = load_data()

# --- КЭШ (чтобы не спамить API) ---
cache = {}
CACHE_TIME = 30 # Секунд

# --- БЫСТРЫЙ ЗАПРОС К API ---
async def get_server_info(ip):
    # Проверка кэша
    if ip in cache and time.time() - cache[ip]['time'] < CACHE_TIME:
        return cache[ip]['data']
    
    try:
        async with aiohttp.ClientSession() as session:
            # Используем быстрый API mcstatus.io
            async with session.get(f"https://api.mcstatus.io/v2/status/java/{ip}", timeout=5) as response:
                if response.status == 200:
                    res = await response.json()
                    cache[ip] = {'time': time.time(), 'data': res}
                    return res
    except Exception as e:
        print(f"Ошибка API: {e}")
    return None

# --- ФОНОВАЯ ЗАДАЧА ---
async def track_peaks():
    while True:
        for name, ip in data["servers"].items():
            info = await get_server_info(ip)
            if info and info.get("online"):
                online = info.get("players", {}).get("online", 0)
                if name not in data["history"]:
                    data["history"][name] = {"peak": 0, "date": ""}
                
                if online > data["history"][name]["peak"]:
                    data["history"][name]["peak"] = online
                    data["history"][name]["date"] = time.strftime("%Y-%m-%d %H:%M")
                    save_data(data)
        await asyncio.sleep(600) # 10 минут

# --- КЛАВИАТУРА ---
def get_keyboard():
    kb = [
        [KeyboardButton(text="📊 Онлайн HayCraft")],
        [KeyboardButton(text="📈 Пик онлайна")],
        [KeyboardButton(text="🛡️ Админы онлайн")],
        [KeyboardButton(text="➕ Добавить сервер")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- ХЭНДЛЕРЫ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Привет! Я слежу за серверами. Выбери действие:", reply_markup=get_keyboard())

@dp.message(lambda message: message.text == "📊 Онлайн HayCraft")
async def check_haycraft(message: types.Message):
    ip = data["servers"].get("HayCraft")
    info = await get_server_info(ip)
    
    if info and info.get("online"):
        players = info.get("players", {})
        online = players.get("online", 0)
        max_players = players.get("max", 0)
        names = [p["name_clean"] for p in players.get("list", [])]
        
        text = f"🟢 Сервер: HayCraft\n👥 Онлайн: {online}/{max_players}\n"
        if names:
            text += f"👤 Игроки: {', '.join(names[:15])}"
            if len(names) > 15: text += "..."
        else:
            text += "Игроки скрыты."
    else:
        text = "🔴 Сервер офлайн или не отвечает."
    await message.answer(text)

@dp.message(lambda message: message.text == "📈 Пик онлайна")
async def check_peak(message: types.Message):
    text = "📈 Статистика пиков:\n\n"
    for name, stats in data["history"].items():
        text += f"🔹 {name}: {stats['peak']} игроков (в {stats['date']})\n"
    await message.answer(text)

@dp.message(lambda message: message.text == "🛡️ Админы онлайн")
async def check_admins(message: types.Message):
    ip = data["servers"].get("HayCraft")
    info = await get_server_info(ip)
    
    if info and info.get("online"):
        names = [p["name_clean"] for p in info.get("players", {}).get("list", [])]
        admins_online = [name for name in names if name in data["admins"]]
        if admins_online:
            await message.answer(f"🛡️ Админы на сервере: {', '.join(admins_online)}")
        else:
            await message.answer("😴 Админов из вашего списка сейчас нет на сервере.")
    else:
        await message.answer("🔴 Сервер офлайн.")

@dp.message(lambda message: message.text == "➕ Добавить сервер")
async def add_server_start(message: types.Message):
    await message.answer("Введите название и IP сервера через пробел (например: `MyServer play.myserver.com`):")
    # Ждем следующее сообщение от пользователя
    dp.message.register(process_add_server)

async def process_add_server(message: types.Message):
    try:
        name, ip = message.text.split(maxsplit=1)
        data["servers"][name] = ip
        save_data(data)
        await message.answer(f"✅ Сервер {name} ({ip}) добавлен!")
        dp.message.handlers.pop() # Убираем ожидание
    except ValueError:
        await message.answer("❌ Ошибка формата. Напишите: Название IP")

# --- ЗАПУСК ---
async def main():
    # Запускаем фоновую задачу в фоне
    asyncio.create_task(track_peaks())
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
