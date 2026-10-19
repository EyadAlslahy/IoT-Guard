import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cipher_api import (
    encrypt_text_to_hex,
    decrypt_hex_to_text
)


def test_full_cipher():
    print("\n=== Test Full Cipher ===")

    KEY = 0x0123456789ABCDEF0123              # مفتاح مشترك 80 بت

    samples = [
        "AA:BB:CC:DD:EE:FF",
        "192.168.8.20",
        "NEW_DEVICE|AA:BB:CC:DD:EE:FF|192.168.8.20",
        "ATTACK|ARP_Spoofing|AA:BB:CC:DD:EE:FF",
    ]

    for text in samples:
        hex_enc = encrypt_text_to_hex(text, KEY)         # شفّر
        recovered = decrypt_hex_to_text(hex_enc, KEY)    # فك
        status = "PASS" if recovered == text else "FAIL"
        print(f"Original : {text}")
        print(f"Encrypted: {hex_enc}")
        print(f"Recovered: {recovered}  [{status}]")
        assert recovered == text


if __name__ == "__main__":
    test_full_cipher()
    print("\n>>> Full cipher tests passed!")