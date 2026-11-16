# -*- coding: utf-8 -*-
"""
admin.py
- اشتراك إجباري في قناة
- صلاحيات: مالك أساسي + أدمن
- تحكم بالمجموعات: /allow /disallow /kick /unban
- إيقاف/تشغيل البوت: /off /on
- صفحة حالة ويب (للاستضافة اللي تعطي دومين)
"""
import asyncio
import json
import logging
import os
import time
from datetime import date
from html import escape

from aiohttp import web
from accounts import pool
import ui
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import (
    ApplicationHandlerStop,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

log = logging.getLogger("admin")

# ───────────── الإعدادات ─────────────
REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL", "@UXD_10")   # تقدر تحط أكثر من قناة مفصولة بفاصلة
OWNER_ID = int(os.environ.get("OWNER_ID", "6533075996"))
MAX_ACTIVE_BOTS = int(os.environ.get("MAX_ACTIVE_BOTS", "15"))   # أقصى عدد جلسات بنفس الوقت
CONFIG_PATH = os.environ.get("CONFIG_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_config.json"))
STOPPED_TEXT = "⛔ البوت متوقف حاليا"

GROUP_TYPES = ("group", "supergroup")
STARTED_AT = time.time()

# يضبطها main.py: {"active": () -> (جلسات, داخل فرق), "close_all": async () -> None}
hooks = {}

_cfg = None
_group_notice_at = {}
_sub_warned = set()


# ───────────── التخزين ─────────────
def _default_cfg():
    return {"admins": [], "enabled": True, "allowed_groups": [], "banned_groups": [], "channels": [], "disabled_cmds": [],
            "stats": {"teams_joined": 0, "daily": {}}}


def cfg():
    global _cfg
    if _cfg is None:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        base = _default_cfg()
        base.update(data)
        base["stats"] = {**_default_cfg()["stats"], **base.get("stats", {})}
        _cfg = base
    return _cfg


def save_cfg():
    tmp = CONFIG_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg(), f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except Exception as e:
        log.warning("save config failed: %s", e)


def is_owner(uid):
    return int(uid) == OWNER_ID


def is_admin(uid):
    return is_owner(uid) or int(uid) in cfg()["admins"]


def record_team_join():
    """يُستدعى كل ما دخل البوت فريق (بتيم كود أو بدعوة)"""
    st = cfg()["stats"]
    st["teams_joined"] = int(st.get("teams_joined", 0)) + 1
    today = date.today().isoformat()
    daily = st.setdefault("daily", {})
    daily[today] = int(daily.get(today, 0)) + 1
    for k in sorted(daily)[:-14]:      # نحتفظ بآخر 14 يوم فقط
        daily.pop(k, None)
    save_cfg()


def bot_enabled():
    return bool(cfg()["enabled"])


# ───────────── الاشتراك الإجباري (أكثر من قناة) ─────────────
def _norm_channel(raw):
    """يرجع @username من @name أو t.me/name أو https://t.me/name، أو None"""
    t = str(raw).strip()
    for pre in ("https://", "http://"):
        if t.lower().startswith(pre):
            t = t[len(pre):]
    for pre in ("t.me/", "telegram.me/"):
        if t.lower().startswith(pre):
            t = t[len(pre):]
    t = t.split("?")[0].strip("/ @")
    if not t or not all(c.isalnum() or c == "_" for c in t) or len(t) < 4:
        return None
    return "@" + t


PINNED_CHANNELS = os.environ.get("PINNED_CHANNELS", "uxd_10")   # قنوات ثابتة دايماً تنفرض ما تنحذف


def env_channels():
    out = []
    for x in (PINNED_CHANNELS + "," + REQUIRED_CHANNEL).replace(";", ",").split(","):
        n = _norm_channel(x) if x.strip() else None
        if n and n.lower() not in [o.lower() for o in out]:
            out.append(n)
    return out


def channels():
    """كل قنوات الاشتراك: اللي من المتغير REQUIRED_CHANNEL + اللي أضافها الأدمن بـ /addchannel"""
    out = list(env_channels())
    for c in cfg().get("channels", []):
        if c.lower() not in [o.lower() for o in out]:
            out.append(c)
    return out


