# -*- coding: utf-8 -*-
"""
رسائل البوت داخل اللعبة: كل رسالة لها رقم، وتتعدل من تيليجرام بـ /change
(تنحفظ في bot_messages.json بجانب ملف الإعدادات، أو في MESSAGES_PATH)
ألوان اللعبة: [FF0000] أحمر  [00FF7F] أخضر  [FFD700] ذهبي  [00FFFF] سماوي  [FF69B4] وردي  [FFFFFF] أبيض
"""
import json
import logging
import os

log = logging.getLogger("messages")

_CFG_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_config.json")
PATH = os.environ.get("MESSAGES_PATH") or os.path.join(
    os.path.dirname(os.environ.get("CONFIG_PATH", _CFG_DEFAULT)), "bot_messages.json")

# (المفتاح، الوصف، النص الافتراضي، المتغيرات المسموحة). الرقم = ترتيبه في القائمة
CATALOG = [
    ("help", "قائمة الأوامر (!help)",
     "[FF69B4]🎵 أوامر الموسيقى 🎵\n[FFD700]!play اسم أغنية  ← بحث وتشغيل\n[FFD700]!play رابط  ← تشغيل من رابط\n"
     "[FFD700]!search كلمات  ← عرض نتائج البحث\n[FFFFFF]!next / !previous  ← تنقل بين النتائج\n"
     "[FFFFFF]!select رقم  ← تشغيل نتيجة\n[00FF7F]!stop  ← إيقاف مؤقت\n[00FF7F]!resume  ← متابعة\n"
     "[00FF7F]!status  ← الأغنية الحالية\n[00FF7F]!sound 1-200  ← مستوى الصوت\n[FF8C00]!dance اسم/رقم  ← رقصة\n"
     "[FF8C00]!em  ← كل الرقصات\n[FF8C00]!evo_list  ← أسماء الرقصات\n[FF8C00]!5 / !3 / !6  ← ينشئ فريق ويدعوك\n"
     "[FF4500]!leave  ← خروج البوت", ()),
    ("play_usage", "طريقة !play لو كتبه بدون اسم",
     "[FF0000]اكتب كذا:\n[FFD700]!play اسم الأغنية\n[FFD700]!play رابط يوتيوب", ()),
    ("searching", "جاري البحث عن الأغنية",
     "[00FFFF]🔎 جاري البحث عن أغنية...\n[FFFFFF]{query}", ("query",)),
    ("not_found", "ما لقى الأغنية", "[FF0000]❌ ما لقيت الأغنية، جرب اسم ثاني", ()),
    ("found_loading", "لقى الأغنية وجاري التحميل",
     "[00FF7F]✅ لقيتها:\n[FFFFFF]{title}\n[FFD700]⏳ جاري التحميل... انتظر شوي", ("title",)),
    ("now_playing", "بدأ التشغيل",
     "[00FF7F]▶ يشتغل الآن\n[5427F5]{title}\n[A627F5]{channel}", ("title", "channel")),
    ("voice_connecting", "جاري الاتصال بالصوت", "[27EBF5]⏳ جاري الاتصال بالصوت... انتظر", ()),
    ("voice_failed", "فشل الاتصال بالصوت", "[F52727]❌ فشل الاتصال بالصوت، جرب !play مرة ثانية", ()),
    ("download_failed", "فشل تحميل الأغنية", "[F52727]❌ فشل التحميل: {error}", ("error",)),
    ("play_failed", "تعذر تشغيل الصوت", "[FF0000]❌ تعذر تشغيل الصوت، جرب مرة ثانية", ()),
    ("stopped", "إيقاف مؤقت للأغنية",
     "[FF0000]Stopped at {pos} / {total}\n[FFD700]{title}\n[00FFFF]!resume للمتابعة", ("pos", "total", "title")),
    ("resumed", "متابعة الأغنية", "[00FFFF]▶ {title}", ("title",)),
    ("nothing_playing", "ما في شي شغال", "[FF0000]ما في شي شغال.", ()),
    ("nothing_to_resume", "ما في شي يكمله", "[FF0000]ما في شي أكمله.", ()),
    ("no_music", "!status وما في موسيقى", "[FFD700]ما في موسيقى. جرب !play [اسم أغنية]", ()),
    ("volume", "تغيير مستوى الصوت", "[00FFFF]Volume {volume}%\n[FFD700]يتغير مع الأغنية الجاية.", ("volume",)),
    ("usage_sound", "طريقة !sound", "[FF0000]Usage: !sound [1-200]", ()),
    ("search_none", "البحث ما رجع نتائج", "[FF0000]ما لقيت نتائج.", ()),
    ("search_page", "نتيجة بحث",
     "[FF69B4]🔎 {i}/{n}\n[FFFFFF]{title}\n[00FFFF]{channel} • {duration}\n[FFD700]!select {i} للتشغيل , !next , !previous",
     ("i", "n", "title", "channel", "duration")),
    ("usage_search", "طريقة !search", "[FF0000]Usage: !search [كلمات]", ()),
    ("usage_select", "طريقة !select", "[FF0000]Usage: !select [number]", ()),
    ("invalid_selection", "رقم نتيجة غلط", "[FF0000]Invalid selection.", ()),
    ("no_results_yet", "!next أو !previous قبل البحث", "[FF0000]No search results. Use !search first.", ()),
    ("last_result", "آخر نتيجة", "[00FFFF]آخر نتيجة.", ()),
    ("first_result", "أول نتيجة", "[FF0000]أول نتيجة.", ()),
    ("usage_dance", "طريقة !dance", "[FF0000]Usage: !dance [name or id] [uid]", ()),
    ("dance_unknown", "رقصة مو معروفة", "[FF0000]رقصة مو معروفة: {name}\n[FFD700]اكتب !evo_list", ("name",)),
    ("dance_sent", "تم إرسال الرقصة", "[00FFFF]💃 تم إرسال الرقصة.", ()),
    ("dance_busy", "الرقص شغال", "[FF0000]الرقص شغال، اكتب !stop أول.", ()),
    ("dance_none", "ما في لاعبين أو رقصات", "[FF0000]ما لقيت لاعبين أو رقصات.", ()),
    ("dance_started", "بدأ رقص كل الرقصات",
     "[FF69B4]💃 بيرقص {players} لاعب بـ {count} رقصة\n[FFD700]!stop للإيقاف", ("players", "count")),
    ("dance_done", "خلصت كل الرقصات", "[00FF7F]✅ خلصت كل الرقصات.", ()),
    ("dance_stopped", "إيقاف الرقص", "[FF4500]⏹ تم إيقاف الرقص.", ()),
    ("team_creating", "جاري إنشاء فريق", "[00FFFF]🔄 جاري إنشاء فريق {size} لاعبين...", ("size",)),
    ("no_id", "ما قدر يعرف ايدي اللاعب", "[FF0000]ما قدرت أعرف ايديك", ()),
    ("bye", "عند !leave", "[FF4500]⏹ Bye! 👋", ()),
    ("idle_leave", "يطلع بسبب عدم النشاط", "[FFD700]ما في نشاط، بطلع من الفريق 👋", ()),
    ("error_generic", "خطأ عام", "[FF0000]صار خطأ، جرب مرة ثانية.", ()),
    ("friend_help", "قائمة أوامر البوت الصديق (/help في الخاص)",
     "[FF69B4]🤖 بوت صديق\n[FFD700]/3 /5 /6  ← ينشئ فريق ويدعوك\n[FFD700]/dance كود uid... رقم  ← رقصة للاعبين\n"
     "[FFD700]/evo كود uid... رقم  ← رقصة إيفو\n[00FF7F]/evos كود uid  ← كل الرقصات بدون توقف (للأدمن)\n"
     "[00FF7F]/stop  ← إيقاف /evos\n[FFFFFF]ادعُني لفريقك واكتب !help للموسيقى", ()),
    ("friend_working", "البوت الصديق: جاري التنفيذ", "[00FFFF]🔄 {text}", ("text",)),
    ("friend_ok", "البوت الصديق: تم", "[00FF7F]✅ {text}", ("text",)),
    ("friend_fail", "البوت الصديق: فشل", "[FF0000]❌ {text}", ("text",)),
    ("friend_usage_dance", "البوت الصديق: صيغة /dance و /evo",
     "[FF0000]الصيغة: /{name} كود_الفريق uid1 uid2 رقم_الرقصة", ("name",)),
    ("friend_usage_evos", "البوت الصديق: صيغة /evos", "[FF0000]الصيغة: /evos كود_الفريق uid", ()),
    ("friend_no_admin", "البوت الصديق: أمر للأدمن فقط", "[FF0000]هذا الأمر للأدمن فقط", ()),
    ("private_help", "رد البوت على الخاص",
     "[B][C][FF69B4]أهلاً! أنا بوت موسيقى 🎵\n[B][C][FFD700]ادعُني لفريقك، وبعد ما أدخل اكتب !help في شات الفريق\n"
     "[B][C][00FF7F]/5 /3 /6 ← أنشئ لك فريق وأدعوك", ()),
]

