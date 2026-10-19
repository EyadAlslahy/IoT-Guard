# جدول S-Box الرسمي لخوارزمية PRESENT
# يُستخدم لاستبدال كل nibble (4 بت) بقيمة جديدة (Non-linear)
SBOX = [
    0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0xA, 0xD,   # المدخلات 0..7
    0x3, 0xE, 0xF, 0x8, 0x4, 0x7, 0x1, 0x2    # المدخلات 8..F
]

# جدول S-Box العكسي (يُستخدم في فك التشفير)
# نبني العكس تلقائيًا: إذا كان SBOX[a]=b فإن SBOX_INV[b]=a
SBOX_INV = [0] * 16                # مصفوفة فارغة بحجم 16
for i, v in enumerate(SBOX):       # نمر على كل عنصر في SBOX
    SBOX_INV[v] = i                # نضع العكس: القيمة v تشير إلى الموقع i


def apply_sbox(state):
    """تطبيق S-Box على 64 بت (16 nibble)"""
    result = 0                                     # الناتج يبدأ صفر
    for i in range(16):                            # نمر على 16 nibble
        nibble = (state >> (i * 4)) & 0xF          # استخراج الـ nibble رقم i
        new_nibble = SBOX[nibble]                  # استبداله بالقيمة من الجدول
        result |= new_nibble << (i * 4)            # إعادته لمكانه في الناتج
    return result                                  # إرجاع الحالة الجديدة


def apply_sbox_inv(state):
    """تطبيق S-Box العكسي (لفك التشفير)"""
    result = 0                                     # الناتج يبدأ صفر
    for i in range(16):                            # نمر على 16 nibble
        nibble = (state >> (i * 4)) & 0xF          # استخراج الـ nibble رقم i
        new_nibble = SBOX_INV[nibble]              # استبداله بالقيمة العكسية
        result |= new_nibble << (i * 4)            # إعادته لمكانه في الناتج
    return result                                  # إرجاع الحالة الجديدة