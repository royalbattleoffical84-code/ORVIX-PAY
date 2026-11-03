import os, re, json, time, html, logging, uuid
from datetime import datetime, timezone
from io import BytesIO
import requests, telebot, firebase_admin
from telebot import types
from firebase_admin import credentials, db, storage

# Secure storage + subscription bot. Uploaded scripts are stored, NOT executed.
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("orvix-hosting-bot")

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
OWNER_ID = int(os.getenv("OWNER_ID", str(ADMIN_ID)))
DB_URL = os.environ["FIREBASE_DATABASE_URL"]
BUCKET_NAME = os.environ["FIREBASE_STORAGE_BUCKET"]
SERVICE_JSON = os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"]
PAYX_KEY = os.environ["PAYX_API_KEY"]
PAYX_URL = os.getenv("PAYX_BASE_URL", "https://payx-q1nn.onrender.com").rstrip("/")
MAX_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
ALLOWED = {".py", ".js", ".zip", ".txt", ".json"}

cred = credentials.Certificate(json.loads(SERVICE_JSON))
firebase_admin.initialize_app(cred, {"databaseURL": DB_URL, "storageBucket": BUCKET_NAME})
bucket = storage.bucket()
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Admin wizard state: all admin operations are available through buttons.
ADMIN_STATES = {}
ADMIN_CANCEL = "❌ Cancel"
ADMIN_BACK = "⬅️ Admin Panel"

def ts(): return int(time.time() * 1000)
def owner(uid): return int(uid) == OWNER_ID
def admin(uid): return int(uid) in (ADMIN_ID, OWNER_ID)
def ref(path): return db.reference(path)
def user(uid, tg=None):
    r = ref(f"users/{uid}")
    u = r.get() or {}
    if not u:
        u = {"telegramId": int(uid), "name": tg.first_name if tg else "User",
             "username": tg.username if tg else None, "createdAt": ts(),
             "blocked": False, "subscription": {"planId": "free", "expiresAt": 0},
             "usedBytes": 0, "fileCount": 0}
        r.set(u)
    elif tg:
        r.update({"name": tg.first_name, "username": tg.username, "lastSeenAt": ts()})
    return r.get() or u

def plan_for(uid):
    if owner(uid):
        return {"id":"owner","name":"Owner Lifetime","quotaMb":0,"fileLimit":0}
    u = user(uid); s = u.get("subscription") or {}
    if s.get("planId") != "free" and int(s.get("expiresAt") or 0) > ts():
        return ref("plans/" + s["planId"]).get() or ref("plans/free").get()
    return ref("plans/free").get() or {"name":"Free","quotaMb":50,"fileLimit":5}

def payx(method, path, body=None):
    r = requests.request(method, PAYX_URL + path,
        headers={"X-PayX-Key": PAYX_KEY, "Content-Type":"application/json"},
        json=body, timeout=20)
    try: d = r.json()
    except ValueError: d = {}
    if not r.ok or d.get("success") is False:
        raise RuntimeError((d.get("error") or {}).get("message") or d.get("message") or f"PayX HTTP {r.status_code}")
    return d

def kb(uid):
    k = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    k.add("📤 Upload File", "📁 My Files")
    k.add("💎 Plans", "👤 My Account")
    k.add("🆘 Support")
    if admin(uid): k.add("👑 Admin Panel")
    return k

def account(uid):
    u=user(uid); p=plan_for(uid); s=u.get("subscription") or {}
    exp = "Lifetime (Owner)" if owner(uid) else (
        datetime.fromtimestamp(int(s.get("expiresAt",0))/1000, timezone.utc).strftime("%d %b %Y UTC")
        if int(s.get("expiresAt") or 0)>ts() else "Free / expired")
    return (f"👤 <b>Account</b>\nID: <code>{uid}</code>\n"
            f"Plan: <b>{html.escape(str(p.get('name','Free')))}</b>\n"
            f"Expiry: {exp}\nStorage: {u.get('usedBytes',0)/1048576:.2f} MB\n"
            f"Files: {u.get('fileCount',0)}")

def admin_only(m):
    if not admin(m.from_user.id):
        bot.reply_to(m, "⛔ Access denied."); return False
    return True

@bot.message_handler(commands=["start","help"])
def start(m):
    u=user(m.from_user.id,m.from_user)
    if u.get("blocked") and not admin(m.from_user.id):
        bot.reply_to(m,"⛔ Account blocked."); return
    bot.send_message(m.chat.id,
        "👋 <b>ORVIX HOSTING BOT</b>\nFirebase file storage + PayX subscriptions.\n"
        "<b>Uploaded scripts are stored only; this bot does not execute them.</b>",
        reply_markup=kb(m.from_user.id))

