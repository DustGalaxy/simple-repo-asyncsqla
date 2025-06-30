import pytest
from dataclasses import dataclass, fields, MISSING
from typing import Any, AsyncGenerator, Type

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

from simple_repository.utils import BaseDomainModel, BaseSchema
from src.simple_repository.abctract import IAsyncCrud
from src.simple_repository.implementation import AsyncCrud
from src.simple_repository.factory import crud_factory
from src.simple_repository.protocols import SqlaModel, DomainModel
from src.simple_repository.exceptions import DiffAtrrsOnCreateCrud, NotFoundException

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
def crud(sqla_model, domain_model) -> IAsyncCrud[SqlaModel, DomainModel]:
    """Create CRUD repository for tests."""
    crud_class = crud_factory(sqla_model, domain_model)
    return crud_class()


def test_crud_factory_with_pydantic():
    """Test crud_factory with Pydantic model."""

    class SimpleSqlaModel:
        __tablename__ = "simple"
        id: Mapped[int]
        field: Mapped[str]

    class SimpleDomainModel(BaseModel):
        id: int
        field: str

    crud = crud_factory(SimpleSqlaModel, SimpleDomainModel)
    assert crud is not None


@pytest.mark.asyncio
async def test_crud_factory_with_dataclass(session: AsyncSession):
    """Test crud_factory with dataclass model."""

    @dataclass
    class SimpleDomainModel(BaseDomainModel):
        id: int = 0
        name: str = ""
        description: str | None = None

    crud = crud_factory(SqlaTestModel, SimpleDomainModel)
    assert crud is not None

    impl_crud = crud()
    dm = SimpleDomainModel(name="filled")
    created = await impl_crud.create(session, dm)

    assert created.id > 0
    assert created.name == "filled"
    assert created.description is None

    @dataclass
    class PatchSchema(BaseSchema):
        name: str | None = None
        description: str | None = None

    data = PatchSchema(description="...")
    patched = await impl_crud.patch(session, data, created.id)

    assert patched.name == "filled"
    assert patched.description == "..."


@pytest.mark.asyncio
async def test_crud_factory_with_class(session: AsyncSession):
    """Test crud_factory with class model."""

    class SimpleDomainModel(BaseDomainModel):
        id: int
        name: str
        description: str | None

        def __init__(self, id: int = 0, name: str = "", description: str | None = None) -> None:
            self.id = id
            self.name = name
            self.description = description

    crud = crud_factory(SqlaTestModel, SimpleDomainModel)
    assert crud is not None

    impl_crud = crud()
    dm = SimpleDomainModel(name="filled")
    created = await impl_crud.create(session, dm)

    assert created.id > 0
    assert created.name == "filled"
    assert created.description is None

    class PatchSchema(BaseSchema):
        name: str | None = None
        description: str | None = None

        def __init__(self, name: str | None = None, description: str | None = None) -> None:
            self.name = name
            self.description = description

    data = PatchSchema(description="...")
    patched = await impl_crud.patch(session, data, created.id)

    assert patched.name == "filled"
    assert patched.description == "..."


def test_crud_factory_different_attributes():
    """Test crud_factory raises error when attributes don't match."""

    class SimpleSqlaModel:
        __tablename__ = "simple"
        id: Mapped[int]
        field1: Mapped[str]
        field2: Mapped[str]

    class SimpleDomainModel(BaseModel):
        id: int
        field1: str

    with pytest.raises(DiffAtrrsOnCreateCrud):
        crud_factory(SimpleSqlaModel, SimpleDomainModel)


def test_crud_class_name():
    class SimpleSqlaModel:
        __tablename__ = "simple"
        id: Mapped[int]
        field: Mapped[str]

    class SimpleDomainModel(BaseModel):
        id: int
        field: str

    crud = crud_factory(SimpleSqlaModel, SimpleDomainModel)
    assert crud.__name__ == "SimpleSqlaModelRepository"


@pytest.mark.asyncio
async def test_crud_operations(
    session: AsyncSession, crud: AsyncCrud[SqlaTestModel, DomainTestModel], domain_model: Type[DomainTestModel]
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
    updated = await crud.update(session, retrieved)
    assert updated.name == "Updated"

    # Patch
    @dataclass
    class PatchSchema:
        name: str | None = None
        description: str | None = None

        def model_dump(self, *, exclude_unset: bool = False) -> dict[str, Any]:
            result = {}

            for field in fields(self):
                value = getattr(self, field.name)
                if exclude_unset:
                    if field.default is not MISSING and value == field.default:
                        continue

                    elif field.default_factory is not MISSING and value == field.default_factory():
                        continue

                result[field.name] = value
            return result

    data = PatchSchema(name="Patched")

    patched = await crud.patch(session, data, retrieved.id)
    assert patched.name == "Patched"
    assert patched.description == "Description"

    # List
    models, count = await crud.get_all(session, order_by="id")
    assert len(models) == 1
    assert count == 1
    assert models[0].name == "Patched"

    # Filter
    filtred = await crud.get_many(session, filter="Description", column="description")
    assert len(filtred) == 1

    # Delete
    await crud.remove(session, created.id)

    with pytest.raises(NotFoundException):
        await crud.get_one(session, created.id)
