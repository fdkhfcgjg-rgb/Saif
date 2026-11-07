# -*- coding: utf-8 -*-
"""مشغّل الصوت (مستخرج من بوت VOICE_CHAT_REMAKED_OB54)
يتصل بسيرفر صوت الفريق ويرسل الأغنية كصوت Opus.
الاستخدام:
    vp = VoicePlayer(uid, region_prefix="ME", send_chat=async_fn(msg))
    vp.start(voice_region_id)          # من حقل 17 في حزمة الفريق
    await vp.play(url_or_search)       # يشغّل الأغنية
    vp.stop()
"""
import asyncio
import struct
import time
import re
import os
import json
import random
import shutil
import sys

from proto import HELLXdecode_proto, HELLXenc_varint, HELLXcreate_proto

def HELLXlog(tag, message):
    print(f"{tag} = > {message}")

import struct as _struct
import time as _time

import struct as _struct
_VOICE_BASE_HEX = (
    '0a8e01'
    '0811100b180122'
    '04534f4e59'
    '2a013930cc80868c02'
    '3a0b61726d65616269'
    '2d763761'
    '4200'
    '4a2438323934386166322d313737392d346438372d613864352d356237363962376365623934'
    '522a464644353846423446373646363438433241354532314542434641334141453831423443394237443937'
    '5a05766f696365'
    '62075851'
    '2d42453432'
    '6802'
    '720471636f6d'
    '100b'
)
_STEP1_FIXED128_HEX = (
    '69839458c071310bbc7e2eede4101c55f0e8c682102c5b100c79'
    '291ae9800ad21d16f7a4e484d4c09f5960f58d00a576128a7bad'
    '036fe886b369e6e2e07ad339be2d93f40eb37e640790972809ea'
    '078b24540912ca6dd3f54183ac721db4c50cd3703941'
    '9f467a430d9429eeee04ead8b83073e54e45a51e0d33b9b273fd2942'
)
def _make_voice_packet(pkt_type: int, region_id: int, uid: str) -> bytes:
    RAW = bytearray(bytes.fromhex(_VOICE_BASE_HEX))
    RAW[4] = pkt_type
    return _struct.pack('>I', len(RAW)) + bytes(RAW)
def HELLXbuild_voice_step1(uid: str, region_id: int) -> bytes:
    base = bytearray(bytes.fromhex(_VOICE_BASE_HEX))
    base[4] = 0x00
    fixed128 = bytes.fromhex(_STEP1_FIXED128_HEX)
    payload = bytes(base) + b'\x12\x80\x01' + fixed128 + b'\x18\x01\x20\x06\x38\x01'
    return _struct.pack('>I', len(payload)) + payload
def HELLXbuild_voice_auth(uid: str, region_id: int, voice_port: int, region_prefix: str = "EUROPE") -> bytes:
    base = bytearray(bytes.fromhex(_VOICE_BASE_HEX))
    base[4] = 0x07
    device_id = "FFD58FB4F76F648C2A5E21EBCFA3AAE81B4C9B7D97"
    region_str = f"{region_prefix}_{region_id}"
    field2_str = (device_id + region_str).encode()
    uid_b = uid.encode()
    field2_len = len(field2_str)
    field2_len_varint = bytes([field2_len]) if field2_len < 128 else bytes([0x80 | (field2_len & 0x7F), field2_len >> 7])
    payload = (
        bytes(base) +
        b'\x12' + field2_len_varint + field2_str +
        bytes.fromhex('20052801' '30d008' '380040005001') +
        b'\x5a' + bytes([len(uid_b)]) + uid_b +
        bytes.fromhex('60007000800101')
    )
    return _struct.pack('>I', len(payload)) + payload
def HELLXbuild_voice_ping(uid: str, region_id: int, voice_port: int, session_id: int = 0x0b) -> bytes:
    base = bytearray(bytes.fromhex(_VOICE_BASE_HEX))
    base[4] = 0x09
    base_bytes = bytes(base[:-2])
    session_varint = HELLXenc_varint(session_id)
    payload = base_bytes + b'\x10' + session_varint
    return _struct.pack('>I', len(payload)) + payload
def HELLXbuild_voice_stat_report(uid: str, region_id: int, session_id: int, region_prefix: str = "EUROPE") -> bytes:
    base = bytearray(bytes.fromhex(_VOICE_BASE_HEX))
    base[4] = 0x38
    base_bytes = bytes(base[:-2])
    region_str = f"{region_prefix}_{region_id}".encode()
    session_varint = HELLXenc_varint(session_id)
    payload = (
        base_bytes +
        b'\x10' + session_varint +
        b'\x1a\x40' + b'FFD58FB4F76F648C2A5E21EBCFA3AAE81B4C9B7D97'.encode() +
        region_str
    )
    return _struct.pack('>I', len(payload)) + payload
def HELLXbuild_voice_broadcast_sub(uid: str, region_id: int, session_id: int, region_prefix: str = "EUROPE") -> bytes:
    base = bytearray(bytes.fromhex(_VOICE_BASE_HEX))
    base[4] = 0x37
    base_bytes = bytes(base[:-2])
    region_str = f"{region_prefix}_{region_id}".encode()
    session_varint = HELLXenc_varint(session_id)
    payload = (
        base_bytes +
        b'\x10' + session_varint +
        b'\x1a\x40' + b'FFD58FB4F76F648C2A5E21EBCFA3AAE81B4C9B7D97'.encode() +
        region_str +
        b'\x22\x03all'
    )
    return _struct.pack('>I', len(payload)) + payload
