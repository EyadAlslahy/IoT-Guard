from .present import encrypt, decrypt                # دوال PRESENT الأساسية
from .text_helper import text_to_blocks, blocks_to_text  # تحويل نص↔blocks

MASK_64 = (1 << 64) - 1                              # قناع 64 بت


# ============================================================
# CBC Mode — Cipher Block Chaining
# ============================================================
# كل block XOR مع ciphertext السابق، ثم يُشفّر
# يحتاج IV (قيمة ابتدائية) بطول 64 بت
# ============================================================

def cbc_encrypt(plaintext, key, iv):
    """تشفير CBC — plaintext: نص | key: 80 بت | iv: 64 بت"""
    blocks = text_to_blocks(plaintext)               # حوّل النص إلى blocks
    result = []                                      # القائمة الناتجة
    prev = iv & MASK_64                              # السابق = IV

    for block in blocks:                             # لكل block
        mixed = block ^ prev                         # XOR مع السابق
        encrypted = encrypt(mixed, key)              # شفّر
        result.append(encrypted)                     # أضفه للناتج
        prev = encrypted                             # السابق الجديد = المشفر

    return result                                    # قائمة blocks مشفرة


def cbc_decrypt(encrypted_blocks, key, iv):
    """فك تشفير CBC — يرجع النص الأصلي"""
    result = []                                      # القائمة الناتجة
    prev = iv & MASK_64                              # السابق = IV

    for block in encrypted_blocks:                   # لكل block مشفر
        decrypted = decrypt(block, key)              # فك التشفير
        plain = decrypted ^ prev                     # XOR مع السابق
        result.append(plain)                         # أضفه للناتج
        prev = block                                 # السابق = المشفر الأصلي

    return blocks_to_text(result)                    # حوّل إلى نص


# ============================================================
# CTR Mode — Counter Mode
# ============================================================
# يحوّل block cipher إلى stream cipher
# لا يحتاج padding
# كل block: شفّر العداد → XOR مع النص
# ============================================================

def ctr_encrypt(plaintext, key, nonce):
    """تشفير CTR — متطابق مع ESP32"""
    data = plaintext.encode('utf-8')
    result = bytearray()
    counter = 0

    for i in range(0, len(data), 8):
        counter_block = ((nonce & 0xFFFFFFFF) << 32) | (counter & 0xFFFFFFFF)
        keystream = encrypt(counter_block, key)
        chunk = data[i:i+8]

        ks_bytes = keystream.to_bytes(8, 'big')
        for j in range(len(chunk)):
            result.append(chunk[j] ^ ks_bytes[j])
        counter += 1

    return bytes(result)

def ctr_decrypt(cipher, key, nonce):
    """فك تشفير CTR — متطابق مع ESP32"""
    result = bytearray()
    counter = 0

    for i in range(0, len(cipher), 8):
        counter_block = ((nonce & 0xFFFFFFFF) << 32) | (counter & 0xFFFFFFFF)
        keystream = encrypt(counter_block, key)
        chunk = cipher[i:i+8]

        ks_bytes = keystream.to_bytes(8, 'big')
        for j in range(len(chunk)):
            result.append(chunk[j] ^ ks_bytes[j])
        counter += 1

    return result.decode('utf-8', errors='ignore')