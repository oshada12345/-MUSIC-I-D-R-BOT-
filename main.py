import os
import shutil
import telebot
import requests
import asyncio
from shazamio import Shazam, serialize_track
from telebot import types
from dotenv import load_dotenv

load_dotenv()

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))

TEMP_FOLDER = ".temp"

if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER, exist_ok=True)


def download_file_and_return_path(cache_id, file_id):
    file_info = bot.get_file(file_id)
    filename = file_info.file_path.split("/")[-1]  # get filename from filepath
    resp = requests.get(f'https://api.telegram.org/file/bot{os.getenv("BOT_TOKEN")}/{file_info.file_path}')
    folder = os.path.join(TEMP_FOLDER, str(cache_id))  # get temp folder name for specific audio sample
    os.makedirs(folder, exist_ok=True)  # create such folder
    filepath = os.path.join(folder, filename)
    with open(filepath, "wb") as f:
        f.write(resp.content)  # write downloaded sample file to temp folder
    return filepath


def download_cover_and_return_path(cache_id, url):
    name = url.split("/")[-1]  # get cover's filename from the last part of URL
    resp = requests.get(url)
    folder = os.path.join(TEMP_FOLDER, str(cache_id))  # get temp folder name for track's covers
    os.makedirs(folder, exist_ok=True)  # create the folder if it doesn't exist
    filepath = os.path.join(folder, name)
    with open(filepath, "wb") as f:
        f.write(resp.content)  # write downloaded track cover to sample's temp folder
    return filepath


async def recognize(path):
    shazam = Shazam()
    out = await shazam.recognize_song(path)
    return out


@bot.message_handler(commands=["start"])
def welcome(message):
    bot.send_message(message.chat.id, "Send audio or voice message to start using the bot")


def escape_markdown(text: str):
    esc = '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'
    for ch in esc:
        if ch in text:
            text = text.replace(ch, '\\' + ch)
    return text


@bot.message_handler(content_types=["audio", "voice"])
def handle_audio(message):
    type_is_voice = message.content_type == "voice"
    file_id = message.voice.file_id if type_is_voice else message.audio.file_id
    duration = message.voice.duration if type_is_voice else message.audio.duration
    file_local_path = download_file_and_return_path(message.chat.id, file_id)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    data = loop.run_until_complete(recognize(file_local_path))

    if duration > 15:
        bot.reply_to(message, "Please try sending a shorter sample")
    elif not data["matches"]:
        bot.reply_to(message, "Sorry, couldn't recognize any song. Try sending a longer sample")
    else:
        track = serialize_track(data['track'])
        song_name = escape_markdown(f'{track.subtitle} - {track.title}')
        caption = f"[{song_name}]({track.apple_music_url})"
        photo_url = data['track']['images']['coverarthq']
        if photo_url:
            cover_path = download_cover_and_return_path(message.chat.id, photo_url)
            with open(cover_path, "rb") as cover:
                bot.send_photo(message.chat.id, cover, caption=caption, parse_mode="MarkdownV2")
            os.remove(cover_path)
        else:
            bot.reply_to(message, caption, parse_mode="MarkdownV2")
    shutil.rmtree(os.path.join(TEMP_FOLDER, str(message.chat.id)))


bot.polling()