def HELLXbuild_voice_join(uid: str, region_id: int, counter: int, voice_secret: str, chat_key: str, region_prefix: str = "EUROPE") -> bytes:
    base = bytearray(bytes.fromhex(_VOICE_BASE_HEX))
    base[4] = 0x18
    device_id = "FFD58FB4F76F648C2A5E21EBCFA3AAE81B4C9B7D97"
    region_str = f"{region_prefix}_{region_id}"
    field2_str = (device_id + region_str).encode()
    uid_b = uid.encode()
    uid_last3 = uid.zfill(11)[-3:].encode()
    field2_len = len(field2_str)
    field2_len_varint = bytes([field2_len]) if field2_len < 128 else bytes([0x80 | (field2_len & 0x7F), field2_len >> 7])
    flag = b'\x01' if counter == 0 else b'\x00'
    payload = (
        bytes(base) +
        b'\x12' + field2_len_varint + field2_str +
        bytes.fromhex('20052801' '30d008' '380040005001') +
        b'\x5a' + bytes([len(uid_b)]) + uid_b +
        bytes.fromhex('60007000800101') +
        b'\x1a\x0b' + uid_last3 +
        bytes([0x20, counter & 0xFF, 0x28]) + flag
    )
    return _struct.pack('>I', len(payload)) + payload
def HELLXbuild_voice_auth_device(uid: str, region_id: int) -> bytes:
    payload = bytearray()
    payload.append(0x01)
    payload.append(0x0a)
    device_model = b"samsung"
    payload.append(len(device_model))
    payload.extend(device_model)
    payload.append(0x12)
    device_info = b"SM-S9210"
    payload.append(len(device_info))
    payload.extend(device_info)
    length = len(payload)
    return _struct.pack('>I', length) + bytes(payload)
import time as _time
_VOICE_CUSTOM_MAGIC = bytes.fromhex('feffffff04b50001')
def HELLXbuild_voice_custom(uid: str, region_id: int, uuid: str = "f687ba460e-9b6b8bc39",
                              device_id: str = "F76F648CCFA3AAE897",
                              mcu_ip: str = "0.0.0.0",
                              region_prefix: str = "EUROPE") -> bytes:
    uid_str = uid.zfill(11)
    uid_last3 = uid_str[-3:].encode()
    region_str = f"{region_prefix}_{region_id}".encode()
    uuid_b = uuid.encode()
    device_b = device_id.encode()
    local_ip = b"0.0.0.0"
    mcu_ip_b = mcu_ip.encode()
    ts = int(_time.time()) & 0xFFFFFFFF
    pkt = bytearray()
    pkt.extend(_VOICE_CUSTOM_MAGIC)
    pkt.extend(b'\x00\x24')
    pkt.extend(uuid_b); pkt.append(0)
    pkt.extend(b'\x00\x2a')
    pkt.extend(device_b); pkt.append(0)
    pkt.extend(b'\x00\x1a')
    pkt.extend(region_str); pkt.append(0)
    pkt.extend(b'\x00\x0b')
    pkt.extend(uid_last3); pkt.extend(b'\x00\x00\x00\x00')
    pkt.extend(b'\x28\x2e\x30\x00')
    pkt.append(0x07)
    pkt.extend(local_ip); pkt.extend(b'\x00')
    pkt.append(0x0d)
    pkt.extend(mcu_ip_b); pkt.extend(b'\x00')
    pkt.extend(b'\x17\x76')
    pkt.extend(_struct.pack('>I', ts))
    pkt.extend(b'\x00\x00\x00\x00')
    return _struct.pack('>I', len(pkt)) + bytes(pkt)
def HELLXparse_voice_custom_response(data: bytes):
    if len(data) > 4 and data[4:8] == b'\xfe\xff\xff\x7f':
        data = data[4:]
    if not data.startswith(b'\xfe\xff\xff\x7f'):
        return None
    import re
    matches = re.findall(rb'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', data)
    for m in matches:
        parts = m.split(b'.')
        if all(0 <= int(p) <= 255 for p in parts) and parts[0] not in (b'0', b'1'):
            return m.decode()
    return None
def HELLXbuild_voice_redirect(uid: str, region_id: int, region_prefix: str = "EUROPE", ext_region: str = "de") -> bytes:
    device_id = "FFD58FB4F76F648C2A5E21EBCFA3AAE81B4C9B7D97"
    region_str = f"{region_prefix}_{region_id}"
    field1 = (device_id + region_str).encode()
    base = bytes.fromhex(_VOICE_BASE_HEX)
    inner = bytearray(base[3:3+142])
    inner[1] = 0x11
    ext_b = ext_region.encode()
    payload = bytearray()
    payload.append(0x0a)
    payload.append(len(field1))
    payload.extend(field1)
    payload.append(0x12)
    payload.append(0x8e); payload.append(0x01)
    payload.extend(inner)
    payload.append(0x18); payload.append(0x02)
    payload.append(0x22); payload.append(len(ext_b))
    payload.extend(ext_b)
    return _struct.pack('>I', len(payload)) + bytes(payload)


