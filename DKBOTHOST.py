import telebot
from telebot import types
import os
import json
import subprocess
import shutil
import time
import zipfile
import psutil
from datetime import datetime

# ✅ Apna Bot Token yahan daalein
BOT_TOKEN = os.getenv("BOT_TOKEN", "8966967834:AAHUwKnvPhDbnJtijrkqm4roUAIHQp0_PuU")
bot = telebot.TeleBot(BOT_TOKEN)

# ---------------- Storage Setup ----------------
BASE_DIR = "hosted_bots"
USERS_FILE = "users.json"
os.makedirs(BASE_DIR, exist_ok=True)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

users = load_users()
active_processes = {}

# ---------------- Main Reply Keyboard (Neeche wale buttons) ----------------
def main_reply_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_channel = types.KeyboardButton("📢 Updates Channel")
    btn_upload = types.KeyboardButton("📤 Upload File")
    btn_check = types.KeyboardButton("📁 Check Files")
    btn_speed = types.KeyboardButton("⚡ Bot Speed")
    btn_stats = types.KeyboardButton("📊 Statistics")
    btn_contact = types.KeyboardButton("📞 Contact Owner")
    
    # Layout setting (Jaisa screenshot mein hai)
    markup.add(btn_channel)
    markup.add(btn_upload, btn_check)
    markup.add(btn_speed, btn_stats)
    markup.add(btn_contact)
    return markup

# ---------------- /start Command ----------------
@bot.message_handler(commands=['start'])
def start(message):
    uid = str(message.from_user.id)
    
    # User DB Setup
    if uid not in users:
        users[uid] = {
            "name": message.from_user.first_name,
            "username": message.from_user.username,
            "bots": {},
            "status": "FREE Free User",
            "joined": str(datetime.now())
        }
        save_users(users)

    # Welcome Message (Screenshot jaisa)
    text = (
        f"👋 Welcome, <b>{message.from_user.first_name.upper()}</b>!\n\n"
        f"🆔 Your User ID: <code>{uid}</code>\n"
        f"👤 Username: @{message.from_user.username or 'N/A'}\n"
        f"🟩 Your Status: <b>{users[uid].get('status', 'FREE Free User')}</b>\n"
        f"📁 Files Uploaded: {len(users[uid].get('bots', {}))} / 10\n\n"
        f"🤖 Host & run Python (.py) or JS (.js) scripts.\n"
        f"Upload single scripts or .zip archives.\n\n"
        f"👇 Use buttons or type commands."
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=main_reply_keyboard())

# ---------------- Text Buttons Handler ----------------
@bot.message_handler(func=lambda message: message.text in [
    "📢 Updates Channel", "📤 Upload File", "📁 Check Files", 
    "⚡ Bot Speed", "📊 Statistics", "📞 Contact Owner"
])
def handle_buttons(message):
    uid = str(message.from_user.id)
    
    if message.text == "📢 Updates Channel":
        bot.reply_to(message, "📢 Yahan hamara updates channel hai: @YourUpdatesChannel\n(Link change karein code mein)")
        
    elif message.text == "📤 Upload File":
        bot_count = len(users.get(uid, {}).get("bots", {}))
        if bot_count >= 10:
            bot.reply_to(message, "❌ Aapki limit puri ho gayi hai (10/10).\nPehle kuch files delete karein.")
            return
        msg = bot.reply_to(message, "📤 Apni <b>.py</b> ya <b>.zip</b> file bhejein.", parse_mode='HTML')
        bot.register_next_step_handler(msg, process_file_upload)

    elif message.text == "📁 Check Files":
        user_bots = users.get(uid, {}).get("bots", {})
        if not user_bots:
            bot.reply_to(message, "📁 Aapne abhi tak koi file upload nahi ki hai.")
            return

        text = "📁 <b>Your Hosted Files:</b>\n\n"
        markup = types.InlineKeyboardMarkup(row_width=2)
        for name, info in user_bots.items():
            status = "🟢 Running" if info.get("status") == "running" else "🔴 Stopped"
            text += f"• <b>{name}</b> — {status}\n"
            markup.add(
                types.InlineKeyboardButton(f"▶️ Start", callback_data=f"start_{name}"),
                types.InlineKeyboardButton(f"⏹ Stop", callback_data=f"stop_{name}")
            )
            markup.add(types.InlineKeyboardButton(f"🗑 Delete {name}", callback_data=f"delete_{name}"))
        
        bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)

    elif message.text == "⚡ Bot Speed":
        start_time = time.time()
        msg = bot.reply_to(message, "⏳ Checking speed...")
        end_time = time.time()
        ping = round((end_time - start_time) * 1000, 2)
        bot.edit_message_text(f"⚡ <b>Bot Speed:</b>\nPing: {ping} ms\nStatus: Very Fast 🚀", 
                              chat_id=message.chat.id, message_id=msg.message_id, parse_mode='HTML')

    elif message.text == "📊 Statistics":
        total_users = len(users)
        total_bots = sum(len(u.get("bots", {})) for u in users.values())
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        
        text = (
            f"📊 <b>Bot Statistics</b>\n\n"
            f"👥 Total Users: {total_users}\n"
            f"🤖 Total Hosted Bots: {total_bots}\n"
            f"🖥 CPU Usage: {cpu}%\n"
            f"💾 RAM Usage: {ram}%"
        )
        bot.reply_to(message, text, parse_mode='HTML')

    elif message.text == "📞 Contact Owner":
        bot.reply_to(message, "📞 <b>Contact Owner</b>\n\nOwner: @YourUsername\nSupport: @YourSupport", parse_mode='HTML')

