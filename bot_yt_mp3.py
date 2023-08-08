import logging
import re
import os
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from pytube import YouTube

# Set up bot
bot_token = 'token'
bot = Bot(token=bot_token)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)
dp.middleware.setup(LoggingMiddleware())

# Function to extract YouTube link from the message text
def extract_youtube_link(text):
    match = re.search(r'(https?://(?:www\.)?youtube\.com\S+|https?://youtu\.be\S+)', text)
    return match.group(1) if match else None

# Handler to handle text messages
@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle_text(message: types.Message):
    text = message.text
    youtube_link = extract_youtube_link(text)
    c = await bot.send_message(message.chat.id, "Please wait, I'm downloading the audio...")
    await bot.send_chat_action(message.chat.id, 'upload_document')

    if youtube_link:
        mp3_file_path, title, artist, artist_image_url = await download_video_and_convert_to_mp3(youtube_link)

        if mp3_file_path:
            audio_size_mb = os.path.getsize(mp3_file_path) / (1024 * 1024)  # Convert file size to MB
            if audio_size_mb <= 50:  # Check if the file size is within the 50MB limit

                with open(mp3_file_path, 'rb') as audio_file:
                    await bot.send_audio(message.chat.id, audio=audio_file, title=title, performer=artist, thumb=artist_image_url)

                os.remove(mp3_file_path)  # Remove the temporary mp3 file after sending it

                # Delete the previous message sent by the bot (waiting message)
                await bot.delete_message(c.chat.id, c.message_id)
            else:
                await message.answer("The audio file exceeds the 50MB limit and cannot be sent.")
                os.remove(mp3_file_path)  # Remove the temporary mp3 file as it won't be sent
                await bot.delete_message(c.chat.id, c.message_id)
        else:
            await message.answer("Sorry, unable to extract audio from the provided video.")

    else:
        await message.answer("Please provide a valid YouTube link.")

        # Delete the previous message sent by the bot (waiting message)
        await bot.delete_message(message.chat.id, message.message_id)
 


async def download_video_and_convert_to_mp3(video_url):
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

        mp3_file_name = "temp_audio.mp3"
        cmd = f'ffmpeg -i "{audio_url}" -codec:a libmp3lame -qscale:a 2 "{mp3_file_name}"'
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return mp3_file_name, title, artist, artist_image_url
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during download: {e}")
        return None, None, None, None
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return None, None, None, None

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
