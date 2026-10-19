import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.modes import cbc_encrypt, cbc_decrypt, ctr_encrypt, ctr_decrypt


KEY = 0x0123456789ABCDEF0123                # مفتاح 80 بت
IV  = 0x1122334455667788                    # IV لـ CBC (64 بت)
NONCE = 0xDEADBEEF                          # Nonce لـ CTR (32 بت)


def test_cbc():
    print("\n=== CBC Mode ===")
    samples = [
        "AA:BB:CC:DD:EE:FF",
        "NEW_DEVICE|AA:BB:CC:DD:EE:FF|192.168.8.20",
        "ATTACK|ARP_Spoofing|AA:BB:CC:DD:EE:FF",
    ]
    for text in samples:
        enc = cbc_encrypt(text, KEY, IV)                # شفّر
        dec = cbc_decrypt(enc, KEY, IV)                 # فك
        status = "PASS" if dec == text else "FAIL"
        print(f"Original : {text}")
        print(f"Encrypted: {[hex(b) for b in enc]}")
        print(f"Decrypted: {dec}  [{status}]")
        assert dec == text


def test_ctr():
    print("\n=== CTR Mode ===")
    samples = [
        "AA:BB:CC:DD:EE:FF",
        "NEW_DEVICE|AA:BB:CC:DD:EE:FF|192.168.8.20",
        "Short",
        "Exactly8",  # 8 بايت بالضبط
    ]
    for text in samples:
        enc = ctr_encrypt(text, KEY, NONCE)             # شفّر
        dec = ctr_decrypt(enc, KEY, NONCE)              # فك
        status = "PASS" if dec == text else "FAIL"
        print(f"Original : {text}")
        print(f"Encrypted: {enc.hex()}")
        print(f"Decrypted: {dec}  [{status}]")
        assert dec == text


if __name__ == "__main__":
    test_cbc()
    test_ctr()
    print("\n>>> All modes passed!")