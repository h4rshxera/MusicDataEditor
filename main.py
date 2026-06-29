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

# --- CONFIGURATION ---
TOKEN = "8874026541:AAHGszEOPJ1qJc2rESvj6MdJqfu1BhZkwZs"
# ---------------------

# Conversation states
GET_TITLE, GET_ARTIST, GET_COVER = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user"""
    await update.message.reply_text(
        "A MusicData Editor Bot By @RcHarsh, Send Any music",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers when user sends an audio track"""
    audio_file = update.message.audio
    if not audio_file:
        await update.message.reply_text("❌ Please send a valid music file.")
        return ConversationHandler.END

    status_msg = await update.message.reply_text("📥 Downloading your song...")
    
    # Save extension type safely
    ext = audio_file.mime_type.split('/')[-1] if audio_file.mime_type else "mp3"
    if ext == "mpeg": ext = "mp3"
    
    file_path = f"temp_{audio_file.file_id}.{ext}"
    tg_file = await context.bot.get_file(audio_file.file_id)
    await tg_file.download_to_drive(file_path)

    # Store file data inside context user data memory
    context.user_data["file_path"] = file_path
    context.user_data["ext"] = ext
    context.user_data["original_msg_id"] = update.message.message_id
    context.user_data["cover_path"] = None

    await status_msg.edit_text("📝 File downloaded!\n\n👉 Now, type and send the **Song Title**:")
    return GET_TITLE

async def get_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores title and requests artist name"""
    context.user_data["title"] = update.message.text
    await update.message.reply_text("👤 Awesome. Now send the **Artist Name**:")
    return GET_ARTIST

async def get_artist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores artist and requests cover image"""
    context.user_data["artist"] = update.message.text
    
    # Setup custom keyboard option to skip cover art injection
    reply_keyboard = [["Skip Cover Art ⏭️"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        "send the Cover Photo as an image.\n\n",
        reply_markup=markup
    )
    return GET_COVER

async def process_and_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, download_cover=False):
    """Saves metadata and sends file back"""
    chat_id = update.effective_chat.id
    status_msg = await update.message.reply_text("⚙️ Compiling audio metadata tags...", reply_markup=ReplyKeyboardRemove())
    
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

        # Apply Tags via Smart Mutagen File detector
        audio = mutagen.File(file_path)
        
        if audio is None:
            raise Exception("Unsupported file format.")

        # Check if the metadata is MP4 structure or traditional ID3/Flac structure
        is_mp4 = hasattr(audio, 'tags') and type(audio.tags).__name__ == "MP4Tags"

        if is_mp4:
            # MP4 Key Mapping Structures
            audio["©nam"] = [title]
            audio["©ART"] = [artist]
            
            if cover_path:
                with open(cover_path, "rb") as f:
                    audio["covr"] = [MP4Cover(f.read(), imageformat=MP4Cover.FORMAT_JPEG)]
        else:
            # MP3 / Generic Audio Structure
            if audio.tags is None:
                audio.add_tags()
                
            audio["title"] = [title]
            audio["artist"] = [artist]
            
            if cover_path:
                # Flush old MP3 covers safely 
                for key in list(audio.keys()):
                    if key.startswith("APIC"):
                        del audio[key]
                with open(cover_path, "rb") as f:
                    audio.tags.add(APIC(
                        encoding=3, mime="image/jpeg", type=3, desc="Cover", data=f.read()
                    ))

        audio.save()

        try:
            await status_msg.edit_text("Uploading your customized file... 📤")
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
        await update.message.reply_text(f"❌ Error while updating tags: {str(e)}", reply_markup=ReplyKeyboardRemove())

    finally:
        if os.path.exists(file_path): os.remove(file_path)
        if cover_path and os.path.exists(cover_path): os.remove(cover_path)
        context.user_data.clear()

    return ConversationHandler.END

async def get_cover_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered if user sends an image"""
    return await process_and_upload(update, context, download_cover=True)

async def skip_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered if user taps skip"""
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

    print("Bot is running... Open Telegram and message your bot.")
    app.run_polling()

if __name__ == "__main__":
    main()
      
