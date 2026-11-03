ORVIX HOSTING BOT — UPDATED PACKAGE

Files:
- dk_bot_host_pro.py: updated Telegram bot with button-based Admin Panel
- requirements.txt: Python dependencies

Railway:
Build command: pip install -r requirements.txt
Start command: python dk_bot_host_pro.py

Required environment variables:
BOT_TOKEN
ADMIN_ID
OWNER_ID (optional; defaults to ADMIN_ID)
FIREBASE_DATABASE_URL
FIREBASE_STORAGE_BUCKET
FIREBASE_SERVICE_ACCOUNT_JSON
PAYX_API_KEY
PAYX_BASE_URL (optional; defaults to https://payx-q1nn.onrender.com)
MAX_UPLOAD_BYTES (optional)
SUPPORT_TEXT (optional)

Admin:
Open Telegram bot -> Admin Panel. Use Add Plan, Set Plan Price, Enable/Disable/Delete Plan,
Block/Unblock User, Grant Access, Overview, Users and Orders. These actions use guided
button/menu flows; no admin slash commands are needed.

Security:
- Never upload service-account JSON, bot token, or PayX key to GitHub.
- Firebase Admin SDK access is server-side.
- Uploaded files are stored in Firebase Storage and are NOT executed by this bot.
- Owner unlimited access applies only to app-level quota/expiry, not Firebase or hosting limits.
