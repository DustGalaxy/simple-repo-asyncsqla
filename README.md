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

# you can use dataclass or normal class but see protocol - DomainModel
class UserDTO(BaseModel):
    id: int = 0
    name: str
    email: str
    is_active: bool = True
    
    model_config = ConfigDict(from_attributes=True)

engine = create_async_engine("sqlite+aiosqlite:///./db.sqlite3")
async_session = async_sessionmaker(engine, expire_on_commit=False)

user_crud = crud_factory(User, UserDTO)

async def example():
    async with async_session() as session:
        # Create
        new_user = await user_crud.create(
            session, 
            UserDTO(name="John Doe", email="john@example.com")
        )
        
        # Read
        user = await user_crud.get_one(session, new_user.id)

        # Update
        user.name = "John Smith"
        updated = await user_crud.update(session, user, user.id)
        
        # List with pagination
        users, total = await user_crud.get_all(
            session,
            offset=0,
            limit=10,
            order_by="name",
            desc=True
        )
        
        # Delete
        await user_crud.remove(session, user.id)
        
        # Get exception
        try:
            user = await user_crud.get_one(session, new_user.name, column="name")
        except NotFoundException: 
            ...
```

### Custom Repository

Extend the base repository with advanced query methods:

```python
from sqlalchemy import select, case, func, text

from simple_repository import crud_factory

from .models.user import User
from .domains.user import UserDTO

class UserRepository(crud_factory(User, UserDTO)):
    """Custom repository with advanced analytics capabilities."""
    
    @classmethod
    async def get_user_activity_stats(
        cls,
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
                cls.sqla_model.id,
                cls.sqla_model.name,
                cls.sqla_model.email,
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
            .join(orders_stats, cls.sqla_model.id == orders_stats.c.user_id)
            .where(cls.sqla_model.is_active == True)
            .order_by(text('engagement_score DESC'))
        )
        
        result = await session.execute(query)
        return list(result.mappings().all())

# Usage example
async def analyze_user_activity(session):
    stats = await UserRepository.get_user_activity_stats(
        session,
        min_orders=5,   
        days_window=30   
    )
    
```

### Error Handling

```python
from simple_repository.exceptions import NotFoundException

from .my_repository import user_crud

async def get_user(session, user_id: int) -> UserDTO:
    try:
        return await user_crud.get_one(session, user_id)
    except NotFoundException:
        raise HTTPException(status_code=404, detail="User not found")
```

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License.