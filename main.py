# -*- coding: utf-8 -*-
# تحميل ملف .env (اختياري) قبل أي استيراد، عشان باقي الملفات تقرأ المتغيرات
import os as _os
_env_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".env")
if _os.path.exists(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
            if _k and _v:
                _os.environ.setdefault(_k, _v)      # متغيرات النظام (Railway) لها الأولوية
import os
import json
import asyncio
import random
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

# لا نطبع روابط تيليجرام في السجل (فيها التوكن)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
from app_2 import build_ob55_online_auth, create_auth_token_chat, JoinSq_original, MahirAccepted

# إعداد السجلات
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# توكن تليجرام المحدد
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("حط توكن البوت في متغير البيئة TELEGRAM_BOT_TOKEN")

from accounts import pool
import ui
import messages

# فيديو الترحيب الذي يظهر قبل قائمة الأوامر عند إرسال /start.
HELP_VIDEO_URL = "https://files.catbox.moe/qjktwg.mp4"
INFO_VIDEO_URLS = [
    "https://files.catbox.moe/63asg2.mp4",
    "https://files.catbox.moe/qjktwg.mp4",
    "https://files.catbox.moe/0ugm65.mp4",
    "https://files.catbox.moe/vfgl4q.mp4",
    "https://files.catbox.moe/ga1jcv.mp4",
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return

    # فيديو عشوائي ولوحة الأوامر في رسالة واحدة، مثل المثال المرسل.
    info_video_url = random.choice(INFO_VIDEO_URLS)
    try:
        await message.reply_video(
            video=info_video_url,
            caption=ui.menu(),
            parse_mode="HTML",
            supports_streaming=True,
        )
    except Exception as ex:
        logging.warning("تعذر إرسال فيديو /start: %s", ex)
        # إذا تعذّر إرسال الفيديو، نعرض لوحة الأوامر وحدها.
        await ui.reply(message, ui.menu())


# ═══════════════════════════ بوت الفريق: موسيقى + أوامر داخل اللعبة ═══════════════════════════
squad_bots = {}            # telegram_id -> SquadBot
AUTO_LEAVE_SECONDS = int(float(os.environ.get("AUTO_LEAVE_MINUTES", "30")) * 60)  # يطلع من الفريق بعد 30 دقيقة (إلا في وضع /online)

def _drop_bot(tid, bot):
    if squad_bots.get(tid) is bot:
        squad_bots.pop(tid, None)

WARM_BOTS = int(os.environ.get("WARM_BOTS", "2"))      # عدد البوتات الجاهزة (مسجلة دخول ومتصلة) للانضمام الفوري
WARM_MAX_AGE = int(float(os.environ.get("WARM_MAX_AGE_HOURS", "2")) * 3600)                              # نجدد البوت الجاهز كل ساعتين
warm_bots = []          # [(bot, وقت_الإنشاء)]
_warm_busy = False

def _warm_target():
    # نخلي دايماً حساب واحد على الأقل خارج الجاهزين
    return min(WARM_BOTS, max(0, len(pool.usable()) - 1))

LOGIN_GAP = float(os.environ.get("LOGIN_GAP_SECONDS", "3"))      # أقل فاصل بين تسجيلين دخول (يمنع الرفض بسبب السرعة)
_login_gate_lock = None
_last_login = [0.0]

async def _paced_login(acc):
    global _login_gate_lock
    if _login_gate_lock is None:
        _login_gate_lock = asyncio.Lock()
    async with _login_gate_lock:
        wait = LOGIN_GAP - (time.time() - _last_login[0])
        if wait > 0:
            await asyncio.sleep(wait)
        _last_login[0] = time.time()
    return await login_engine.do_login(acc["uid"], acc["password"], acc["region"])

async def _make_connected_bot():
    """ياخذ حساب عشوائي فاضي ويسجل دخول ويتصل. إذا فشل حساب يجرب غيره (لين 3). يرجع bot أو None.
    الحساب يرجع للمخزن لما يتسكر البوت"""
    failed = []
    _login_failed[0] = False
    try:
        for _ in range(3):
            acc = pool.acquire()
            if not acc:
                break
            try:
                login = await _paced_login(acc)
            except Exception as ex:
                logging.warning("login error for account ...%s: %s", acc["uid"][-4:], ex)
                login = None
            if not login:
                _login_failed[0] = True
                pool.report_fail(acc["uid"])
                failed.append(acc["uid"])          # نبقيه محجوز لين نخلص عشان ما نعيد اختياره
                continue
            pool.report_ok(acc["uid"])
            bot = SquadBot(login, on_close=lambda b, _u=acc["uid"]: pool.release(_u))
            try:
                await bot.connect()
            except Exception as ex:
                logging.warning("connect error ...%s: %s", acc["uid"][-4:], ex)
                _login_failed[0] = True
                await bot.close()
                failed.append(None)
                continue
            return bot
        return None
    finally:
        for u in failed:
            if u:
                pool.release(u)

def _prune_warm():
    now = time.time()
    for item in list(warm_bots):
        b, t = item
        if b.closed or now - t > WARM_MAX_AGE:
            warm_bots.remove(item)
            if not b.closed:
                asyncio.create_task(b.close())

def _take_warm():
    """يرجع بوت جاهز فوراً (أو None)"""
    _prune_warm()
    if warm_bots:
        return warm_bots.pop(0)[0]
    return None

async def _refill_warm():
    global _warm_busy
    if _warm_busy:
        return
    _warm_busy = True
    try:
        if not admin.cfg().get("enabled", True):
            return
        _prune_warm()
        while len(warm_bots) < _warm_target() and not admin.at_capacity():
            bot = await _make_connected_bot()
            if not bot:
                break
            warm_bots.append((bot, time.time()))
            logging.info("warm bot ready (%d/%d)", len(warm_bots), _warm_target())
    finally:
        _warm_busy = False

async def _warm_maintainer():
    await asyncio.sleep(5)
    while True:
        try:
            await _refill_warm()
        except Exception as ex:
            logging.warning("warm refill: %s", ex)
        await asyncio.sleep(60)

# ═══════════ إصلاح تلقائي لما تظهر رسالة "كل الحسابات مشغولة أو تعذر تسجيل الدخول" ═══════════
START_TIME = time.time()
RECOVER_MIN_GAP = 60            # أقل فاصل بين إصلاحين (ثواني)
RESTART_AFTER = 3               # بعد كم إصلاح في النافذة نعيد تشغيل المشروع كامل
RESTART_WINDOW = 600            # النافذة (ثواني)
RESTART_MIN_UPTIME = 900        # ما نعيد التشغيل إلا إذا المشروع شغال أكثر من 15 دقيقة (يمنع حلقة إعادة تشغيل)
_recover_times = []
_recovering = False
_login_failed = [False]
_APP = {"app": None}

async def _notify_owner(text):
    try:
        if _APP["app"]:
            await _APP["app"].bot.send_message(admin.OWNER_ID, text)
    except Exception as ex:
        logging.warning("notify owner failed: %s", ex)

async def _recover_pool(reason):
    """يعيد تسجيل دخول كل الحسابات من جديد. وإذا تكرر الفشل يعيد تشغيل المشروع كامل (Railway يشغله تلقائياً)"""
    global _recovering
    now = time.time()
    if _recovering or (_recover_times and now - _recover_times[-1] < RECOVER_MIN_GAP):
        return
    _recovering = True
    try:
        _recover_times.append(now)
        _recover_times[:] = [t for t in _recover_times if now - t <= RESTART_WINDOW]
        logging.warning("pool recovery #%d (%s)", len(_recover_times), reason)
        if (len(_recover_times) >= RESTART_AFTER and now - START_TIME > RESTART_MIN_UPTIME
                and not squad_bots and not active_em_tasks):
            await _notify_owner("🔄 الحسابات ما رجعت بعد عدة محاولات، جاري إعادة تشغيل المشروع تلقائياً ...")
            await asyncio.sleep(2)
            logging.warning("restarting process (auto)")
            os._exit(1)                         # Railway يرجّع المشروع تلقائياً
        # 1) نسكر البوتات الجاهزة القديمة
        for b, _ in list(warm_bots):
            try:
                await b.close()
            except Exception:
                pass
        warm_bots.clear()
        # 2) نصفّر حالة الحسابات ونعيد قراءتها
        pool.reload()
        pool.fails.clear()
        pool.cool_until.clear()
        pool.in_use = {str(b.uid) for b in squad_bots.values()}
        _login_failed[0] = False
        # 3) نسجل دخول من جديد
        await _refill_warm()
        logging.info("pool recovery done: %d usable, %d warm", len(pool.usable()), len(warm_bots))
    except Exception as ex:
        logging.warning("pool recovery failed: %s", ex)
    finally:
        _recovering = False

def _maybe_recover(reason):
    """نستدعيها لما نعرض خطأ الحسابات: نبدأ الإصلاح فقط لو السبب فشل تسجيل دخول (مو ضغط مستخدمين)"""
    stuck = _login_failed[0] or (pool.accounts and not pool.usable() and len(squad_bots) < len(pool.accounts))
    if stuck:
        asyncio.create_task(_recover_pool(reason))

async def _new_bot(tid):
    """يرجع بوت جاهز فوراً لو متوفر، وإلا ياخذ حساب فاضي ويسجل دخول. يرجع (bot, None) أو (None, رسالة_خطأ)"""
    old = squad_bots.pop(tid, None)
    if old:
        await old.close()
    if not pool.accounts:
        return None, "⚠️ ما في حسابات مضافة للبوت حالياً."
    if admin.at_capacity():
        return None, "⚠️ كل حسابات البوت مشغولة حالياً (ضغط عالي)، جرب بعد شوي."
    bot = _take_warm()
    if bot is None:
        bot = await _make_connected_bot()
        if bot is None:
            _maybe_recover("music login failed")
            return None, "❌ كل الحسابات مشغولة أو تعذر تسجيل الدخول، جرب مرة ثانية."
    uid_s = str(bot.uid)

    def _closed(b, _uid=uid_s):
        pool.release(_uid)
        _drop_bot(tid, b)

    bot.on_close = _closed
    bot.on_joined = admin.record_team_join
    squad_bots[tid] = bot
    asyncio.create_task(_refill_warm())        # نجهز بديل بالخلفية
    return bot, None

async def _auto_leave(tid, bot):
    await asyncio.sleep(AUTO_LEAVE_SECONDS)
    if squad_bots.get(tid) is bot and not bot.persistent:
        await bot.close()

async def music_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/music <كود_الفريق> ← يدخل الفريق ويرسل الأوامر، واللاعبين يستخدمونها من داخل اللعبة"""
    tid = update.effective_user.id
    if not context.args or not context.args[0].isdigit():
        await ui.reply(update.message, ui.usage("/music", "‹كود_الفريق› [أغنية]", "/music 5592884"))
        return
    team_code = context.args[0]
    query = " ".join(context.args[1:]).strip()
    msg = await ui.reply(update.message, ui.working("جاري الانضمام للفريق", team_code))
    try:
        bot, err = await _new_bot(tid)
        if err:
            await ui.edit(msg, ui.err(ui.clean(err)))
            return
        if not await bot.join(team_code):
            await bot.close()
            await ui.edit(msg, ui.err("ما قدرت أنضم للفريق", "تأكد من الكود وإن الفريق مفتوح"))
            return
        asyncio.create_task(_auto_leave(tid, bot))
        await ui.edit(msg, ui.ok("تم الانضمام", "البوت صار معك في الفريق",
                                 [("🏷", "الفريق", team_code), ("🤖", "الحساب", bot.name or bot.uid)],
                                 "اكتب !help في شات الفريق"))
        if query:
            await asyncio.sleep(3)
            await bot.handle_command("!play " + query)
    except Exception as ex:
        await ui.edit(msg, ui.err("حصل خطأ", str(ex)))

async def online_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/online ← البوت يبقى أونلاين ويقبل دعوات الفريق"""
    tid = update.effective_user.id
    msg = await ui.reply(update.message, ui.working("جاري تشغيل البوت"))
    bot, err = await _new_bot(tid)
    if err:
        await ui.edit(msg, ui.err(ui.clean(err)))
        return
    bot.persistent = True
    await ui.edit(msg, ui.ok("البوت أونلاين", "ادعُه لفريقك من داخل اللعبة وبيقبل الدعوة",
                             [("🤖", "الحساب", bot.name or bot.uid)], "للإيقاف: /offline"))

async def offline_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = squad_bots.pop(update.effective_user.id, None)
    if bot:
        await bot.close()
    await ui.reply(update.message, ui.stopped("البوت طلع من اللعبة") if bot else ui.err("البوت مو شغال"))

async def _forward_command(update, text):
    bot = squad_bots.get(update.effective_user.id)
    if not bot or not bot.in_team:
        await ui.reply(update.message, ui.err("البوت مو في فريق", "استخدم أول: /music ‹كود_الفريق›"))
        return
    await bot.handle_command(text)
    await ui.reply(update.message, ui.ok("تم", "نُفّذ الأمر"))

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = " ".join(context.args).strip()
    if not q:
        await ui.reply(update.message, ui.usage("/play", "‹رابط أو اسم أغنية›", "/play حدائق الكلمات"))
        return
    await _forward_command(update, "!play " + q)

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _forward_command(update, "!resume")


# ═══════════════════════════ أمر الرقص /em ═══════════════════════════
EMOTE_DELAY = float(os.environ.get("EMOTE_DELAY", "4.0"))          # ثواني بين كل رقصة والثانية
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

async def _run_em(update, msg, team_code, extra_uids):
    online_w = chat_w = None
    used_uid = None
    try:
        emotes = load_all_emote_ids()
        if not emotes:
            await ui.edit(msg, ui.err("ما لقيت ملفات الرقصات", "emotes.json / singele_emote.json"))
            return
        if not pool.accounts:
            await ui.edit(msg, ui.err("ما في حسابات مضافة للبوت حالياً"))
            return
        acc = pool.acquire()
        if not acc:
            await ui.edit(msg, ui.err("كل حسابات البوت مشغولة حالياً", "جرب بعد شوي"))
            return
        used_uid = acc["uid"]
        result = await login_engine.do_login(acc["uid"], acc["password"], acc["region"])
        if not result:
            pool.report_fail(used_uid)
            await ui.edit(msg, ui.err("تعذر تسجيل دخول حساب البوت", "جرب مرة ثانية"))
            return
        pool.report_ok(used_uid)
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
            await ui.edit(msg, ui.err("ما قدرت أنضم للفريق", "تأكد من الكود وإن الفريق مفتوح"))
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
            await ui.edit(msg, ui.err("ما لقيت لاعبين أرقصهم"))
            return

        await ui.edit(msg, ui.card("💃", "الرقص بدأ", "انضممت للفريق وبدأت الرقص",
                                   [("👥", "اللاعبين", len(targets)), ("🎞", "الرقصات", len(emotes))], "للإيقاف: /stop"))
        for n, eid in enumerate(emotes, 1):
            for t in targets:
                online_w.write(await Emote_k(t, eid, key, iv, region)); await online_w.drain()
                await asyncio.sleep(0.15)
            if n % 20 == 0:
                try:
                    await ui.edit(msg, ui.card("💃", "الرقص شغال", None,
                                                   [("🎞", "التقدم", f"{n}/{len(emotes)}")], "للإيقاف: /stop"))
                except Exception:
                    pass
            await asyncio.sleep(EMOTE_DELAY)

        online_w.write(await ExiT(None, key, iv)); await online_w.drain()
        await ui.edit(msg, ui.ok("خلصت", "انتهت كل الرقصات", [("🎞", "العدد", len(emotes))]))
    except asyncio.CancelledError:
        try:
            if online_w:
                online_w.write(await ExiT(None, key, iv)); await online_w.drain()
            await ui.edit(msg, ui.stopped("وقفت الرقص وطلعت من الفريق"))
        except Exception:
            pass
    except Exception as e:
        await ui.edit(msg, ui.err("حصل خطأ", str(e)))
    finally:
        for w in (online_w, chat_w):
            if w:
                try:
                    w.close(); await w.wait_closed()
                except Exception:
                    pass
        if used_uid:
            pool.release(used_uid)
        active_em_tasks.pop(update.effective_user.id, None)

async def em_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not context.args or not context.args[0].isdigit():
        await ui.reply(update.message, ui.usage("/em", "‹كود_الفريق› [uid …]", "/em 5592884"))
        return
    if tid in active_em_tasks and not active_em_tasks[tid].done():
        await ui.reply(update.message, ui.err("عندك رقص شغال", "أرسل /stop أول"))
        return
    team_code = context.args[0]
    extra = [u for u in context.args[1:] if u.isdigit()]
    msg = await ui.reply(update.message, ui.working("جاري الانضمام للفريق", team_code))
    active_em_tasks[tid] = asyncio.create_task(_run_em(update, msg, team_code, extra))


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if context.args and admin.is_admin(tid):
        await admin.cmd_disable(update, context)          # /stop music ← يوقف أمر محدد (أدمن)
        return
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
    await ui.reply(update.message, ui.stopped("البوت طلع من الفريق") if stopped else ui.err("ما في شي شغال"))


# ═══════════════════════════ تعديل رسائل اللعبة: /messeg و /change ═══════════════════════════
def _msg_preview(text, n=70):
    one = text.replace("\n", " ⏎ ")
    return one if len(one) <= n else one[:n] + "…"


async def _send_chunks(message, header, lines, limit=3500):
    """يرسل قائمة طويلة على دفعات (حد تيليجرام 4096 حرف)"""
    chunk = header
    for ln in lines:
        if len(chunk) + len(ln) + 1 > limit:
            await ui.reply(message, chunk)
            chunk = ""
        chunk += ("\n" if chunk else "") + ln
    if chunk:
        await ui.reply(message, chunk)


def _msg_detail(num):
    key, label, default, allowed = messages.info(num)
    cur = messages.text(key)
    vars_line = "  ".join("{" + a + "}" for a in allowed) or "ما فيها متغيرات"
    out = (f"╭─ ✏️ <b>رسالة رقم {num}</b>\n"
           f"│ {ui.esc(label)}\n│\n"
           f"│ <b>الحالي:</b>\n<pre>{ui.esc(cur)}</pre>")
    if messages.is_modified(key):
        out += f"\n│ <b>الأصلي:</b>\n<pre>{ui.esc(default)}</pre>"
    out += (f"\n│ 🔣 المتغيرات: <code>{ui.esc(vars_line)}</code>\n"
            f"╰─ <i>/change {num} ‹النص الجديد›  ·  /change {num} reset</i>")
    return out


@admin._admin_only
async def messeg_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/messeg ← كل رسائل اللعبة بأرقامها، و /messeg 5 ← تفاصيل رسالة"""
    if context.args and context.args[0].isdigit():
        num = int(context.args[0])
        if not messages.info(num):
            await ui.reply(update.message, ui.err("رقم غير موجود", f"الأرقام من 1 إلى {messages.count()}"))
            return
        await ui.reply(update.message, _msg_detail(num))
        return
    header = (f"╭─ 💬 <b>رسائل اللعبة</b>  ({messages.count()})\n"
              "│ ✏️ = معدّلة\n"
              "╰─ <i>/change ‹رقم› ‹نص›  ·  /messeg ‹رقم› للتفاصيل</i>\n")
    lines = []
    for i, (key, label, default, allowed) in enumerate(messages.CATALOG, 1):
        mark = "✏️" if messages.is_modified(key) else "▫️"
        lines.append(f"{mark} <b>{i}</b> · {ui.esc(label)}\n      <code>{ui.esc(_msg_preview(messages.text(key)))}</code>")
    await _send_chunks(update.message, header, lines)


@admin._admin_only
async def change_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/change <رقم> <النص الجديد> ← يعدل رسالة داخل اللعبة. /change <رقم> reset ← يرجعها للأصل"""
    parts = (update.message.text or "").split(None, 2)
    usage = ui.usage("/change", "‹رقم› ‹النص الجديد›", "/change 4 [FF0000]ما لقيت الأغنية!")
    if len(parts) < 2 or not parts[1].isdigit():
        await ui.reply(update.message, usage + "\n\n<i>الأرقام والرسائل: /messeg</i>")
        return
    num = int(parts[1])
    if not messages.info(num):
        await ui.reply(update.message, ui.err("رقم غير موجود", f"الأرقام من 1 إلى {messages.count()}"))
        return
    if len(parts) < 3 or not parts[2].strip():
        await ui.reply(update.message, _msg_detail(num))
        return
    new_text = parts[2].strip()
    if new_text.lower() in ("reset", "default", "افتراضي", "الأصل"):
        messages.reset(num)
        await ui.reply(update.message, ui.ok("رجعت الرسالة للأصل", messages.info(num)[1], [("🔢", "الرقم", num)]))
        return
    new_text = new_text.replace("\\n", "\n")                  # \n المكتوبة تصير سطر جديد
    if len(new_text) > 400:
        await ui.reply(update.message, ui.err("الرسالة طويلة", "الحد 400 حرف"))
        return
    problem = messages.validate(num, new_text)
    if problem:
        await ui.reply(update.message, ui.err(problem.split("\n")[0], problem.split("\n", 1)[1] if "\n" in problem else None))
        return
    saved = messages.set_text(num, new_text)
    await ui.reply(update.message, ui.ok("تم تعديل الرسالة", messages.info(num)[1],
                                         [("🔢", "الرقم", num), ("📝", "الجديد", _msg_preview(new_text, 90))],
                                         "تظهر الحين داخل اللعبة" + ("" if saved else "  (تعذر حفظها للملف)")))


# ═══════════════════════════ /stopall و /msgmusic ═══════════════════════════
MSG_INTERVAL = max(5.0, float(os.environ.get("MSGMUSIC_INTERVAL", "5")))       # ثواني بين كل رسالة (5 كحد أدنى)
MSG_MAX_LEN = int(os.environ.get("MSGMUSIC_MAX_LEN", "120"))                   # أقصى طول للرسالة
MSG_COLORS = ("FFD700", "00FF7F", "00BFFF", "FF69B4")

@admin._admin_only
async def stopall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stopall ← يوقف كل البوتات المشغولة ويرجعها متاحة (مثل إعادة تشغيل)"""
    msg = await ui.reply(update.message, ui.working("جاري إيقاف كل البوتات"))
    n_sessions = len(squad_bots)
    n_tasks = sum(1 for t in active_em_tasks.values() if not t.done())
    await _close_all_bots()                      # يلغي الرقص ويسكر كل الجلسات والجاهزة
    main_state = "فاضي"
    b = MAIN["bot"]
    try:
        if b and not b.closed and b.in_team:
            await b.leave()
            main_state = "طلع من الفريق"
    except Exception:
        pass
    await asyncio.sleep(1.0)                     # نخلي مهام الإلغاء تخلص وترجّع حساباتها
    pool.in_use = set()
    pool.fails.clear()
    pool.cool_until.clear()
    asyncio.create_task(_refill_warm())          # نجهز بوتات جديدة بالخلفية
    await ui.edit(msg, ui.ok("تم إيقاف كل البوتات", "كل الحسابات رجعت متاحة",
                             [("🎧", "جلسات موسيقى", n_sessions), ("💃", "مهام رقص", n_tasks),
                              ("🤖", "الحساب الأساسي", main_state)],
                             "رجع الوضع كأنك سويت إعادة تشغيل"))


def _parse_msgmusic(raw):
    """raw = النص بعد كود الفريق. يرجع (أغنية, رسالة) أو None.
    الصيغ:  أغنية | رسالة   أو   "أغنية بين علامتين" رسالة   أو   كلمة_واحدة رسالة"""
    raw = raw.strip()
    if "|" in raw:
        song, text = [x.strip() for x in raw.split("|", 1)]
    elif raw[:1] in ('"', "“", "«"):
        close = {'"': '"', "“": "”", "«": "»"}[raw[0]]
        end = raw.find(close, 1)
        if end == -1:
            return None
        song, text = raw[1:end].strip(), raw[end + 1:].strip()
    else:
        parts = raw.split(None, 1)
        if len(parts) < 2:
            return None
        song, text = parts[0], parts[1].strip()
    return (song, text) if song and text else None


async def _msg_loop(bot, text):
    """يرسل الرسالة في شات الفريق كل MSG_INTERVAL ثواني لين يطلع البوت أو يتلغى"""
    i = 0
    try:
        while not bot.closed:
            if bot.in_team:
                color = MSG_COLORS[i % len(MSG_COLORS)]
                await bot.say(f"[B][C][{color}]{text}")
                i += 1
            await asyncio.sleep(MSG_INTERVAL)
    except asyncio.CancelledError:
        pass


async def msgmusic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/msgmusic <كود_الفريق> <أغنية> | <رسالة> ← يدخل الفريق، يشغل الأغنية، ويكرر الرسالة كل 5 ثواني"""
    tid = update.effective_user.id
    usage = ui.usage("/msgmusic", "‹كود_الفريق› ‹أغنية› | ‹رسالة›", "/msgmusic 5592884 حدائق الكلمات | اشتركوا في قناتنا")
    parts = (update.message.text or "").split(None, 2)
    if len(parts) < 3 or not parts[1].isdigit():
        await ui.reply(update.message, usage)
        return
    team_code = parts[1]
    parsed = _parse_msgmusic(parts[2])
    if not parsed:
        await ui.reply(update.message, usage)
        return
    song, text = parsed
    if len(text) > MSG_MAX_LEN:
        await ui.reply(update.message, ui.err(f"الرسالة طويلة (الحد {MSG_MAX_LEN} حرف)", "اختصرها وأعد المحاولة"))
        return
    t = active_em_tasks.get(tid)
    if t and not t.done():
        await ui.reply(update.message, ui.err("عندك مهمة شغالة", "أرسل /stop أول"))
        return
    msg = await ui.reply(update.message, ui.working("جاري الانضمام للفريق", team_code))
    try:
        bot, err = await _new_bot(tid)
        if err:
            await ui.edit(msg, ui.err(ui.clean(err)))
            return
        if not await bot.join(team_code):
            await bot.close()
            await ui.edit(msg, ui.err("ما قدرت أنضم للفريق", "تأكد من الكود وإن الفريق مفتوح"))
            return
        asyncio.create_task(_auto_leave(tid, bot))
        active_em_tasks[tid] = asyncio.create_task(_msg_loop(bot, text))
        await ui.edit(msg, ui.ok("تم الانضمام", "البوت يشغل الأغنية ويكرر الرسالة",
                                 [("🏷", "الفريق", team_code), ("🎵", "الأغنية", song),
                                  ("💬", "الرسالة", text), ("⏱", "كل", f"{int(MSG_INTERVAL)} ثواني")],
                                 "للإيقاف: /stop"))
        await asyncio.sleep(3)
        await bot.handle_command("!play " + song)
    except Exception as ex:
        await ui.edit(msg, ui.err("حصل خطأ", str(ex)))


# ═══════════════════════════ فرق ورقصات من تيليجرام (للجميع) + /evos و /co للأدمن ═══════════════════════════
# ═══════════ البوت الصديق: أوامر من داخل اللعبة (خاص أو شات الفريق) بالحساب الأساسي ═══════════
GAME_ADMINS = {x.strip() for x in os.environ.get("GAME_ADMINS", "").replace(";", ",").split(",") if x.strip()}
game_tasks = {}          # uid اللاعب -> مهمة /evos شغالة

def _pm(text):
    """نضيف [B][C] لكل سطر في الرسائل الخاصة"""
    return "\n".join("[B][C]" + ln for ln in str(text).split("\n"))

async def friend_hook(bot, cmd, args, sender_uid, private):
    """يرجع True إذا عالج الأمر. الأوامر: /help /3 /5 /6 /dance /em /evo /evos /stop"""
    sender = str(sender_uid) if sender_uid else None
    if not sender or not sender.isdigit():
        return False

    async def to_sender(text):                      # النتائج توصل خاص (لأن البوت ممكن يغير الفريق أثناء التنفيذ)
        await bot._private_reply(sender, _pm(text))

    async def ack(text):                            # التأكيد الفوري في نفس مكان الأمر
        if private:
            await to_sender(text)
        else:
            await bot.say(text)

    if cmd in ("help", "start", "bot", "h") and private:
        await to_sender(messages.t("friend_help"))
        return True

    if cmd in ("3", "5", "6"):
        size = int(cmd)
        await ack(messages.t("friend_working", text=f"جاري إنشاء فريق {size} لاعبين..."))
        ok, text = await _with_main(lambda b: b.make_team(size, int(sender)))
        await to_sender(messages.t("friend_ok" if ok else "friend_fail", text=text))
        return True

    if cmd in ("dance", "em", "evo"):
        evo = cmd == "evo"
        strav = len(args) >= 3 and args[0].isdigit() and args[-1].isdigit()
        if not strav:
            if not private and cmd != "evo":
                return False                        # !dance و !em في شات الفريق تبقى للموسيقى
            await to_sender(messages.t("friend_usage_dance", name=cmd))
            return True
        uids = [a for a in args[1:-1] if a.isdigit()]
        if not uids:
            await to_sender(messages.t("friend_usage_dance", name=cmd))
            return True
        await ack(messages.t("friend_working", text="جاري التنفيذ..."))
        ok, text = await _with_main(lambda b: b.dance_uids(args[0], uids, args[-1], evo=evo))
        await to_sender(messages.t("friend_ok" if ok else "friend_fail", text=text))
        return True

    if cmd == "evos":
        if sender not in GAME_ADMINS:
            await to_sender(messages.t("friend_no_admin"))
            return True
        if len(args) < 2 or not args[0].isdigit() or not args[1].isdigit():
            await to_sender(messages.t("friend_usage_evos"))
            return True
        old = game_tasks.get(sender)
        if old and not old.done():
            await to_sender(messages.t("friend_fail", text="عندك /evos شغال، اكتب /stop أول"))
            return True
        code, uid = args[0], args[1]
        await ack(messages.t("friend_working", text=f"/evos بدأ على {uid} في الفريق {code} (للإيقاف: /stop)"))

        async def _run():
            try:
                ok, text = await _with_main(lambda b: b.evos_loop(code, uid, EMOTE_DELAY, None), wait=5)
                if not ok:
                    await to_sender(messages.t("friend_fail", text=text))
            except asyncio.CancelledError:
                await to_sender(messages.t("friend_ok", text="تم إيقاف /evos"))
            finally:
                game_tasks.pop(sender, None)

        game_tasks[sender] = asyncio.create_task(_run())
        return True

    if cmd == "stop":
        t = game_tasks.get(sender)
        if t and not t.done():
            t.cancel()
            return True
        return False                                # !stop للموسيقى
    return False

# ═══════════ الحساب الأساسي (acces.txt): مخصص لـ /evo /evos /dance /team ═══════════
ACCES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "acces.txt")
MAIN_MAX_AGE = int(float(os.environ.get("MAIN_MAX_AGE_HOURS", "2")) * 3600)
MAIN = {"acc": None, "bot": None, "ts": 0.0, "lock": None}

def _load_main_account():
    """من متغيرات MAIN_UID / MAIN_PASSWORD / MAIN_REGION أو من acces.txt (uid= و password= و region=  أو  uid:pass)"""
    uid, pw = os.environ.get("MAIN_UID"), os.environ.get("MAIN_PASSWORD")
    reg = os.environ.get("MAIN_REGION", os.environ.get("FF_REGION", "ME"))
    if not (uid and pw):
        uid = pw = None
        try:
            with open(ACCES_PATH, "r", encoding="utf-8") as f:
                raw = f.read().strip()
        except FileNotFoundError:
            return None
        try:
            import json as _json
            d = _json.loads(raw)
            uid, pw, reg = str(d["uid"]), str(d["password"]), str(d.get("region", reg))
        except Exception:
            for line in raw.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip().lower(), v.strip()
                    if k in ("uid", "user", "username"):
                        uid = v
                    elif k in ("password", "pw", "pass"):
                        pw = v
                    elif k in ("region", "reg"):
                        reg = v
                elif ":" in line and not uid:
                    u, p = line.split(":", 1)
                    uid, pw = u.strip(), p.strip()
    if not uid or not pw or not str(uid).isdigit() or str(uid).startswith("PUT_") or str(pw).startswith("PUT_"):
        return None
    return {"uid": str(uid), "password": str(pw), "region": reg or "ME"}

MAIN["acc"] = _load_main_account()
if MAIN["acc"]:
    pool.reserved.add(MAIN["acc"]["uid"])      # ما ينسحب من مخزن الموسيقى

def _main_lock():
    if MAIN["lock"] is None:
        MAIN["lock"] = asyncio.Lock()
    return MAIN["lock"]

async def _main_bot():
    """يرجع بوت الحساب الأساسي متصل (يعيد تسجيل الدخول إذا انقطع أو انتهى عمره). نستدعيه والقفل معنا"""
    acc = MAIN["acc"]
    b = MAIN["bot"]
    if b and not b.closed and time.time() - MAIN["ts"] < MAIN_MAX_AGE:
        return b
    if b and not b.closed:
        await b.close()
    MAIN["bot"] = None
    try:
        login = await login_engine.do_login(acc["uid"], acc["password"], acc["region"])
    except Exception as ex:
        logging.warning("main account login error: %s", ex)
        return None
    if not login:
        logging.warning("main account login failed")
        return None
    b = SquadBot(login)
    b.quiet = True
    try:
        await b.connect()
    except Exception as ex:
        logging.warning("main account connect error: %s", ex)
        await b.close()
        return None
    b.persistent = True          # يقبل دعوات الفريق داخل اللعبة ويرد على الأوامر (/help ...)
    b.command_hook = friend_hook  # أوامر البوت الصديق
    b.quiet = False
    MAIN["bot"], MAIN["ts"] = b, time.time()
    logging.info("main account online: %s (%s)", b.name, b.uid)
    return b

async def _main_maintainer():
    """يخلي الحساب الأساسي متصل وجاهز دايم (ما يقاطع مهمة شغالة)"""
    await asyncio.sleep(3)
    while True:
        try:
            if MAIN["acc"] and not _main_lock().locked():
                async with _main_lock():
                    await _main_bot()
        except Exception as ex:
            logging.warning("main maintainer: %s", ex)
        await asyncio.sleep(30)

async def _with_main(fn, wait=20):
    """ينفذ fn(bot) بالحساب الأساسي (مهمة وحدة بنفس الوقت). يرجع (نجح, رسالة)"""
    if not MAIN["acc"]:
        return False, "الحساب الأساسي غير مضبوط (acces.txt)"
    lock = _main_lock()
    try:
        await asyncio.wait_for(lock.acquire(), wait)
    except asyncio.TimeoutError:
        return False, "الحساب الأساسي مشغول بمهمة ثانية، جرب بعد شوي"
    bot = None
    try:
        bot = await _main_bot()
        if not bot:
            return False, "تعذر تسجيل دخول الحساب الأساسي"
        # المهمة لها الأولوية: نترك أي فريق داخل اللعبة ونوقف قبول الدعوات لين تخلص
        bot.persistent = False
        bot.quiet = True
        if bot.in_team:
            await bot.leave()
            await asyncio.sleep(1.0)
        return await fn(bot)
    except asyncio.CancelledError:
        raise
    except Exception as ex:
        logging.exception("main account task failed")
        return False, f"خطأ: {type(ex).__name__}: {ex}"
    finally:
        try:
            if bot and not bot.closed:
                if bot.in_team:
                    await bot.leave()
                bot.persistent = True
                bot.quiet = False
        except Exception:
            pass
        lock.release()

def _make_team_cmd(size):
    async def _cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args or not context.args[0].isdigit():
            await ui.reply(update.message, ui.usage(f"/team{size}", "‹uid_اللاعب›", f"/team{size} 1234567890"))
            return
        msg = await ui.reply(update.message, ui.working(f"جاري إنشاء فريق {size} لاعبين", context.args[0]))
        ok, text = await _with_main(lambda b: b.make_team(size, int(context.args[0])))
        await ui.edit(msg, ui.ok("الفريق جاهز", text, [("👥", "الحجم", size), ("🎯", "اللاعب", context.args[0])]) if ok else ui.err(text))
    return _cmd

def _make_dance_cmd(evo):
    name = "evo" if evo else "dance"
    async def _cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        if len(args) < 3 or not args[0].isdigit() or not args[-1].isdigit():
            await ui.reply(update.message, ui.usage(f"/{name}", "‹كود_الفريق› ‹uid…› ‹رقم_الرقصة›", f"/{name} 5592884 1234567890 5"))
            return
        uids = [a for a in args[1:-1] if a.isdigit()]
        if not uids:
            await ui.reply(update.message, ui.err("ما دخلت أي UID صالح"))
            return
        msg = await ui.reply(update.message, ui.working("جاري التنفيذ", f"الفريق {args[0]}"))
        ok, text = await _with_main(lambda b: b.dance_uids(args[0], uids, args[-1], evo=evo))
        await ui.edit(msg, ui.ok("تمت الرقصة", text, [("🏷", "الفريق", args[0]), ("💃", "الرقم", args[-1])]) if ok else ui.err(text))
    return _cmd


async def _run_evos(update, msg, team_code, uid):
    tid = update.effective_user.id
    try:
        async def _job(bot):
            await ui.edit(msg, ui.card("💃", "الرقص المستمر", "كل الرقصات وتتكرر بدون توقف",
                                       [("🏷", "الفريق", team_code), ("🎯", "اللاعب", uid)], "للإيقاف: /stop"))

            async def _prog(rounds, n):
                await ui.edit(msg, ui.card("💃", "الرقص المستمر", "شغال الحين",
                                           [("🏷", "الفريق", team_code), ("🎯", "اللاعب", uid), ("🔁", "الدورة", rounds + 1), ("🎞", "الرقصات", n)], "للإيقاف: /stop"))

            ok, text = await bot.evos_loop(team_code, uid, EMOTE_DELAY, _prog)
            if ok and bot.closed:
                return False, "انقطع اتصال الحساب الأساسي"
            return ok, text

        ok, text = await _with_main(_job, wait=5)
        if not ok:
            await ui.edit(msg, ui.err(text))
    except asyncio.CancelledError:
        try:
            await ui.edit(msg, ui.stopped("وقف الرقص المستمر"))
        except Exception:
            pass
    except Exception as ex:
        logging.exception("evos failed")
        try:
            await ui.edit(msg, ui.err("حصل خطأ", f"{type(ex).__name__}: {ex}"))
        except Exception:
            pass
    finally:
        active_em_tasks.pop(tid, None)

@admin._admin_only
async def evos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/evos <كود_الفريق> <uid> ← يرقّص اللاعب بكل الرقصات ويكررها بدون توقف (أدمن فقط)"""
    tid = update.effective_user.id
    a = context.args
    if len(a) < 2 or not a[0].isdigit() or not a[1].isdigit():
        await ui.reply(update.message, ui.usage("/evos", "‹كود_الفريق› ‹uid›", "/evos 5592884 1234567890"))
        return
    t = active_em_tasks.get(tid)
    if t and not t.done():
        await ui.reply(update.message, ui.err("عندك رقص شغال", "أرسل /stop أول"))
        return
    msg = await ui.reply(update.message, ui.working("جاري الانضمام للفريق", a[0]))
    active_em_tasks[tid] = asyncio.create_task(_run_evos(update, msg, a[0], a[1]))

@admin._admin_only
async def co_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/co ← يعرض أوامر الأدمن (للأدمن فقط)"""
    await ui.reply(update.message, ui.admin_menu())


# ═══════════════════════════ ربط لوحة الأدمن ═══════════════════════════
async def _close_all_bots():
    """يوقف كل الجلسات (يستخدمها /off)"""
    for t in list(active_em_tasks.values()) + list(game_tasks.values()):
        if not t.done():
            t.cancel()
    for b in list(squad_bots.values()):
        try:
            await b.close()
        except Exception:
            pass
    squad_bots.clear()
    for b, _ in list(warm_bots):
        try:
            await b.close()
        except Exception:
            pass
    warm_bots.clear()

admin.hooks["active"] = lambda: (len(squad_bots), sum(1 for b in squad_bots.values() if b.in_team))
admin.hooks["close_all"] = _close_all_bots
admin.hooks["capacity"] = lambda: len(pool.usable())

async def _post_init(application):
    _APP["app"] = application
    await admin.start_web()
    application.bot_data["warm_task"] = asyncio.create_task(_warm_maintainer())
    if MAIN["acc"]:
        application.bot_data["main_task"] = asyncio.create_task(_main_maintainer())
    else:
        logging.info("الحساب الأساسي غير مضبوط (acces.txt): أوامر /evo /evos /dance /team ما بتشتغل")

async def _post_shutdown(application):
    for key in ("warm_task", "main_task"):
        t = application.bot_data.get(key)
        if t:
            t.cancel()
    if MAIN["bot"]:
        try:
            await MAIN["bot"].close()
        except Exception:
            pass
    for b, _ in list(warm_bots):
        try:
            await b.close()
        except Exception:
            pass
    warm_bots.clear()
    await admin.stop_web()


# ═══════════════════════════ تشغيل البوت ═══════════════════════════
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(_post_init).post_shutdown(_post_shutdown).build()
    admin.register(app)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("music", music_command))
    app.add_handler(CommandHandler("play", play_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("online", online_command))
    app.add_handler(CommandHandler("offline", offline_command))
    app.add_handler(CommandHandler("em", em_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("stopall", stopall_command))
    app.add_handler(CommandHandler("messeg", messeg_command))
    app.add_handler(CommandHandler("change", change_command))
    app.add_handler(CommandHandler("msgmusic", msgmusic_command))
    for _size in (3, 5, 6):
        app.add_handler(CommandHandler(f"team{_size}", _make_team_cmd(_size)))
        app.add_handler(CommandHandler(str(_size), _make_team_cmd(_size)))
    app.add_handler(CommandHandler("dance", _make_dance_cmd(False)))
    app.add_handler(CommandHandler("evos", evos_command))
    app.add_handler(CommandHandler("co", co_command))
    app.add_handler(CommandHandler("evo", _make_dance_cmd(True)))

    print("🚀 البوت يعمل الآن...")
    app.run_polling()
