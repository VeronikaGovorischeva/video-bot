import os, json, datetime, tempfile
from dotenv import load_dotenv
from telegram import Update, ForceReply
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler
)
from drive_utils import upload_video, create_folder

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(",")))
TRAININGS_FOLDER_ID = os.getenv("TRAININGS_FOLDER_ID")

STATE_FILE = "state.json"

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"active_event": None}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# --- COMMANDS FOR ADMINS ONLY ---
async def start_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("Access denied.")

    await update.message.reply_text("Please send the event folder name:")
    return 1

async def receive_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    folder_id = create_folder(name, TRAININGS_FOLDER_ID)
    save_state({"active_event": folder_id})
    await update.message.reply_text(f"Event started. Videos will be uploaded to '{name}'")
    return ConversationHandler.END

async def end_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("Access denied.")
    save_state({"active_event": None})
    await update.message.reply_text("Event ended.")
    return

# --- VIDEO HANDLING ---
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        return

    file = await context.bot.get_file(video.file_id)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
        await file.download_to_drive(f.name)
        local_path = f.name

    state = load_state()

    if state["active_event"]:
        target_folder = state["active_event"]
    else:
        today = datetime.date.today().isoformat()
        target_folder = create_folder(today, TRAININGS_FOLDER_ID)

    upload_video(local_path, target_folder)
    os.remove(local_path)

# --- SETUP ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start_event", start_event)],
        states={1: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_event_name)]},
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("end_event", end_event))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
