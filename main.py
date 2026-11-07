# -*- coding: utf-8 -*-
import os
import json
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# استدعاء محرك وحزم المشروع المحلية
import html
import time
import login_engine
from Pb2 import DEcwHisPErMsG_pb2
from xC4 import AutH_Chat, xSEndMsgsQ, DeCode_PackEt, ExiT, Emote_k
from squad_bot import SquadBot
import admin
from app_2 import build_ob55_online_auth, create_auth_token_chat, JoinSq_original, MahirAccepted

# إعداد السجلات
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# توكن تليجرام المحدد
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8714651372:AAFC3SeI0S1SQX4icfzWe6zB9UGihmAqfBI")
if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("حط توكن البوت في متغير البيئة TELEGRAM_BOT_TOKEN")

# مجلد تخزين حسابات المستخدمين (كل مستخدم له ملف مستقل)
ACCOUNTS_DIR = "user_accounts"
os.makedirs(ACCOUNTS_DIR, exist_ok=True)

# حالات محادثة تسجيل الدخول
UID, PASSWORD = range(2)

def get_user_file_path(telegram_id):
    """إرجاع مسار الملف الخاص بكل مستخدم بناءً على الآيدي الخاص به في التليجرام"""
    return os.path.join(ACCOUNTS_DIR, f"user_{telegram_id}.json")