def _yt_dlp_command():
    return [sys.executable, "-m", "yt_dlp"]

def _ffmpeg_executable():
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise FileNotFoundError(
            "ffmpeg is not installed. Install imageio-ffmpeg or add ffmpeg to PATH."
        ) from exc

def _ogg_opus_frames(stream):
    buf = b''
    while True:
        chunk = stream.read(4096)
        if not chunk:
            break
        buf += chunk
        buf, frames = _parse_ogg_buf(buf)
        yield from frames
def _ogg_opus_frames_bytes(data: bytes):
    _, frames = _parse_ogg_buf(data, drain_all=True)
    yield from frames
def _parse_ogg_buf(buf: bytes, drain_all=False):

    frames = []
    while True:
        pos = buf.find(b'OggS')
        if pos == -1:
            buf = buf[-3:] if len(buf) >= 3 else buf
            break
        if len(buf) < pos + 27:
            break
        n_segs = buf[pos + 26]
        header_end = pos + 27 + n_segs
        if len(buf) < header_end:
            break
        seg_table = buf[pos + 27: header_end]
        page_size = sum(seg_table)
        if len(buf) < header_end + page_size:
            break
        page_data = buf[header_end: header_end + page_size]
        buf = buf[header_end + page_size:]
        if page_data[:8] in (b'OpusHead', b'OpusTags'):
            continue
        off = 0
        for s in seg_table:
            frame = page_data[off: off + s]
            off += s
            if len(frame) >= 4:
                frames.append(frame)
    return buf, frames

