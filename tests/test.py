import pytest
from dataclasses import dataclass
from typing import Self, Any, AsyncGenerator, Type

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

from src.simple_repository.repository import crud_factory, AsyncCrud
from src.simple_repository.protocols import SqlaModel
from src.simple_repository.exceptions import DiffAtrrsOnCreateCrud, NotFoundException
from pydantic import BaseModel, ConfigDict, Field

from tests.database import Base, async_session_maker, create_db, drop_db


@pytest.fixture(autouse=True)
async def setup_database():
    """Setup and teardown the test database."""
    await drop_db()
    await create_db()
    yield
    await drop_db()


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session for tests."""
    async with async_session_maker() as session:
        yield session


class SqlaTestModel(Base):
    """SQLAlchemy model for testing."""

    __tablename__ = "test_table"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str]
    description: Mapped[str | None]


@pytest.fixture
def sqla_model() -> Type[SqlaTestModel]:
    """SQLAlchemy model for basic tests."""
    return SqlaTestModel


# Define test models
class DomainTestModel(BaseModel):
    """Pydantic model for testing."""
    id: int = Field(default=0)
    name: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


@pytest.fixture
def domain_model() -> Type[DomainTestModel]:
    """Pydantic model for basic tests."""
    return DomainTestModel


@pytest.fixture
def crud(sqla_model, domain_model) -> Type[AsyncCrud[SqlaModel, DomainTestModel]]:
    """Create CRUD repository for tests."""
    return crud_factory(sqla_model, domain_model)


def test_crud_factory_with_pydantic():
    """Test crud_factory with Pydantic model."""

    class SimpleSqlaModel:
        __tablename__ = "simple"
        field: Mapped[str]

    class SimpleDomainModel(BaseModel):
        field: str

    crud = crud_factory(SimpleSqlaModel, SimpleDomainModel)
    assert crud is not None


def test_crud_factory_with_dataclass():
    """Test crud_factory with dataclass model."""

    class SimpleSqlaModel:
        __tablename__ = "simple"
        field: Mapped[str]

    @dataclass
    class SimpleDomainModel:
        field: str

        def model_dump(self) -> dict[str, Any]:
            return {"field": self.field}

        @classmethod
        def model_validate(cls, obj: SqlaModel) -> Self:
            return cls(field=obj.field)  # type: ignore

    crud = crud_factory(SimpleSqlaModel, SimpleDomainModel)
    assert crud is not None


def test_crud_factory_different_attributes():
    """Test crud_factory raises error when attributes don't match."""

    class SimpleSqlaModel:
        __tablename__ = "simple"
        field1: Mapped[str]
        field2: Mapped[str]

    class SimpleDomainModel(BaseModel):
        field1: str

    with pytest.raises(DiffAtrrsOnCreateCrud):
        crud_factory(SimpleSqlaModel, SimpleDomainModel)


@pytest.mark.asyncio
async def test_crud_operations(
    session: AsyncSession, crud: Type[AsyncCrud[SqlaTestModel, DomainTestModel]], domain_model: Type[DomainTestModel]
):
    """Test basic CRUD operations."""
    # Create
    model = domain_model(name="Test", description="Description")
    created = await crud.create(session, model)
    assert created.id > 0
    assert created.name == "Test"

    # Read
    retrieved = await crud.get_one(session, created.id)
    assert retrieved is not None
    assert retrieved.name == created.name

    # Update
    retrieved.name = "Updated"
    updated = await crud.update(session, retrieved, retrieved.id)
    assert updated.name == "Updated"

    # List
    models, count = await crud.get_all(session, order_by="id")
    assert len(models) == 1
    assert count == 1
    assert models[0].name == "Updated"

    # Delete
    await crud.remove(session, created.id)
    try:
        await crud.get_one(session, created.id)
    except NotFoundException:
        pass