@bot.message_handler(func=lambda m: bool(m.from_user and m.from_user.id in ADMIN_STATES), content_types=["text"])
def admin_wizard(m):
    uid=m.from_user.id
    if not admin(uid):
        ADMIN_STATES.pop(uid,None); return
    text_in=(m.text or "").strip()
    if text_in==ADMIN_CANCEL:
        ADMIN_STATES.pop(uid,None); bot.send_message(m.chat.id,"Cancelled.",reply_markup=kb(uid)); return
    if text_in==ADMIN_BACK:
        ADMIN_STATES.pop(uid,None); admin_panel(m); bot.send_message(m.chat.id,"Admin menu",reply_markup=kb(uid)); return
    st=ADMIN_STATES.get(uid)
    if not st: return
    action=st["action"]
    try:
        if action=="addplan":
            prompts=["Plan name (example: Starter)","Price in INR (number only)","Duration in days","Storage quota in MB","Maximum file count"]
            st["values"].append(text_in)
            if len(st["values"])<6:
                bot.send_message(m.chat.id,prompts[len(st["values"])-1]); return
            pid,name,price,days,quota,count=st["values"]
            if not re.fullmatch(r"[a-z0-9_-]{2,24}",pid) or pid=="free": raise ValueError("Plan ID must be 2–24 lowercase letters/numbers/_/-")
            p={"id":pid,"name":name[:40],"price":int(price),"days":int(days),"quotaMb":int(quota),"fileLimit":int(count),"enabled":True,"updatedAt":ts()}
            if min(p["price"],p["days"],p["quotaMb"],p["fileLimit"])<1: raise ValueError("Price, days, quota and file limit must be positive.")
            ref("plans/"+pid).set(p)
            ADMIN_STATES.pop(uid,None); bot.send_message(m.chat.id,f"✅ Plan <b>{html.escape(name)}</b> added.",reply_markup=kb(uid)); return
        if action=="setprice":
            price=int(text_in)
            if price<1: raise ValueError("Price must be greater than zero.")
            pid=st["values"][0]; ref(f"plans/{pid}/price").set(price)
            ADMIN_STATES.pop(uid,None); bot.send_message(m.chat.id,f"✅ {pid} price updated to ₹{price}.",reply_markup=kb(uid)); return
        if action in ("block","unblock","grant"):
            if st["step"]==0:
                if not text_in.isdigit(): raise ValueError("Send a numeric Telegram User ID.")
                target=int(text_in)
                if target in (ADMIN_ID,OWNER_ID): raise ValueError("Cannot change admin/owner access.")
                st["values"]=[target]; st["step"]=1
                if action=="grant":
                    bot.send_message(m.chat.id,"How many days? (1–3650)"); return
                ref(f"users/{target}/blocked").set(action=="block")
                ADMIN_STATES.pop(uid,None); bot.send_message(m.chat.id,"✅ User updated.",reply_markup=kb(uid)); return
            days=int(text_in)
            if not 1<=days<=3650: raise ValueError("Days must be between 1 and 3650.")
            target=st["values"][0]; u=user(target); sub=u.get("subscription") or {}
            expiry=max(ts(),int(sub.get("expiresAt") or 0))+days*86400000
            ref(f"users/{target}/subscription").set({"planId":"admin_grant","startedAt":ts(),"expiresAt":expiry,"grantedBy":str(uid)})
            ref("plans/admin_grant").set({"id":"admin_grant","name":"Admin Grant","price":0,"days":days,"quotaMb":1024,"fileLimit":100,"enabled":True})
            ADMIN_STATES.pop(uid,None); bot.send_message(m.chat.id,"🎁 Access granted.",reply_markup=kb(uid)); return
    except Exception as e:
        bot.send_message(m.chat.id,"❌ "+html.escape(str(e))+"\\nTry again or tap Cancel.")
        return

@bot.message_handler(func=lambda m:m.text=="👤 My Account")
def my_account(m): bot.reply_to(m,account(m.from_user.id))

@bot.message_handler(func=lambda m:m.text=="💎 Plans")
def plans(m):
    ps=ref("plans").get() or {}; rows=[]; markup=types.InlineKeyboardMarkup()
    for pid,p in ps.items():
        if not p or p.get("enabled") is False: continue
        rows.append(f"• <b>{html.escape(p.get('name',pid))}</b> — ₹{p.get('price',0)} / {p.get('days',0)} days · {p.get('quotaMb',0)} MB · {p.get('fileLimit',0)} files")
        if pid!="free":
            markup.add(types.InlineKeyboardButton(f"Buy {p.get('name')} ₹{p.get('price')}",callback_data="buy:"+pid))
    bot.send_message(m.chat.id,"💎 <b>Plans</b>\n\n"+"\n".join(rows),reply_markup=markup)