async def _is_member(bot, channel, user_id):
    try:
        m = await bot.get_chat_member(channel, user_id)
        if m.status in ("member", "administrator", "creator", "owner"):
            return True
        if m.status == "restricted":
            return bool(getattr(m, "is_member", False))
        return False
    except (BadRequest, Forbidden) as e:
        # غالباً البوت مو أدمن في القناة: ما نقفل البوت على الناس، بس ننبه المالك مرة وحدة
        log.warning("subscription check failed for %s: %s", channel, e)
        if channel not in _sub_warned:
            _sub_warned.add(channel)
            try:
                await bot.send_message(OWNER_ID, f"⚠️ ما أقدر أتحقق من الاشتراك في {channel}.\nلازم تجعل البوت أدمن في القناة.")
            except Exception:
                pass
        return True
    except Exception as e:
        log.warning("subscription check error: %s", e)
        return True


async def missing_channels(bot, user_id):
    """القنوات اللي المستخدم ما اشترك فيها"""
    out = []
    for ch in channels():
        if not await _is_member(bot, ch, user_id):
            out.append(ch)
    return out


async def is_subscribed(bot, user_id):
    return not await missing_channels(bot, user_id)


def _sub_markup(missing):
    rows = [[InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in missing]
    rows.append([InlineKeyboardButton("✅ تحققت", callback_data="chk_sub")])
    return InlineKeyboardMarkup(rows)


async def _ask_subscribe(update, context, missing=None):
    if missing is None:
        missing = await missing_channels(context.bot, update.effective_user.id)
    if not missing:
        return
    text = ui.card("📢", "اشتراك إجباري", "اشترك في القنوات التالية ثم اضغط «تحققت»",
                   [("🔗", "قناة", ch) for ch in missing])
    if update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=_sub_markup(missing),
                                                   parse_mode="HTML", disable_web_page_preview=True)


async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if await is_subscribed(context.bot, q.from_user.id):
        await q.answer("✅ تم التحقق، تقدر تستخدم البوت", show_alert=True)
        try:
            await q.edit_message_text("✅ تم التحقق من اشتراكك، أعد إرسال الأمر.")
        except Exception:
            pass
    else:
        await q.answer("❌ لسا ما اشتركت في كل القنوات", show_alert=True)


# ───────────── البوابة (تمر عليها كل الأوامر) ─────────────
async def gate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not msg or not user or not chat or not msg.text:
        return
    cmd = msg.text.split()[0][1:].split("@")[0].lower()

    # الأدمن يمرون دائماً
    if is_admin(user.id):
        return

    # مجموعة محظورة: يطلع منها
    if chat.type in GROUP_TYPES and chat.id in cfg()["banned_groups"]:
        try:
            await context.bot.leave_chat(chat.id)
        except Exception:
            pass
        raise ApplicationHandlerStop

    # البوت متوقف
    if not bot_enabled():
        await msg.reply_text(STOPPED_TEXT)
        raise ApplicationHandlerStop

    if chat.type in GROUP_TYPES:
        # المجموعة لازم تكون مفعّلة بـ /allow
        if chat.id not in cfg()["allowed_groups"]:
            now = time.time()
            if now - _group_notice_at.get(chat.id, 0) > 60:
                _group_notice_at[chat.id] = now
                await msg.reply_text("⚠️ البوت مو مفعّل في هذي المجموعة. الأدمن لازم يكتب /allow")
            raise ApplicationHandlerStop

    # أمر موقوف من الأدمن (/stop اسم_الأمر)
    if cmd in disabled_cmds():
        await msg.reply_text(ui.err("هذا الأمر متوقف حالياً", "جرب بعد شوي"), parse_mode="HTML")
        raise ApplicationHandlerStop

    # الاشتراك الإجباري
    missing = await missing_channels(context.bot, user.id)
    if missing:
        await _ask_subscribe(update, context, missing)
        raise ApplicationHandlerStop


# ───────────── أوامر الأدمن ─────────────
def _admin_only(fn):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user or not is_admin(update.effective_user.id):
            return
        await fn(update, context)
    return wrapper


