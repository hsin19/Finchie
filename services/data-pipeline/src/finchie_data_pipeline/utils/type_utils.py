from inspect import signature
from types import UnionType
from typing import Any, TypeVar, get_args, get_origin, get_type_hints

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

    if isinstance(value, str):
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1].strip()
        if value:
            return [item.strip() for item in value.split(",")]
        return []

    if isinstance(value, dict | set | tuple):
        return list(value)

    return [value]


def _convert_value(value: Any, target_type: type) -> Any | None:
    origin = get_origin(target_type)
    args = get_args(target_type)

    # Handle basic types
    if target_type is bool:
        return to_bool(value, default=None)
    elif target_type is int:
        return to_int(value, default=None)
    elif target_type is float:
        return to_float(value, default=None)
    elif target_type is str:
        return to_string(value, default=None)
    elif target_type is list or origin is list:
        # Convert to list first
        base_list = to_list(value, default=None)

        # If it's a generic list type with arguments, also convert each element
        if origin is list and args and len(args) > 0:
            element_type = args[0]
            return [_convert_value(item, element_type) for item in base_list]

        return base_list
    elif origin is UnionType:
        for arg in args:
            if arg is type(None):
                continue
            try:
                return _convert_value(value, arg)
            except Exception:
                continue
        raise TypeError(f"Cannot convert value '{value}' to any of the union types {args}")
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
