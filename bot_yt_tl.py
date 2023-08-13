from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeAudio
import yt_dlp
import os
import re
import ffmpeg
import subprocess
import asyncio
import json


# Configurazione delle credenziali di Telethon
api_id = 2
api_hash = 'di183s'


# Inizializza il client di Telethon
client = TelegramClient("bot_yt_tl", api_id, api_hash)
client.start()
print("bot on ok")


owner_id = 5942569516

# Carica i dati dal file JSON al caricamento dello script
def load_data():
    try:
        with open('user_data.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []

user_data = load_data()

# Comando /start per salvare l'ID dell'utente nel database
@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user_id = event.sender_id
    if user_id not in user_data:
        user_data.append(user_id)
        save_data()

    await event.respond("Ciao, Mandami un link di YouTube e ti manderò il file come mp3")

# Funzione per salvare i dati nel file JSON
def save_data():
    with open('user_data.json', 'w') as file:
        json.dump(user_data, file)

# Comando /post per inviare un messaggio personalizzato a tutti gli utenti salvati
@client.on(events.NewMessage(pattern='/post'))
async def post_handler(event):
    if event.sender_id == owner_id:
        if event.reply_to_msg_id:
            replied_msg = await event.get_reply_message()
            for user_id in user_data:
                await replied_msg.forward_to(user_id)
            await event.respond("Messaggio inviato a tutti gli utenti.")
        else:
            await event.respond("Rispondi al messaggio che vuoi inviare a tutti gli utenti.")



@client.on(events.NewMessage)
async def start(event):
	if event.text == "/clear":
		os.system("clear")
		print("bot on ok")
		await event.delete()


@client.on(events.NewMessage)
async def handle_message(event):
    if event.text.startswith(('http://www.youtube.com/', 'https://www.youtube.com/', 'http://youtu.be/', 'https://youtu.be/')):
        video_url = event.text
        await download_and_send_audio(event, video_url)


# Dizionario per tenere traccia degli eventi in corso di download
downloading_events = {}

async def download_and_send_audio(event, video_url):
    try:
        # Verifica se il download è già stato avviato per questo evento
        if event.chat_id in downloading_events:
            return

        # Imposta l'evento corrente come in corso di download
        downloading_events[event.chat_id] = True

        # Scarica il video di YouTube utilizzando yt_dlp e salva l'output in una cartella temporanea
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join('/storage/emulated/0/spammerBot/convert_mp3', '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            audio_file = ydl.prepare_filename(info_dict)

        # Calcola il tempo stimato in minuti
        estimated_time = info_dict.get('duration', 0) / 60

        # Invia un messaggio di notifica con il tempo stimato
        downloading_msg = await event.respond(f"Sto scaricando la musica, attendi... Tempo stimato: {estimated_time:.2f} secondi")

        # Converte il file audio in MP3 utilizzando FFmpeg
        mp3_file = audio_file.replace('.webm', '.mp3')
        ffmpeg_command = ['ffmpeg', '-i', audio_file, mp3_file]
        subprocess.run(ffmpeg_command, stderr=subprocess.PIPE)

        # Verifica che il file MP3 esista prima di inviarlo
        if os.path.exists(mp3_file):
            # Invia il file audio MP3 tramite un messaggio su Telegram
            await client.send_file(
                event.chat_id,
                mp3_file,
                voice=True,
                attributes=[
                    DocumentAttributeAudio(
                        duration=info_dict['duration'],
                        title=info_dict['title'],
                        performer=info_dict.get('creator', None)
                    )
                ]
            )

            # Invia un messaggio di completamento
            await downloading_msg.edit(f"Download completato in {estimated_time:.2f} secondi !")

            # Rimuovi i file temporanei
            if os.path.exists(audio_file):
                os.remove(audio_file)
            if os.path.exists(mp3_file):
                os.remove(mp3_file)
        else:
            await downloading_msg.edit("Errore durante la conversione dell'audio in formato MP3.")

    except Exception as e:
        pass  # Gestisci l'errore senza inviare messaggi

    finally:
        # Resetta lo stato dell'evento corrente
        downloading_events.pop(event.chat_id, None)


# Loop per gestire i messaggi in arrivo
@client.on(events.NewMessage)
async def handle_message(event):
    if event.text.startswith("/download"):
        video_url = event.text.split(" ")[1]
        await download_and_send_audio(event, video_url)


# Avvia il client Telethon
with client:
    client.run_until_disconnected()
