# -*- coding: utf-8 -*-
"""
SquadBot: جلسة بوت داخل اللعبة
- اتصال الشات والأونلاين (طريقة بوت VOICE_CHAT_REMAKED_OB54 للشات)
- قراءة أوامر اللاعبين من شات الفريق (! أو /)
- تشغيل الصوت عبر VoicePlayer
- أوامر الرقص
"""
import asyncio
import json
import logging
import os
import struct
import time

from proto import HELLXdecode_proto
from chat_proto import HELLXbuild_auth_startup, HELLXbuild_chat_auth, HELLXbuild_chat_message
from voice_player import VoicePlayer
from app_2 import build_ob55_online_auth, JoinSq_original, MahirAccepted
from xC4 import Emote_k, ExiT

log = logging.getLogger("squad_bot")

EMOTE_DELAY = 4.0

EVO_MAP = {
    "scarlet": 909039011, "tiger": 909042008, "woodpecker": 909042008,
    "dreamland": 909051003, "m60": 909051003, "xm8": 909000085,
    "devil": 909000090, "famas": 909000090, "booyahday": 909000098, "ump": 909000098,
    "m4a1": 909033001, "m4": 909033001, "mp40": 909040010, "100lvl": 909042007,
    "throne": 909000014, "heart": 909000045, "love": 909000045,
    "laugh": 909000002, "lol": 909000002, "ak": 909000063, "mp5": 909033002,
    "p90": 909049010, "groza": 909041005, "an94": 909035012, "scar": 909000068,
    "m1887": 909035007, "g18": 909038012, "thompson": 909038010,
    "parafal": 909045001, "namdam": 909037011,
}

HELP_TEXT = (
    "[FF69B4]✨ Welcome back ✨\n"
    "[00FFFF]━━ Commands ━━\n"
    "[FFD700]!play {url / اسم أغنية}\n"
    "[FFD700]!search {كلمات} , !next , !previous , !select {n}\n"
    "[00FF7F]!stop , !resume , !status\n"
    "[00FF7F]!sound {1-200}  ← مستوى الصوت\n"
    "[FF8C00]!dance {اسم/ايدي} [uid]  ← رقصة وحدة\n"
    "[FF8C00]!em [uid ...]  ← كل الرقصات\n"
    "[FF8C00]!evo_list  ← أسماء الرقصات\n"
    "[FF4500]!leave  ← يطلع البوت"
)

EVO_LIST_TEXT = (
    "[FF69B4]» EVO «\n"
    "[FFD700]scarlet 909039011\n"
    "tiger , woodpecker 909042008\n"
    "dreamland , m60 909051003\n"
    "xm8 909000085 , devil , famas 909000090\n"
    "booyahday , ump 909000098\n"
    "m4a1 , m4 909033001 , mp40 909040010\n"
    "100lvl 909042007 , throne 909000014\n"
    "heart , love 909000045 , laugh , lol 909000002\n"
    "[00FFFF]!dance {name or id} [uid]"
)


def _fmt(sec):
    sec = int(max(sec or 0, 0))
    return f"{sec // 60}:{sec % 60:02d}"


