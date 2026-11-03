DK BOT HOST PRO — SETUP

Included:
- Telegram owner/admin panel and commands
- Firebase Realtime Database: users, plans, subscriptions, orders, file metadata
- Firebase Storage: uploaded file objects
- PayX merchant API: POST /api/v1/orders and GET /api/v1/orders/{id}
- Payment activation only after server-side PayX status/reference/amount verification
- Owner ID receives lifetime access and bypasses plan quotas
- File list, download and delete

IMPORTANT SECURITY LIMITATION:
This build stores uploaded .py/.js/.zip files. It DOES NOT execute user uploads.
The original code used subprocess.Popen to run arbitrary user scripts on the same host.
That is unsafe for a multi-user service. Do not add subprocess, eval or exec to this bot.
Actual script hosting needs a separate isolated runner with per-job containers, CPU/RAM/time
limits, non-root users, restricted networking and strict filesystem isolation.

RAILWAY:
Build command: pip install -r requirements.txt
Start command: python dk_bot_host_pro.py

REQUIRED ENVIRONMENT VARIABLES:
BOT_TOKEN = newly regenerated Telegram bot token
ADMIN_ID = numeric Telegram admin ID
OWNER_ID = numeric Telegram owner ID (can equal ADMIN_ID)
FIREBASE_DATABASE_URL = https://YOUR-PROJECT-default-rtdb.firebaseio.com/
FIREBASE_STORAGE_BUCKET = exact bucket name shown in Firebase Storage settings
FIREBASE_SERVICE_ACCOUNT_JSON = complete service account JSON as one-line JSON
PAYX_API_KEY = your PayX LIVE merchant API key (px_live_...)
PAYX_BASE_URL = https://payx-q1nn.onrender.com

Optional:
MAX_UPLOAD_BYTES = 10485760
SUPPORT_TEXT = support contact text

ADMIN COMMANDS:
 /addplan id|name|price|days|quotaMB|fileLimit
 /setprice PLAN_ID PRICE
 /disableplan PLAN_ID
 /enableplan PLAN_ID
 /delplan PLAN_ID
 /block USER_ID
 /unblock USER_ID
 /grant USER_ID DAYS

Example plan:
 /addplan starter|Starter|49|30|500|20

FIREBASE:
1. Enable Realtime Database and Storage.
2. Create a service account JSON in Firebase project settings.
3. Keep that JSON private; put it only in Railway environment variables.
4. Suggested client rules: deny all public client access. Admin SDK on the server bypasses rules.

Realtime Database rules:
{
  "rules": { ".read": false, ".write": false }
}

Storage rules:
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /{allPaths=**} {
      allow read, write: if false;
    }
  }
}

PAYX:
Create/verify a PayX merchant account, then set the LIVE API key in Railway.
The key is sent only in the server-side X-PayX-Key header.
Start with a test/sandbox key and low-value test before accepting real payments.

"Owner unlimited" means no app-level expiry/quota for the owner. Firebase, Telegram and hosting
provider quotas/billing still apply. It does not mean physically unlimited/free storage.