def _target_chat(update, context):
    """يحدد المجموعة: من الأرقام بعد الأمر، أو المجموعة الحالية"""
    if context.args:
        try:
            return int(context.args[0])
        except ValueError:
            return None
    chat = update.effective_chat
    return chat.id if chat.type in GROUP_TYPES else None


@_admin_only
async def cmd_off(update, context):
    cfg()["enabled"] = False
    save_cfg()
    closer = hooks.get("close_all")
    if closer:
        try:
            await closer()
        except Exception as e:
            log.warning("close_all failed: %s", e)
    await update.message.reply_text(f"⏹ تم إيقاف البوت في كل المجموعات.\nيظهر للمستخدمين: {STOPPED_TEXT}\nللتشغيل: /on")


@_admin_only
async def cmd_on(update, context):
    cfg()["enabled"] = True
    save_cfg()
    await update.message.reply_text("✅ تم تشغيل البوت.")


@_admin_only
async def cmd_allow(update, context):
    cid = _target_chat(update, context)
    if cid is None:
        await update.message.reply_text("❌ اكتب /allow داخل المجموعة، أو من الخاص: /allow <group_id>")
        return
    c = cfg()
    if cid in c["banned_groups"]:
        await update.message.reply_text("⛔ هذي المجموعة محظورة. استخدم /unban أول.")
        return
    if cid not in c["allowed_groups"]:
        c["allowed_groups"].append(cid)
        save_cfg()
    await update.message.reply_text(f"✅ تم تفعيل البوت في المجموعة ({cid}).")


@_admin_only
async def cmd_disallow(update, context):
    cid = _target_chat(update, context)
    if cid is None:
        await update.message.reply_text("❌ اكتب /disallow داخل المجموعة، أو من الخاص: /disallow <group_id>")
        return
    c = cfg()
    if cid in c["allowed_groups"]:
        c["allowed_groups"].remove(cid)
        save_cfg()
    await update.message.reply_text(f"⏹ تم إلغاء التفعيل في ({cid}).")


@_admin_only
async def cmd_kick(update, context):
    cid = _target_chat(update, context)
    if cid is None:
        await update.message.reply_text("❌ اكتب /kick داخل المجموعة، أو من الخاص: /kick <group_id>")
        return
    c = cfg()
    if cid in c["allowed_groups"]:
        c["allowed_groups"].remove(cid)
    if cid not in c["banned_groups"]:
        c["banned_groups"].append(cid)
    save_cfg()
    try:
        await context.bot.leave_chat(cid)
        note = "طلعت منها وكل ما ينضاف لها يطلع تلقائياً."
    except Exception as e:
        note = f"تم حظرها، لكن تعذر الخروج الحين ({e}). يطلع أول ما ينضاف لها."
    if update.effective_chat.type == "private":
        await update.message.reply_text(f"🚪 ({cid}): {note}\nلرفع الحظر: /unban {cid}")


@_admin_only
async def cmd_unban(update, context):
    if not context.args:
        await update.message.reply_text("❌ الصيغة: /unban <group_id>")
        return
    try:
        cid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ المعرّف لازم يكون رقم.")
        return
    c = cfg()
    if cid in c["banned_groups"]:
        c["banned_groups"].remove(cid)
        save_cfg()
    await update.message.reply_text(f"✅ تم رفع الحظر عن ({cid}).")


async def cmd_addadmin(update, context):
    if not update.effective_user or not is_owner(update.effective_user.id):
        return
    if not context.args or not context.args[0].lstrip("-").isdigit():
        await update.message.reply_text("❌ الصيغة: /addadmin <user_id>")
        return
    uid = int(context.args[0])
    c = cfg()
    if uid != OWNER_ID and uid not in c["admins"]:
        c["admins"].append(uid)
        save_cfg()
    await update.message.reply_text(f"✅ تمت إضافة الأدمن {uid}.")