def _ytdl_search(query, n=1):
    """يرجع قائمة نتائج [{title,url,channel,duration}]"""
    import yt_dlp
    opts = {"quiet": True, "skip_download": True, "extract_flat": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        if query.startswith(("http://", "https://")):
            info = ydl.extract_info(query, download=False)
            return [{"title": info.get("title") or query,
                     "url": info.get("webpage_url") or query,
                     "channel": info.get("uploader") or info.get("channel") or "",
                     "duration": int(info.get("duration") or 0)}]
        info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    out = []
    for e in info.get("entries") or []:
        out.append({"title": e.get("title") or "?",
                    "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
                    "channel": e.get("uploader") or e.get("channel") or "",
                    "duration": int(e.get("duration") or 0)})
    return out


def load_all_emote_ids():
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
            log.warning("تعذر قراءة %s: %s", name, e)
    return ids


class SquadBot:
    def __init__(self, login, on_close=None, on_joined=None):
        self.login = login
        self.uid = int(login["bot_uid"])
        self.token = login["token"]
        self.key, self.iv = login["key"], login["iv"]
        self.ts = int(login["timestamp"])
        self.region = (login.get("region") or "ME")
        self.name = login.get("account_name") or "Bot"
        self.on_close = on_close
        self.on_joined = on_joined

        self.online_r = self.online_w = None
        self.chat_r = self.chat_w = None
        self._chat_buf = bytearray()
        self._online_buf = bytearray()
        self._tasks = []
        self.closed = False

        self.persistent = False          # يقبل الدعوات ويبقى أونلاين
        self._last_invite = None
        self.owner_uid = None
        self.voice_region_id = None
        self.chat_region_id = None
        self._joined = asyncio.Event()

        self.voice = None
        self._search_results = []
        self._search_query = ""
        self._search_page = 0
        self._em_task = None

    # ───────────── الاتصال ─────────────
    def _spawn(self, coro):
        t = asyncio.create_task(coro)
        self._tasks.append(t)
        return t

    async def connect(self):
        r = self.login
        # الشات: مصادقة البداية (طريقة بوت صاحبك)
        self.chat_r, self.chat_w = await asyncio.wait_for(
            asyncio.open_connection(r["chat_ip"], int(r["chat_port"])), 10)
        self.chat_w.write(bytes.fromhex(
            HELLXbuild_auth_startup(self.uid, self.token, self.ts, self.key, self.iv)))
        await self.chat_w.drain()
        self._spawn(self._chat_read_loop())
        self._spawn(self._keepalive(self.chat_w))
        await asyncio.sleep(1)

        # الأونلاين (OB55)
        auth, _ = build_ob55_online_auth(self.uid, self.token, self.ts, self.key, self.iv)
        self.online_r, self.online_w = await asyncio.wait_for(
            asyncio.open_connection(r["online_ip"], int(r["online_port"])), 10)
        self.online_w.write(auth)
        await self.online_w.drain()
        self._spawn(self._online_read_loop())
        self._spawn(self._keepalive(self.online_w))

        self.voice = VoicePlayer(str(self.uid), region_prefix=self.region.upper(),
                                 ext_region=self.region.lower()[:2], send_chat=self.say)
        self.voice.configure(r.get("login_data_raw"), self.region)

    async def _keepalive(self, writer):
        try:
            while not self.closed and not writer.transport.is_closing():
                await asyncio.sleep(5)
                try:
                    writer.write(bytes.fromhex("0201"))
                    await writer.drain()
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    # ───────────── الانضمام ─────────────
    async def join(self, team_code, timeout=12):
        self._joined.clear()
        self.online_w.write(await JoinSq_original(str(team_code), self.key, self.iv))
        await self.online_w.drain()
        try:
            await asyncio.wait_for(self._joined.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def _on_joined(self, f5):
        """وصلت حزمة الفريق: نربط الشات والصوت ونرسل الترحيب"""
        self.voice_region_id = int(f5.get("17"))
        self.chat_region_id = int(self.voice_region_id / 256 + 0.5) * 256
        try:
            self.owner_uid = int(f5.get("1", self.uid))
        except Exception:
            self.owner_uid = self.uid
        self._joined.set()
        if self.on_joined:
            try:
                self.on_joined()
            except Exception:
                pass
        try:
            self.chat_w.write(HELLXbuild_chat_auth(self.owner_uid, str(self.chat_region_id), self.key, self.iv))
            await self.chat_w.drain()
        except Exception as e:
            log.warning("chat auth failed: %s", e)
        if self.voice:
            self.voice.stop()
            self.voice.voice_region_id = None
            self.voice.start(self.voice_region_id)
        await asyncio.sleep(1.5)
        await self.say(HELP_TEXT)

    async def leave(self):
        try:
            self.online_w.write(await ExiT(None, self.key, self.iv))
            await self.online_w.drain()
        except Exception:
            pass
        self._reset_team()

    def _reset_team(self):
        if self._em_task and not self._em_task.done():
            self._em_task.cancel()
        if self.voice:
            self.voice.stop()
        self.voice_region_id = self.chat_region_id = self.owner_uid = None
        self._last_invite = None
        self._joined.clear()

    @property
    def in_team(self):
        return bool(self.voice_region_id)

    # ───────────── القراءة ─────────────
    async def _online_read_loop(self):
        try:
            while True:
                data = await self.online_r.read(16384)
                if not data:
                    break
                self._online_buf.extend(data)
                await self._drain_frames(self._online_buf, self._on_online_packet)
        except asyncio.CancelledError:
            return
        except Exception as e:
            log.warning("online loop: %s", e)
        await self.close()

    async def _chat_read_loop(self):
        try:
            while True:
                data = await self.chat_r.read(16384)
                if not data:
                    break
                self._chat_buf.extend(data)
                await self._drain_frames(self._chat_buf, self._on_chat_packet)
        except asyncio.CancelledError:
            return
        except Exception as e:
            log.warning("chat loop: %s", e)

    @staticmethod
    async def _drain_frames(buf, handler):
        pos = 0
        while len(buf) - pos >= 5:
            length = struct.unpack(">I", buf[pos + 1:pos + 5])[0]
            if 0 < length < 200000:
                if pos + 5 + length > len(buf):
                    break
                payload = bytes(buf[pos + 5:pos + 5 + length])
                try:
                    pd = HELLXdecode_proto(payload)
                    if pd:
                        await handler(pd)
                except Exception as e:
                    log.warning("packet error: %s", e)
                pos += 5 + length
            else:
                pos += 1
        if pos:
            del buf[:pos]

    async def _on_online_packet(self, pd):
        f5 = pd.get("5")
        if not isinstance(f5, dict):
            return
        # دعوة فريق
        code = f5.get("8")
        if isinstance(code, str) and "_" in code and code != self._last_invite and self.persistent and not self.in_team:
            self._last_invite = code
            try:
                owner = int(f5.get("1", self.uid))
                self.online_w.write(await MahirAccepted(owner, code, self.key, self.iv, self.region))
                await self.online_w.drain()
                log.info("invite accepted code=%s", code)
            except Exception as e:
                log.warning("accept invite failed: %s", e)
        # انضممنا لفريق
        if not self.voice_region_id and f5.get("17"):
            await self._on_joined(f5)

    async def _on_chat_packet(self, pd):
        f5 = pd.get("5")
        if not isinstance(f5, dict):
            return
        sender = str(f5.get("1", ""))
        message = f5.get("4", "")
        msg_type = str(f5.get("3", 0))
        if not isinstance(message, str) or not message.strip():
            return
        if sender == str(self.uid) or msg_type == "2" or not self.in_team:
            return
        name = ""
        f9 = f5.get("9")
        if isinstance(f9, dict):
            name = str(f9.get("1", ""))
        log.info("[%s|%s]: %s", name, sender, message)
        asyncio.create_task(self.handle_command(message.strip(), sender))

    # ───────────── الإرسال ─────────────
    async def say(self, message):
        if not self.chat_w or self.chat_w.transport.is_closing():
            return
        try:
            owner = self.owner_uid or self.uid
            pkt = await HELLXbuild_chat_message(self.uid, owner, message, int(time.time()),
                                                self.key, self.iv, name=self.name)
            self.chat_w.write(pkt)
            await self.chat_w.drain()
        except Exception as e:
            log.warning("send failed: %s", e)

    # ───────────── الأوامر ─────────────
    async def handle_command(self, message, sender_uid=None):
        msg = message.strip()
        if msg.startswith("/") and not msg.startswith("//"):
            msg = "!" + msg[1:]
        if not msg.startswith("!"):
            return
        parts = msg.split()
        cmd = parts[0].lower()
        args = parts[1:]
        try:
            if cmd == "!help":
                await self.say(HELP_TEXT)
            elif cmd == "!play":
                if not args:
                    await self.say("[FF0000]Usage: !play [url / اسم أغنية]")
                    return
                if args[-1].lower() in ("on", "off"):
                    args = args[:-1]
                await self._play_query(" ".join(args))
            elif cmd == "!search":
                if not args:
                    await self.say("[FF0000]Usage: !search [كلمات]")
                    return
                await self._do_search(" ".join(args))
            elif cmd == "!next":
                if not self._search_results:
                    await self.say("[FF0000]No search results. Use !search first.")
                elif self._search_page >= len(self._search_results) - 1:
                    await self.say("[00FFFF]آخر نتيجة.")
                else:
                    self._search_page += 1
                    await self._show_search_page()
            elif cmd in ("!previous", "!prev"):
                if not self._search_results:
                    await self.say("[FF0000]No search results. Use !search first.")
                elif self._search_page <= 0:
                    await self.say("[FF0000]أول نتيجة.")
                else:
                    self._search_page -= 1
                    await self._show_search_page()
            elif cmd == "!select":
                if not args or not args[0].isdigit():
                    await self.say("[FF0000]Usage: !select [number]")
                    return
                idx = int(args[0]) - 1
                if not self._search_results or not (0 <= idx < len(self._search_results)):
                    await self.say("[FF0000]Invalid selection.")
                    return
                await self._play_item(self._search_results[idx])
            elif cmd == "!sound":
                if not args or not args[0].isdigit() or not (1 <= int(args[0]) <= 200):
                    await self.say("[FF0000]Usage: !sound [1-200]")
                    return
                self.voice._volume = int(args[0])
                await self.say(f"[00FFFF]Volume {args[0]}%\n[FFD700]يتغير مع الأغنية الجاية.")
            elif cmd == "!stop":
                await self._stop()
            elif cmd == "!resume":
                await self._resume()
            elif cmd == "!status":
                await self._status()
            elif cmd == "!evo_list":
                await self.say(EVO_LIST_TEXT)
            elif cmd == "!dance":
                await self._dance(args, sender_uid)
            elif cmd == "!em":
                await self._start_em(args, sender_uid)
            elif cmd == "!leave":
                await self.say("[FF4500]⏹ Bye! 👋")
                await asyncio.sleep(1)
                if self.persistent:
                    await self.leave()
                else:
                    await self.close()
        except Exception as e:
            log.warning("command error [%s]: %s", message[:20], e)
            await self.say("[FF0000]صار خطأ، جرب مرة ثانية.")

    # ── موسيقى ──
    async def _play_query(self, query):
        loop = asyncio.get_running_loop()
        await self.say(f"[00FFFF]🔎 {query[:40]}")
        results = await loop.run_in_executor(None, _ytdl_search, query, 1)
        if not results:
            await self.say("[FF0000]❌ ما لقيت الأغنية")
            return
        await self._play_item(results[0])

    async def _play_item(self, item):
        v = self.voice
        v._track_title = item["title"]
        v._track_channel = item.get("channel", "")
        await self.say(f"[00FFFF]⏳ {item['title'][:50]}\n[FFFFFF]{item['url']}")
        asyncio.create_task(self._play_voice(item["url"]))

    async def _play_voice(self, url):
        try:
            await self.voice.play(url)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning("voice play failed: %s", e)
            await self.say("[FF0000]❌ تعذر تشغيل الصوت")

    async def _do_search(self, query):
        loop = asyncio.get_running_loop()
        self._search_query = query
        self._search_results = await loop.run_in_executor(None, _ytdl_search, query, 10)
        self._search_page = 0
        if not self._search_results:
            await self.say("[FF0000]ما لقيت نتائج.")
            return
        await self._show_search_page()

    async def _show_search_page(self):
        i = self._search_page
        r = self._search_results[i]
        await self.say(
            f"[FF69B4]🔎 {i + 1}/{len(self._search_results)}\n"
            f"[FFFFFF]{r['title'][:55]}\n[00FFFF]{r.get('channel', '')[:30]} • {_fmt(r.get('duration'))}\n"
            f"[FFD700]!select {i + 1} للتشغيل , !next , !previous")

    async def _stop(self):
        v = self.voice
        playing = v._udp_task and not v._udp_task.done()
        if self._em_task and not self._em_task.done():
            self._em_task.cancel()
            if not playing:
                await self.say("[FF4500]⏹ تم إيقاف الرقص.")
        if playing:
            v._udp_task.cancel()
            for t in (v._progress_task, v._lyrics_task):
                if t and not t.done():
                    t.cancel()
            v._stopped_frame = v._track_current_frame
            await self.say(
                f"[FF0000]Stopped at {_fmt(v._stopped_frame * 0.02)} / {_fmt(v._track_total_frames * 0.02)}\n"
                f"[FFD700]{v._track_title}\n[00FFFF]!resume للمتابعة")
        elif not (self._em_task and not self._em_task.done()):
            await self.say("[FF0000]ما في شي شغال.")

    async def _resume(self):
        v = self.voice
        if v._current_ogg and v._voice_ip:
            await self.say(f"[00FFFF]▶ {v._track_title}")
            v._udp_task = asyncio.create_task(
                v._voice_udp_loop(v._voice_ip, v._voice_port, ogg_data=v._current_ogg,
                                  start_frame=getattr(v, "_stopped_frame", 0)))
            if v._progress_task and not v._progress_task.done():
                v._progress_task.cancel()
            v._progress_task = asyncio.create_task(v._auto_progress_loop())
        else:
            await self.say("[FF0000]ما في شي أكمله.")

    async def _status(self):
        v = self.voice
        if v._track_title and v._track_total_frames > 0:
            frac = min(v._track_current_frame / v._track_total_frames, 1.0)
            filled = int(18 * frac)
            bar = "[00CED1]" + "▓" * filled + "[555555]" + "░" * (18 - filled)
            playing = v._udp_task and not v._udp_task.done()
            await self.say(
                f"{'[00FF7F]▶' if playing else '[FF0000]⏸'} [FF69B4]{v._track_title[:40]}\n"
                f"{bar}\n[FFFFFF]{_fmt(v._track_current_frame * 0.02)} / {_fmt(v._track_total_frames * 0.02)}"
                f"  [FFD700]Vol:{v._volume}%")
        else:
            await self.say("[FFD700]ما في موسيقى. جرب !play [اسم أغنية]")

    # ── رقص ──
    def _resolve_emote(self, token):
        t = token.lower()
        if t in EVO_MAP:
            return EVO_MAP[t]
        return int(t) if t.isdigit() else None

    async def _dance(self, args, sender_uid):
        if not args:
            await self.say("[FF0000]Usage: !dance {name or id} [uid]")
            return
        eid = self._resolve_emote(args[0])
        if eid is None:
            await self.say(f"[FF0000]رقصة مو معروفة: {args[0]}\n[FFD700]اكتب !evo_list")
            return
        target = int(args[1]) if len(args) > 1 and args[1].isdigit() else int(sender_uid or self.owner_uid or self.uid)
        self.online_w.write(await Emote_k(target, eid, self.key, self.iv, self.region))
        await self.online_w.drain()
        await self.say("[00FFFF]💃 تم إرسال الرقصة.")

    async def _start_em(self, args, sender_uid):
        if self._em_task and not self._em_task.done():
            await self.say("[FF0000]الرقص شغال، اكتب !stop أول.")
            return
        extra = [int(a) for a in args if a.isdigit()]
        if extra:
            targets = extra
        else:
            targets = []
            for t in (sender_uid, self.owner_uid):
                if t and int(t) != self.uid and int(t) not in targets:
                    targets.append(int(t))
        emotes = load_all_emote_ids()
        if not targets or not emotes:
            await self.say("[FF0000]ما لقيت لاعبين أو رقصات.")
            return
        await self.say(f"[FF69B4]💃 بيرقص {len(targets)} لاعب بـ {len(emotes)} رقصة\n[FFD700]!stop للإيقاف")
        self._em_task = asyncio.create_task(self._em_loop(targets, emotes))

    async def _em_loop(self, targets, emotes):
        try:
            for eid in emotes:
                for t in targets:
                    self.online_w.write(await Emote_k(t, eid, self.key, self.iv, self.region))
                    await self.online_w.drain()
                    await asyncio.sleep(0.15)
                await asyncio.sleep(EMOTE_DELAY)
            await self.say("[00FF7F]✅ خلصت كل الرقصات.")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning("em loop: %s", e)

    # ───────────── الإغلاق ─────────────
    async def close(self):
        if self.closed:
            return
        self.closed = True
        self._reset_team()
        for w in (self.online_w, self.chat_w):
            if w:
                try:
                    if w is self.online_w and not w.transport.is_closing():
                        w.write(await ExiT(None, self.key, self.iv))
                        await w.drain()
                except Exception:
                    pass
                try:
                    w.close()
                except Exception:
                    pass
        me = asyncio.current_task()
        for t in self._tasks:
            if t is not me and not t.done():
                t.cancel()
        if self.on_close:
            try:
                self.on_close(self)
            except Exception:
                pass
