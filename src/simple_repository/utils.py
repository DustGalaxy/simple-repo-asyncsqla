import inspect
from typing import Any, Mapping, Self, Type, Union, get_type_hints
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


class BaseSchema:
    def model_dump(self, *args, exclude_unset: bool = False, **kwargs) -> dict[str, Any]:
        if is_dataclass(self):
            data = asdict(self)
            if exclude_unset:
                defaults = {f.name: f.default for f in fields(self) if f.default is not MISSING}
                return {k: v for k, v in data.items() if k not in defaults or v != defaults[k]}
            return data
        else:
            result = self.__dict__.copy()
            if exclude_unset:
                filtered_result = {}
                sig = inspect.signature(self.__init__)
                init_defaults = {
                    p.name: p.default
                    for p in sig.parameters.values()
                    if p.name != "self" and p.default is not inspect.Parameter.empty
                }
                annotations = get_type_hints(self.__class__)

                for key, value in result.items():
                    if key in annotations and key in init_defaults and value == init_defaults[key]:
                        continue
                    filtered_result[key] = value
                return filtered_result
            return result


class BaseDomainModel:
    """
    Universal base class providing implementations
    of 'model_validate' and 'model_dump' methods for:
    - Regular Python classes
    - Dataclasses
    """

    id: Any

    @classmethod
    def _get_class_fields_info(cls) -> dict[str, Any]:
        """
        Helper to get field names and their types, and default values
        for the class, considering both dataclasses and regular classes.
        """
        field_info = {}
        if is_dataclass(cls):
            for f in fields(cls):
                field_info[f.name] = {
                    "type": f.type,
                    "has_default": f.default is not MISSING,
                    "default_value": f.default if f.default is not MISSING else None,
                    "is_init_arg": f.init,
                }
        else:
            annotations = get_type_hints(cls)
            init_signature = inspect.signature(cls.__init__)
            init_params = init_signature.parameters

            for name, param in init_params.items():
                if name == "self":
                    continue
                field_info[name] = {
                    "type": annotations.get(name, Any),
                    "has_default": param.default is not inspect.Parameter.empty,
                    "default_value": param.default if param.default is not inspect.Parameter.empty else None,
                    "is_init_arg": True,
                }
            for name, type_hint in annotations.items():
                if name not in field_info:
                    field_info[name] = {
                        "type": type_hint,
                        "has_default": False,
                        "default_value": None,
                        "is_init_arg": False,
                    }
        return field_info

    @classmethod
    def model_validate(cls, obj: Union[Mapping[str, Any], object]) -> Self:
        """
        Creates an instance of the domain model from an object (e.g., ORM model) or a dictionary.
        Automatically copies attributes from 'obj' to a new instance of 'cls'.
        """
        class_fields_info = cls._get_class_fields_info()
        init_args = {}
        post_init_attrs = {}

        source_data = {}
        if isinstance(obj, Mapping):
            source_data = obj
        else:
            for attr_name in dir(obj):
                if not attr_name.startswith("_") and hasattr(obj, attr_name):
                    source_data[attr_name] = getattr(obj, attr_name)

        for field_name, info in class_fields_info.items():
            value_from_source = source_data.get(field_name, MISSING)

            if value_from_source is not MISSING:
                if info["is_init_arg"]:
                    init_args[field_name] = value_from_source
                else:
                    post_init_attrs[field_name] = value_from_source
            elif info["has_default"]:
                if info["is_init_arg"]:
                    init_args[field_name] = info["default_value"]
                else:
                    post_init_attrs[field_name] = info["default_value"]

        instance = None
        try:
            instance = cls(**init_args)
        except TypeError as e:
            print(
                f"Warning: Could not initialize {cls.__name__} with provided init_args: {e}. Attempting to create empty instance and populate."
            )
            try:
                instance = cls()
            except TypeError:
                raise TypeError(
                    f"Cannot initialize {cls.__name__}. Missing required arguments for __init__ or source object is incomplete. Original error: {e}"
                )

        for attr_name, attr_value in post_init_attrs.items():
            setattr(instance, attr_name, attr_value)

        return instance

    def model_dump(self, *args, exclude_unset: bool = False, **kwargs) -> dict[str, Any]:
        if is_dataclass(self):
            data = asdict(self)
            if exclude_unset:
                defaults = {f.name: f.default for f in fields(self) if f.default is not MISSING}
                return {k: v for k, v in data.items() if k not in defaults or v != defaults[k]}
            return data
        else:
            result = self.__dict__.copy()
            if exclude_unset:
                filtered_result = {}
                sig = inspect.signature(self.__init__)
                init_defaults = {
                    p.name: p.default
                    for p in sig.parameters.values()
                    if p.name != "self" and p.default is not inspect.Parameter.empty
                }
                annotations = get_type_hints(self.__class__)

                for key, value in result.items():
                    if key in annotations and key in init_defaults and value == init_defaults[key]:
                        continue
                    filtered_result[key] = value
                return filtered_result
            return result
