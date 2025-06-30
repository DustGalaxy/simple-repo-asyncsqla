import inspect
from typing import Any, Self, Type, get_type_hints
from dataclasses import is_dataclass, fields, asdict, MISSING

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import inspect as sqla_inspect


def get_attrs(model: Type[Any]) -> set[str]:
    """
    Get model fields/attributes for various model types:
    Pydantic v2, dataclasses, SQLAlchemy models, and general classes.
    """
    # 1. Pydantic v2 models
    if hasattr(model, "model_fields"):
        return set(model.model_fields.keys())

    # 2. Dataclass models
    if is_dataclass(model):
        return {f.name for f in fields(model) if f.init}

    # 3. SQLAlchemy model
    if inspect.isclass(model) and issubclass(model, DeclarativeBase):
        try:
            mapper = sqla_inspect(model).mapper
            attrs = set(col.key for col in mapper.columns)
            attrs.update(rel.key for rel in mapper.relationships)
            return attrs
        except Exception:
            pass

    # 4. General class
    if inspect.isclass(model):
        all_annotations = {}
        for base in reversed(model.__mro__):
            all_annotations.update(getattr(base, "__annotations__", {}))
        return set(all_annotations.keys())

    return set()


def same_attrs(model1: Type[Any], model2: Type[Any]) -> bool:
    attrs1 = get_attrs(model1)
    attrs2 = get_attrs(model2)
    return attrs1 == attrs2


class BaseDomainModel:
    """
    Universal base class providing implementations
    of 'model_validate' and 'model_dump' methods for:
    - Regular Python classes
    - Dataclasses
    """

    id: Any

    @classmethod
    def model_validate(cls, obj: Any, *args, **kwargs) -> Self:
        """
        Implementation of model_validate for creating an instance of the domain model.
        Automatically copies attributes from 'obj' to a new instance of 'cls'.
        """
        instance = cls() if not inspect.isfunction(cls.__init__) else cls(*args, **kwargs)

        if is_dataclass(cls):
            field_names = {f.name for f in fields(cls)}
            init_args = {name: getattr(obj, name) for name in field_names if hasattr(obj, name)}
            return cls(**init_args)

        for attr_name in get_type_hints(cls).keys():
            if hasattr(obj, attr_name):
                setattr(instance, attr_name, getattr(obj, attr_name))

        if hasattr(obj, "id") and not hasattr(instance, "id"):
            instance.id = obj.id

        return instance

    def model_dump(self, *args, exclude_unset: bool = False, **kwargs) -> dict[str, Any]:
        """
        Implementation of model_dump for converting a domain model instance to a dictionary.
        """
        if is_dataclass(self):
            data = asdict(self)
            if exclude_unset:
                defaults = {f.name: f.default for f in fields(self) if f.default is not MISSING}
                return {k: v for k, v in data.items() if k not in defaults or v != defaults[k]}
            return data

        result = self.__dict__.copy()
        if exclude_unset:
            sig = inspect.signature(self.__init__)
            defaults = {}
            for param_name, param in sig.parameters.items():
                if param_name != "self" and param.default is not inspect.Parameter.empty:
                    defaults[param_name] = param.default

            filtered_result = {}
            for key, value in result.items():
                if key in defaults and value == defaults[key]:
                    continue
                filtered_result[key] = value
            return filtered_result

        return result
