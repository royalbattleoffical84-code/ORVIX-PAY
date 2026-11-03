ORVIX HOSTING BOT — TELEGRAM FILE-ID STORAGE

How it works:
- Uploads save Telegram file_id/file_unique_id and metadata in Firebase RTDB.
- File bytes are not downloaded into the bot or saved as Base64 in RTDB.
- My Files lists each user's own files; tapping one resends it using file_id.
- Existing legacy Base64 files remain downloadable through a compatibility fallback.
- No file-delete action or automatic deletion is implemented.
- Uploaded scripts are stored only; this bot does not execute them.

Owner access:
- OWNER_ID has Owner Lifetime access and bypasses this bot's plan expiry,
  file-count and storage-quota checks. This is app-level access only, not
  unlimited Telegram, Firebase or hosting capacity.

Deployment:
Build: pip install -r requirements.txt
Start: python dk_bot_host_pro.py

Required environment variables:
BOT_TOKEN
ADMIN_ID
OWNER_ID (optional; defaults to ADMIN_ID)
FIREBASE_DATABASE_URL
FIREBASE_SERVICE_ACCOUNT_JSON
PAYX_API_KEY
PAYX_BASE_URL (optional; defaults to https://payx-q1nn.onrender.com)
MAX_UPLOAD_BYTES (optional; default 0 = no extra application-level cap)
SUPPORT_TEXT (optional)

Limits and reliability:
- RTDB stores only metadata and file references, so file bytes do not consume
  RTDB storage quota. RTDB quotas still apply to metadata/user data.
- Telegram controls actual upload, retention and resend limits. This code does
  not install a Local Bot API Server and does not promise 500 MB/2 GB delivery.
  Test large-file delivery with your actual bot before relying on it.
- MAX_UPLOAD_BYTES=0 removes only this bot's extra cap; Telegram limits and
  non-owner subscription quotas still apply.
- A Telegram file_id is not an independent permanent backup and may stop
  working if Telegram invalidates it or the bot/account setup changes.
- No automatic deletion is not a guarantee against accidental deletion,
  project/account deletion, corruption or operator mistakes. Back up RTDB.
- Keep Telegram token, Firebase service-account JSON and PayX key private.