# ---------------- File Upload Handler ----------------
def process_file_upload(message):
    if not message.document:
        bot.reply_to(message, "❌ Kripya koi valid file (document) bhejein.")
        return

    doc = message.document
    if not (doc.file_name.endswith(".py") or doc.file_name.endswith(".zip") or doc.file_name.endswith(".js")):
        bot.reply_to(message, "❌ Sirf <b>.py</b>, <b>.js</b>, ya <b>.zip</b> file allowed hai!", parse_mode='HTML')
        return

    msg = bot.reply_to(message, "✏️ Is file ka naam kya rakhna hai? (Reply mein likhein)")
    bot.register_next_step_handler(msg, save_uploaded_file, doc)

def save_uploaded_file(message, doc):
    uid = str(message.from_user.id)
    bot_name = message.text.strip().replace(" ", "_")[:20]
    
    user_dir = os.path.join(BASE_DIR, uid, bot_name)
    os.makedirs(user_dir, exist_ok=True)

    # File Download
    file_info = bot.get_file(doc.file_id)
    downloaded = bot.download_file(file_info.file_path)
    file_path = os.path.join(user_dir, doc.file_name)
    
    with open(file_path, "wb") as f:
        f.write(downloaded)

    # ZIP extract logic
    if doc.file_name.endswith(".zip"):
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(user_dir)
            os.remove(file_path) # Zip delete kar do
            bot.reply_to(message, "✅ ZIP file successfully extract ho gayi!")
        except Exception as e:
            bot.reply_to(message, f"❌ ZIP extract error: {e}")
            return

    # Save to DB
    users[uid].setdefault("bots", {})[bot_name] = {
        "status": "stopped",
        "uploaded": str(datetime.now()),
        "path": user_dir
    }
    save_users(users)

    bot.send_message(
        message.chat.id,
        f"✅ <b>File Uploaded Successfully!</b>\n\n"
        f"📁 Name: <b>{bot_name}</b>\n"
        f"📄 File: {doc.file_name}\n"
        f"📊 Total Files: {len(users[uid]['bots'])} / 10\n\n"
        f"Ab '📁 Check Files' par jaakar ise Start karein.",
        parse_mode='HTML',
        reply_markup=main_reply_keyboard()
    )

# ---------------- Inline Buttons (Start/Stop/Delete) ----------------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = str(call.from_user.id)
    data = call.data

    if data.startswith("start_"):
        name = data.replace("start_", "")
        user_dir = os.path.join(BASE_DIR, uid, name)
        
        # Find entry file (bot.py ya index.js)
        entry_file = None
        for f in os.listdir(user_dir):
            if f == "bot.py" or f == "main.py":
                entry_file = f
                break
            elif f == "index.js":
                entry_file = f
                break

        if not entry_file:
            bot.answer_callback_query(call.id, "❌ Entry file (bot.py / main.py) nahi mili!")
            return

        if uid in active_processes and name in active_processes[uid]:
            bot.answer_callback_query(call.id, "⚠️ Pehle se chal raha hai!")
            return

        try:
            # Run based on extension
            if entry_file.endswith(".py"):
                proc = subprocess.Popen(["python", entry_file], cwd=user_dir)
            else:
                proc = subprocess.Popen(["node", entry_file], cwd=user_dir)
                
            if uid not in active_processes:
                active_processes[uid] = {}
            active_processes[uid][name] = proc
            
            users[uid]["bots"][name]["status"] = "running"
            save_users(users)
            bot.answer_callback_query(call.id, f"✅ {name} started!")
            bot.send_message(call.message.chat.id, f"🟢 <b>{name}</b> start ho gaya!", parse_mode='HTML')
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {str(e)[:50]}")

    elif data.startswith("stop_"):
        name = data.replace("stop_", "")
        if uid in active_processes and name in active_processes[uid]:
            active_processes[uid][name].terminate()
            del active_processes[uid][name]
        users[uid]["bots"][name]["status"] = "stopped"
        save_users(users)
        bot.answer_callback_query(call.id, f"⏹ {name} stopped!")
        bot.send_message(call.message.chat.id, f"🔴 <b>{name}</b> stop ho gaya.", parse_mode='HTML')

    elif data.startswith("delete_"):
        name = data.replace("delete_", "")
        if uid in active_processes and name in active_processes[uid]:
            active_processes[uid][name].terminate()
            del active_processes[uid][name]
        
        folder = os.path.join(BASE_DIR, uid, name)
        if os.path.exists(folder):
            shutil.rmtree(folder)
            
        users[uid]["bots"].pop(name, None)
        save_users(users)
        bot.answer_callback_query(call.id, f"🗑 {name} deleted!")
        bot.send_message(call.message.chat.id, f"🗑 <b>{name}</b> delete ho gaya.", parse_mode='HTML')

# ---------------- Run ----------------
if __name__ == "__main__":
    print("🚀 DK HOSTING PRO Style Bot Chal Raha Hai...")
    bot.infinity_polling()