@bot.message_handler(func=lambda m:m.text=="📤 Upload File")
def upload_prompt(m):
    bot.reply_to(m,f"Send a .py, .js, .zip, .txt or .json file. Max {MAX_BYTES//1048576} MB. Files are stored, not executed.")

@bot.message_handler(content_types=["document"])
def upload(m):
    uid=m.from_user.id; u=user(uid,m.from_user); d=m.document
    if u.get("blocked") and not admin(uid): bot.reply_to(m,"⛔ Account blocked."); return
    name=os.path.basename(d.file_name or "file")
    ext=os.path.splitext(name)[1].lower()
    if ext not in ALLOWED: bot.reply_to(m,"❌ File type not allowed."); return
    if int(d.file_size or 0)>MAX_BYTES: bot.reply_to(m,"❌ File too large."); return
    p=plan_for(uid)
    if not owner(uid):
        if int(u.get("fileCount",0))>=int(p.get("fileLimit",5)):
            bot.reply_to(m,"❌ File limit reached. Upgrade your plan."); return
        if int(u.get("usedBytes",0))+int(d.file_size or 0)>int(p.get("quotaMb",50))*1048576:
            bot.reply_to(m,"❌ Storage quota reached. Upgrade or delete files."); return
    try:
        fi=bot.get_file(d.file_id); data=bot.download_file(fi.file_path)
        if len(data)>MAX_BYTES: raise ValueError("Upload exceeds size limit")
        safe=re.sub(r"[^A-Za-z0-9._-]","_",name)[:80]
        path=f"users/{uid}/{ts()}_{safe}"
        blob=bucket.blob(path)
        blob.metadata={"telegram_user_id":str(uid),"original_name":safe,"uploaded_at":str(ts())}
        blob.upload_from_string(data,content_type=d.mime_type or "application/octet-stream")
        fid=ref(f"files/{uid}").push().key
        ref(f"files/{uid}/{fid}").set({"id":fid,"name":safe,"storagePath":path,"sizeBytes":len(data),"createdAt":ts()})
        ref(f"users/{uid}").update({"usedBytes":int(u.get("usedBytes",0))+len(data),"fileCount":int(u.get("fileCount",0))+1})
        bot.reply_to(m,f"✅ Saved to Firebase Storage: <b>{html.escape(safe)}</b>")
    except Exception as e:
        log.exception("upload error"); bot.reply_to(m,"❌ Upload failed: "+html.escape(str(e)[:160]))

@bot.message_handler(func=lambda m:m.text=="📁 My Files")
def files(m):
    uid=m.from_user.id; items=ref(f"files/{uid}").get() or {}
    if not items: bot.reply_to(m,"No uploaded files."); return
    mk=types.InlineKeyboardMarkup(); lines=["📁 <b>Your files</b>"]
    for fid,x in list(items.items())[:25]:
        lines.append(f"• {html.escape(x.get('name','file'))} ({int(x.get('sizeBytes',0))/1024:.1f} KB)")
        mk.row(types.InlineKeyboardButton("⬇️ "+x.get("name","file")[:18],callback_data="get:"+fid),
               types.InlineKeyboardButton("🗑 Delete",callback_data="del:"+fid))
    bot.send_message(m.chat.id,"\n".join(lines),reply_markup=mk)

@bot.message_handler(func=lambda m:m.text=="🆘 Support")
def support(m): bot.reply_to(m,os.getenv("SUPPORT_TEXT","Contact the owner for support."))

