import sys                                    # للتعامل مع مسارات الملفات
import os                                     # لبناء المسار النسبي
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.present import encrypt, decrypt      # دوال التشفير وفك التشفير


# قائمة test vectors (من الملف الرسمي)
VECTORS = [
    # (plaintext, key, expected_ciphertext)
    (0x0000000000000000, 0x00000000000000000000, 0x5579C1387B228445),
    (0x0000000000000000, 0xFFFFFFFFFFFFFFFFFFFFFF, 0xE72C46C0F5945049),
    (0xFFFFFFFFFFFFFFFF, 0x00000000000000000000, 0xA112FFC72F68417B),
    (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFFFFFFFF, 0x3333DCD3213210D2),
]


def test_encrypt():
    """اختبار: تشفير plaintext يجب أن يطابق expected ciphertext"""
    print("\n=== Test Encryption ===")
    for pt, key, expected in VECTORS:
        result = encrypt(pt, key)                         # نحسب التشفير
        status = "PASS" if result == expected else "FAIL" # نقارن
        print(f"PT={pt:016X} KEY={key:020X}")
        print(f"  Expected: {expected:016X}")
        print(f"  Got     : {result:016X}  [{status}]")
        assert result == expected, f"Encryption mismatch!"  # إذا فشل يوقف


def test_decrypt():
    """اختبار: فك تشفير ciphertext يجب أن يعيد plaintext الأصلي"""
    print("\n=== Test Decryption ===")
    for pt, key, ct in VECTORS:
        result = decrypt(ct, key)                          # نفك التشفير
        status = "PASS" if result == pt else "FAIL"        # نقارن
        print(f"CT={ct:016X} KEY={key:020X}")
        print(f"  Expected: {pt:016X}")
        print(f"  Got     : {result:016X}  [{status}]")
        assert result == pt, f"Decryption mismatch!"       # إذا فشل يوقف


def test_roundtrip():
    """اختبار: encrypt ثم decrypt يجب أن يعيد النص الأصلي"""
    print("\n=== Test Round Trip ===")
    pt = 0x123456789ABCDEF0                                  # قيمة عشوائية
    key = 0x0123456789ABCDEF0123                             # مفتاح عشوائي
    ct = encrypt(pt, key)                                    # تشفير
    result = decrypt(ct, key)                                # فك
    print(f"Plaintext : {pt:016X}")
    print(f"Ciphertext: {ct:016X}")
    print(f"Recovered : {result:016X}")
    assert result == pt, "Roundtrip failed!"                 # تحقق


if __name__ == "__main__":
    test_encrypt()      # شغّل اختبار التشفير
    test_decrypt()      # شغّل اختبار فك التشفير
    test_roundtrip()    # شغّل اختبار الدورة
    print("\n>>> All tests passed!")