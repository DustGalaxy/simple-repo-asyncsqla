def get_attrs(model):
    """Get model fields for any model type."""
    if hasattr(model, "model_fields"):  # Pydantic v2
        return set(model.model_fields.keys())
    elif hasattr(model, "__tablename__"):  # SQLAlchemy models
        return set(getattr(model, "__annotations__", {}).keys())
    else:  # Other models (dataclasses, etc)
        return set(getattr(model, "__annotations__", {}).keys())


def same_attrs(model1, model2):
    attrs1 = get_attrs(model1)
    attrs2 = get_attrs(model2)
    return attrs1 == attrs2