@bot.message_handler(func=lambda m:m.text=="👑 Admin Panel")
def admin_panel(m):
    if not admin(m.from_user.id): return
    mk=types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton("📊 Overview",callback_data="adm:stats"),
           types.InlineKeyboardButton("💎 Manage Plans",callback_data="adm:plans"))
    mk.row(types.InlineKeyboardButton("➕ Add Plan",callback_data="adm:add"),
           types.InlineKeyboardButton("💰 Set Plan Price",callback_data="adm:setprice"))
    mk.row(types.InlineKeyboardButton("⏸ Disable Plan",callback_data="adm:disable"),
           types.InlineKeyboardButton("▶️ Enable Plan",callback_data="adm:enable"))
    mk.row(types.InlineKeyboardButton("🗑 Delete Plan",callback_data="adm:delete"))
    mk.row(types.InlineKeyboardButton("👥 Users",callback_data="adm:users"),
           types.InlineKeyboardButton("💳 Orders",callback_data="adm:orders"))
    mk.row(types.InlineKeyboardButton("🚫 Block User",callback_data="adm:block"),
           types.InlineKeyboardButton("✅ Unblock User",callback_data="adm:unblock"))
    mk.row(types.InlineKeyboardButton("🎁 Grant Access",callback_data="adm:grant"))
    bot.send_message(m.chat.id,"👑 <b>ORVIX HOSTING BOT — Admin Panel</b>\\nChoose an action:",reply_markup=mk)

