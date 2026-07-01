import os
import asyncio
import mutagen
from mutagen.id3 import ID3, APIC, TIT2, TPE1
from mutagen.mp4 import MP4, MP4Cover
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

# --- CONFIGURATION ---
TOKEN = "8753218694:AAHVZedi378mEZ9wh9bKaODWtsz0JxE9TiE"
GET_TITLE, GET_ARTIST, GET_COVER = range(3)

# Font Mapping Dictionaries
BOLD_MAP = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz", "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙")
MONO_MAP = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz", "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ")

def style_text(text: str) -> str:
    """
    Har word ka first letter BOLD font mein aur baaki saare letters MONO font mein badalta hai.
    """
    words = text.split(" ")
    styled_words = []
    for word in words:
        if not word:
            continue
        first_letter = word[0].translate(BOLD_MAP)
        remaining_letters = word[1:].translate(MONO_MAP)
        styled_words.append(f"{first_letter}{remaining_letters}")
    return " ".join(styled_words)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        welcome_text = (
            f"🤖 {style_text('Bot Running! Send any kind of music file to edit')}\n\n"
            f"{style_text('Owner')} @RcHarsh\n"
            f"{style_text('all rights reserved.')}"
        )
        await update.message.reply_text(welcome_text, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.is_bot:
        return ConversationHandler.END

    audio_file = update.message.audio
    if not audio_file:
        return ConversationHandler.END

    status_msg = await update.message.reply_text(f"📥 {style_text('Downloading...')}")
    ext = audio_file.mime_type.split('/')[-1] if audio_file.mime_type else "mp3"
    if ext == "mpeg": ext = "mp3"
    
    file_path = f"temp_{update.message.chat_id}_{audio_file.file_id}.{ext}"
    tg_file = await context.bot.get_file(audio_file.file_id)
    await tg_file.download_to_drive(file_path)

    context.user_data["file_path"] = file_path
    context.user_data["ext"] = ext
    context.user_data["original_msg_id"] = update.message.message_id
    context.user_data["active_user_id"] = update.message.from_user.id
    context.user_data["cover_path"] = None

    await status_msg.edit_text(f"📝 {style_text('Done! Send the New Title:')}")
    return GET_TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != context.user_data.get("active_user_id"):
        return GET_TITLE
        
    if not update.message or not update.message.text:
        return GET_TITLE
        
    context.user_data["title"] = update.message.text
    await update.message.reply_text(f"👤 {style_text('Send the Artist Name:')}")
    return GET_ARTIST

async def get_artist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != context.user_data.get("active_user_id"):
        return GET_ARTIST
        
    if not update.message or not update.message.text:
        return GET_ARTIST
        
    context.user_data["artist"] = update.message.text
    
    skip_button_text = f"{style_text('Skip Cover Art')} ⏭️"
    reply_keyboard = [[skip_button_text]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(f"🖼️ {style_text('Send a Cover Photo or tap skip.')}", reply_markup=markup)
    return GET_COVER

async def process_and_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, download_cover=False):
    chat_id = update.effective_chat.id
    status_msg = await update.message.reply_text(f"⚙️ {style_text('Saving tags...')}", reply_markup=ReplyKeyboardRemove())
    file_path = context.user_data.get("file_path")
    ext = context.user_data.get("ext")
    title = context.user_data.get("title")
    artist = context.user_data.get("artist")
    cover_path = context.user_data.get("cover_path")

    if not file_path or not os.path.exists(file_path):
        return ConversationHandler.END

    try:
        if download_cover and update.message.photo:
            photo = update.message.photo[-1]
            cover_path = f"cover_{photo.file_id}.jpg"
            tg_photo = await context.bot.get_file(photo.file_id)
            await tg_photo.download_to_drive(cover_path)

        if ext in ["mp4", "m4a"]:
            audio = MP4(file_path)
            audio["©nam"] = [title]
            audio["©ART"] = [artist]
            if cover_path:
                with open(cover_path, "rb") as f:
                    audio["covr"] = [MP4Cover(f.read(), imageformat=MP4Cover.FORMAT_JPEG)]
            audio.save()
        else:
            try:
                audio_tags = ID3(file_path)
                audio_tags.delete()
            except Exception:
                audio_tags = ID3()
                
            audio_tags.add(TIT2(encoding=3, text=[title]))
            audio_tags.add(TPE1(encoding=3, text=[artist]))
            
            if cover_path:
                with open(cover_path, "rb") as f:
                    audio_tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=f.read()))
            audio_tags.save(file_path)

        try: await status_msg.edit_text(f"📤 {style_text('Uploading...')}")
        except Exception: pass
        
        with open(file_path, "rb") as f:
            await context.bot.send_audio(chat_id=chat_id, audio=f, title=title, performer=artist, reply_to_message_id=context.user_data["original_msg_id"])
        try: await status_msg.delete()
        except Exception: pass
    except Exception:
        with open(file_path, "rb") as f:
            await context.bot.send_audio(chat_id=chat_id, audio=f, title=title, performer=artist, reply_to_message_id=context.user_data["original_msg_id"])
        try: await status_msg.delete()
        except Exception: pass
    finally:
        if file_path and os.path.exists(file_path): os.remove(file_path)
        if cover_path and os.path.exists(cover_path): os.remove(cover_path)
        context.user_data.clear()
    return ConversationHandler.END

async def get_cover_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != context.user_data.get("active_user_id"):
        return GET_COVER
    return await process_and_upload(update, context, download_cover=True)

async def skip_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != context.user_data.get("active_user_id"):
        return GET_COVER
    return await process_and_upload(update, context, download_cover=False)

async def post_init(application: Application) -> None:
    menu_desc = f"{style_text('Check I Am Alive')}"
    await application.bot.set_my_commands([BotCommand("start", menu_desc)])

async def start_bot():
    """
    Asynchronous runner config for stable deployment under Python 3.13 environments
    """
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.AUDIO, handle_audio)],
        states={
            GET_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            GET_ARTIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_artist)],
            GET_COVER: [MessageHandler(filters.PHOTO, get_cover_photo), MessageHandler(filters.TEXT, skip_cover)],
        },
        fallbacks=[CommandHandler("start", start)],
        per_chat=True,
        per_user=False,
        allow_reentry=True
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    # Keeping the background script loop up infinitely 24/7
    while True:
        await asyncio.sleep(3600)

def main():
    try:
        asyncio.run(start_bot())
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    main()
    