_INDEX = {c[0]: i for i, c in enumerate(CATALOG)}
_over = {}


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def load():
    global _over
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _over = {k: v for k, v in data.items() if k in _INDEX and isinstance(v, str)}
    except FileNotFoundError:
        _over = {}
    except Exception as e:
        log.warning("messages load failed: %s", e)
        _over = {}


def save():
    try:
        os.makedirs(os.path.dirname(PATH) or ".", exist_ok=True)
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(_over, f, ensure_ascii=False, indent=1)
        return True
    except Exception as e:
        log.warning("messages save failed: %s", e)
        return False


def text(key):
    """النص الحالي (المعدّل أو الافتراضي) بدون تعبئة المتغيرات"""
    return _over.get(key, CATALOG[_INDEX[key]][2])


def t(key, **kw):
    tpl = text(key)
    try:
        return tpl.format_map(_Safe(kw))
    except Exception:
        return tpl


def count():
    return len(CATALOG)


def info(num):
    """(key, label, default, allowed_vars) لرقم الرسالة (يبدأ من 1) أو None"""
    if not (1 <= num <= len(CATALOG)):
        return None
    return CATALOG[num - 1]


def is_modified(key):
    return key in _over


def validate(num, new_text):
    """يرجع رسالة خطأ أو None. نمنع المتغيرات الغير معروفة للرسالة"""
    import string
    allowed = set(info(num)[3])
    try:
        names = {f[1] for f in string.Formatter().parse(new_text) if f[1] is not None}
    except ValueError:
        return "الأقواس { } غير متوازنة"
    bad = sorted(n for n in names if n not in allowed)
    if bad:
        ok = ", ".join("{" + a + "}" for a in allowed) or "ما فيها متغيرات"
        return "متغير غير مسموح: " + ", ".join("{" + b + "}" for b in bad) + f"\nالمتاح لهذي الرسالة: {ok}"
    return None


def set_text(num, new_text):
    key = CATALOG[num - 1][0]
    _over[key] = new_text
    return save()


def reset(num):
    key = CATALOG[num - 1][0]
    _over.pop(key, None)
    return save()


load()
