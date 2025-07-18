import os
import json
import datetime
import tempfile
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, filters
)
from drive_utils import upload_video, create_folder

# === CONFIG ===
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
TRAININGS_FOLDER_ID = os.getenv("TRAININGS_FOLDER_ID")
STATE_FILE = "state.json"


# === STATE MGMT ===
def load_state():
    if not os.path.exists(STATE_FILE):
        return {"active_event": None}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# === ADMIN COMMANDS ===
async def start_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("⛔ You are not authorized.")

    await update.message.reply_text("📁 Send the folder name for this event:")
    return 1

async def receive_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    folder_id = create_folder(name, TRAININGS_FOLDER_ID)
    save_state({"active_event": folder_id})
    await update.message.reply_text(f"✅ Event started. Folder: *{name}*", parse_mode="Markdown")
    return ConversationHandler.END

async def end_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("⛔ You are not authorized.")
    save_state({"active_event": None})
    await update.message.reply_text("🛑 Event ended.")
    return


# === VIDEO HANDLER ===
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        return

    user = update.effective_user
    print(f"📥 Video from {user.username or user.first_name}")

    # Download to temp file
    file = await context.bot.get_file(video.file_id)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
        await file.download_to_drive(f.name)
        local_path = f.name

    # Respond immediately to avoid Telegram timeout
    await update.message.reply_text("📤 Uploading to Drive in background...")

    # Async background task
    asyncio.create_task(upload_to_drive(local_path))


# === ASYNC UPLOAD TASK ===
async def upload_to_drive(local_path):
    try:
        state = load_state()

        if state["active_event"]:
            folder_id = state["active_event"]
        else:
            today = datetime.date.today().isoformat()
            folder_id = create_folder(today, TRAININGS_FOLDER_ID)

        print(f"📁 Uploading {local_path} to folder {folder_id}")
        upload_video(local_path, folder_id)

    except Exception as e:
        print(f"❌ Upload failed: {e}")
    finally:
        os.remove(local_path)


# === MAIN ENTRY ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Conversation to start an event
    start_conv = ConversationHandler(
        entry_points=[CommandHandler("start_event", start_event)],
        states={1: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_event_name)]},
        fallbacks=[]
    )

    app.add_handler(start_conv)
    app.add_handler(CommandHandler("end_event", end_event))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    print("🚀 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()

