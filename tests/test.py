import pytest
from dataclasses import dataclass
from typing import Self, Any
import asyncio

from sqlalchemy.orm import Mapped, mapped_column

from src.simple_repository.repository import crud_factory
from src.simple_repository.protocols import SqlaModel
from src.simple_repository.exceptions import DiffAtrrsOnCreateCrud
from pydantic import BaseModel, ConfigDict, Field

from tests.database import Base, async_session_maker, create_db, drop_db


def test1():
    class MyBelovedSqlaModel:
        __tablename__ = "1"

        meme: Mapped[str]

    class MyBelovedDomainModel(BaseModel):
        meme: str

        # def model_dump(self) -> dict[str, Any]:
        #     return {"meme": self.meme}

        # @classmethod
        # def model_validate(cls, sqla_model: SqlaModel) -> Self:
        #     return cls(meme=sqla_model.meme)  # type: ignore

    test_crud = crud_factory(MyBelovedSqlaModel, MyBelovedDomainModel)
    print("✅ Test 1 passed")


def test2():
    class MyBelovedSqlaModel:
        __tablename__ = "1"

        meme: Mapped[str]
        add_attr: Mapped[str]

    @dataclass
    class MyBelovedDomainModel:
        meme: str

        def model_dump(self) -> dict[str, Any]:
            return {"meme": self.meme}

        @classmethod
        def model_validate(cls, obj: SqlaModel) -> Self:
            return cls(meme=obj.meme)  # type: ignore

    try:
        test_crud = crud_factory(MyBelovedSqlaModel, MyBelovedDomainModel)
    except DiffAtrrsOnCreateCrud:
        print("✅ Test 2 passed")


async def test3():
    class MyBelovedSqlaModel(Base):
        __tablename__ = "1"
        id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
        meme: Mapped[str]

    class MyBelovedDomainModel(BaseModel):
        id: int = Field(default=0)
        meme: str | None = None

        model_config = ConfigDict(from_attributes=True)

    test_crud = crud_factory(MyBelovedSqlaModel, MyBelovedDomainModel)

    await drop_db()
    await create_db()

    async with async_session_maker() as session:
        d_model = await test_crud.create(session, MyBelovedDomainModel(meme="axaxxxax"))
        d_model = await test_crud.create(session, MyBelovedDomainModel(meme="axaxxxax"))
        d_model = await test_crud.create(session, MyBelovedDomainModel(meme="axaxxxax"))
        d_model = await test_crud.create(session, MyBelovedDomainModel(meme="axaxxxax"))
        assert d_model.meme == "axaxxxax"

        d_model.meme = "01010101010101010100101010010101110101"
        d_model = await test_crud.update(session, d_model, d_model.id)
        assert d_model.meme == "01010101010101010100101010010101110101"

        list_of_models, count = await test_crud.get_all(session=session, order_by="id")
        assert [obj.id for obj in list_of_models] == [1, 2, 3, 4]
    print("✅ Test 3 passed")


if __name__ == "__main__":
    test1()
    test2()
    asyncio.run(test3())
