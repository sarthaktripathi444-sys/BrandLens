# schemas package: shapes of the data sent to and from the API.


def to_dict(model):
    """Turn a Pydantic model into a plain dict (works with Pydantic v1 and v2)."""
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()
