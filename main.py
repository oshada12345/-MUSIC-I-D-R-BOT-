import os
import telebot
import requests
import shutil
import asyncio
from shazamio import Shazam, serialize_track
from telebot import types
from os import getenv

bot = telebot.TeleBot(getenv("BOT_TOKEN",'1871709611:AAECVz2KZv74IpDyJvRsGZi7OW3q1z8Wx6I'))

TEMP_FOLDER = ".temp"

if not os.path.exists(TEMP_FOLDER):
    os.mkdir(TEMP_FOLDER)

with open("TOKEN.txt") as token_file:
    TOKEN = token_file.read().strip()  # read token string from plaintext file named TOKEN.txt

bot = telebot.TeleBot(TOKEN, parse_mode=None)


def download_file_and_return_path(cache_id, file_id):
    file_info = bot.get_file(file_id)
    filename = file_info.file_path.split("/")[-1]  # get filename from filepath
    resp = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(TOKEN, file_info.file_path))
    folder = os.path.join(TEMP_FOLDER, str(cache_id))  # get temp folder name for specific audio sample
    if not os.path.exists(folder):
        os.mkdir(folder)  # create such folder
    filepath = os.path.join(folder, filename)
    with open(filepath, "wb") as f:
        f.write(resp.content)  # write downloaded sample file to temp folder
    return filepath


def download_cover_and_return_path(cache_id, url):
    name = url.split("/")[-1]  # get cover's filename from the last part of URL
    resp = requests.get(url)
    folder = os.path.join(TEMP_FOLDER, str(cache_id))  # get temp folder name for track's covers
    if os.path.exists(folder):
        filepath = os.path.join(folder, name)
        with open(filepath, "wb") as f:
            f.write(resp.content)  # write downloaded track cover to sample's temp folder
        return filepath
    return None


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
    data = asyncio.run(recognize(file_local_path))

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
            if cover_path:
                cover = open(cover_path, "rb")
                bot.send_photo(message.chat.id, cover, caption=caption,
                               reply_to_message_id=message.message_id, parse_mode="MarkdownV2")
                cover.close()
            else:
                bot.reply_to(message, caption, parse_mode="MarkdownV2")
        else:
            bot.reply_to(message, caption, parse_mode="MarkdownV2")
    shutil.rmtree(os.path.join(TEMP_FOLDER, str(message.chat.id)))


bot.polling()
