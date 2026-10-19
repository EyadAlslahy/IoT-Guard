def text_to_blocks(text):
    """
    يحوّل نص إلى قائمة blocks كل واحد 64 بت (8 بايت)
    مع padding إذا لزم
    """
    data = text.encode('utf-8')                 # تحويل النص إلى bytes
    blocks = []                                 # قائمة blocks

    # تقسيم إلى مجموعات 8 بايت
    for i in range(0, len(data), 8):
        chunk = data[i:i+8]                     # خذ 8 بايت

        # padding: إذا أقل من 8 بايت نضيف أصفار
        if len(chunk) < 8:
            chunk = chunk + b'\x00' * (8 - len(chunk))

        # تحويل 8 بايت إلى عدد صحيح 64 بت
        value = int.from_bytes(chunk, 'big')
        blocks.append(value)

    return blocks


def blocks_to_text(blocks):
    """يحوّل قائمة blocks إلى نص أصلي"""
    data = b''                                  # بيانات فارغة

    for block in blocks:
        # حوّل العدد إلى 8 بايت
        chunk = block.to_bytes(8, 'big')
        data += chunk                           # أضفه للبيانات

    # إزالة padding (الأصفار في النهاية)
    text = data.rstrip(b'\x00').decode('utf-8', errors='ignore')

    return text


def hex_to_block(hex_string):
    """يحوّل hex string (16 حرف) إلى block 64 بت"""
    return int(hex_string, 16)


def block_to_hex(block):
    """يحوّل block 64 بت إلى hex string (16 حرف)"""
    return f"{block:016X}"