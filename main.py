import telebot
from telebot import types
import os
import yt_dlp
from datetime import datetime
import re
import requests
from dotenv import load_dotenv
from telebot.apihelper import ApiTelegramException

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

# Создание папок
os.makedirs('downloads', exist_ok=True)
os.makedirs('downloads/mp3', exist_ok=True)

deezer_preview_links = {}  # Глобальный словарь для превью

def safe_send_message(chat_id, text, **kwargs):
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except ApiTelegramException as e:
        print(f"❌ Ошибка при отправке сообщения: {e}")
        return None

def get_menu_button():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 Меню"))
    return markup

def download_and_send_media(url, message):
    try:
        if not url.startswith(('http://', 'https://')):
            raise ValueError("Неверный формат ссылки")

        bot.send_chat_action(message.chat.id, 'upload_video')

        wait_sticker_path = "waiting.webp"
        wait_msg = None
        if os.path.exists(wait_sticker_path):
            with open(wait_sticker_path, "rb") as sticker:
                wait_msg = bot.send_sticker(message.chat.id, sticker)
        else:
            wait_msg = safe_send_message(message.chat.id, "⏳ Подождите, скачиваем видео...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_template = f"downloads/{timestamp}.%(ext)s"

        ydl_opts = {
            'outtmpl': output_template,
            'format': 'best',
            'noplaylist': True,
            'quiet': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ['.mp4', '.webm', '.mov']:
            safe_send_message(message.chat.id, "Видео не распознано.")
            return

        markup = types.InlineKeyboardMarkup()
        download_button = types.InlineKeyboardButton(text="🎧 Скачать музыку", callback_data=f"extract_audio:{file_path}")
        markup.add(download_button)

        with open(file_path, 'rb') as f:
            caption = "Вот ваше видео 🎬\nНажмите кнопку ниже, чтобы извлечь музыку."
            bot.send_video(message.chat.id, f, caption=caption, reply_markup=markup)

        if wait_msg:
            bot.delete_message(message.chat.id, wait_msg.message_id)

    except Exception as e:
        safe_send_message(message.chat.id, f"Ошибка при скачивании: {str(e)}")

def extract_audio(file_path, chat_id):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_output_path = f"downloads/mp3/{timestamp}_audio.mp3"
        command = f"ffmpeg -i \"{file_path}\" -vn -acodec libmp3lame -ab 192k \"{audio_output_path}\""
        os.system(command)

        with open(audio_output_path, 'rb') as audio_file:
            bot.send_audio(chat_id, audio_file, caption="🎧 Вот извлечённый трек")
    except Exception as e:
        safe_send_message(chat_id, f"Ошибка при извлечении аудио: {str(e)}")

def search_music_by_name(message):
    global deezer_preview_links
    query = message.text.strip()
    if not query:
        safe_send_message(message.chat.id, "Введите корректное название.")
        return

    search_url = f"https://api.deezer.com/search?q={query}"
    try:
        res = requests.get(search_url)
        data = res.json()
        if 'data' in data and len(data['data']) > 0:
            markup = types.InlineKeyboardMarkup()
            deezer_preview_links = {}
            for idx, track in enumerate(data['data'][:5]):
                title = track.get('title')
                artist = track.get('artist', {}).get('name')
                preview = track.get('preview')
                deezer_preview_links[str(idx)] = preview
                button_text = f"🎵 {title} - {artist}"
                markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f"deezer_preview:{idx}"))

            safe_send_message(message.chat.id, "Выберите трек из списка:", reply_markup=markup)
        else:
            safe_send_message(message.chat.id, "🚫 Ничего не найдено по запросу.")
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Ошибка при поиске: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("deezer_preview:"))
def send_deezer_preview(call):
    idx = call.data.split(":", 1)[1]
    preview_url = deezer_preview_links.get(idx)

    if not preview_url:
        safe_send_message(call.message.chat.id, "❌ Превью не найдено.")
        return

    try:
        audio_data = requests.get(preview_url).content
        audio_path = f"downloads/mp3/{datetime.now().strftime('%Y%m%d_%H%M%S')}_preview.mp3"
        with open(audio_path, 'wb') as f:
            f.write(audio_data)
        with open(audio_path, 'rb') as audio_file:
            bot.send_audio(call.message.chat.id, audio_file, caption="🎧 Превью трека из Deezer")
    except Exception as e:
        safe_send_message(call.message.chat.id, f"Ошибка: {str(e)}")

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📸 Скачать из Instagram"),
        types.KeyboardButton("🎬 Скачать из TikTok"),
        types.KeyboardButton("📌 Скачать из Pinterest"),
        types.KeyboardButton("▶️ Скачать из YouTube"),
        types.KeyboardButton("🔍 Найти музыку по имени"),
        types.KeyboardButton("🎵 Поиск песни (YouTube)"),
        types.KeyboardButton("ℹ️ Помощь")
    )
    safe_send_message(
        message.chat.id,
        "👋 Привет! Я бот, который может:\n"
        "- Скачать видео из Instagram, TikTok, Pinterest и YouTube 📥\n"
        "- Найти трек по названию и прислать превью 🎶\n"
        "- Скачать песню по имени с YouTube 🎵\n\n"
        "Выбери, что хочешь сделать:",
        reply_markup=markup
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "ℹ️ Помощь:\n\n"
        "Этот бот умеет:\n\n"
        "📥 Скачивать видео по ссылке:\n• Instagram\n• TikTok\n• Pinterest\n• YouTube\n\n"
        "🎵 Извлекать музыку из видео\n\n"
        "🔍 Искать трек по названию:\n• Deezer (превью 30 сек)\n• YouTube (полная песня)\n\n"
        "📌 Как пользоваться:\n"
        "1. Нажми нужную кнопку в меню\n"
        "2. Отправь ссылку или название трека\n"
        "3. Получи результат — видео или аудио\n\n"
        "❓ Поддерживаемые ссылки:\n"
        " #https://instagram.com/...\n"
        " #https://www.tiktok.com/...\n"
        " #https://www.pinterest.com/...\n"
        " #https://www.youtube.com/...\n\n"
        "👨‍💻 Бот работает бесплатно и без регистрации. Если есть ошибки — попробуй позже или пришли другую ссылку."
    )
    safe_send_message(message.chat.id, help_text)

