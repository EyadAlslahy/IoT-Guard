from .sbox import SBOX   # نستورد جدول S-Box لتطبيقه على المفتاح

# عدد الـ rounds في PRESENT
ROUNDS = 31


def rotate_left_80(key, n):
    """تدوير 80 بت لليسار بمقدار n"""
    n = n % 80                                          # لضمان بقاء n ضمن 0..79
    return ((key << n) | (key >> (80 - n))) & ((1 << 80) - 1)
    #       ↑ الجزء الأعلى                          ↑ قناع 80 بت للحفاظ على الحجم


def generate_round_keys(key_80):
    """
    يولّد 32 مفتاح فرعي (key[0]..key[31]) من المفتاح الأصلي 80 بت
    key_80: عدد صحيح يمثل المفتاح (80 بت)
    """
    round_keys = []                                     # قائمة المفاتيح الفرعية
    key_reg = key_80                                    # نسخة العمل من المفتاح

    # key[0] = أعلى 64 بت من المفتاح الأصلي
    round_keys.append((key_reg >> 16) & ((1 << 64) - 1))

    for r in range(1, ROUNDS + 1):                      # 31 round
        # 1) تدوير لليسار بـ 61
        key_reg = rotate_left_80(key_reg, 61)

        # 2) تطبيق S-Box على أعلى 4 بت
        top_nibble = (key_reg >> 76) & 0xF              # استخراج أعلى nibble
        new_nibble = SBOX[top_nibble]                   # استبداله من S-Box
        key_reg &= (1 << 76) - 1                        # مسح أعلى 4 بت
        key_reg |= new_nibble << 76                     # وضع القيمة الجديدة

        # 3) XOR عداد الـ round مع البتات 15..19
        counter = r & 0x1F                              # عداد 5 بت
        key_reg ^= counter << 15                        # وضعه في الموضع 15

        # key[r] = أعلى 64 بت من السجل
        round_keys.append((key_reg >> 16) & ((1 << 64) - 1))

    return round_keys                                   # 32 مفتاح (0..31)