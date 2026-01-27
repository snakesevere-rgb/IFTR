"""
Pydantic models for MealsMiles food delivery platform
"""

"""
Location models for iftr food delivery system.

Design Note: Coordinates are encrypted separately (lat, lng) for simplicity.
For deployments expecting >1,000,000 active locations (major metropolitan areas),
consider combining coordinates into a single encrypted JSON object to:
1. Reduce storage by ~30% (one IV/tag instead of two)
2. Ensure atomic updates (lat/lng can't get mismatched)
3. Slightly faster encryption/decryption (one operation instead of two)

Current separate encryption supports moderate-scale deployments effectively.

See documes/snippets_for_different_builds.txt for major metropolitan support and enhanced encryption options.
"""

MAX_TIP_AMOUNT = 200
MAX_TIP_PERCENTAGE = 200

from pydantic import BaseModel, Field, EmailStr, ConfigDict, ValidationError, model_validator
from typing import Optional, List, Dict, Any
from pydantic import SecretStr
from pydantic import BaseModel, Field
from enum import Enum
from pydantic import BaseModel, Ffrom utils.ids import generate_idield, field_validator
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .encryption import encrypt_instructions, decrypt_instructions, encrypt_location
from utils.ids import generate_id

def generate_id(prefix: str = "") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}" if prefix else uuid.uuid4().hex[:12]

# Enums
class UserRole(str, Enum):
    CUSTOMER = "customer"
    DRIVER = "driver"
    RESTAURANT = "restaurant"
    ORGANIZATION = "organization"
    ADMIN = "admin"
    SUPPORT_STAFF = "support_staff"

class OrderStatus(str, Enum):
    PENDING = "pending"        # Charge customer but allow refund if restaurant declines
    CONFIRMED = "confirmed"    # Restaurant has accepted the order, no more refund unless issue
    PREPARING = "preparing"
    READY = "ready"            # Order is waiting for driver
    ASSIGNED = "assigned"      # Driver accepted, on the way to restaurant
    PICKED_UP = "picked_up"    # Driver has the food
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"    # Default cancellation policy is not allowing customer to cancel after confirmed
                               # If order has issue, customer can receive credits or refund after contacting support
                               # Feel free to change this, but remember cancellation can be a major platform issue

class PaymentStatus(str, Enum):
    PENDING = "pending"        # Associated with PENDING order
    INITIATED = "initiated"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class FoodType(str, Enum):
    REGULAR = "regular"
    SURPLUS = "surplus"
    DONATION = "donation"

class VehicleType(str, Enum):
    MOTORCYCLE = "motorcycle"
    CAR = "car"
    TRUCK = "truck"
    E_BIKE = "e-bike"
    BIKE = "bike"
    SKATES = "rollerskates/skateboard"

# Base Models
class EncryptedLocation(BaseModel):
    lat: str = ""  # Encrypted latitude
    lng: str = ""  # Encrypted longitude
    # NOTE: For high-volume applications (>1M locations), consider
    # combined encryption (lat+lng as single encrypted JSON) to reduce
    # storage overhead and ensure atomicity. Current separate encryption
    # is simpler for moderate-scale deployments.
    address: str = ""
    city: str = ""
    zip_code: str = ""

class DecryptedLocation(BaseModel):
    lat: float = 0.0
    lng: float = 0.0
    # NOTE: For high-volume applications (>1M locations), consider
    # combined encryption (lat+lng as single encrypted JSON) to reduce
    # storage overhead and ensure atomicity. Current separate encryption
    # is simpler for moderate-scale deployments.
    address: str = ""
    city: str = ""
    zip_code: str = ""

# User Models
class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: UserRole = UserRole.CUSTOMER
    phone: Optional[str] = None
    picture: Optional[str] = None

class UserCreate(BaseModel):
    # Input for registration
    email: EmailStr
    name: str
    password: Optional[SecretStr] = None  # For traditional signup
    # ... other fields needed for creation

class UserResponse(UserBase):
    # What gets returned to clients
    user_id: str = Field(default_factory=lambda: generate_id("user"))
    is_active: bool = True
    is_approved: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    theme_preference: str = "light"
    # NO password_hash, NO location (unless explicitly requested)