async def cmd_deladmin(update, context):
    if not update.effective_user or not is_owner(update.effective_user.id):
        return
    if not context.args or not context.args[0].lstrip("-").isdigit():
        await update.message.reply_text("❌ الصيغة: /deladmin <user_id>")
        return
    uid = int(context.args[0])
    c = cfg()
    if uid in c["admins"]:
        c["admins"].remove(uid)
        save_cfg()
    await update.message.reply_text(f"✅ تم حذف الأدمن {uid}.")


@_admin_only
async def cmd_admins(update, context):
    admins = cfg()["admins"]
    lines = [f"👑 المالك: {OWNER_ID}"] + [f"🛡 {a}" for a in admins]
    await update.message.reply_text("\n".join(lines))


@_admin_only
async def cmd_groups(update, context):
    c = cfg()
    allowed = "\n".join(f"✅ {g}" for g in c["allowed_groups"]) or "—"
    banned = "\n".join(f"⛔ {g}" for g in c["banned_groups"]) or "—"
    await update.message.reply_text(f"المجموعات المفعّلة:\n{allowed}\n\nالمجموعات المحظورة:\n{banned}")


@_admin_only
async def cmd_status(update, context):
    s = snapshot()
    await update.message.reply_text(
        f"{'🟢 يعمل' if s['enabled'] else '🔴 متوقف'}\n"
        f"👥 جلسات نشطة: {s['active_sessions']}/{s['capacity']} (داخل فرق: {s['in_team']})\n"
        f"🎮 فرق دخلها البوت: {s['teams_joined']} (اليوم: {s['teams_today']})\n"
        f"📊 الضغط: {s['load_label']} ({s['load_percent']}%)\n"
        f"⏱ مدة التشغيل: {s['uptime']}")


@_admin_only
async def cmd_accounts(update, context):
    st = pool.stats()
    lines = [f"👤 الحسابات: {st['total']} (شغالة: {st['usable']} • مشغولة: {st['busy']} • فاضية: {st['free']} • معطلة: {st['bad']})"]
    for a in pool.accounts:
        uid = a["uid"]
        if pool.fails.get(uid, 0) >= 3:
            flag = "⚠️ معطل"
        elif uid in pool.in_use:
            flag = "🔴 مشغول"
        else:
            flag = "🟢 فاضي"
        lines.append(f"{flag}  ...{uid[-6:]}")
    await update.message.reply_text("\n".join(lines[:60]))


@_admin_only
async def cmd_reload(update, context):
    n = pool.reload()
    pool.fails.clear()
    pool.cool_until.clear()
    await update.message.reply_text(f"🔄 تم تحميل {n} حساب من accent.txt وتصفير حالة التعطيل.")


@_admin_only
async def cmd_addacc(update, context):
    raw = " ".join(context.args).strip()
    try:
        await update.message.delete()      # نحذف رسالة الأدمن لأن فيها كلمة مرور
    except Exception:
        pass
    if ":" not in raw:
        await context.bot.send_message(update.effective_chat.id, "❌ الصيغة: /addacc uid:pass")
        return
    uid, pw = raw.split(":", 1)
    res = pool.add(uid.strip(), pw.strip())
    text = {True: "✅ تمت إضافة الحساب.", None: "⚠️ الحساب موجود من قبل.", False: "❌ صيغة غير صحيحة، لازم uid:pass"}[res]
    await context.bot.send_message(update.effective_chat.id, text)


# ───────────── قنوات الاشتراك: /addchannel /delchannel /channels ─────────────
@_admin_only
async def cmd_addchannel(update, context):
    if not context.args:
        await ui.reply(update.message, ui.usage("/addchannel", "‹@channel›", "/addchannel @mychannel"))
        return
    ch = _norm_channel(context.args[0])
    if not ch:
        await ui.reply(update.message, ui.err("اسم القناة غير صحيح", "اكتبها بصيغة @username أو رابط t.me"))
        return
    if ch.lower() in [c.lower() for c in channels()]:
        await ui.reply(update.message, ui.err("القناة مضافة من قبل", ch))
        return
    try:
        chat = await context.bot.get_chat(ch)
        me = await context.bot.get_chat_member(chat.id, context.bot.id)
        if me.status not in ("administrator", "creator", "owner"):
            raise Forbidden("bot is not admin")
    except (BadRequest, Forbidden):
        await ui.reply(update.message, ui.err("ما قدرت أتحقق من القناة",
                                              "تأكد إن الاسم صحيح، واجعل البوت أدمن في القناة أول ثم أعد المحاولة"))
        return
    except Exception as e:
        await ui.reply(update.message, ui.err("حصل خطأ", str(e)))
        return
    name = ("@" + chat.username) if getattr(chat, "username", None) else ch
    cfg().setdefault("channels", []).append(name)
    save_cfg()
    await ui.reply(update.message, ui.ok("تمت إضافة القناة", "صارت ضمن الاشتراك الإجباري",
                                         [("📢", "القناة", name), ("🔢", "المجموع", len(channels()))]))


