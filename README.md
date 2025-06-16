# Simple Repository AsyncSQLA

A lightweight and type-safe repository pattern implementation for SQLAlchemy async with Pydantic integration.

## Features

- 🚀 Async-first design
- 🔒 Type-safe CRUD operations
- 🎯 Easy integration with SQLAlchemy models
- 📦 Pydantic support out of the box
- 🛠 Generic repository pattern implementation

## Installation

```bash
pip install simple-repo-asyncsqla
```

## Quick Start

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.declarative import DeclarativeMeta
from pydantic import BaseModel
from simple_repository import crud_factory

# Define your SQLAlchemy model
class UserModel(DeclarativeMeta):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str]

# Define your Pydantic model
class UserDTO(BaseModel):
    id: int = 0
    name: str
    email: str
    
    model_config = {"from_attributes": True}

# Create CRUD repository
user_crud = crud_factory(UserModel, UserDTO)

# Use in your async code
async def example_usage():
    async with async_session() as session:
        # Create
        new_user = await user_crud.create(
            session, 
            UserDTO(name="John", email="john@example.com")
        )
        
        # Read
        user = await user_crud.get_one(session, new_user.id)
        
        # Update
        updated = await user_crud.update(
            session, 
            UserDTO(id=user.id, name="John Doe", email=user.email)
        )
        
        # Delete
        await user_crud.remove(session, user.id)
        
        # Get all with pagination
        users, count = await user_crud.get_all(
            session,
            skip=0,
            limit=10,
            order_by="id"
        )
```

## Features in Detail

### Type Safety

The repository ensures type safety between your SQLAlchemy models and Pydantic DTOs:

```python
def crud_factory(sqla_model: Type[SqlaModel], domain_model: Type[DomainModel]) -> CRUDRepository:
    """
    Creates a type-safe CRUD repository for your models.
    Validates that SQLAlchemy and Domain models have matching attributes.
    """
```

### Async Support

All operations are async by default and work with SQLAlchemy's async session:

- `create(session, DomainModel)`
- `create_many(session, list[DomainModel])`
- `get_one(session, id)`
- `get_many(session, filter, column, order_by, desc)`
- `get_all(session, offset, limit, order_by, desc)`
- `update(session, DomainModel, id, column)`
- `remove(session, id, column, raise_not_found)`
- `remove_many(session, ids, column)`
- `count(session, filters)`

### Error Handling

Built-in exceptions for common cases:

- `NotFoundException`: When entity is not found
- `IntegrityConflictException`: For database integrity violations
- `DiffAtrrsOnCreateCrud`: When model attributes don't match
- `RepositoryException`: Base exception class

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## License

MIT