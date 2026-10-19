import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.text_helper import text_to_blocks, blocks_to_text


def test_text_roundtrip():
    print("\n=== Test Text Roundtrip ===")
    
    samples = [
        "AA:BB:CC:DD:EE:FF",       # MAC
        "192.168.8.20",            # IP
        "NEW_DEVICE",              # Event
        "Hello IoT Guard!",        # نص عام
    ]
    
    for text in samples:
        blocks = text_to_blocks(text)
        recovered = blocks_to_text(blocks)
        status = "PASS" if recovered == text else "FAIL"
        print(f"Original : {text}")
        print(f"Blocks   : {[hex(b) for b in blocks]}")
        print(f"Recovered: {recovered}  [{status}]")
        assert recovered == text


if __name__ == "__main__":
    test_text_roundtrip()
    print("\n>>> Text helper tests passed!")