from .present import encrypt, decrypt                            # دوال PRESENT
from .text_helper import text_to_blocks, blocks_to_text          # تحويل نص↔blocks


def encrypt_text(text, key):
    """يشفر نصًا كاملًا ويرجع قائمة blocks مشفرة"""
    blocks = text_to_blocks(text)                    # حوّل النص إلى blocks
    encrypted = [encrypt(b, key) for b in blocks]    # شفّر كل block
    return encrypted                                 # أرجع القائمة


def decrypt_text(encrypted_blocks, key):
    """يفك تشفير قائمة blocks ويرجع النص الأصلي"""
    decrypted = [decrypt(b, key) for b in encrypted_blocks]  # فك كل block
    return blocks_to_text(decrypted)                          # حوّل إلى نص


def encrypt_text_to_hex(text, key):
    """يشفر نصًا ويرجع سلسلة hex واحدة (مفيدة للنقل)"""
    blocks = encrypt_text(text, key)                 # شفّر النص
    return "".join(f"{b:016X}" for b in blocks)      # حوّل كل block إلى hex


def decrypt_hex_to_text(hex_string, key):
    """يفك تشفير سلسلة hex ويرجع النص"""
    blocks = []                                      # قائمة blocks فارغة
    for i in range(0, len(hex_string), 16):          # كل 16 حرف = block واحد
        chunk = hex_string[i:i+16]                   # خذ 16 حرف hex
        blocks.append(int(chunk, 16))                # حوّلها إلى عدد
    return decrypt_text(blocks, key)                 # فك التشفير