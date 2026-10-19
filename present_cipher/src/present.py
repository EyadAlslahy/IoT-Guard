from .sbox import apply_sbox, apply_sbox_inv          # دوال S-Box (عادي وعكسي)
from .pbox import apply_pbox, apply_pbox_inv          # دوال P-Box (عادي وعكسي)
from .key_schedule import generate_round_keys, ROUNDS # توليد المفاتيح + عدد الجولات

# قناع 64 بت (كل البتات = 1)
MASK_64 = (1 << 64) - 1


def encrypt(plaintext, key):
    """
    تشفير block واحد (64 بت) باستخدام PRESENT-80
    plaintext: عدد صحيح 64 بت
    key: عدد صحيح 80 بت
    يرجع: ciphertext 64 بت
    """
    round_keys = generate_round_keys(key)              # نولّد 32 مفتاح فرعي

    state = plaintext & MASK_64                        # نأخذ 64 بت فقط
    state ^= round_keys[0]                             # AddRoundKey الأولي (key[0])

    for r in range(1, ROUNDS + 1):                     # 31 جولة
        state = apply_sbox(state)                      # 1) طبقة S-Box
        state = apply_pbox(state)                      # 2) طبقة P-Box
        state ^= round_keys[r]                         # 3) AddRoundKey

    return state & MASK_64                             # إرجاع الناتج 64 بت


def decrypt(ciphertext, key):
    """
    فك تشفير block واحد (64 بت) باستخدام PRESENT-80
    ciphertext: عدد صحيح 64 بت
    key: عدد صحيح 80 بت
    يرجع: plaintext 64 بت
    """
    round_keys = generate_round_keys(key)              # نفس المفاتيح الفرعية

    state = ciphertext & MASK_64                       # نأخذ 64 بت فقط

    for r in range(ROUNDS, 0, -1):                     # من 31 نزولًا إلى 1
        state ^= round_keys[r]                         # 1) AddRoundKey عكسي
        state = apply_pbox_inv(state)                  # 2) عكس P-Box
        state = apply_sbox_inv(state)                  # 3) عكس S-Box

    state ^= round_keys[0]                             # AddRoundKey الأخير (key[0])

    return state & MASK_64                             # إرجاع النص الأصلي