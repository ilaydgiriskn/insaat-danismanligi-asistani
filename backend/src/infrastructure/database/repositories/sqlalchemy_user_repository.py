"""SQLAlchemy implementation of user repository."""

from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities import UserProfile
from domain.value_objects import Budget, Location, PropertyPreferences
from domain.enums import PropertyType, QuestionCategory
from domain.repositories import IUserRepository
from infrastructure.database.models import UserModel


class SQLAlchemyUserRepository(IUserRepository):
    """Concrete implementation of IUserRepository using SQLAlchemy."""
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session
    
    async def create(self, user_profile: UserProfile) -> UserProfile:
        """Create a new user profile in the database."""
        model = self._entity_to_model(user_profile)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._model_to_entity(model)
    
    async def get_by_id(self, user_id: UUID) -> Optional[UserProfile]:
        """Retrieve a user profile by ID."""
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._model_to_entity(model)
    
    async def get_by_session_id(self, session_id: str) -> Optional[UserProfile]:
        """Retrieve a user profile by session ID."""
        stmt = select(UserModel).where(UserModel.session_id == session_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._model_to_entity(model)
    
    async def update(self, user_profile: UserProfile) -> UserProfile:
        """Update an existing user profile."""
        stmt = select(UserModel).where(UserModel.id == user_profile.id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            raise ValueError(f"User profile {user_profile.id} not found")
        
        self._update_model_from_entity(model, user_profile)
        await self.session.flush()
        await self.session.refresh(model)
        
        return self._model_to_entity(model)
    
    async def delete(self, user_id: UUID) -> bool:
        """Delete a user profile."""
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            return False
        
        await self.session.delete(model)
        await self.session.flush()
        return True
    
    def _entity_to_model(self, entity: UserProfile) -> UserModel:
        """Convert domain entity to ORM model."""
        model = UserModel(
            id=entity.id,
            session_id=entity.session_id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            name=entity.name,
            email=entity.email,
            phone=entity.phone,
            hometown=entity.hometown,
            profession=entity.profession,
            marital_status=entity.marital_status,
            has_children=entity.has_children,
            family_size=entity.family_size,
            hobbies=entity.hobbies,
            estimated_salary=entity.estimated_salary,
            lifestyle_notes=entity.lifestyle_notes,
            answered_categories=[cat.value for cat in entity.answered_categories],
        )
        
        # Budget
        if entity.budget:
            model.budget_min = entity.budget.min_amount
            model.budget_max = entity.budget.max_amount
            model.budget_currency = entity.budget.currency
        
        # Location
        if entity.location:
            model.location_city = entity.location.city
            model.location_district = entity.location.district
            model.location_country = entity.location.country
        
        # Property preferences
        if entity.property_preferences:
            model.property_type = entity.property_preferences.property_type.value
            model.min_rooms = entity.property_preferences.min_rooms
            model.max_rooms = entity.property_preferences.max_rooms
            model.has_balcony = entity.property_preferences.has_balcony
            model.has_parking = entity.property_preferences.has_parking
        
        return model
    
    def _update_model_from_entity(self, model: UserModel, entity: UserProfile) -> None:
        """Update ORM model from domain entity."""
        model.session_id = entity.session_id
        model.updated_at = entity.updated_at
        model.name = entity.name
        model.email = entity.email
        model.phone = entity.phone
        model.hometown = entity.hometown
        model.profession = entity.profession
        model.marital_status = entity.marital_status
        model.has_children = entity.has_children
        model.family_size = entity.family_size
        model.hobbies = entity.hobbies
        model.estimated_salary = entity.estimated_salary
        model.lifestyle_notes = entity.lifestyle_notes
        model.answered_categories = [cat.value for cat in entity.answered_categories]
        
        # Budget
        if entity.budget:
            model.budget_min = entity.budget.min_amount
            model.budget_max = entity.budget.max_amount
            model.budget_currency = entity.budget.currency
        else:
            model.budget_min = None
            model.budget_max = None
            model.budget_currency = None
        
        # Location
        if entity.location:
            model.location_city = entity.location.city
            model.location_district = entity.location.district
            model.location_country = entity.location.country
        else:
            model.location_city = None
            model.location_district = None
            model.location_country = None
        
        # Property preferences
        if entity.property_preferences:
            model.property_type = entity.property_preferences.property_type.value
            model.min_rooms = entity.property_preferences.min_rooms
            model.max_rooms = entity.property_preferences.max_rooms
            model.has_balcony = entity.property_preferences.has_balcony
            model.has_parking = entity.property_preferences.has_parking
        else:
            model.property_type = None
            model.min_rooms = None
            model.max_rooms = None
            model.has_balcony = None
            model.has_parking = None
    
    def _model_to_entity(self, model: UserModel) -> UserProfile:
        """Convert ORM model to domain entity."""
        # Reconstruct Budget value object
        budget = None
        if model.budget_min is not None and model.budget_max is not None:
            budget = Budget(
                min_amount=model.budget_min,
                max_amount=model.budget_max,
                currency=model.budget_currency or "TRY",
            )
        
        # Reconstruct Location value object
        location = None
        if model.location_city:
            location = Location(
                city=model.location_city,
                district=model.location_district,
                country=model.location_country or "Turkey",
            )
        
        # Reconstruct PropertyPreferences value object
        property_preferences = None
        if model.property_type:
            from domain.enums import PropertyType
            property_preferences = PropertyPreferences(
                property_type=PropertyType(model.property_type),
                min_rooms=model.min_rooms,
                max_rooms=model.max_rooms,
                has_balcony=model.has_balcony,
                has_parking=model.has_parking,
            )
        
        # Reconstruct answered categories
        answered_categories = {
            QuestionCategory(cat) for cat in (model.answered_categories or [])
        }
        
        # Create entity
        entity = UserProfile(
            id=model.id,
            session_id=model.session_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            name=model.name,
            email=model.email,
            phone=model.phone,
            hometown=model.hometown,
            profession=model.profession,
            marital_status=model.marital_status,
            has_children=model.has_children,
            budget=budget,
            location=location,
            property_preferences=property_preferences,
            family_size=model.family_size,
            hobbies=model.hobbies,
            estimated_salary=model.estimated_salary,
            lifestyle_notes=model.lifestyle_notes,
            answered_categories=answered_categories,
        )
        
        return entity
