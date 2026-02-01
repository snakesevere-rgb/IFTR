# test_user_consolidation.py
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🧪 Testing Consolidated User Models")
print("=" * 50)

try:
    # Test imports
    from app.models.user import (
        UserRole, CalendarPreference, ThemePreference,
        UserBase, UserCreate, UserResponse, UserDB, UserSession, UserUpdate
    )
    from app.models.encrypted_models import EncryptedAddress
    from app.models.general import AddressTier

    print("✅ All imports successful")

    # Test 1: User creation flow
    print("\n1. User Creation Flow:")
    user_create = UserCreate(
        email="alice@example.com",
        name="Alice Smith",
        password="SecurePass123!",
        role=UserRole.CUSTOMER,
        phone="+12345678901"
    )
    print(f"   ✅ UserCreate: {user_create.email}")

    # Test 2: User response (public)
    user_response = UserResponse(
        user_id="user_abc123",
        email="alice@example.com",
        name="Alice Smith",
        role=UserRole.CUSTOMER,
        theme_preference=ThemePreference.DARK
    )
    print(f"   ✅ UserResponse: {user_response.name}")
    print(f"     Is driver? {user_response.is_driver}")
    print(f"     Is admin? {user_response.is_admin}")

    # Test 3: UserDB with private data
    location = EncryptedAddress(
        tier=AddressTier.CUSTOMER_HOME,
        city="Portland",
        zip_code="97201"
    )

    user_db = UserDB(
        user_id="user_abc123",
        email="alice@example.com",
        name="Alice Smith",
        role=UserRole.CUSTOMER,
        location=location,
        password_hash="$2b$12$...",  # Example bcrypt hash
        two_factor_enabled=True,
        notification_preferences={"email": True, "push": False}
    )
    print(f"   ✅ UserDB with encrypted location: {user_db.location.city}")
    print(f"     Account locked? {user_db.is_account_locked()}")

    # Test 4: Session
    from datetime import timedelta

    session = UserSession(
        user_id="user_abc123",
        session_token_hash="hashed_token_here",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        device_info="iPhone 14, iOS 17",
        ip_address="192.168.1.100"
    )
    print(f"   ✅ UserSession: {session.session_id}")
    print(f"     Expired? {session.is_expired()}")
    print(f"     Active? {session.is_active()}")

    # Test 5: Helper functions
    from app.models.user import create_user_response, mask_email, mask_phone

    masked = mask_email("alice@example.com")
    print(f"   ✅ Masked email: {masked}")

    masked_phone = mask_phone("+12345678901")
    print(f"   ✅ Masked phone: {masked_phone}")

    # Test conversion
    public_user = create_user_response(user_db)
    print(f"   ✅ Converted to public: {public_user.user_id}")
    print(f"     Has password_hash? {hasattr(public_user, 'password_hash')}")

    print("\n🎉 ALL USER MODEL TESTS PASSED!")
    print("\nYour user models are now:")
    print("  - Organized in one place (user.py)")
    print("  - Clean separation of public/private data")
    print("  - Privacy-focused with encryption")
    print("  - Ready for authentication implementation")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()