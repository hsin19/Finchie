import numbers
from inspect import signature
from types import UnionType
from typing import Any, TypeVar, get_args, get_origin, get_type_hints

T = TypeVar("T")


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


def to_string(value: Any, default: str = "") -> tuple[str, bool]:
    """Convert any value to string

    Returns:
        - (converted_value, True) if value can be converted clearly
        - (default, False) if value is unclear or invalid
    """
    if value is None:
        return default, False
    return str(value), True


def to_bool(value: Any, default: bool = False) -> tuple[bool, bool]:
    """Convert any value to boolean

    Returns:
        - (converted_value, True) if value can be converted clearly
        - (default, False) if value is unclear or invalid

    True values: 'true', 'yes', 'y', '1', 1, True

    False values: 'false', 'no', 'n', '0', 0, False
    """
    if value is None:
        return default, False

    if isinstance(value, bool):
        return value, True

    if isinstance(value, numbers.Number):
        return bool(value), True

    if isinstance(value, str):
        value = value.lower().strip()
        if value in ("true", "yes", "y", "1"):
            return True, True
        if value in ("false", "no", "n", "0"):
            return False, True

    return default, False


def to_int(value: Any, default: int = 0) -> tuple[int, bool]:
    """Convert any value to integer

    Returns:
        - (converted_value, True) if value can be converted clearly
        - (default, False) if value is unclear or invalid
    """
    if value is None:
        return default, False

    if isinstance(value, int):
        return value, True

    if isinstance(value, float):
        return int(value), True

    if isinstance(value, str):
        try:
            return int(value), True
        except (ValueError, TypeError):
            pass

    return default, False


def to_float(value: Any, default: float = 0.0) -> tuple[float, bool]:
    """Convert any value to float

    Returns:
        - (converted_value, True) if value can be converted clearly
        - (default, False) if value is unclear or invalid
    """
    if value is None:
        return default, False

    if isinstance(value, int | float):
        return float(value), True

    if isinstance(value, str):
        try:
            return float(value), True
        except (ValueError, TypeError):
            pass

    return default, False


def to_list(value: Any) -> list:
    """Convert any value to list"""
    if value is None:
        return []

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


def _convert_value(value: Any, target_type: type) -> tuple[Any | None, bool]:
    origin = get_origin(target_type)
    args = get_args(target_type)

    if len(args) == 0 and isinstance(value, target_type):
        return value, True
    if target_type is type(None):
        if value is None:
            return None, True
        return value, False

    elif target_type is bool:
        return to_bool(value, default=None)
    elif target_type is int:
        return to_int(value, default=None)
    elif target_type is float:
        return to_float(value, default=None)
    elif target_type is str:
        return to_string(value, default=None)
    elif target_type is list or origin is list:
        # Convert to list first
        base_list = to_list(value)

        # If it's a generic list type with arguments, also convert each element
        if origin is list and args and len(args) > 0:
            element_type = args[0]
            # return [converted[0] for item in base_list if (converted := _convert_value(item, element_type))[1]], True
            generic_list = []
            for item in base_list:
                converted_value, is_success = _convert_value(item, element_type)
                if not is_success:
                    return base_list, False
                generic_list.append(converted_value)
            return generic_list, True

        return base_list, True
    elif origin is UnionType:
        for arg in args:
            if arg is type(None):
                continue
            try:
                if isinstance(value, arg):
                    return value, True
            except Exception:
                continue

        for arg in args:
            try:
                convert_value, is_success = _convert_value(value, arg)
                if is_success:
                    return convert_value, True
            except Exception:
                continue
        return None, False
    else:
        return None, False


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
                converted_value, is_success = _convert_value(raw_value, expected_type)
                if not is_success:
                    raise TypeError(f"Cannot convert {raw_value} to {expected_type}")
                filtered[k] = converted_value

        return cls(**filtered)
    raise TypeError(f"Unsupported type for coercion: {type(data)}")
