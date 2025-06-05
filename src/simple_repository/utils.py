def get_attrs(model):
    if hasattr(model, "__fields__"):
        return set(getattr(model, "__fields__", {}).keys())
    elif hasattr(model, "__tablename__"):
        return set(getattr(model, "__annotations__", {}).keys())
    else:
        return set(getattr(model, "__annotations__", {}).keys())


def same_attrs(model1, model2):
    attrs1 = get_attrs(model1)
    attrs2 = get_attrs(model2)
    return attrs1 == attrs2
