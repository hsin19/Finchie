from inspect import signature
from typing import Any, TypeVar, get_type_hints

T = TypeVar("T")


def to_string(value: Any, default: str = "") -> str:
    """Convert any value to string"""
    if value is None:
        return default
    return str(value)


def get_value(obj: Any, key: str, default: T | None = None, required: bool = False) -> Any | T:
    """Get value from an object by key, with type safety"""
    if obj is None:
        if required:
            raise ValueError(f"Required key '{key}' not found in None object")
        return default

    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
    else:
        if hasattr(obj, key):
            return getattr(obj, key)

    if required:
        raise ValueError(f"Required key '{key}' not found in object")
    return default


def to_bool(value: Any, default: bool = False) -> bool:
    """Convert any value to boolean

    True values: 'true', 'yes', 'y', '1', 1, True
    False values: 'false', 'no', 'n', '0', 0, False, None
    """
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, int | float):
        return bool(value)

    if isinstance(value, str):
        value = value.lower().strip()
        if value in ("true", "yes", "y", "1"):
            return True
        if value in ("false", "no", "n", "0"):
            return False

    return default


def to_int(value: Any, default: int = 0) -> int:
    """Convert any value to integer"""
    if value is None:
        return default

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    if isinstance(value, str):
        try:
            return int(value)
        except (ValueError, TypeError):
            pass

    return default


def to_float(value: Any, default: float = 0.0) -> float:
    """Convert any value to float"""
    if value is None:
        return default

    if isinstance(value, int | float):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            pass

    return default


def to_list(value: Any, default: list | None = None) -> list:
    """Convert any value to list"""
    if default is None:
        default = []

    if value is None:
        return default

    if isinstance(value, list):
        return value

    if isinstance(value, str | dict | set | tuple):
        return list(value)

    return [value]


def _convert_value(value: Any, target_type: type) -> Any | None:
    if target_type is bool:
        return to_bool(value, default=None)
    elif target_type is int:
        return to_int(value, default=None)
    elif target_type is float:
        return to_float(value, default=None)
    elif target_type is str:
        return to_string(value, default=None)
    elif target_type is list:
        return to_list(value, default=None)
    else:
        return value


def coerce_to_instance(data: dict | T | None, cls: type[T], allow_none: bool = False) -> T | None:
    """
    Coerces the given data into an instance of the specified class.

    Args:
        data (dict | T | None): The input data to be coerced. It can be:
            - An instance of the target class `cls`.
            - A dictionary containing parameters to initialize an instance of `cls`.
            - None, if `allow_none` is True.
        cls (type[T]): The target class to which the data should be coerced.
        allow_none (bool, optional): If True, allows `data` to be None and returns None.
            Defaults to False.

    Returns:
        T | None: An instance of the specified class `cls` or None if `allow_none` is True
        and `data` is None.

    Raises:
        TypeError: If `data` is not an instance of `cls`, not a dictionary, or None when
        `allow_none` is False.
    """
    if data is None:
        return None if allow_none else cls()
    if isinstance(data, cls):
        return data
    if isinstance(data, dict):
        sig = signature(cls)
        type_hints = get_type_hints(cls.__init__)
        filtered = {}

        for k, _ in sig.parameters.items():
            if k == "self":
                continue
            if k in data:
                raw_value = data[k]
                expected_type = type_hints.get(k, Any)
                filtered[k] = _convert_value(raw_value, expected_type)

        return cls(**filtered)
    raise TypeError(f"Unsupported type for coercion: {type(data)}")
