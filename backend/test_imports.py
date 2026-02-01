# test_imports.py
import sys

sys.path.insert(0, '.')

try:
    from app.core.shift_logger import shift_logger
    from app.core.delivery_verification import delivery_verification
    from app.core.audit import audit_logger
    from app.core.encryption import encrypt_data, decrypt_data

    print("✓ All core imports successful!")

    # Test encryption quickly
    test = "test123"
    encrypted = encrypt_data(test)
    decrypted = decrypt_data(encrypted)
    if decrypted == test:
        print("✓ Encryption/decryption working!")
    else:
        print("✗ Encryption test failed")

except ImportError as e:
    print(f"✗ Import error: {e}")
except Exception as e:
    print(f"✗ Other error: {e}")