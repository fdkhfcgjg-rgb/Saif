# -*- coding: utf-8 -*-
"""بناة حزم الشات (مستخرجة من بوت VOICE_CHAT_REMAKED_OB54)"""
import random
from encrypt import HELLXenc_packet
from proto import HELLXcreate_proto, HELLXgenerate_packet

def HELLXbuild_auth_startup(uid, token, timestamp, key, iv):
    uid_hex = hex(int(uid))[2:]
    uid_length = len(uid_hex)
    r = hex(timestamp)
    f = str(r)[2:]
    if len(f) == 1:
        f = "0" + f
    encrypted_timestamp = f
    encrypted_account_token = token.encode().hex()
    encrypted_packet = HELLXenc_packet(encrypted_account_token, key, iv)
    length_val = len(encrypted_packet) // 2
    length_hex = hex(length_val)[2:].zfill(4)
    if uid_length == 9:
        headers = '0000000'
    elif uid_length == 8:
        headers = '00000000'
    elif uid_length == 10:
        headers = '000000'
    elif uid_length == 7:
        headers = '000000000'
    else:
        headers = '0000000'
    return f"0115{headers}{uid_hex}{encrypted_timestamp}0000{length_hex}{encrypted_packet}"

def HELLXbuild_chat_auth(uid: int, region_id, key, iv) -> bytes:
    # fields = {
    #     1: 3,
    #     2: {
    #         1: uid,
    #         3: "en",
    #         4: str(region_id),
    #     }
    # }
    fields = {1: 3, 2: {1: int(uid), 3: 'en', 4: str(region_id)}}
    proto_hex = HELLXcreate_proto(fields).hex()
    return HELLXgenerate_packet(proto_hex, '1215', key, iv)

async def get_randm_avatar():
    avatars = [902000068, 902000016, 902000011, 902000084, 902000085, 902000087, 902000106, 902045016]
    return random.choice(avatars)

async def HELLXbuild_chat_message(uid: int, owner_uid: int, message: str, timestamp: int, key, iv, name: str = "Bot") -> bytes:
    fields = {
        1: 1,
        2: {
            1: uid,
            2: owner_uid,
            4: message,
            5: timestamp,
            7: 6,
            9: {
                1: name,
                2: await get_randm_avatar(),
                3: 901000029,
                4: 330,
                5: 801043518,
                7: 2,
                10: 1,
                12: 0,
                13: {
                    1: 2,
                },
                13: "",
                14: {
                    1: uid,
                    2: 8,
                    3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006",
                }
            },
            10: "en",
            13: {3: 1},
            14: "",
        }
    }
    proto_hex = HELLXcreate_proto(fields).hex()
    return HELLXgenerate_packet(proto_hex, '1215', key, iv)
