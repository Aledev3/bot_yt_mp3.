import logging
import re
import os
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from pytube import YouTube

# Set up bot
bot_token = 'token'
bot = Bot(token=bot_token)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)
dp.middleware.setup(LoggingMiddleware())

#proprietario bot 
OWNER_ID = 5942569516 

# Connessione al database e creazione della tabella
def create_users_table():
    conn = sqlite3.connect('user_ids.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY
        )
    ''')
    conn.commit()
    conn.close()

# Chiamare la funzione di creazione della tabella all'avvio dell'app
create_users_table()


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect('user_ids.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()
    
    start_message = (
        "Welcome to the YouTube Music Bot!\n\n"
        "This bot allows you to download audio from YouTube videos and send them as MP3 files.\n\n"
        "How to use:\n"
        "1. Send me a YouTube video link.\n"
        "2. I will download the audio from the video and send it to you as an MP3 file.\n\n"
        "Please note:\n"
        "- The audio file size is limited to 50MB due to Telegram API limits.\n"
        "- Only valid YouTube video links are supported.\n\n"
        "Send me a YouTube video link to get started!"
    )
    await message.reply(start_message)



@dp.message_handler(commands=['source'])
async def source(message: types.Message):
    source_message = "I'm an open source bot! You can find my source code on GitHub:\n\n[Link to source code](https://github.com/Aledev3/bot_yt_mp3)"
    await message.reply(source_message, parse_mode=ParseMode.MARKDOWN)


@dp.message_handler(commands=['post'], user_id=OWNER_ID)
async def post_to_users(message: types.Message):
    conn = sqlite3.connect('user_ids.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users')
    user_ids = [str(row[0]) for row in cursor.fetchall()]
    conn.close()
    
    # Divide il comando in due parti: /post <testo del messaggio>
    command_parts = message.text.split(' ', 1)
    if len(command_parts) > 1:
        custom_message = command_parts[1]
    else:
        custom_message = BROADCAST_MESSAGE
    
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, custom_message)
        except types.BotBlocked:
            pass  # Skip blocked users
    
    await message.answer("Broadcast message sent to all users.")


# Function to extract YouTube link from the message text
def extract_youtube_link(text):
    match = re.search(r'(https?://(?:www\.)?youtube\.com\S+|https?://youtu\.be\S+)', text)
    return match.group(1) if match else None

# Dichiarazione del contatore all'inizio del modulo
request_counter = 0

# Handler to handle text messages
@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle_text(message: types.Message):
    global request_counter
    user_id = message.from_user.id
    conn = sqlite3.connect('user_ids.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('INSERT INTO users (id) VALUES (?)', (user_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        # L'utente è già presente nella tabella
        pass
    
    conn.close()
 
    text = message.text
    youtube_link = extract_youtube_link(text)
    c = await bot.send_message(message.chat.id, "Please wait, I'm processing your request...")
    await bot.send_chat_action(message.chat.id, 'upload_document')  # Notify the user that the bot is typing

    if youtube_link:
        # Incrementa il contatore delle richieste e usa quel valore per il nome del file temporaneo
        request_counter += 1
        download_task = asyncio.create_task(download_and_send_audio(bot, c, youtube_link, request_counter))
        await asyncio.gather(download_task)
    else:
        await message.answer("Please provide a valid YouTube link.")
        await bot.delete_message(message.chat.id, message.message_id)  # Delete the waiting message

async def download_and_send_audio(bot, c, youtube_link, request_num):
    mp3_file_path, title, artist, artist_image_url = await download_video_and_convert_to_mp3(youtube_link, request_num)

    if mp3_file_path:
        audio_size_mb = os.path.getsize(mp3_file_path) / (1024 * 1024)  # Convert file size to MB
        if audio_size_mb <= 50:
            # Usa il numero di richiesta nel nome del file temporaneo
            temp_file_name = f"temp_audio({request_num}).mp3"
            with open(mp3_file_path, 'rb') as audio_file:
                await bot.send_audio(c.chat.id, audio=audio_file, title=title, performer=artist, thumb=artist_image_url)

            os.remove(mp3_file_path)  # Remove the temporary mp3 file after sending it
            await c.delete()  # Delete the waiting message
        else:
            await c.edit_text("The audio file exceeds the 50MB limit and cannot be sent.")
            os.remove(mp3_file_path)
    else:
        await c.edit_text("Sorry, unable to extract audio from the provided video.")



async def download_video_and_convert_to_mp3(video_url, request_num):
    cmd = f'yt-dlp --get-url --format bestaudio --no-playlist "{video_url}"'
    try:
        audio_url = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
        if not audio_url:
            logging.error("Failed to get audio URL.")
            return None, None, None, None

        yt = YouTube(video_url)
        title = yt.title
        artist = yt.author
        artist_channel = yt.channel_url
        artist_image_url = get_artist_channel_image(artist_channel)

        mp3_file_name = get_unique_temp_file_name(request_num)
        cmd = f'ffmpeg -i "{audio_url}" -codec:a libmp3lame -qscale:a 2 "{mp3_file_name}"'
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return mp3_file_name, title, artist, artist_image_url
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during download: {e}")
        return None, None, None, None
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return None, None, None, None

def get_unique_temp_file_name(request_num):
    base_name = f"temp_audio({request_num}).mp3"
    if os.path.exists(base_name):
        i = 1
        while os.path.exists(f"temp_audio({request_num})_{i}.mp3"):
            i += 1
        return f"temp_audio({request_num})_{i}.mp3"
    else:
        return base_name

def get_artist_channel_image(artist_channel_url):
    try:
        yt = YouTube(artist_channel_url)
        return yt.thumbnail_url
    except Exception as e:
        logging.error(f"Failed to get artist channel image: {e}")
        return None
 


# Set the log level for pytube and ffmpeg to ERROR
#logging.getLogger('pytube').setLevel(logging.ERROR)
#logging.getLogger('ffmpeg').setLevel(logging.ERROR)

# Start the bot
if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