@bot.callback_query_handler(func=lambda c:True)
def callbacks(c):
    uid=c.from_user.id; data=c.data or ""
    try:
        if data.startswith("adm:"):
            if not admin(uid): bot.answer_callback_query(c.id,"Denied",show_alert=True); return
            action=data.split(":",1)[1]
            if action=="add":
                ADMIN_STATES[uid]={"action":"addplan","step":0,"values":[]}
                bot.send_message(c.message.chat.id,"➕ <b>Add Plan Wizard</b>\\nSend Plan ID (example: starter).",reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(ADMIN_CANCEL,ADMIN_BACK))
            elif action in ("setprice","disable","enable","delete"):
                ps=ref("plans").get() or {}
                mk=types.InlineKeyboardMarkup()
                for pid,p in ps.items():
                    if pid=="free": continue
                    mk.add(types.InlineKeyboardButton(f"{p.get('name',pid)} ({pid})",callback_data=f"admop:{action}:{pid}"))
                bot.send_message(c.message.chat.id,"Select a plan:",reply_markup=mk)
            elif action in ("block","unblock"):
                ADMIN_STATES[uid]={"action":action,"step":0,"values":[]}
                bot.send_message(c.message.chat.id,"Send the Telegram numeric User ID.",reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(ADMIN_CANCEL,ADMIN_BACK))
            elif action=="grant":
                ADMIN_STATES[uid]={"action":"grant","step":0,"values":[]}
                bot.send_message(c.message.chat.id,"Send the Telegram numeric User ID.",reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(ADMIN_CANCEL,ADMIN_BACK))
            elif action=="stats":
                us=ref("users").get() or {}; fs=ref("files").get() or {}; os_=ref("paymentOrders").get() or {}
                bot.send_message(c.message.chat.id,f"📊 Users: {len(us)}\nFiles: {sum(len(x or {}) for x in fs.values())}\nOrders: {len(os_)}")
            elif action=="plans":
                ps=ref("plans").get() or {}
                bot.send_message(c.message.chat.id,"\n".join(f"{k}: ₹{v.get('price')} / {v.get('days')} days" for k,v in ps.items())+
                    "\n\n/addplan id|name|price|days|quotaMB|fileLimit\n/setprice ID PRICE\n/disableplan ID\n/enableplan ID")
            elif action=="users":
                us=ref("users").get() or {}
                bot.send_message(c.message.chat.id,"\n".join(f"{k} · {html.escape(str(v.get('name','User')))} · blocked={v.get('blocked',False)}" for k,v in list(us.items())[:40]) or "No users")
            elif action=="orders":
                os_=ref("paymentOrders").get() or {}
                bot.send_message(c.message.chat.id,"\n".join(f"{k} · user {v.get('uid')} · ₹{v.get('amount')} · {v.get('status')}" for k,v in list(os_.items())[-30:]) or "No orders")
            bot.answer_callback_query(c.id); return

        if data.startswith("admop:"):
            if not admin(uid): bot.answer_callback_query(c.id,"Denied",show_alert=True); return
            _,action,pid=data.split(":",2)
            p=ref("plans/"+pid).get()
            if not p or pid=="free": raise ValueError("Plan unavailable")
            if action=="setprice":
                ADMIN_STATES[uid]={"action":"setprice","step":0,"values":[pid]}
                bot.send_message(c.message.chat.id,f"Current price: ₹{p.get('price',0)}\\nSend new price in INR (number only).",reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(ADMIN_CANCEL,ADMIN_BACK))
            elif action=="disable":
                ref(f"plans/{pid}/enabled").set(False); bot.send_message(c.message.chat.id,"⏸ Plan disabled.")
            elif action=="enable":
                ref(f"plans/{pid}/enabled").set(True); bot.send_message(c.message.chat.id,"▶️ Plan enabled.")
            elif action=="delete":
                ref("plans/"+pid).delete(); bot.send_message(c.message.chat.id,"🗑 Plan deleted.")
            bot.answer_callback_query(c.id); return

        if data.startswith("buy:"):
            pid=data.split(":",1)[1]; p=ref("plans/"+pid).get()
            if not p or p.get("enabled") is False or pid=="free": raise ValueError("Plan unavailable")
            if owner(uid): raise ValueError("Owner already has lifetime access")
            amount=int(p["price"]); reference=f"DKH-{uid}-{ts()}"
            result=payx("POST","/api/v1/orders",{"amount":amount,"reference":reference,"note":f"ORVIX HOSTING BOT {p['name']} plan"})
            o=result.get("order") or {}; oid=o.get("id"); checkout=o.get("checkoutUrl")
            if not oid or not checkout or int(o.get("amount",-1))!=amount: raise ValueError("PayX order response mismatch")
            ref("paymentOrders/"+oid).set({"uid":uid,"planId":pid,"amount":amount,"reference":reference,"status":o.get("status","created"),"createdAt":ts()})
            mk=types.InlineKeyboardMarkup()
            mk.add(types.InlineKeyboardButton("💳 Pay with PayX",url=checkout))
            mk.add(types.InlineKeyboardButton("🔄 Verify payment",callback_data="verify:"+oid))
            bot.send_message(c.message.chat.id,f"Plan: {p['name']}\nAmount: ₹{amount}\nPay, then tap Verify.",reply_markup=mk)
            bot.answer_callback_query(c.id); return

        if data.startswith("verify:"):
            oid=data.split(":",1)[1]; rec=ref("paymentOrders/"+oid).get()
            if not rec or int(rec.get("uid",-1))!=uid: raise ValueError("Order not found")
            result=payx("GET",f"/api/v1/orders/{oid}"); o=result.get("order") or {}
            if o.get("reference")!=rec["reference"] or int(o.get("amount",-1))!=int(rec["amount"]):
                raise ValueError("Payment reference/amount mismatch")
            status=str(o.get("status","")).lower(); ref(f"paymentOrders/{oid}/status").set(status)
            if status!="success":
                bot.answer_callback_query(c.id,"Payment status: "+status,show_alert=True); return
            # Transaction prevents double extension from repeated verify taps.
            claim = uuid.uuid4().hex
            tx = ref("processedPayments/"+oid).transaction(lambda old: claim if old is None else old)
            if tx == claim:
                p=ref("plans/"+rec["planId"]).get()
                if not p: raise ValueError("Plan missing; contact admin")
                u=user(uid); s=u.get("subscription") or {}
                expiry=max(ts(),int(s.get("expiresAt") or 0))+int(p["days"])*86400000
                ref(f"users/{uid}/subscription").set({"planId":rec["planId"],"startedAt":ts(),"expiresAt":expiry,"paymentOrderId":oid})
            bot.answer_callback_query(c.id,"Payment verified; plan activated.",show_alert=True)
            bot.send_message(c.message.chat.id,account(uid)); return

        if data.startswith(("get:","del:")):
            action,fid=data.split(":",1); item=ref(f"files/{uid}/{fid}").get()
            if not item: raise ValueError("File not found")
            blob=bucket.blob(item["storagePath"])
            if action=="get":
                bot.send_document(c.message.chat.id,(item["name"],BytesIO(blob.download_as_bytes())))
                bot.answer_callback_query(c.id,"Sent")
            else:
                blob.delete(); ref(f"files/{uid}/{fid}").delete(); u=user(uid)
                ref(f"users/{uid}").update({"usedBytes":max(0,int(u.get("usedBytes",0))-int(item.get("sizeBytes",0))),
                    "fileCount":max(0,int(u.get("fileCount",0))-1)})
                bot.answer_callback_query(c.id,"Deleted")
                bot.send_message(c.message.chat.id,"🗑 Deleted from Firebase Storage")
    except Exception as e:
        log.exception("callback error")
        try: bot.answer_callback_query(c.id,"Failed: "+str(e)[:100],show_alert=True)
        except Exception: pass

def bootstrap():
    if not ref("plans/free").get():
        ref("plans/free").set({"id":"free","name":"Free","price":0,"days":0,"quotaMb":50,"fileLimit":5,"enabled":True})
    log.info("ORVIX HOSTING BOT started; owner=%s",OWNER_ID)

if __name__=="__main__":
    bootstrap()
    bot.infinity_polling(skip_pending=True,timeout=30,long_polling_timeout=30)