@_admin_only
async def cmd_delchannel(update, context):
    if not context.args:
        await ui.reply(update.message, ui.usage("/delchannel", "‹@channel›", "/delchannel @mychannel"))
        return
    ch = _norm_channel(context.args[0])
    if ch and ch.lower() in [c.lower() for c in env_channels()]:
        await ui.reply(update.message, ui.err("هذي القناة من المتغير REQUIRED_CHANNEL", "هذي قناة ثابتة (من المتغيرات)"))
        return
    lst = cfg().setdefault("channels", [])
    found = next((c for c in lst if ch and c.lower() == ch.lower()), None)
    if not found:
        await ui.reply(update.message, ui.err("القناة مو في القائمة", ch or str(context.args[0])))
        return
    lst.remove(found)
    save_cfg()
    await ui.reply(update.message, ui.ok("تم حذف القناة", found, [("🔢", "المتبقي", len(channels()))]))


@_admin_only
async def cmd_channels(update, context):
    chs = channels()
    if not chs:
        await ui.reply(update.message, ui.card("📢", "قنوات الاشتراك", "ما في قنوات حالياً",
                                               (), "أضف قناة بـ /addchannel @name"))
        return
    env = [c.lower() for c in env_channels()]
    rows = [("🔒" if c.lower() in env else "📢", "ثابتة" if c.lower() in env else "مضافة", c) for c in chs]
    await ui.reply(update.message, ui.card("📢", "قنوات الاشتراك", f"العدد: {len(chs)}", rows,
                                           "/addchannel لإضافة  ·  /delchannel للحذف"))


# ───────────── إيقاف أمر محدد: /stop اسم_الأمر  و  /enable ─────────────
# أوامر المستخدمين اللي يجوز إيقافها (الأدمن دايماً يقدر يستخدمها)
TOGGLEABLE = {"music", "msgmusic", "online", "offline", "play", "resume", "em", "dance", "evo",
              "team3", "team5", "team6", "3", "5", "6"}
CMD_ALIASES = {"team": ["team3", "team5", "team6", "3", "5", "6"], "teams": ["team3", "team5", "team6", "3", "5", "6"],
               "dancing": ["em", "dance", "evo"]}


def disabled_cmds():
    return set(cfg().get("disabled_cmds", []))


def _resolve_cmds(name):
    n = str(name).strip().lstrip("/").lower()
    if n in CMD_ALIASES:
        return CMD_ALIASES[n]
    return [n] if n in TOGGLEABLE else []


@_admin_only
async def cmd_disable(update, context):
    """/stop music  أو  /disable music ← يوقف الأمر عن المستخدمين"""
    if not context.args:
        await ui.reply(update.message, ui.usage("/stop", "‹اسم_الأمر›", "/stop music"))
        return
    names = _resolve_cmds(context.args[0])
    if not names:
        await ui.reply(update.message, ui.err("هذا الأمر ما ينوقف",
                                              "المتاح: " + "، ".join(sorted(TOGGLEABLE - {"3", "5", "6"})) + "، team"))
        return
    dis = cfg().setdefault("disabled_cmds", [])
    for n in names:
        if n not in dis:
            dis.append(n)
    save_cfg()
    await ui.reply(update.message, ui.ok("تم إيقاف الأمر", "ما يقدر أحد يستخدمه غير الأدمن",
                                         [("🚫", "الأمر", "، ".join("/" + n for n in names))],
                                         "للتشغيل: /enable " + context.args[0].lstrip("/")))


