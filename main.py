import os
import mutagen
from mutagen.id3 import APIC
from mutagen.mp4 import MP4Cover
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

# --- CREDITS ---
# Edited by @RcHarsh
# ---------------

# --- CONFIGURATION ---
TOKEN = "8753218694:AAHVZedi378mEZ9wh9bKaODWtsz0JxE9TiE"
# ---------------------

GET_TITLE, GET_ARTIST, GET_COVER = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Send me any MP3/M4A file to start editing!",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    audio_file = update.message.audio
    if not audio_file:
        await update.message.reply_text("❌ Send a valid audio track.")
        return ConversationHandler.END

    status_msg = await update.message.reply_text("📥 Downloading...")
    
    ext = audio_file.mime_type.split('/')[-1] if audio_file.mime_type else "mp3"
    if ext == "mpeg": ext = "mp3"
    
    file_path = f"temp_{audio_file.file_id}.{ext}"
    tg_file = await context.bot.get_file(audio_file.file_id)
    await tg_file.download_to_drive(file_path)

    context.user_data["file_path"] = file_path
    context.user_data["ext"] = ext
    context.user_data["original_msg_id"] = update.message.message_id
    context.user_data["cover_path"] = None

    await status_msg.edit_text("📝 Done! Send the **New Title**:")
    return GET_TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    await update.message.reply_text("👤 Send the **Artist Name**:")
    return GET_ARTIST

async def get_artist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["artist"] = update.message.text
    
    reply_keyboard = [["Skip Cover Art ⏭️"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        "🖼️ Send a **Cover Photo** or tap skip.",
        reply_markup=markup
    )
    return GET_COVER

async def process_and_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, download_cover=False):
    chat_id = update.effective_chat.id
    status_msg = await update.message.reply_text("⚙️ Saving tags...", reply_markup=ReplyKeyboardRemove())
    
    file_path = context.user_data["file_path"]
    ext = context.user_data["ext"]
    title = context.user_data["title"]
    artist = context.user_data["artist"]
    cover_path = context.user_data.get("cover_path")

    try:
        if download_cover:
            photo = update.message.photo[-1]
            cover_path = f"cover_{photo.file_id}.jpg"
            tg_photo = await context.bot.get_file(photo.file_id)
            await tg_photo.download_to_drive(cover_path)

        audio = mutagen.File(file_path)
        if audio is None:
            raise Exception("Invalid file layout.")

        is_mp4 = hasattr(audio, 'tags') and type(audio.tags).__name__ == "MP4Tags"

        if is_mp4:
            audio["©nam"] = [title]
            audio["©ART"] = [artist]
            if cover_path:
                with open(cover_path, "rb") as f:
                    audio["covr"] = [MP4Cover(f.read(), imageformat=MP4Cover.FORMAT_JPEG)]
        else:
            if audio.tags is None:
                audio.add_tags()
                
            audio["title"] = [title]
            audio["artist"] = [artist]
            
            if cover_path:
                for key in list(audio.keys()):
                    if key.startswith("APIC"):
                        del audio[key]
                with open(cover_path, "rb") as f:
                    audio.tags.add(APIC(
                        encoding=3, mime="image/jpeg", type=3, desc="Cover", data=f.read()
                    ))

        audio.save()

        try:
            await status_msg.edit_text("📤 Uploading...")
        except Exception:
            pass
        
        with open(file_path, "rb") as f:
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=f,
                title=title,
                performer=artist,
                reply_to_message_id=context.user_data["original_msg_id"]
            )
            
        try:
            await status_msg.delete()
        except Exception:
            pass

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}", reply_markup=ReplyKeyboardRemove())

    finally:
        if os.path.exists(file_path): os.remove(file_path)
        if cover_path and os.path.exists(cover_path): os.remove(cover_path)
        context.user_data.clear()

    return ConversationHandler.END

async def get_cover_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await process_and_upload(update, context, download_cover=True)

async def skip_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await process_and_upload(update, context, download_cover=False)

def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.AUDIO, handle_audio)],
        states={
            GET_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_title)],
            GET_ARTIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_artist)],
            GET_COVER: [
                MessageHandler(filters.PHOTO, get_cover_photo),
                MessageHandler(filters.Regex("^Skip Cover Art ⏭️$"), skip_cover)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
                        