@bot.message_handler(commands=['song'])
def song_search(message):
    safe_send_message(message.chat.id, "🔍 Введите название песни для поиска на YouTube:")
    bot.register_next_step_handler(message, download_song_by_name)

def download_song_by_name(message):
    query = message.text.strip()
    if not query:
        safe_send_message(message.chat.id, "❗ Введите корректное название песни.")
        return

    safe_send_message(message.chat.id, f"⏳ Ищем и скачиваем трек: {query}")
    search_url = f"ytsearch:{query}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_output_path = f"downloads/mp3/{timestamp}_song.%(ext)s"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': audio_output_path,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'noplaylist': True,
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([search_url])

        final_path = audio_output_path.replace('%(ext)s', 'mp3')
        with open(final_path, 'rb') as audio_file:
            bot.send_audio(message.chat.id, audio_file, caption="🎶 Вот найденный трек!")
    except Exception as e:
        safe_send_message(message.chat.id, f"❌ Ошибка при скачивании трека: {str(e)}")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    text = message.text.strip()
    if text in [
        "📸 Скачать из Instagram",
        "🎬 Скачать из TikTok",
        "📌 Скачать из Pinterest",
        "▶️ Скачать из YouTube"
    ]:
        safe_send_message(message.chat.id, "📎 Пришли ссылку на видео")
    elif text == "🔍 Найти музыку по имени":
        safe_send_message(message.chat.id, "🔎 Введите название трека или исполнителя")
        bot.register_next_step_handler(message, search_music_by_name)
    elif text == "🎵 Поиск песни (YouTube)":
        safe_send_message(message.chat.id, "🎤 Введите название песни:")
        bot.register_next_step_handler(message, download_song_by_name)
    elif text == "ℹ️ Помощь":
        help_command(message)
    elif text.startswith("http"):
        download_and_send_media(text, message)
    else:
        safe_send_message(
            message.chat.id,
            "Пожалуйста, выбери одну из опций или отправь ссылку на видео."
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("extract_audio:"))
def callback_audio(call):
    file_path = call.data.split(":", 1)[1]
    extract_audio(file_path, call.message.chat.id)

if __name__ == "__main__":
    print("🤖 Бот запущен...")
    bot.infinity_polling()
