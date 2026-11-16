
# -*- coding: utf-8 -*-
"""شكل رسائل تيليجرام: بطاقات مميزة بإيموجيات Custom Emoji"""

import html
import logging
import os
import re

BOT_NAME = os.environ.get("BOT_NAME", "Music Bot")
log = logging.getLogger("ui")


# Custom Emojis - نفس المعرفات الأصلية
EMOJI = {
    "like": '<tg-emoji emoji-id="6037574517423872665">🗿</tg-emoji>',
    "auto": '<tg-emoji emoji-id="5933807141184871381">🗿</tg-emoji>',
    "remove": '<tg-emoji emoji-id="5226431245918942763">🗿</tg-emoji>',
    "list": '<tg-emoji emoji-id="5417875345804108985">🗿</tg-emoji>',
    "status": '<tg-emoji emoji-id="5453957997418004470">🗿</tg-emoji>',
    "welcome": '<tg-emoji emoji-id="5766943869279146835">🗿</tg-emoji>',
    "processing": '<tg-emoji emoji-id="5195417377268836481">🗿</tg-emoji>',
    "done": '<tg-emoji emoji-id="5219899949281453881">🗿</tg-emoji>',
    "error": '<tg-emoji emoji-id="5309981979167463973">🗿</tg-emoji>',
    "warning": '<tg-emoji emoji-id="5766943869279146835">🗿</tg-emoji>',
    "success": '<tg-emoji emoji-id="5219899949281453881">🗿</tg-emoji>',
    "star": '<tg-emoji emoji-id="5219899949281453881">🗿</tg-emoji>',
    "fire": '<tg-emoji emoji-id="5235972142104857532">🗿</tg-emoji>',
    "check": '<tg-emoji emoji-id="6158973086600273462">🗿</tg-emoji>',
    "info": '<tg-emoji emoji-id="5305763947620618616">🗿</tg-emoji>',
    "rocket": '<tg-emoji emoji-id="6077773538708689405">🗿</tg-emoji>',
}


def esc(x):
    return html.escape(str(x), quote=False)


_LEAD = re.compile(r"^[^\w\u0600-\u06FF/]+")


def clean(text):
    return _LEAD.sub("", str(text)).strip()


def card(icon, title, line=None, rows=(), note=None):
    out = [f"╭─ {icon} <b>{esc(title)}</b>"]

    if line:
        for ln in str(line).split("\n"):
            out.append(f"│ {ln}")

    if rows:
        out.append("│")
        for emo, label, val in rows:
            out.append(
                f"│ {emo} {esc(label)} ‹<code>{esc(val)}</code>›"
            )

    out.append(
        f"╰─ <i>{esc(note)}</i>" if note else "╰─"
    )

    return "\n".join(out)


def working(what, detail=None):
    rows = [
        (EMOJI["info"], "الهدف", detail)
    ] if detail else ()

    return card(
        EMOJI["processing"],
        "لحظة",
        esc(what) + " ...",
        rows
    )


def ok(title, line, rows=(), note=None):
    return card(
        EMOJI["success"],
        title,
        esc(line),
        rows,
        note
    )


def err(line, hint=None):
    return card(
        EMOJI["error"],
        "تنبيه",
        EMOJI["warning"] + " " + esc(line),
        (),
        hint
    )


def usage(cmd, args, example):
    return card(
        EMOJI["info"],
        "طريقة الاستخدام",
        f"<code>{esc(cmd)} {esc(args)}</code>",
        [(EMOJI["star"], "مثال", example)]
    )


def stopped(line):
    return card(
        EMOJI["remove"],
        "تم الإيقاف",
        esc(line)
    )


def menu():
    return (
        f"╭─ {EMOJI['welcome']} <b>{esc(BOT_NAME)}</b>\n"
        f"│ {EMOJI['fire']} موسيقى ورقص وفرق لفري فاير\n"
        "│\n"
        f"├ {EMOJI['like']} <b>الموسيقى</b>\n"
        f"│   {EMOJI['rocket']} /music ‹كود_الفريق› [أغنية]\n"
        f"│   {EMOJI['status']} /online  ·  /play  ·  /resume  ·  /stop\n"
        f"│   {EMOJI['auto']} /msgmusic ‹كود› ‹أغنية› | ‹رسالة›\n"
        "│\n"
        f"├ {EMOJI['fire']} <b>الرقص</b>\n"
        f"│   {EMOJI['like']} /em ‹كود_الفريق›\n"
        f"│   {EMOJI['auto']} /dance ‹كود› ‹uid…› ‹رقم›\n"
        f"│   {EMOJI['star']} /evo ‹كود› ‹uid…› ‹رقم›\n"
        "│\n"
        f"├ {EMOJI['rocket']} <b>الفرق</b>\n"
        f"│   {EMOJI['list']} /team3  ·  /team5  ·  /team6  ‹uid›\n"
        f"╰─ <i>داخل اللعبة اكتب !help في شات الفريق</i>"
    )


def admin_menu():
    return (
        f"╭─ {EMOJI['star']} <b>لوحة الأدمن</b>\n"
        "│\n"
        f"├ {EMOJI['fire']} <b>رقص</b>\n"
        f"│   {EMOJI['auto']} /evos ‹كود_الفريق› ‹uid›  ← كل الرقصات بدون توقف\n"
        "│\n"
        f"├ {EMOJI['status']} <b>التحكم</b>\n"
        f"│   {EMOJI['success']} /on  ·  {EMOJI['remove']} /off  ·  /status\n"
        f"│   {EMOJI['warning']} /stopall  ← يوقف كل البوتات ويرجعها متاحة\n"
        "│\n"
        f"├ {EMOJI['list']} <b>المجموعات</b>\n"
        "│   /allow  ·  /disallow  ·  /kick  ·  /unban  ·  /groups\n"
        "│\n"
        f"├ {EMOJI['welcome']} <b>الأدمنية</b>\n"
        "│   /admins  ·  /addadmin  ·  /deladmin\n"
        "│\n"
        f"├ {EMOJI['error']} <b>إيقاف أمر</b>\n"
        "│   /stop ‹أمر›  ·  /enable ‹أمر›  ·  /enable  (القائمة)\n"
        "│\n"
        f"├ {EMOJI['info']} <b>الاشتراك الإجباري</b>\n"
        "│   /addchannel ‹@قناة›  ·  /delchannel  ·  /channels\n"
        "│\n"
        f"├ {EMOJI['like']} <b>الحسابات</b>\n"
        "│   /accounts  ·  /reload  ·  /addacc ‹uid:pass›\n"
        f"╰─ {EMOJI['check']} <i>/stop يوقف أي رقص شغال</i>"
    )


async def reply(message, text):
    return await message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def edit(msg, text):
    try:
        return await msg.edit_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        log.debug("edit skipped: %s", e)
        return None