# ==================== PRIVATE MODELS (DATABASE) ====================
class User(UserResponse):
    # The database version, named User to ensure other code calls this one and not the other one
    model_config = ConfigDict(extra="ignore")
    password_hash: Optional[str] = None  # Hashed password
    location: Optional[EncryptedLocation] = None  # Encrypted server-side
    # Other internal fields...

class UserSession(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_id: str = Field(default_factory=lambda: generate_id("sess"))
    user_id: str
    session_token_hash: str  # ✅ Hash of the actual token
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class User(UserBase):
    model_config = ConfigDict(extra="ignore")
    user_id: str = Field(default_factory=lambda: generate_id("user"))
    password_hash: Optional[str] = None
    is_active: bool = True
    is_approved: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    location: Optional[EncryptedLocation] = None
    theme_preference: str = "light"

# Restaurant Models
class MenuItem(BaseModel):
    item_id: str = Field(default_factory=lambda: generate_id("item"))
    name: str
    description: str = ""
    price: float
    category: str = ""
    image_url: Optional[str] = None
    is_available: bool = True
    is_surplus: bool = False
    surplus_quantity: int = 0
    surplus_expiry: Optional[datetime] = None

class RestaurantHours(BaseModel):
    """Operating hours for a single day"""
    day: str  # monday, tuesday, etc.
    open_time: str = ""  # HH:MM format, empty = closed
    close_time: str = ""  # HH:MM format, empty = closed
    is_closed: bool = False  # Explicitly closed for this day

    @model_validator(mode="after")
    def validate_times(self):
        # If explicitly closed, accept missing times
        if self.is_closed:
            return self

        # Both open and close should be provided or both empty
        if (bool(self.open_time) != bool(self.close_time)):
            raise ValueError("Both open_time and close_time must be set, or both empty when not closed")

        if self.open_time and self.close_time:
            try:
                ot = datetime.strptime(self.open_time, "%H:%M")
                ct = datetime.strptime(self.close_time, "%H:%M")
            except Exception:
                raise ValueError("open_time and close_time must be in HH:MM format")

            # Allow cross-midnight hours (e.g. 18:00 to 02:00)
            # if ot >= ct:
            #     raise ValueError("open_time must be before close_time")

        return self

class Restaurant(BaseModel):
    model_config = ConfigDict(extra="ignore")
    restaurant_id: str = Field(default_factory=lambda: generate_id("rest"))
    user_id: str  # Owner user ID
    name: str
    description: str = ""
    cuisine_type: str = ""
    image_url: Optional[str] = None
    location: EncryptedLocation
    is_active: bool = True
    is_online: bool = True  # Manual online/offline toggle
    manual_is_open: Optional[bool] = None # True=Force Open, False=Force Closed, None=Auto
    next_auto_close_at: Optional[datetime] = None # Failsafe time
    timezone: str = "UTC" # Default timezone
    operating_hours: List[RestaurantHours] = []  # Weekly schedule
    rating: float = 0.0
    total_reviews: int = 0
    menu: List[MenuItem] = []
    # Delivery settings can be customized per-restaurant:
    # {
    #   "per_km": 0.25,
    #   "base_fees": {"priority": 6.0, "standard": 6.0, "economy": 3.0},
    #   "company_fee_enabled": False,
    #   "company_fee_amount": 1.0,
    #   "free_over_total": 30.0
    # }
    delivery_settings: Dict[str, Any] = {}
    # Leaderboard and donation tracking
    show_in_leaderboard: bool = False
    total_meals_donated: int = 0
    surplus_deliveries_completed: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RestaurantCreate(BaseModel):
    name: str
    description: str = ""
    cuisine_type: str = ""
    image_url: Optional[str] = None
    lat: float
    lng: float
    address: str = ""
    city: str = ""
    zip_code: str = ""

class RestaurantSettingsUpdate(BaseModel):
    operating_hours: Optional[List[RestaurantHours]] = None
    manual_is_open: Optional[bool] = None
    timezone: Optional[str] = None
    show_in_leaderboard: Optional[bool] = None
    max_delivery_km: Optional[float] = None  # Drivers are not associated with restaurant
                                             # Main purpose is in case restaurant is concerned about order errors
                                             # Recommend opt-in for restaurants rather than default configuration

# Order Models
class DeliveryInstructionType(str, Enum):
    HAND_TO_CUSTOMER = "hand_to_customer"
    LEAVE_AT_DOOR = "leave_at_door"
    MEET_OUTSIDE = "meet_outside"
    MEET_IN_LOBBY = "meet_in_lobby"
    OTHER = "other"

class OrderItem(BaseModel):
    item_id: str
    name: str
    quantity: int
    price: float
    is_surplus: bool = False
    is_drink: bool = False  # For driver to know if order has drinks

class Order(BaseModel):
    """
    Order model with encrypted sensitive data.
    This is the internal/database representation.
    """
    model_config = ConfigDict(extra="ignore")

    # Core identifiers
    order_id: str = Field(default_factory=lambda: generate_id("order"))
    restaurant_id: str
    customer_id: str
    driver_id: Optional[str] = None

    # Order content
    items: List[OrderItem]
    subtotal: Decimal = Field(ge=0)
    tax_amount: Decimal = Field(ge=0)
    delivery_fee: Decimal = Field(ge=0)
    tip_amount: Decimal = Field(default=Decimal("0.0"), ge=0)
    total_amount: Decimal = Field(ge=0)

    # Payment
    payment_status: PaymentStatus = PaymentStatus.PENDING
    payment_method: Optional[str] = None
    payment_intent_id: Optional[str] = None

    # Location (encrypted)
    pickup_location: EncryptedLocation
    delivery_location: EncryptedLocation
    distance_km: Optional[float] = Field(None, ge=0)

    # Delivery details
    delivery_instruction_type: DeliveryInstructionType = DeliveryInstructionType.HAND_TO_CUSTOMER
    delivery_instructions_encrypted: str = Field(default="", max_length=1000)

    # Donation
    is_donation: bool = False
    donation_org_id: Optional[str] = None

    # Timing
    scheduled_for: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    accepted_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    # Status
    order_status: OrderStatus = OrderStatus.PENDING
    cancellation_reason: Optional[str] = None
    cancelled_at: Optional[datetime] = None

    # Ratings
    restaurant_rating: Optional[int] = Field(None, ge=1, le=5)
    customer_rating: Optional[int] = Field(None, ge=1, le=5)

    # Platform
    platform_fee: Decimal = Field(default=Decimal("0.0"), ge=0)
    commission_rate: float = Field(default=0.15, ge=0, le=1)  # 15% default

    # --- Properties for encrypted fields ---
    @property
    def delivery_instructions(self) -> str:
        """Decrypt instructions when accessed."""
        return decrypt_instructions(self.delivery_instructions_encrypted)

    @delivery_instructions.setter
    def delivery_instructions(self, value: str):
        """Encrypt instructions when setting."""
        if value is None:
            value = ""
        cleaned = value.strip()

        # Validate length
        if len(cleaned) > 500:
            raise ValueError("Delivery instructions exceed 500 character limit")

        self.delivery_instructions_encrypted = encrypt_instructions(cleaned)

    # --- Validators ---
    @field_validator('total_amount')
    @classmethod
    def validate_total_amount(cls, v: Decimal, info) -> Decimal:
        """Ensure total matches sum of components."""
        values = info.data

        # Recalculate to verify
        calculated = (
                values.get('subtotal', Decimal('0')) +
                values.get('tax_amount', Decimal('0')) +
                values.get('delivery_fee', Decimal('0')) +
                values.get('tip_amount', Decimal('0')) +
                values.get('platform_fee', Decimal('0'))
        )

        if abs(v - calculated) > Decimal('0.01'):  # Allow small rounding differences
            raise ValueError(f"Total amount {v} doesn't match sum {calculated}")

        return v

    @field_validator('delivery_instructions_encrypted')
    @classmethod
    def validate_encrypted_length(cls, v: str) -> str:
        """Ensure encrypted data isn't suspiciously large."""
        if v and len(v) > 1000:
            raise ValueError("Encrypted instructions too large")
        return v

    # --- Helper methods ---
    def to_response(self) -> "OrderResponse":
        """Convert to safe API response model."""
        return OrderResponse(
            order_id=self.order_id,
            restaurant_id=self.restaurant_id,
            customer_id=self.customer_id,
            # ... include all public fields
            # EXCLUDE: delivery_instructions_encrypted, pickup/delivery location raw
            delivery_instructions=self.delivery_instructions,  # Decrypted!
            # ... etc
        )

    def calculate_total(self) -> Decimal:
        """Recalculate total amount from components."""
        return (
                self.subtotal +
                self.tax_amount +
                self.delivery_fee +
                self.tip_amount +
                self.platform_fee
        )

class OrderCreateRequest(BaseModel):
    """What the client sends to create an order"""
    restaurant_id: str

    items: List[OrderItem]
    @field_validator('items')
    @classmethod
    def validate_items_not_empty(cls, v: List[OrderItem]) -> List[OrderItem]:
        if not v:
            raise ValueError("Order must contain at least one item")
        return v

    # Location data (will be encrypted server-side)
    delivery_lat: float = Field(description="Will be encrypted immediately upon receipt")
    delivery_lng: float = Field(description="Will be encrypted immediately upon receipt")

    delivery_address: str = Field(
        default="",
        max_length=200
    )

    delivery_city: str = ""
    delivery_zip: str = ""

    # Other order details
    is_donation: bool = False
    donation_org_id: Optional[str] = None

    delivery_instructions: str = Field(
        default="",
        max_length=500,
        description="Optional delivery notes. Will be encrypted before storage."
    )
    @field_validator('delivery_instructions')
    @classmethod
    def sanitize_instructions(cls, v: str) -> str:
        """Clean up instructions before processing."""
        if v is None:
            return ""

        # Trim whitespace
        cleaned = v.strip()

        # Optional: Remove excessive newlines
        # cleaned = ' '.join(cleaned.split())

        return cleaned

    tip_amount: Decimal = Field(
        default=Decimal("0.0"),
        ge=0,
        le=MAX_TIP_AMOUNT,
        description=f"Tip amount, max ${MAX_TIP_AMOUNT}"
    )
    @validator('tip_amount')
    def validate_tip_reasonable(cls, v, values):
        # Get order total from items (you'd need to calculate)
        order_total = calculate_order_total(values.get('items', []))
        max_tip_by_percentage = order_total * (MAX_TIP_PERCENTAGE / 100)

        if v > max_tip_by_percentage:
            raise ValueError(
                f"Tip cannot exceed {MAX_TIP_PERCENTAGE}% of order total "
                f"(${max_tip_by_percentage:.2f})"
            )
        return v

    scheduled_for: Optional[datetime] = None  # Let Pydantic parse ISO string

    model_config = {
        "json_schema_extra": {
            "security_note": "Location coordinates are encrypted immediately upon server receipt"
        }
    }

class OrderResponse(BaseModel):
    """
    Safe API response model for orders.
    Excludes sensitive/encrypted fields and internal data.
    """
    # Core identifiers
    order_id: str
    restaurant_id: str
    customer_id: str
    driver_id: Optional[str] = None

    # Order summary
    items: List[OrderItem]
    subtotal: Decimal
    tax_amount: Decimal
    delivery_fee: Decimal
    tip_amount: Decimal
    total_amount: Decimal

    # Payment status (safe)
    payment_status: PaymentStatus

    # Delivery information (safe/decrypted)
    delivery_address: str = ""  # From delivery_location.address
    delivery_city: str = ""  # From delivery_location.city
    delivery_zip: str = ""  # From delivery_location.zip_code
    distance_km: Optional[float] = None

    # Delivery instructions (decrypted)
    delivery_instruction_type: DeliveryInstructionType
    delivery_instructions: str = ""  # Decrypted!

    # Donation info
    is_donation: bool = False
    donation_org_id: Optional[str] = None

    # Timing
    scheduled_for: Optional[datetime] = None
    created_at: datetime
    accepted_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    # Status
    order_status: OrderStatus
    cancellation_reason: Optional[str] = None

    # Ratings (if visible)
    restaurant_rating: Optional[int] = None
    customer_rating: Optional[int] = None

    # Platform fees (transparent)
    platform_fee: Decimal

    model_config = ConfigDict(
        json_encoders={
            Decimal: lambda v: str(v),  # Convert Decimal to string for JSON
            datetime: lambda v: v.isoformat()  # ISO format dates
        }
    )

    @classmethod
    def from_order(cls, order: "Order") -> "OrderResponse":
        """Create response from internal Order model."""
        return cls(
            order_id=order.order_id,
            restaurant_id=order.restaurant_id,
            customer_id=order.customer_id,
            driver_id=order.driver_id,
            items=order.items,
            subtotal=order.subtotal,
            tax_amount=order.tax_amount,
            delivery_fee=order.delivery_fee,
            tip_amount=order.tip_amount,
            total_amount=order.total_amount,
            payment_status=order.payment_status,
            # Extract safe location info
            delivery_address=order.delivery_location.address if order.delivery_location else "",
            delivery_city=order.delivery_location.city if order.delivery_location else "",
            delivery_zip=order.delivery_location.zip_code if order.delivery_location else "",
            distance_km=order.distance_km,
            delivery_instruction_type=order.delivery_instruction_type,
            delivery_instructions=order.delivery_instructions,  # Decrypted via property
            is_donation=order.is_donation,
            donation_org_id=order.donation_org_id,
            scheduled_for=order.scheduled_for,
            created_at=order.created_at,
            accepted_at=order.accepted_at,
            picked_up_at=order.picked_up_at,
            delivered_at=order.delivered_at,
            order_status=order.order_status,
            cancellation_reason=order.cancellation_reason,
            restaurant_rating=order.restaurant_rating,
            customer_rating=order.customer_rating,
            platform_fee=order.platform_fee,
        )

'''----------------DRIVER INFORMATION---------------'''
'''consider adding extra anonymity and/or encryption here'''
# Route Preferences for Driver Optimization
class RoutePreferences(BaseModel):
    revenue_vs_rest: int = Field(default=50, ge=0, le=100)  # 0 = maximize rest, 100 = maximize revenue
    earn_vs_volunteer: int = Field(default=50, ge=0, le=100)  # 0 = volunteer focus, 100 = earn focus
    adventure_mode: bool = False
    end_destination: str = ""
    end_time: str = ""
    max_distance: int = Field(default=10, ge=1, le=100)

# Driver Models
class Driver(BaseModel):
    model_config = ConfigDict(extra="ignore")
    driver_id: str = Field(default_factory=lambda: generate_id("driver"))
    user_id: str
    vehicle_type: VehicleType = VehicleType.CAR
    license_number: str = ""
    license_plate: str = ""
    is_available: bool = True
    current_location: Optional[EncryptedLocation] = None
    # Route Optimization Preferences
    route_preferences: RoutePreferences = Field(default_factory=RoutePreferences)
    # Whether the driver opts in to appear on the volunteer leaderboard
    show_in_leaderboard: bool = False
    total_deliveries: int = 0
    surplus_deliveries: int = 0
    total_earnings: float = 0.0
    rating: float = 5.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DriverCreate(BaseModel):
    vehicle_type: VehicleType = VehicleType.CAR
    license_number: str = ""
    license_plate: str = ""

class DriverLocationUpdate(BaseModel):
    lat: float
    lng: float

# Organization Models (for food distribution)
class Organization(BaseModel):
    model_config = ConfigDict(extra="ignore")
    org_id: str = Field(default_factory=lambda: generate_id("org"))
    user_id: str
    name: str
    description: str = ""
    org_type: str = ""  # food_bank, shelter, community_kitchen
    location: EncryptedLocation
    contact_email: str = ""
    contact_phone: str = ""
    delivery_address: Optional[str] = None # Optional delivery address
    is_verified: bool = False
    total_received: int = 0  # Total meals received
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class OrganizationCreate(BaseModel):
    name: str
    description: str = ""
    org_type: str = ""
    lat: float
    lng: float
    address: str = ""
    city: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    delivery_address: Optional[str] = None

class OrganizationSettingsUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    org_type: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    delivery_address: Optional[str] = None

# Surplus Food Models
class SurplusFood(BaseModel):
    model_config = ConfigDict(extra="ignore")
    surplus_id: str = Field(default_factory=lambda: generate_id("surplus"))
    user_id: str # Owner user ID (Restaurant or Free Kitchen)
    restaurant_id: Optional[str] = None # Optional, for backward compatibility or specific restaurant linkage
    restaurant_name: str = ""
    description: str
    quantity: int
    original_price: float
    discounted_price: float = 0.0  # 0 means free
    expiry_time: datetime
    pickup_location: EncryptedLocation
    is_available: bool = True
    reserved_by_org_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SurplusFoodCreate(BaseModel):
    description: str
    quantity: int
    original_price: float
    discounted_price: float = 0.0
    expiry_hours: int = 4  # Hours until expiry

# Surplus Delivery Model - Driver volunteers to deliver surplus to organizations
class SurplusDeliveryStatus(str, Enum):
    PENDING = "pending"           # Waiting for driver pickup
    PICKED_UP = "picked_up"       # Driver has the food
    IN_TRANSIT = "in_transit"     # On the way to organization
    DELIVERED = "delivered"       # Completed
    CANCELLED = "cancelled"

class SurplusDelivery(BaseModel):
    model_config = ConfigDict(extra="ignore")
    delivery_id: str = Field(default_factory=lambda: generate_id("sdel"))
    surplus_id: str
    restaurant_id: str
    restaurant_name: str = ""
    org_id: str
    org_name: str = ""
    driver_id: Optional[str] = None
    driver_name: str = ""
    status: SurplusDeliveryStatus = SurplusDeliveryStatus.PENDING
    pickup_location: Optional[EncryptedLocation] = None
    delivery_location: Optional[EncryptedLocation] = None
    estimated_time: Optional[int] = None  # minutes
    quantity: int = 1
    description: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    picked_up_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

# Community Support Models
class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: str = Field(default_factory=lambda: generate_id("msg"))
    order_id: str
    sender_id: str
    receiver_id: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_read: bool = False

class MessageCreate(BaseModel):
    order_id: str
    receiver_id: str
    content: str

class SupportQuestion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    question_id: str = Field(default_factory=lambda: generate_id("q"))
    user_id: str
    user_name: str = ""
    user_role: UserRole = UserRole.CUSTOMER
    question: str
    category: str = "general"  # general, delivery, payment, restaurant, technical
    is_resolved: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SupportAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    answer_id: str = Field(default_factory=lambda: generate_id("a"))
    question_id: str
    user_id: str
    user_name: str = ""
    user_role: UserRole
    answer: str
    is_accepted: bool = False
    upvotes: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class QuestionCreate(BaseModel):
    question: str
    category: str = "general"

class AnswerCreate(BaseModel):
    question_id: str
    answer: str

# Forum Models
class ForumCategory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    category_id: str = Field(default_factory=lambda: generate_id("cat"))
    name: str
    description: str = ""
    is_regional: bool = False # To distinguish between regional and general forums

class ForumPost(BaseModel):
    model_config = ConfigDict(extra="ignore")
    post_id: str = Field(default_factory=lambda: generate_id("post"))
    category_id: str
    user_id: str
    user_name: str
    user_role: UserRole
    title: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
class ForumReply(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reply_id: str = Field(default_factory=lambda: generate_id("reply"))
    post_id: str
    user_id: str
    user_name: str
    user_role: UserRole
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ForumPostCreate(BaseModel):
    category_id: str
    title: str
    content: str

class ForumReplyCreate(BaseModel):
    post_id: str
    content: str

# Payment Models
class PaymentTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    transaction_id: str = Field(default_factory=lambda: generate_id("txn"))
    order_id: str
    user_id: str
    amount: float
    currency: str = "usd"
    stripe_session_id: str = ""
    payment_status: PaymentStatus = PaymentStatus.PENDING
    metadata: Dict = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Review Models
class Review(BaseModel):
    model_config = ConfigDict(extra="ignore")
    review_id: str = Field(default_factory=lambda: generate_id("rev"))
    order_id: str
    customer_id: str
    customer_name: str = ""
    restaurant_id: Optional[str] = None
    driver_id: Optional[str] = None
    rating: int  # 1-5
    comment: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ReviewCreate(BaseModel):
    order_id: str
    restaurant_rating: Optional[int] = None
    comment: str = ""

# Analytics Models
class DashboardStats(BaseModel):
    total_orders: int = 0
    active_orders: int = 0
    total_revenue: float = 0.0
    meals_donated: int = 0
    active_drivers: int = 0
    active_restaurants: int = 0
    surplus_saved: int = 0