class VoicePlayer:
    def __init__(self, uid, region_prefix="ME", ext_region="ME", send_chat=None):
        self.uid = uid
        self.region_prefix = region_prefix
        self.ext_region = ext_region
        self._send_chat = send_chat
        self.voice_region_id = None
        self.voice_port = None
        self.voice_session_ts = None
        self._sdk_verify_domain = "ff.rtc.grtc.garenanow.com"
        self._voice_f5 = 0
        self._voice_f3 = 0x13e6
        self._voice_writer = None
        self._voice_reader = None
        self._voice_ping_task = None
        self._voice_connect_task = None
        self._voice_ip = None
        self._voice_port = None
        self._udp_task = None
        self._voice_ssrc_refresh = False
        self.opus_bitrate = 18000
        self._current_url = None
        self._current_ogg = None
        self._track_title = ""
        self._track_channel = ""
        self._track_total_frames = 0
        self._track_current_frame = 0
        self._progress_task = None
        self._stopped_frame = 0
        self._volume = 100
        self._lyrics_enabled = False
        self._lyrics_data = []
        self._lyrics_task = None

    async def _send_chat_message(self, message):
        if self._send_chat:
            try:
                await self._send_chat(message)
            except Exception:
                pass

    async def _lyrics_loop(self):
        return

    def configure(self, login_data_raw=None, region=None):
        """يضبط إعدادات الصوت من رد GetLoginData ومن اسم المنطقة (مثل ما يسوي بوت صاحبك)"""
        if login_data_raw:
            try:
                from voice import HELLXextract_garena_voice_data
                vd = HELLXextract_garena_voice_data(login_data_raw)
                for entry in vd["idc_servers"]:
                    ip, port = entry["ip_port"].split(":")
                    if entry["idc"] == "IDC2":
                        self.voice_port = int(port)
                    elif self.voice_port is None:
                        self.voice_port = int(port)
                w = vd.get("webrtc")
                if w and w.get("domains"):
                    self._sdk_verify_domain = w["domains"][0]
            except Exception as e:
                HELLXlog("VOICE", f"configure failed: {e}")
        if region and isinstance(region, str) and region.isalpha():
            self.region_prefix = region.upper()
            m = {'EUROPE': 'eu', 'VN': 'vn', 'SA': 'sa', 'BR': 'br', 'ID': 'id', 'TW': 'tw', 'TH': 'th',
                 'SG': 'sg', 'ME': 'me', 'IND': 'in', 'NA': 'na', 'LATAM': 'la'}
            self.ext_region = m.get(self.region_prefix, self.region_prefix.lower()[:2])

    def start(self, voice_region_id):
        """يبدأ الاتصال بالصوت بعد الانضمام للفريق"""
        self.voice_region_id = int(voice_region_id)
        if not self._voice_connect_task or self._voice_connect_task.done():
            self._voice_connect_task = asyncio.create_task(self._voice_connect())

    async def play(self, url):
        await self._play_yt(url)

    def stop(self):
        for t in (self._udp_task, self._progress_task, self._voice_ping_task, self._voice_connect_task):
            if t and not t.done():
                t.cancel()
        w = self._voice_writer
        if w:
            try:
                w.close()
            except Exception:
                pass
        self._voice_ip = self._voice_port = None

    async def _voice_connect(self):
        if not self.voice_region_id:
            HELLXlog("VOICE", "ERROR: No region_id")
            return
        self._voice_f5 = 0
        self._voice_f3 = 0x13e6
        import re as _re
        import aiohttp as _aiohttp
        import struct as _st2

        async def _read_voice_frame(reader, timeout):
            header = await asyncio.wait_for(reader.readexactly(4), timeout)
            frame_length = _st2.unpack('>I', header)[0]
            if frame_length <= 0 or frame_length > 65536:
                raise ValueError(f"invalid voice frame length: {frame_length}")
            return await asyncio.wait_for(reader.readexactly(frame_length), timeout)

        sdk_token = None
        redirect_ip, redirect_port = None, None
        SDK_VERIFY_URL = f"https://{self._sdk_verify_domain}/sdk/sdk_verify"
        _SDK_VERIFY_PAYLOAD = bytes.fromhex(
            '0a8e010800100b180122074f6e65506c75732a013930cc80868c023a0961726d3634'
            '2d76386142004a2439313864346563382d383733332d343930622d626334362d643132'
            '666139396337383238522a464644353846423446373646363438433241354532314542'
            '4346413341414538314234433942374439375a05766f69636562064e45323231316802'
            '720471636f6d12800160ad4251d2f821e2701e5e1d8b607d2b34dcb0c512300ac3e5839'
            '6155780dc64686b20d05581c038ae28539fc3bc21ced330e31721e18e6c626972829f'
            '6878cb8ec7d95f2f7391bd25f9d7296f09f56f9bc5bccabaf10f09b58c39dc02c08995'
            'd6abe727d93bcea4123da86ad42f6500fa68e74ddc2ed2cb7af0aadd22d2ec93180120'
            '063800'
        )

        def _parse_sdk_response(data):
            nonlocal sdk_token, redirect_ip, redirect_port
            if len(data) < 4:
                return
            _vproto = HELLXdecode_proto(data)
            _f5 = _vproto.get('5')
            _candidates = _f5 if isinstance(_f5, list) else ([_f5] if _f5 else [])
            for _r in _candidates:
                if isinstance(_r, bytes):
                    _r = HELLXdecode_proto(_r)
                if isinstance(_r, dict):
                    _rip = _r.get('1')
                    _rport = _r.get('2')
                    if isinstance(_rip, str) and '.' in _rip and _rport:
                        redirect_ip = _rip
                        redirect_port = int(_rport)
                        HELLXlog("VOICE", f"SDK verify redirect: {redirect_ip}:{redirect_port}")
                        break
            import re as _re2
            if not redirect_ip:
                m_ip = _re2.search(rb'([\d]{1,3}\.[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3})', data)
                m_port = _re2.search(rb'\x10([\x80-\xff]?.)', data[data.find(b'\x0a\x0d') + 15:] if b'\x0a\x0d' in data else b'')
                if m_ip:
                    redirect_ip = m_ip.group(1).decode()
                    HELLXlog("VOICE", f"SDK verify redirect (regex): {redirect_ip}")
                if not redirect_port and m_port:
                    _pb = m_port.group(1)
                    if len(_pb) == 1:
                        redirect_port = _pb[0]
                    elif len(_pb) == 2 and _pb[0] & 0x80:
                        redirect_port = (_pb[0] & 0x7f) | (_pb[1] << 7)
            m_opus = _re2.search(rb'OPUS_BITRATE[\x00-\x20]{0,8}(\d{4,6})', data)
            if m_opus:
                _brate = int(m_opus.group(1).decode())
                if 8000 <= _brate <= 64000:
                    self.opus_bitrate = _brate
                    HELLXlog("VOICE", f"OPUS_BITRATE from server: {_brate}")
            _pos = 0
            while _pos < len(data) - 2:
                if data[_pos] == 0x12:
                    _p2 = _pos + 1; _vlen = 0; _shift = 0
                    while _p2 < len(data):
                        _b = data[_p2]; _vlen |= (_b & 0x7F) << _shift; _p2 += 1; _shift += 7
                        if not (_b & 0x80): break
                    if _vlen == 128 and _p2 + 128 <= len(data):
                        sdk_token = data[_p2:_p2 + 128]
                        break
                _pos += 1
            HELLXlog("VOICE", f"SDK token: {sdk_token.hex()[:32] if sdk_token else 'None'}")

        try:
            _ssl_ctx = __import__('ssl').create_default_context()
            _ssl_ctx.check_hostname = False
            _ssl_ctx.verify_mode = __import__('ssl').CERT_NONE
            async with _aiohttp.ClientSession() as _sess:
                async with _sess.post(
                    SDK_VERIFY_URL,
                    data=_SDK_VERIFY_PAYLOAD,
                    headers={
                        "Host": self._sdk_verify_domain,
                        "Accept": "*/*",
                        "Accept-Encoding": "identity",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Content-Length": str(len(_SDK_VERIFY_PAYLOAD)),
                    },
                    ssl=_ssl_ctx,
                    timeout=_aiohttp.ClientTimeout(total=8)
                ) as _resp:
                    _rbody = await _resp.read()
                    HELLXlog("VOICE", f"SDK verify HTTPS: status={_resp.status} len={len(_rbody)}")
                    if _resp.status == 200 and len(_rbody) > 4:
                        _parse_sdk_response(_rbody)
        except Exception as e:
            HELLXlog("VOICE", f"SDK verify HTTPS failed: {e}, trying TCP fallback...")

        if not redirect_ip:
            try:
                import socket as _sock
                import struct as _st3
                _infos = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: _sock.getaddrinfo(self._sdk_verify_domain, 8012, _sock.AF_INET)
                )
                _tcp_ips = list(dict.fromkeys(info[4][0] for info in _infos))
                HELLXlog("VOICE", f"SDK verify TCP fallback: DNS={_tcp_ips}")
                _tcp_pkt = _st3.pack('>I', len(_SDK_VERIFY_PAYLOAD)) + _SDK_VERIFY_PAYLOAD
                for _tip in _tcp_ips:
                    try:
                        _tr, _tw = await asyncio.wait_for(
                            asyncio.open_connection(_tip, 8012), timeout=5.0)
                        _tw.write(_tcp_pkt)
                        await _tw.drain()
                        _tbody = b""
                        try:
                            _chunk = await asyncio.wait_for(_tr.read(65536), timeout=8.0)
                            if _chunk:
                                _tbody = _chunk
                                while True:
                                    try:
                                        _more = await asyncio.wait_for(_tr.read(65536), timeout=2.0)
                                        if not _more: break
                                        _tbody += _more
                                    except asyncio.TimeoutError:
                                        break
                        except asyncio.TimeoutError:
                            pass
                        try:
                            _tw.close()
                        except Exception:
                            pass
                        if _tbody:
                            HELLXlog("VOICE", f"SDK verify TCP: {_tip}:8012 RX {len(_tbody)}B")
                            _parse_sdk_response(_tbody[4:] if len(_tbody) > 4 else _tbody)
                            if redirect_ip:
                                break
                    except Exception as _te:
                        HELLXlog("VOICE", f"SDK verify TCP {_tip} failed: {_te}")
            except Exception as e:
                HELLXlog("VOICE", f"SDK verify TCP fallback failed: {e}")

        if not redirect_ip or not redirect_port:
            HELLXlog("VOICE", "ERROR: No redirect from SDK verify")
            return
        HELLXlog("VOICE", f"Step2: {redirect_ip}:{redirect_port}")
        try:
            r2, w2 = await asyncio.wait_for(
                asyncio.open_connection(redirect_ip, redirect_port), timeout=5.0)
        except Exception as e:
            HELLXlog("VOICE", f"Step2 failed: {e}")
            return
        redir_pkt = HELLXbuild_voice_redirect(self.uid, self.voice_region_id, self.region_prefix, self.ext_region)
        HELLXlog("VOICE", f"Step2 TCP CONNECT: {redirect_ip}:{redirect_port}")
        HELLXlog("VOICE", f"Step2 REQUEST ({len(redir_pkt)}B): {redir_pkt.hex()}")
        w2.write(redir_pkt)
        await w2.drain()
        HELLXlog("VOICE", "Step2: TX sent")
        voice_ip, voice_port = None, None
        try:
            header2 = await asyncio.wait_for(r2.readexactly(4), timeout=5.0)
            response_length = struct.unpack('>I', header2)[0]
            if response_length <= 0 or response_length > 65536:
                raise ValueError(f"invalid Step2 response length: {response_length}")
            resp2 = header2 + await asyncio.wait_for(
                r2.readexactly(response_length), timeout=5.0
            )
            if resp2:
                HELLXlog("VOICE", f"Step2 RESPONSE ({len(resp2)}B): {resp2.hex()}")
                data = resp2[4:]
                proto = HELLXdecode_proto(data)
                ip_val = proto.get('1')
                port_val = proto.get('2')
                if isinstance(ip_val, str) and '.' in ip_val:
                    voice_ip = ip_val
                if isinstance(port_val, int):
                    voice_port = port_val
                HELLXlog("VOICE", f"UDP VOICE TARGET: {voice_ip}:{voice_port} (audio UDP port={voice_port + 2 if voice_port else None})")
        except asyncio.TimeoutError:
            HELLXlog("VOICE", "Step2: timeout")
        w2.close()
        if not voice_ip or not voice_port:
            HELLXlog("VOICE", "ERROR: No voice IP from redirect")
            return
        HELLXlog("VOICE", f"Step3: {voice_ip}:{voice_port}")
        try:
            r3, w3 = await asyncio.wait_for(
                asyncio.open_connection(voice_ip, voice_port), timeout=5.0)
        except Exception as e:
            HELLXlog("VOICE", f"Step3 failed: {e}")
            return
        self._voice_writer = w3
        self._voice_reader = r3
        auth3 = HELLXbuild_voice_auth(self.uid, self.voice_region_id, voice_port, self.region_prefix)
        w3.write(auth3[:4])
        await w3.drain()
        w3.write(auth3[4:])
        await w3.drain()
        HELLXlog("VOICE", "Step3: TX auth type=7")
        try:
            resp3 = await _read_voice_frame(r3, 3.0)
            if resp3:
                _p = HELLXdecode_proto(resp3)
                HELLXlog("VOICE", f"Step3 resp: {_p}")
                self._voice_f3 = int(_p.get('3', 0x13e6))
                f5_value = _p.get('5', _p.get('13', 0))
                if isinstance(f5_value, dict):
                    f5_value = f5_value.get('1', 0)
                if isinstance(f5_value, list):
                    f5_value = f5_value[0] if f5_value else 0
                self._voice_f5 = int(f5_value) & 0xFFFFFFFF
                HELLXlog("VOICE", f"f5=0x{self._voice_f5:08x} f3=0x{self._voice_f3:04x}")
        except (asyncio.TimeoutError, TypeError, ValueError):
            pass
        if self._voice_f5 == 0:
            HELLXlog("VOICE", "f5=0 detected, wrong MCU session. Sending warning to chat...")
            asyncio.create_task(self._send_chat_message(
                "[F52727]Wrong IPs detected, please wait, i will handle!\n"
                "[A627F5]If voice still not coming, please contact:\n"
                "[27EBF5]Make bot leave and create a new team -> invite it.\n"
                "[F227F5]Leave command => !leave or /help"
            ))
            try:
                w3.close()
                await w3.wait_closed()
            except Exception:
                pass
            self._voice_writer = None
            self._voice_reader = None
            await asyncio.sleep(3)
            self._voice_connect_task = asyncio.create_task(self._voice_connect())
            return
        custom = HELLXbuild_voice_custom(self.uid, self.voice_region_id, mcu_ip=voice_ip, region_prefix=self.region_prefix)
        w3.write(custom[:4])
        await w3.drain()
        w3.write(custom[4:])
        await w3.drain()
        HELLXlog("VOICE", "Step3: TX custom binary")
        try:
            resp4 = await _read_voice_frame(r3, 3.0)
            if resp4:
                HELLXlog("VOICE", f"Custom resp: {resp4.hex()[:80]}")
                raw = resp4[4:] if resp4[:4] != b'\xfe\xff\xff\x7f' else resp4
                idx = raw.find(b'\xfe\xff\xff\x7f')
                if idx != -1:
                    ts_idx = raw.find(b'\x17\x76', idx)
                    if ts_idx != -1 and ts_idx + 6 <= len(raw):
                        self.voice_session_ts = raw[ts_idx+2:ts_idx+6]
                        HELLXlog("VOICE", f"session_ts: {self.voice_session_ts.hex()}")
        except asyncio.TimeoutError:
            pass
        if self._voice_ping_task:
            self._voice_ping_task.cancel()
        self._voice_ping_task = asyncio.create_task(
            self._voice_ping_loop(w3, r3)
        )
        self._voice_ip = voice_ip
        self._voice_port = voice_port
        async def _voice_tcp_reader():
            try:
                while True:
                    try:
                        data = await _read_voice_frame(r3, 30.0)
                    except (asyncio.IncompleteReadError, ConnectionError):
                        HELLXlog("VOICE", "TCP: Server closed connection!")
                        if self._udp_task and not self._udp_task.done():
                            self._udp_task.cancel()
                        break
                    HELLXlog("VOICE", f"TCP RX: {len(data)}B hex={data.hex()}")
                    try:
                        p = HELLXdecode_proto(data)
                        inner = p.get('1', {})
                        pkt_type = inner.get('1', 0) if isinstance(inner, dict) else 0
                        field2 = p.get('2', 0)
                        if pkt_type == 0x0b and field2:
                            HELLXlog("VOICE", f"TCP: 0x0b received, re-sending auth type=7")
                            self._voice_ssrc_refresh = True
                            async def _do_reauth():
                                auth3 = HELLXbuild_voice_auth(self.uid, self.voice_region_id, voice_port, self.region_prefix)
                                w3.write(auth3[:4]); await w3.drain()
                                w3.write(auth3[4:]); await w3.drain()
                                custom = HELLXbuild_voice_custom(self.uid, self.voice_region_id, mcu_ip=voice_ip, region_prefix=self.region_prefix)
                                w3.write(custom[:4]); await w3.drain()
                                w3.write(custom[4:]); await w3.drain()
                                HELLXlog("VOICE", "TCP: Re-auth sent")
                            asyncio.create_task(_do_reauth())
                    except Exception:
                        pass
            except Exception as e:
                HELLXlog("VOICE", f"TCP reader error: {e}")
        asyncio.create_task(_voice_tcp_reader())
        HELLXlog("VOICE", f"Step3: Done. Streaming to {voice_ip}:{voice_port+2}")
    async def _voice_ping_loop(self, writer, reader):
        try:
            counter = 0
            while writer and not writer.transport.is_closing():
                await asyncio.sleep(5)
                try:
                    session_id = getattr(self, '_voice_f3', 0x0b)
                    ping_pkt = HELLXbuild_voice_ping(self.uid, self.voice_region_id, self.voice_port, session_id)
                    writer.write(ping_pkt)
                    await writer.drain()
                    counter += 1
                except Exception as e:
                    HELLXlog("VOICE", f"TCP ping error: {e}")
                    break
        except asyncio.CancelledError:
            pass
    async def _auto_progress_loop(self):
        try:
            await asyncio.sleep(15)
            while self._udp_task and not self._udp_task.done():
                if self._track_total_frames > 0:
                    frame = self._track_current_frame
                    total = self._track_total_frames
                    elapsed_s = int(frame * 0.02)
                    total_s = int(total * 0.02)
                    pct = min(frame / total, 1.0)
                    bar_len = 16
                    filled = int(bar_len * pct)
                    bar = "[27EBF5]" + "\u25a0" * filled + "[5427F5]" + "\u25a1" * (bar_len - filled)
                    elapsed_str = f"{elapsed_s//60}:{elapsed_s%60:02d}"
                    total_str = f"{total_s//60}:{total_s%60:02d}"
                    playing = not self._udp_task.done()
                    status = "[27EBF5]\u25b6" if playing else "[F52727]\u23f8"
                    await self._send_chat_message(
                        f"{status} [5427F5]{self._track_title[:38]}\n"
                        f"[A627F5]{self._track_channel[:30]}\n"
                        f"{bar}\n"
                        f"[27EBF5]{elapsed_str} [F227F5]/ [27EBF5]{total_str}  "
                        f"[A627F5]Vol:{self._volume}%"
                    )
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            pass
    async def _voice_udp_loop(self, ip: str, port: int, encode_task=None, ogg_data: bytes = None, start_frame: int = 0):
        import socket as _sock
        import struct as _st
        import time as _time
        udp_port = port + 2
        if ogg_data is None and encode_task is not None:
            ogg_data = await encode_task
        if not ogg_data:
            HELLXlog("VOICE", "UDP: No audio data")
            return
        frames = list(_ogg_opus_frames_bytes(ogg_data))
        converted = []
        for f in frames:
            if f[0] == 0x78:
                continue
            if f[0] == 0x4b and len(f) > 2 and f[1] == 0x01:
                converted.append(bytes([0x48]) + f[2:])
            else:
                converted.append(f)
        frames = converted
        HELLXlog("VOICE", f"UDP: Streaming {len(frames)} frames from {start_frame} to {ip}:{udp_port}")
        udp = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
        magic = b'\x41\x6f'
        import random as _random
        seq = _random.randint(0, 0xFFFF)
        ts = _random.randint(0, 0xFFFFFFFF)
        FRAME_SAMPLES = 0x3c0
        FRAME_DURATION = 0.020
        f3_val = getattr(self, '_voice_f3', 0x13e6)
        FIXED_2 = b'\x00\x00' + f3_val.to_bytes(2, 'big')
        mic_open = b'\x71\x5c\x35\x07\x00\x00\x00\x00\x80\x02\x00\x00\x00\x00' + f3_val.to_bytes(2, 'big')
        udp.setblocking(False)
        loop = asyncio.get_running_loop()
        udp_rx_count = 0

        async def _udp_receiver():
            nonlocal udp_rx_count
            try:
                while True:
                    packet, address = await loop.sock_recvfrom(udp, 4096)
                    udp_rx_count += 1
                    if udp_rx_count <= 5 or udp_rx_count % 100 == 0:
                        HELLXlog(
                            "VOICE",
                            f"UDP RX: #{udp_rx_count} {len(packet)}B from {address} hex={packet[:32].hex()}"
                        )
            except asyncio.CancelledError:
                pass
            except (ConnectionError, OSError) as e:
                HELLXlog("VOICE", f"UDP receiver stopped: {e}")

        udp_rx_task = asyncio.create_task(_udp_receiver())
        try:
            udp.sendto(mic_open, (ip, udp_port))
        except OSError as e:
            HELLXlog("VOICE", f"UDP: Failed to open voice stream: {e}")
        try:
            while True:
                seq_loop = seq
                ts_loop = ts
                loop_start = start_frame if seq_loop == seq else 0
                self._track_current_frame = loop_start
                next_send = _time.monotonic()
                for i in range(loop_start, len(frames)):
                    opus_frame = frames[i]
                    f5_val = getattr(self, '_voice_f5', 0)
                    FIXED_1 = f5_val.to_bytes(4, 'big')
                    header = _st.pack('>2sHI4s4s', magic, seq_loop & 0xFFFF, ts_loop & 0xFFFFFFFF, FIXED_1, FIXED_2)
                    try:
                        udp.sendto(header + opus_frame, (ip, udp_port))
                    except Exception:
                        pass
                    if i == loop_start:
                        HELLXlog("VOICE", f"UDP: Streaming started (frame {i})")
                    if i % 500 == 0 and i > loop_start:
                        HELLXlog("VOICE", f"UDP: Frame {i}/{len(frames)}")
                    self._track_current_frame = i
                    seq_loop = (seq_loop + 1) & 0xFFFF
                    ts_loop = (ts_loop + FRAME_SAMPLES) & 0xFFFFFFFF
                    next_send += FRAME_DURATION
                    sleep_time = next_send - _time.monotonic()
                    if sleep_time > 0:
                        try:
                            await asyncio.sleep(sleep_time)
                        except asyncio.CancelledError:
                            self._stopped_frame = i
                            HELLXlog("VOICE", f"UDP: Stopped at frame {i}")
                            raise
                seq = seq_loop
                ts = ts_loop
                start_frame = 0
                HELLXlog("VOICE", "UDP: Track finished, restarting...")
        except asyncio.CancelledError:
            HELLXlog("VOICE", "UDP: Stopped (cancelled)")
        except Exception as e:
            HELLXlog("VOICE", f"UDP: FATAL ERROR {type(e).__name__}: {e}")
        finally:
            udp_rx_task.cancel()
            try:
                await udp_rx_task
            except asyncio.CancelledError:
                pass
            udp.close()
    async def _play_yt(self, url: str, lyrics: bool = False):
        import subprocess, tempfile as _tmp, os as _os
        self._current_url = url
        self._lyrics_enabled = lyrics
        if self._udp_task and not self._udp_task.done():
            self._udp_task.cancel()
            await asyncio.sleep(0.5)
        if self._lyrics_task and not self._lyrics_task.done():
            self._lyrics_task.cancel()
        if not self._voice_ip or not self._voice_port:
            await self._send_chat_message("[27EBF5]Voice connection is still starting, please wait...")
            deadline = asyncio.get_running_loop().time() + 20.0
            while (not self._voice_ip or not self._voice_port) and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.25)
            if not self._voice_ip or not self._voice_port:
                await self._send_chat_message("[F52727]Voice connection failed or timed out.")
                return
        wav_path = _tmp.mktemp(suffix='.wav')
        ogg_path = _tmp.mktemp(suffix='.opus')
        volume_val = self._volume / 100.0
        def _encode():
            import glob as _glob
            raw_path = _tmp.mktemp()
            ffmpeg_path = _ffmpeg_executable()
            subprocess.run([
                *_yt_dlp_command(), "-x",
                "--audio-format", "wav",
                "--audio-quality", "0",
                "--ffmpeg-location", ffmpeg_path,
                "-o", raw_path + ".%(ext)s",
                "--no-playlist", url
            ], check=True, capture_output=True, text=True)
            matches = _glob.glob(raw_path + ".*")
            if not matches:
                raise Exception("yt-dlp produced no output file")
            raw_file = matches[0]
            HELLXlog("VOICE", f"Downloaded: {raw_file} ({_os.path.getsize(raw_file)} bytes)")
            subprocess.run([
                _ffmpeg_executable(), "-loglevel", "quiet", "-y",
                "-i", raw_file,
                "-ar", "16000", "-ac", "1",
                "-af", f"volume={volume_val},loudnorm=I=-16:TP=-1.5:LRA=11",
                wav_path
            ], check=True)
            HELLXlog("VOICE", f"Resampled: {wav_path} ({_os.path.getsize(wav_path)} bytes)")
            try: _os.unlink(raw_file)
            except: pass
            # ترميز Opus عبر ffmpeg (بدل opusenc.exe الخاص بجهاز صاحب البوت الأصلي)
            subprocess.run([
                _ffmpeg_executable(), "-loglevel", "error", "-y", "-i", wav_path,
                "-c:a", "libopus", "-application", "voip",
                "-b:a", str(self.opus_bitrate), "-vbr", "off",
                "-frame_duration", "20", "-ar", "16000", "-ac", "1",
                "-f", "ogg", ogg_path
            ], check=True)
            data = open(ogg_path, 'rb').read()
            HELLXlog("VOICE", f"Encoded: {len(data)} bytes opus")
            try: _os.unlink(wav_path)
            except: pass
            try: _os.unlink(ogg_path)
            except: pass
            return data
        def _fetch_lyrics():
            try:
                import yt_dlp, json as _json, tempfile, os, glob
                temp_dir = tempfile.mkdtemp()
                ydl_opts = {
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': ['tr', 'en'],
                    'subtitlesformat': 'json3',
                    'skip_download': True,
                    'quiet': True,
                    'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(url, download=True)
                sub_files = glob.glob(os.path.join(temp_dir, "*.json3"))
                if not sub_files:
                    return []
                with open(sub_files[0], "r", encoding="utf-8") as f:
                    raw = _json.load(f)
                result = []
                for event in raw.get('events', []):
                    start = event.get('tStartMs', 0)
                    dur = event.get('dDurationMs', 2000)
                    segs = event.get('segs', [])
                    text = ''.join(s.get('utf8', '') for s in segs).strip()
                    if text and text != '\n':
                        result.append((start, start + dur, text))
                for f in sub_files:
                    try: os.unlink(f)
                    except: pass
                try: os.rmdir(temp_dir)
                except: pass
                return result
            except Exception as e:
                HELLXlog("LYRICS", f"Fetch failed: {e}")
                return []
        loop = asyncio.get_event_loop()
        if lyrics:
            encode_fut = loop.run_in_executor(None, _encode)
            lyrics_fut = loop.run_in_executor(None, _fetch_lyrics)
            try:
                ogg_data = await encode_fut
            except Exception as e:
                await self._send_chat_message(f"[F52727]Download failed: {str(e)[:60]}")
                return
            self._lyrics_data = await lyrics_fut
            if self._lyrics_data:
                await self._send_chat_message(f"[27EBF5]Lyrics loaded ({len(self._lyrics_data)} lines)")
            else:
                await self._send_chat_message("[F52727]No lyrics found, playing without.")
        else:
            try:
                ogg_data = await loop.run_in_executor(None, _encode)
            except Exception as e:
                await self._send_chat_message(f"[F52727]Download failed: {str(e)[:60]}")
                return
            self._lyrics_data = []
        await self._send_chat_message(
            f"[27EBF5]Now Playing\n"
            f"[5427F5]{self._track_title[:45]}\n"
            f"[A627F5]{self._track_channel[:30]}"
        )
        self._current_ogg = ogg_data
        frames_preview = list(_ogg_opus_frames_bytes(ogg_data))
        self._track_total_frames = len(frames_preview)
        self._track_current_frame = 0
        self._udp_task = asyncio.create_task(
            self._voice_udp_loop(self._voice_ip, self._voice_port, ogg_data=ogg_data)
        )
        if self._progress_task and not self._progress_task.done():
            self._progress_task.cancel()
        self._progress_task = asyncio.create_task(self._auto_progress_loop())
        if lyrics and self._lyrics_data:
            self._lyrics_task = asyncio.create_task(self._lyrics_loop())