@_admin_only
async def cmd_enable(update, context):
    if not context.args:
        dis = sorted(disabled_cmds())
        await ui.reply(update.message, ui.card("🚫", "الأوامر الموقوفة",
                                               "ما في أوامر موقوفة" if not dis else None,
                                               [("🔸", "موقوف", "/" + n) for n in dis],
                                               "للتشغيل: /enable ‹الأمر› (أو /enable all)"))
        return
    arg = context.args[0].strip().lstrip("/").lower()
    dis = cfg().setdefault("disabled_cmds", [])
    if arg == "all":
        names = list(dis)
    else:
        names = _resolve_cmds(arg)
    removed = [n for n in names if n in dis]
    for n in removed:
        dis.remove(n)
    save_cfg()
    if removed:
        await ui.reply(update.message, ui.ok("تم تشغيل الأمر", "رجع متاح للجميع",
                                             [("✅", "الأمر", "، ".join("/" + n for n in removed))]))
    else:
        await ui.reply(update.message, ui.err("هذا الأمر مو موقوف"))


async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أي مرة ينضاف البوت لمجموعة محظورة يطلع منها فوراً"""
    ev = update.my_chat_member
    if not ev:
        return
    chat = ev.chat
    if chat.type in GROUP_TYPES and chat.id in cfg()["banned_groups"]:
        if ev.new_chat_member.status in ("member", "administrator"):
            try:
                await context.bot.leave_chat(chat.id)
            except Exception as e:
                log.warning("leave banned chat failed: %s", e)


# ───────────── الحالة والضغط ─────────────
def _fmt_uptime(sec):
    sec = int(sec)
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m, _ = divmod(r, 60)
    return (f"{d}ي " if d else "") + f"{h}س {m}د"


def _system_load():
    """نسبة المعالج والذاكرة إن كانت psutil متوفرة"""
    try:
        import psutil
        return psutil.cpu_percent(interval=None), psutil.virtual_memory().percent
    except Exception:
        return None, None


def capacity():
    """السعة = عدد الحسابات الشغالة (أو MAX_ACTIVE_BOTS إذا أقل)"""
    cap = MAX_ACTIVE_BOTS
    fn = hooks.get("capacity")
    if fn:
        try:
            cap = min(cap, int(fn()))
        except Exception:
            pass
    return cap


def snapshot():
    active, in_team = 0, 0
    fn = hooks.get("active")
    if fn:
        try:
            active, in_team = fn()
        except Exception:
            pass
    cpu, mem = _system_load()
    cap = capacity()
    ratios = [active / cap if cap else 1.0]
    if cpu is not None:
        ratios.append(cpu / 100.0)
    if mem is not None:
        ratios.append(mem / 100.0)
    load = min(max(ratios), 1.0)
    if load < 0.5:
        label, color = "ممتاز", "#16a34a"
    elif load < 0.8:
        label, color = "متوسط", "#d97706"
    else:
        label, color = "ضغط عالي", "#dc2626"
    st = cfg()["stats"]
    return {
        "enabled": bot_enabled(),
        "active_sessions": active,
        "in_team": in_team,
        "capacity": cap,
        "teams_joined": int(st.get("teams_joined", 0)),
        "teams_today": int(st.get("daily", {}).get(date.today().isoformat(), 0)),
        "load_percent": int(round(load * 100)),
        "load_label": label,
        "load_color": color,
        "cpu": cpu,
        "memory": mem,
        "uptime": _fmt_uptime(time.time() - STARTED_AT),
    }


def at_capacity():
    fn = hooks.get("active")
    if not fn:
        return False
    try:
        return fn()[0] >= capacity()
    except Exception:
        return False


# ───────────── صفحة الويب ─────────────
PAGE = """<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="15">
<title>حالة البوت</title>
<style>
:root{{--bg:#f4f5f7;--card:#fff;--tx:#111827;--mut:#6b7280;--bd:#e5e7eb}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0f1115;--card:#181b22;--tx:#f3f4f6;--mut:#9ca3af;--bd:#262a33}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--tx);font-family:system-ui,-apple-system,Segoe UI,Tahoma,sans-serif;padding:20px}}
.wrap{{max-width:560px;margin:0 auto}}
h1{{font-size:20px;margin:0 0 14px}}
.card{{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:16px;margin-bottom:12px}}
.row{{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--bd)}}
.row:last-child{{border-bottom:0}}
.mut{{color:var(--mut);font-size:13px}}
.big{{font-size:22px;font-weight:700}}
.badge{{display:inline-block;padding:4px 12px;border-radius:999px;color:#fff;font-weight:600;font-size:14px}}
.bar{{height:10px;background:var(--bd);border-radius:99px;overflow:hidden;margin-top:10px}}
.bar>i{{display:block;height:100%;width:{pct}%;background:{color}}}
</style></head><body><div class="wrap">
<h1>🎵 حالة البوت</h1>
<div class="card"><div class="row"><span>الحالة</span>
<span class="badge" style="background:{state_color}">{state}</span></div></div>
<div class="card">
<div class="row"><span>فرق دخلها البوت بتيم كود</span><span class="big">{teams}</span></div>
<div class="row"><span class="mut">اليوم</span><span>{today}</span></div>
<div class="row"><span class="mut">جلسات نشطة الآن</span><span>{active} / {cap}</span></div>
<div class="row"><span class="mut">داخل فرق حالياً</span><span>{in_team}</span></div>
</div>
<div class="card"><div class="row"><span>الضغط على البوت</span>
<span class="badge" style="background:{color}">{label}</span></div>
<div class="bar"><i></i></div><div class="mut" style="margin-top:6px">{pct}%</div></div>
<div class="mut" style="text-align:center">مدة التشغيل: {uptime} • تتحدث الصفحة كل 15 ثانية</div>
</div></body></html>"""


def render_page(s=None):
    s = s or snapshot()
    return PAGE.format(
        pct=s["load_percent"], color=s["load_color"],
        state="يعمل" if s["enabled"] else "متوقف حاليا",
        state_color="#16a34a" if s["enabled"] else "#dc2626",
        teams=s["teams_joined"], today=s["teams_today"], active=s["active_sessions"],
        cap=s["capacity"], in_team=s["in_team"], label=escape(s["load_label"]), uptime=escape(s["uptime"]),
    )


async def _page_handler(request):
    return web.Response(text=render_page(), content_type="text/html", charset="utf-8")


async def _api_handler(request):
    s = snapshot()
    s.pop("load_color", None)
    return web.json_response(s)


_runner = None


async def start_web():
    global _runner
    port = int(os.environ.get("PORT", "8080"))
    app = web.Application()
    app.router.add_get("/", _page_handler)
    app.router.add_get("/api/status", _api_handler)
    app.router.add_get("/health", lambda r: web.Response(text="ok"))
    _runner = web.AppRunner(app)
    await _runner.setup()
    await web.TCPSite(_runner, "0.0.0.0", port).start()
    log.info("status page on port %s", port)


async def stop_web():
    if _runner:
        await _runner.cleanup()


# ───────────── التسجيل ─────────────
def register(app):
    app.add_handler(MessageHandler(filters.COMMAND, gate), group=-1)
    app.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^chk_sub$"))
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    for name, fn in (("off", cmd_off), ("on", cmd_on), ("allow", cmd_allow), ("disallow", cmd_disallow),
                     ("kick", cmd_kick), ("unban", cmd_unban), ("addadmin", cmd_addadmin),
                     ("deladmin", cmd_deladmin), ("admins", cmd_admins), ("groups", cmd_groups),
                     ("status", cmd_status), ("accounts", cmd_accounts),
                     ("reload", cmd_reload), ("addacc", cmd_addacc),
                     ("addchannel", cmd_addchannel), ("delchannel", cmd_delchannel),
                     ("channels", cmd_channels), ("disable", cmd_disable), ("enable", cmd_enable)):
        app.add_handler(CommandHandler(name, fn))
