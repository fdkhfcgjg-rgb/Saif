# -*- coding: utf-8 -*-
"""
accounts.py: مخزن حسابات البوت
حسابات الموسيقى في ملف accent.txt (كل سطر  uid:pass). الحساب الأساسي منفصل في acces.txt
وممكن كمان من متغير البيئة ACCOUNTS (أسطر أو فواصل ،  uid:pass).
كل جلسة تاخذ حساب فاضي، وترجعه لما تخلص.
"""
import logging
import os
import random
import time

log = logging.getLogger("accounts")

BASE = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.environ.get("ACCOUNTS_FILE", os.path.join(BASE, "accent.txt"))
DEFAULT_REGION = os.environ.get("FF_REGION", "ME")
MAX_FAILS = 3          # بعد كم فشل تسجيل دخول متتالي نوقف الحساب مؤقتاً
COOLDOWN = int(os.environ.get("ACCOUNT_COOLDOWN_SECONDS", "300"))   # مدة الإيقاف المؤقت، وبعدها يرجع تلقائياً


def parse_line(line):
    line = line.strip().lstrip("\ufeff")
    if not line or line.startswith("#") or ":" not in line:
        return None
    uid, pw = line.split(":", 1)
    uid, pw = uid.strip(), pw.strip()
    if not uid.isdigit() or not pw:
        return None
    return {"uid": uid, "password": pw, "region": DEFAULT_REGION}


class AccountPool:
    def __init__(self):
        self.accounts = []
        self.in_use = set()
        self.fails = {}
        self.cool_until = {}        # uid -> وقت رجوع الحساب بعد الإيقاف المؤقت
        self.reserved = set()      # حسابات محجوزة (الحساب الأساسي) ما تدخل المخزن
        self._next = 0
        self.reload()

    def reload(self):
        found, seen = [], set()
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except FileNotFoundError:
            lines = []
        except Exception as e:
            log.warning("read accounts file failed: %s", e)
            lines = []
        env = os.environ.get("ACCOUNTS", "")
        for chunk in env.replace(",", "\n").replace(";", "\n").splitlines():
            lines.append(chunk)
        for line in lines:
            acc = parse_line(line)
            if acc and acc["uid"] not in seen:
                seen.add(acc["uid"])
                found.append(acc)
        self.accounts = found
        self.fails = {u: n for u, n in self.fails.items() if u in seen}
        self.in_use &= seen | self.in_use      # لا نفقد حسابات شغالة حالياً
        log.info("accounts loaded: %d", len(found))
        return len(found)

    def _cooling(self, uid):
        t = self.cool_until.get(uid)
        if t is None:
            return False
        if time.time() >= t:                 # انتهى الإيقاف: الحساب يرجع للمخزن
            self.cool_until.pop(uid, None)
            self.fails.pop(uid, None)
            log.info("account ...%s back in pool after cooldown", uid[-4:])
            return False
        return True

    def usable(self):
        return [a for a in self.accounts
                if not self._cooling(a["uid"]) and a["uid"] not in self.reserved]

    def acquire(self):
        """يرجع حساب عشوائي من الحسابات الفاضية (أو None إذا الكل مشغول)"""
        free = [a for a in self.usable() if a["uid"] not in self.in_use]
        if not free:
            return None
        acc = random.choice(free)
        self.in_use.add(acc["uid"])
        return acc

    def release(self, uid):
        self.in_use.discard(str(uid))

    def report_ok(self, uid):
        self.fails.pop(str(uid), None)
        self.cool_until.pop(str(uid), None)

    def report_fail(self, uid):
        uid = str(uid)
        self.fails[uid] = self.fails.get(uid, 0) + 1
        if self.fails[uid] >= MAX_FAILS:
            self.cool_until[uid] = time.time() + COOLDOWN
            log.warning("account ...%s paused for %ds after %d login failures", uid[-4:], COOLDOWN, self.fails[uid])

    def add(self, uid, password):
        acc = parse_line(f"{uid}:{password}")
        if not acc:
            return False
        if any(a["uid"] == acc["uid"] for a in self.accounts):
            return None            # موجود من قبل
        try:
            with open(ACCOUNTS_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n{acc['uid']}:{acc['password']}")
        except Exception as e:
            log.warning("append account failed: %s", e)
        self.accounts.append(acc)
        return True

    def stats(self):
        usable = self.usable()
        bad = len(self.accounts) - len(usable)
        busy = len([a for a in usable if a["uid"] in self.in_use])
        return {"total": len(self.accounts), "usable": len(usable), "busy": busy,
                "free": len(usable) - busy, "bad": bad}


pool = AccountPool()
