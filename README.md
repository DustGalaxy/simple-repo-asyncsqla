# Simple Repository AsyncSQLA

A lightweight and type-safe repository pattern implementation for SQLAlchemy async with Pydantic integration.

## Features

- 🚀 Async-first design
- 🔒 Type-safe CRUD operations
- 🎯 Easy integration with SQLAlchemy models
- 📦 Pydantic support out of the box
- 🛠 Generic repository pattern implementation
- 📝 Full type hints support

## Installation

```bash
pip install simple-repo-asyncsqla
```

## Quick Start

### Common example

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from pydantic import BaseModel, ConfigDict

from simple_repository import crud_factory
from simple_repository.exceptions import NotFoundException

# Define your models
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)

# You can use dataclass or a regular class with inherit BaseDomainModel, refer to the protocol - DomainModel for details
class UserDomain(BaseModel):
    id: int = 0
    name: str
    email: str
    is_active: bool = True
    
    model_config = ConfigDict(from_attributes=True)

# You can use dataclass or a regular class with inherit BaseSchema, refer to the protocol - Schema for details
class UserPatch(BaseModel):
    name: str | None = None
    email: str | None = None
    is_active: bool | None = None

engine = create_async_engine("sqlite+aiosqlite:///./db.sqlite3")
async_session_factory = async_sessionmaker(engine, expire_on_commit=False) # Use session factory

# Create the repository class for User
UserRepositoryClass = crud_factory(User, UserDomain)
# Create a repository instance, passing the session factory
user_repo = UserRepositoryClass()

async def example():
    # Operations are now called on the repository instance
    async with async_session_factory() as session:
        # Create
        new_user = await user_repo.create(
            session, 
            UserDomain(name="John Doe", email="john@example.com")
        )
        
        # Read
        user = await user_repo.get_one(session, new_user.id)

        # Update
        user.name = "John Smith"
        updated = await user_repo.update(session, user)

        # Patch
        data = UserPatch(name="Fredy Smith", email="fredy@example.com")
        patched = await user_repo.patch(session, data, updated.id) # Pass ID for patch

        # List with pagination
        users, total = await user_repo.get_all(
            session,
            offset=0,
            limit=10,
            order_by="name",
            desc=True
        )
        
        # Delete
        await user_repo.remove(session, user.id)
        
        # Get exception
        try:
            user = await user_repo.get_one(session, new_user.name, column="name")
        except NotFoundException: 
            ...

```

### Important part is sameness attrs in SQLA and in Domain models as in the example


```python
class User(Base):
    __tablename__ = "users"

    # attrs: id, name, email, is_active
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)

class UserDTO(BaseModel):

    # attrs: id, name, email, is_active
    id: int = 0
    name: str
    email: str
    is_active: bool = True
    
    model_config = ConfigDict(from_attributes=True)

```

If attributes do not match, DiffAtrrsOnCreateCrud exception will be raised upon CRUD creation.

### Custom Repository

Extend the base repository with advanced query methods:

```python
from sqlalchemy import select, case, func, text

from simple_repository import crud_factory
from simple_repository.abctract import IAsyncCrud

from .models.user import User
from .domains.user import UserDomain
from .db import async_session_factory

# Define interface for custom operations OR don't
class IUserRepository(IAsyncCrud[UserSQLA, UserDomain]):
    @abstractmethod
    async def get_user_activity_stats(
        self,
        min_orders: int = 5,
        days_window: int = 30
    ) -> list[dict]:
        pass

# Inherit from the interface (if defined) and from the class created by the factory
class UserRepository(IUserRepository, crud_factory(UserSQLA, UserDomain)):
    """Custom repository with advanced analytical capabilities."""
    async def get_user_activity_stats(
        self,
        session,
        min_orders: int = 5,
        days_window: int = 30
    ) -> list[dict]:
        current_date = func.current_timestamp()
        window_date = current_date - text(f"interval '{days_window} days'")
        
        orders_stats = (
            select(
                Order.user_id,
                func.count().label('order_count'),
                func.sum(Order.total_amount).label('total_spent'),
                func.avg(Order.total_amount).label('avg_order_value'),
                func.count(case(
                    (Order.created_at > window_date, 1)
                )).label('recent_orders'),
                (func.max(Order.created_at) - func.min(Order.created_at)) /
                    func.nullif(func.count() - 1, 0)
                    .label('avg_order_interval')
            )
            .group_by(Order.user_id)
            .having(func.count() >= min_orders)
            .alias('orders_stats')
        )
        
        query = (
            select(
                self.sqla_model.id,
                self.sqla_model.name,
                self.sqla_model.email,
                orders_stats.c.order_count,
                orders_stats.c.total_spent,
                orders_stats.c.avg_order_value,
                orders_stats.c.recent_orders,
                orders_stats.c.avg_order_interval,
                (
                    orders_stats.c.recent_orders * 0.4 +
                    func.least(orders_stats.c.total_spent / 1000, 10) * 0.3 +
                    (orders_stats.c.order_count * 0.3)
                ).label('engagement_score'),
                func.percent_rank().over(
                    order_by=orders_stats.c.total_spent
                ).label('spending_percentile')
            )
            .join(orders_stats, self.sqla_model.id == orders_stats.c.user_id)
            .where(self.sqla_model.is_active == True)
            .order_by(text('engagement_score DESC'))
        )
        
        result = await session.execute(query)
        return list(result.mappings().all())

# Usage example
async def analyze_user_activity():
    user_repo_instance = UserRepository()
    with async_session_factory() as session:
        stats = await user_repo_instance.get_user_activity_stats(
            session,
            min_orders=5,   
            days_window=30   
        )
        return stats
    
```

### Error Handling

```python
from fastapi import HTTPException, APIRouter
from simple_repository.exceptions import NotFoundException
from sqlalchemy.ext.asyncio import AsyncSession

from .db import async_session_factory
from .my_repository import user_crud
from .domains.user import UserDomain

router = APIRouter("/user")

@router.get("/{user_id}")
async def get_user(
    session: Annotated[AsyncSession, Depends(async_session_factory)], 
    user_id: int,
) -> UserDomain:
    try:
        return await user_crud.get_one(session, user_id)
    except NotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
```

### Out-of-the-box Supported Operations

 - create
 - create_many
 - get_one
 - get_many
 - get_all
 - patch
 - update
 - remove
 - remove_many
 - count

### Class Attribute Protection

The library now uses the FrozenClassAttributesMeta metaclass to prevent accidental or unintended reassignment of sqla_model and domain_model attributes at the class level after they have been set by crud_factory. This ensures the stability and predictability of repository behavior.

Attempting to modify these attributes after class creation will result in an AttributeError.

```python
# Example:
MyUserRepoClass = crud_factory(UserSQLA, UserDomain)
try:
    MyUserRepoClass.sqla_model = SomeOtherSQLA # This will raise an AttributeError
    MyUserRepoClass.domain_model = SomeOtherDomain # This also will raise an AttributeError
except AttributeError as e:
    print(f"Error: {e}")
```

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License.