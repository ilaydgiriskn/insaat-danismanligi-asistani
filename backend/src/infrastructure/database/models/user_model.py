"""User profile SQLAlchemy model."""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, Integer, Float, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from infrastructure.database.session import Base


class UserModel(Base):
    """SQLAlchemy model for user profiles."""
    
    __tablename__ = "user_profiles"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    # Session tracking
    session_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # User information
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    surname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hometown: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profession: Mapped[str | None] = mapped_column(String(255), nullable=True)
    marital_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    has_children: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    estimated_salary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hobbies: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    
    # New Fields
    social_amenities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    purchase_purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lifestyle_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Budget
    budget_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    
    # Location
    location_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_district: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Property preferences
    property_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    min_rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_balcony: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_parking: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    
    # Additional information
    family_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Tracking
    answered_categories: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False
    )
    
    def __repr__(self) -> str:
        return f"<UserModel(id={self.id}, session_id={self.session_id})>"