def save_account_to_file(telegram_id, uid, password, region="ME", nickname=""):
    """حفظ بيانات حساب المستخدم في ملف JSON منفصل خاص به فقط"""
    file_path = get_user_file_path(telegram_id)
    data = {
        "telegram_id": telegram_id,
        "uid": uid,
        "password": password,
        "region": region,
        "nickname": nickname
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_account_from_file(telegram_id):
    """قراءة بيانات الحساب من ملف المستخدم الخاص إذا كان موجوداً"""
    file_path = get_user_file_path(telegram_id)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

# ═══════════════════════════ خطوات تسجيل الدخول ═══════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    
    saved_acc = load_account_from_file(telegram_id)
    if saved_acc:
        await update.message.reply_text(
            f"✅ **أنت مسجل دخول مسبقاً بحسابك المحفوظ في ملفك الخاص!**\n\n"
            f"🆔 **الـ UID:** `{saved_acc['uid']}`\n"
            f"👤 **الاسم:** `{saved_acc.get('nickname', 'غير محدد')}`\n\n"
            f"يمكنك استخدام الأمر مباشرة:\n"
            f"`/music <كود_الفريق> <اسم الأغنية>`",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 **أهلاً بك في بوت فري فاير!**\n\n"
        "🔒 سيتم إنشاء ملف خاص وآمن لحسابك لتخزين بياناتك.\n"
        "الرجاء إرسال **UID** حساب الضيف الخاص بك:",
        parse_mode='Markdown'
    )
    return UID

async def receive_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.text.strip()
    if not uid.isdigit():
        await update.message.reply_text("❌ الـ UID غير صالح. يرجى إرسال أرقام صحيحة فقط:")
        return UID
        
    context.user_data['temp_uid'] = uid
    await update.message.reply_text("🔑 ممتاز. الآن أرسل **كلمة المرور (Password)** الخاصة بالحساب:", parse_mode='Markdown')
    return PASSWORD

async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = context.user_data.get('temp_uid')
    password = update.message.text.strip()
    telegram_id = update.effective_user.id
    
    msg = await update.message.reply_text("🔄 جاري التحقق من البيانات وتسجيل الدخول عبر `login_engine`...", parse_mode='Markdown')

    try:
        # استخدام محرك تسجيل الدخول المحلي
        result = await login_engine.do_login(uid, password, "ME")
        
        if result:
            nickname = result.get("account_name", f"Player_{uid[-4:]}")
            region = result.get("region", "ME")
            
            # حفظ الحساب في ملف منفصل خاص بهذا المستخدم فقط
            save_account_to_file(telegram_id, uid, password, region, nickname)
            
            await msg.edit_text(
                f"🎉 **تم تسجيل الدخول بنجاح وحفظ حسابك في ملفك الخاص!**\n\n"
                f"👤 **الاسم:** `{nickname}`\n"
                f"🆔 **الـ UID:** `{uid}`\n"
                f"🌍 **المنطقة:** `{region}`\n\n"
                f"🎵 يمكنك الآن استخدام أمر الموسيقى:\n"
                f"`/music <كود_الفريق> <اسم الأغنية>`",
                parse_mode='Markdown'
            )
        else:
            await msg.edit_text(
                "❌ **فشل تسجيل الدخول!**\n"
                "تأكد من صحة الـ UID وكلمة المرور، ثم أرسل `/start` للمحاولة مجدداً.",
                parse_mode='Markdown'
            )
    except Exception as e:
        await msg.edit_text(f"❌ حدث خطأ أثناء الاتصال: {str(e)}")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END

# ═══════════════════════════ بوت الفريق: موسيقى + أوامر داخل اللعبة ═══════════════════════════
squad_bots = {}            # telegram_id -> SquadBot
AUTO_LEAVE_SECONDS = 1800  # يطلع من الفريق بعد 30 دقيقة (إلا في وضع /online)

def _drop_bot(tid, bot):
    if squad_bots.get(tid) is bot:
        squad_bots.pop(tid, None)

async def _new_bot(tid, saved_acc):
    """يسجل دخول ويفتح اتصالات اللعبة. يرجع (bot, None) أو (None, رسالة_خطأ)"""
    old = squad_bots.pop(tid, None)
    if old:
        await old.close()
    if admin.at_capacity():
        return None, "⚠️ البوت عليه ضغط عالي حالياً، جرب بعد شوي."
    login = await login_engine.do_login(saved_acc["uid"], saved_acc["password"], saved_acc.get("region", "ME"))
    if not login:
        return None, "❌ فشل تسجيل الدخول، تأكد من بيانات الحساب."
    bot = SquadBot(login, on_close=lambda b: _drop_bot(tid, b), on_joined=admin.record_team_join)
    try:
        await bot.connect()
    except Exception as ex:
        await bot.close()
        return None, f"❌ تعذر الاتصال بسيرفر اللعبة: {ex}"
    squad_bots[tid] = bot
    return bot, None

async def _auto_leave(tid, bot):
    await asyncio.sleep(AUTO_LEAVE_SECONDS)
    if squad_bots.get(tid) is bot and not bot.persistent:
        await bot.close()

async def music_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/music <كود_الفريق> ← يدخل الفريق ويرسل الأوامر، واللاعبين يستخدمونها من داخل اللعبة"""
    tid = update.effective_user.id
    saved_acc = load_account_from_file(tid)
    if not saved_acc:
        await update.message.reply_text("⚠️ ما عندك حساب محفوظ، أرسل /start أول.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ الصيغة: /music <كود_الفريق>\nمثال: /music 5592884")
        return
    team_code = context.args[0]
    query = " ".join(context.args[1:]).strip()
    msg = await update.message.reply_text(f"🔄 جاري الانضمام للفريق {team_code} ...")
    try:
        bot, err = await _new_bot(tid, saved_acc)
        if err:
            await msg.edit_text(err)
            return
        if not await bot.join(team_code):
            await bot.close()
            await msg.edit_text("❌ ما قدرت أنضم للفريق. تأكد من الكود وإن الفريق مفتوح.")
            return
        asyncio.create_task(_auto_leave(tid, bot))
        await msg.edit_text(
            f"✅ انضممت للفريق {team_code} وأرسلت الأوامر في الشات.\n"
            "اكتب الأوامر من داخل اللعبة في شات الفريق:\n"
            "!play [رابط/اسم] ، !stop ، !resume ، !dance ، !em ، !help")
        if query:
            await asyncio.sleep(3)
            await bot.handle_command("!play " + query)
    except Exception as ex:
        await msg.edit_text(f"❌ خطأ: {ex}")

async def online_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/online ← البوت يبقى أونلاين ويقبل دعوات الفريق"""
    tid = update.effective_user.id
    saved_acc = load_account_from_file(tid)
    if not saved_acc:
        await update.message.reply_text("⚠️ ما عندك حساب محفوظ، أرسل /start أول.")
        return
    msg = await update.message.reply_text("🔄 جاري تشغيل البوت ...")
    bot, err = await _new_bot(tid, saved_acc)
    if err:
        await msg.edit_text(err)
        return
    bot.persistent = True
    await msg.edit_text(f"✅ البوت أونلاين (UID: {bot.uid}).\nادعوه لفريقك من داخل اللعبة وبيقبل الدعوة، واكتب الأوامر في شات الفريق.\nللإيقاف: /offline")

async def offline_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = squad_bots.pop(update.effective_user.id, None)
    if bot:
        await bot.close()
    await update.message.reply_text("⏹ تم إيقاف البوت." if bot else "البوت مو شغال.")

async def _forward_command(update, text):
    bot = squad_bots.get(update.effective_user.id)
    if not bot or not bot.in_team:
        await update.message.reply_text("⚠️ البوت مو في فريق. استخدم أول: /music <كود_الفريق>")
        return
    await bot.handle_command(text)
    await update.message.reply_text("✅ تم.")

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = " ".join(context.args).strip()
    if not q:
        await update.message.reply_text("❌ الصيغة: /play [رابط أو اسم أغنية]")
        return
    await _forward_command(update, "!play " + q)

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _forward_command(update, "!resume")


# ═══════════════════════════ أمر الرقص /em ═══════════════════════════
EMOTE_DELAY = 4.0          # ثواني بين كل رقصة والثانية
active_em_tasks = {}       # telegram_id -> asyncio.Task

def load_all_emote_ids():
    """يجمع كل أيدي الرقصات من emotes.json و singele_emote.json بدون تكرار"""
    ids, seen = [], set()
    base = os.path.dirname(os.path.abspath(__file__))
    for name in ("emotes.json", "singele_emote.json"):
        try:
            with open(os.path.join(base, name), "r", encoding="utf-8") as f:
                for item in json.load(f):
                    eid = int(item["Id"])
                    if eid not in seen:
                        seen.add(eid)
                        ids.append(eid)
        except Exception as e:
            logging.warning("تعذر قراءة %s: %s", name, e)
    return ids

def _walk_ints(o, out):
    """يمشي على الحزمة المفكوكة ويجمع كل الأرقام"""
    if isinstance(o, dict):
        for v in o.values():
            _walk_ints(v, out)
    elif isinstance(o, list):
        for v in o:
            _walk_ints(v, out)
    elif isinstance(o, int) and not isinstance(o, bool):
        out.append(o)

def _looks_like_uid(n):
    # أيدي لاعب: 9-11 خانة، ونستبعد التوقيتات (unix time) وأيديات الرقصات
    if not (100_000_000 <= n <= 99_999_999_999):
        return False
    if 1_500_000_000 <= n <= 2_100_000_000:
        return False
    if 900_000_000 <= n <= 910_000_000:
        return False
    return True

async def _collect_squad(reader, timeout=7):
    """يسمع لردود السيرفر بعد الانضمام ويرجع (صاحب الفريق, كود الشات, مرشحين أيديات الأعضاء)"""
    owner, chat_code, cands = None, None, {}
    end_t = time.time() + timeout
    while time.time() < end_t:
        try:
            data = await asyncio.wait_for(reader.read(9999), timeout=1.5)
        except asyncio.TimeoutError:
            continue
        if not data:
            break
        hx = data.hex()
        if not hx.startswith("0500"):
            continue
        try:
            pj = json.loads(await DeCode_PackEt(hx[10:]))
        except Exception:
            continue
        if os.environ.get("DEBUG_SQUAD"):
            print("SQUAD PACKET:", json.dumps(pj, ensure_ascii=False)[:3000])
        try:
            d = pj["5"]["data"]
            if owner is None:
                owner = d["1"]["data"]
            if chat_code is None:
                chat_code = d["17"]["data"]
        except Exception:
            pass
        nums = []
        _walk_ints(pj, nums)
        for n in nums:
            if _looks_like_uid(n):
                cands[n] = cands.get(n, 0) + 1
    return owner, chat_code, cands

async def _run_em(update, msg, saved_acc, team_code, extra_uids):
    online_w = chat_w = None
    try:
        emotes = load_all_emote_ids()
        if not emotes:
            await msg.edit_text("❌ ما لقيت ملفات الرقصات (emotes.json / singele_emote.json).")
            return
        result = await login_engine.do_login(saved_acc["uid"], saved_acc["password"], saved_acc.get("region", "ME"))
        if not result:
            await msg.edit_text("❌ فشل تسجيل الدخول، تأكد من بيانات الحساب.")
            return
        key, iv = result["key"], result["iv"]
        ts = int(result["timestamp"])
        bot_uid = int(result["bot_uid"])
        region = result.get("region", "ME")

        chat_auth = create_auth_token_chat(bot_uid, result["token"], ts, key, iv)
        _, chat_w = await asyncio.open_connection(result["chat_ip"], int(result["chat_port"]))
        chat_w.write(bytes.fromhex(chat_auth)); await chat_w.drain()
        await asyncio.sleep(1)

        online_auth, _ = build_ob55_online_auth(bot_uid, result["token"], ts, key, iv)
        online_r, online_w = await asyncio.open_connection(result["online_ip"], int(result["online_port"]))
        online_w.write(online_auth); await online_w.drain()
        await asyncio.sleep(1)

        online_w.write(await JoinSq_original(team_code, key, iv)); await online_w.drain()
        owner_uid, chat_code, cands = await _collect_squad(online_r)
        if not owner_uid:
            await msg.edit_text("❌ ما قدرت أنضم للفريق. تأكد من الكود وإن الفريق مفتوح.")
            return
        await asyncio.sleep(1.0)

        if extra_uids:
            # المستخدم حدد لاعبين: يرقص هدول بس
            targets = [int(u) for u in extra_uids if int(u) != bot_uid]
        else:
            # الكل: صاحب الفريق أول، ثم باقي الأعضاء اللي انكشفوا من ردود السيرفر
            ordered = [int(owner_uid)] + [u for u, _ in sorted(cands.items(), key=lambda kv: -kv[1])]
            targets = []
            for t in ordered:
                if t != bot_uid and t not in targets:
                    targets.append(t)
            targets = targets[:6]
        if not targets:
            await msg.edit_text("❌ ما لقيت لاعبين أرقصهم.")
            return

        await msg.edit_text(f"💃 انضممت. بيرقص {len(targets)} لاعب بـ {len(emotes)} رقصة.\nلإيقافه: /stop")
        for n, eid in enumerate(emotes, 1):
            for t in targets:
                online_w.write(await Emote_k(t, eid, key, iv, region)); await online_w.drain()
                await asyncio.sleep(0.15)
            if n % 20 == 0:
                try:
                    await msg.edit_text(f"💃 {n}/{len(emotes)} رقصة ... (/stop للإيقاف)")
                except Exception:
                    pass
            await asyncio.sleep(EMOTE_DELAY)

        online_w.write(await ExiT(None, key, iv)); await online_w.drain()
        await msg.edit_text(f"✅ خلصت كل الرقصات ({len(emotes)}).")
    except asyncio.CancelledError:
        try:
            if online_w:
                online_w.write(await ExiT(None, key, iv)); await online_w.drain()
            await msg.edit_text("⏹ تم الإيقاف.")
        except Exception:
            pass
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {e}")
    finally:
        for w in (online_w, chat_w):
            if w:
                try:
                    w.close(); await w.wait_closed()
                except Exception:
                    pass
        active_em_tasks.pop(update.effective_user.id, None)

async def em_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    saved_acc = load_account_from_file(tid)
    if not saved_acc:
        await update.message.reply_text("⚠️ ما عندك حساب محفوظ، أرسل /start أول.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ الصيغة: /em <كود_الفريق> [uid1 uid2 ...]\nمثال: /em 5592884  ← يرقّص كل اللي بالفريق\nإذا تبي لاعبين محددين اكتب UID بعد الكود.")
        return
    if tid in active_em_tasks and not active_em_tasks[tid].done():
        await update.message.reply_text("⚠️ عندك رقص شغال، أرسل /stop أول.")
        return
    team_code = context.args[0]
    extra = [u for u in context.args[1:] if u.isdigit()]
    msg = await update.message.reply_text(f"🔄 جاري الانضمام للفريق {team_code} ...")
    active_em_tasks[tid] = asyncio.create_task(_run_em(update, msg, saved_acc, team_code, extra))


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    stopped = False
    t = active_em_tasks.get(tid)
    if t and not t.done():
        t.cancel()
        stopped = True
    bot = squad_bots.get(tid)
    if bot:
        if bot.persistent:
            await bot.leave()
        else:
            await bot.close()
        stopped = True
    await update.message.reply_text("⏹ تم الإيقاف والخروج من الفريق." if stopped else "ما في شي شغال.")


# ═══════════════════════════ ربط لوحة الأدمن ═══════════════════════════
async def _close_all_bots():
    """يوقف كل الجلسات (يستخدمها /off)"""
    for t in list(active_em_tasks.values()):
        if not t.done():
            t.cancel()
    for b in list(squad_bots.values()):
        try:
            await b.close()
        except Exception:
            pass
    squad_bots.clear()

admin.hooks["active"] = lambda: (len(squad_bots), sum(1 for b in squad_bots.values() if b.in_team))
admin.hooks["close_all"] = _close_all_bots

async def _post_init(application):
    await admin.start_web()

async def _post_shutdown(application):
    await admin.stop_web()


# ═══════════════════════════ تشغيل البوت ═══════════════════════════
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(_post_init).post_shutdown(_post_shutdown).build()
    admin.register(app)

    login_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_uid)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(login_handler)
    app.add_handler(CommandHandler("music", music_command))
    app.add_handler(CommandHandler("play", play_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("online", online_command))
    app.add_handler(CommandHandler("offline", offline_command))
    app.add_handler(CommandHandler("em", em_command))
    app.add_handler(CommandHandler("stop", stop_command))

    print("🚀 البوت يعمل الآن باستخدام التليجرام ومعزول بملفات المستخدمين...")
    app.run_polling()
