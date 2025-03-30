from dataclasses import dataclass
from typing import get_args, get_origin

import pytest

from finchie_data_pipeline.utils.type_utils import (
    _convert_value,
    coerce_to_instance,
    get_value,
    to_bool,
    to_float,
    to_int,
    to_list,
    to_string,
)


class TestToString:
    def test_none_value(self):
        assert to_string(None) == ""
        assert to_string(None, "default") == "default"

    def test_various_types(self):
        assert to_string(123) == "123"
        assert to_string(3.14) == "3.14"
        assert to_string(True) == "True"
        assert to_string([1, 2, 3]) == "[1, 2, 3]"


class TestGetValue:
    def test_none_object(self):
        assert get_value(None, "key") is None
        assert get_value(None, "key", "default") == "default"
        with pytest.raises(ValueError, match="Required key 'key' not found"):
            get_value(None, "key", required=True)

    def test_dict_object(self):
        d = {"name": "John", "age": 30}
        assert get_value(d, "name") == "John"
        assert get_value(d, "age") == 30
        assert get_value(d, "address") is None
        assert get_value(d, "address", "unknown") == "unknown"
        with pytest.raises(ValueError, match="Required key 'address' not found"):
            get_value(d, "address", required=True)

    def test_class_object(self):
        class Person:
            def __init__(self):
                self.name = "John"
                self.age = 30

        p = Person()
        assert get_value(p, "name") == "John"
        assert get_value(p, "age") == 30
        assert get_value(p, "address") is None
        assert get_value(p, "address", "unknown") == "unknown"
        with pytest.raises(ValueError, match="Required key 'address' not found"):
            get_value(p, "address", required=True)


class TestToBool:
    def test_none_value(self):
        assert to_bool(None) is False
        assert to_bool(None, True) is True

    def test_bool_values(self):
        assert to_bool(True) is True
        assert to_bool(False) is False

    def test_numeric_values(self):
        assert to_bool(1) is True
        assert to_bool(0) is False
        assert to_bool(42) is True
        assert to_bool(-1) is True
        assert to_bool(0.0) is False
        assert to_bool(0.1) is True

    def test_string_values(self):
        assert to_bool("true") is True
        assert to_bool("TRUE") is True
        assert to_bool("True") is True
        assert to_bool("yes") is True
        assert to_bool("Y") is True
        assert to_bool("1") is True
        assert to_bool("false") is False
        assert to_bool("FALSE") is False
        assert to_bool("no") is False
        assert to_bool("N") is False
        assert to_bool("0") is False
        assert to_bool("invalid") is False

    def test_other_values(self):
        assert to_bool([]) is False
        assert to_bool({}) is False
        assert to_bool(object()) is False


class TestToInt:
    def test_none_value(self):
        assert to_int(None) == 0
        assert to_int(None, 10) == 10

    def test_int_values(self):
        assert to_int(0) == 0
        assert to_int(42) == 42
        assert to_int(-10) == -10

    def test_float_values(self):
        assert to_int(3.14) == 3
        assert to_int(-2.7) == -2

    def test_string_values(self):
        assert to_int("0") == 0
        assert to_int("42") == 42
        assert to_int("-10") == -10
        assert to_int("3.14") == 0  # This fails to convert
        assert to_int("invalid") == 0

    def test_other_values(self):
        assert to_int(True) == 1  # True converts to 1
        assert to_int([]) == 0
        assert to_int({}) == 0


class TestToFloat:
    def test_none_value(self):
        assert to_float(None) == 0.0
        assert to_float(None, 10.5) == 10.5

    def test_numeric_values(self):
        assert to_float(0) == 0.0
        assert to_float(42) == 42.0
        assert to_float(-10) == -10.0
        assert to_float(3.14) == 3.14
        assert to_float(-2.7) == -2.7

    def test_string_values(self):
        assert to_float("0") == 0.0
        assert to_float("42") == 42.0
        assert to_float("-10") == -10.0
        assert to_float("3.14") == 3.14
        assert to_float("invalid") == 0.0

    def test_other_values(self):
        assert to_float(True) == 1.0  # True converts to 1.0
        assert to_float([]) == 0.0
        assert to_float({}) == 0.0


class TestToList:
    def test_none_value(self):
        assert to_list(None) == []
        assert to_list(None, [1, 2, 3]) == [1, 2, 3]

    def test_list_values(self):
        assert to_list([]) == []
        assert to_list([1, 2, 3]) == [1, 2, 3]

    def test_string_values(self):
        assert to_list("abc") == ["abc"]
        assert to_list("[a, b, c]") == ["a", "b", "c"]
        assert to_list("[a,b,c]") == ["a", "b", "c"]
        assert to_list("a,b,c") == ["a", "b", "c"]
        assert to_list("a, b, c") == ["a", "b", "c"]
        assert to_list("") == []

    def test_other_values(self):
        assert to_list(123) == [123]
        assert to_list(True) == [True]
        assert to_list((1, 2, 3)) == [1, 2, 3]
        assert to_list({"a": 1, "b": 2}) == ["a", "b"]
        assert to_list({1, 2, 3}) == [1, 2, 3]


class TestCoerceToInstance:
    @dataclass
    class Person:
        name: str
        age: int
        active: bool = True
        tags: list[str] | None = None

    def test_none_data(self):
        # When data is None and allow_none is False, it would try to create an empty instance
        # But since Person requires name and age, we can't directly test this case
        # Instead, we test the case where allow_none=True
        assert coerce_to_instance(None, self.Person, allow_none=True) is None

        # Create a class with default values to test default construction
        @dataclass
        class SimpleClass:
            value: str = ""

        assert coerce_to_instance(None, SimpleClass) == SimpleClass()

    def test_instance_data(self):
        p = self.Person(name="John", age=30)
        assert coerce_to_instance(p, self.Person) is p

    def test_dict_data(self):
        data = {"name": "John", "age": "30", "active": "false"}
        p = coerce_to_instance(data, self.Person)
        assert isinstance(p, self.Person)
        assert p.name == "John"
        assert p.age == 30
        assert p.active is False
        assert p.tags is None

    def test_type_conversion(self):
        data = {
            "name": 123,  # Should convert to "123"
            "age": "42",  # Should convert to 42
            "active": "yes",  # Should convert to True
            "tags": "a, bc",  # Should now be converted to ["a", "bc"] and each item to string
        }
        p = coerce_to_instance(data, self.Person)
        assert p.name == "123"
        assert p.age == 42
        assert p.active is True
        assert p.tags == ["a", "bc"]

    def test_invalid_data_type(self):
        with pytest.raises(TypeError):
            coerce_to_instance("invalid", self.Person)


class TestConvertValue:
    def test_convert_to_bool(self):
        assert _convert_value("true", bool) is True
        assert _convert_value("false", bool) is False
        assert _convert_value("invalid", bool) is None
        assert _convert_value(None, bool) is None
        assert _convert_value(1, bool) is True
        assert _convert_value(0, bool) is False

    def test_convert_to_int(self):
        assert _convert_value("42", int) == 42
        assert _convert_value("-10", int) == -10
        assert _convert_value("invalid", int) is None
        assert _convert_value(None, int) is None
        assert _convert_value(3.14, int) == 3

    def test_convert_to_float(self):
        assert _convert_value("3.14", float) == 3.14
        assert _convert_value("-2.5", float) == -2.5
        assert _convert_value("invalid", float) is None
        assert _convert_value(None, float) is None
        assert _convert_value(42, float) == 42.0

    def test_convert_to_string(self):
        assert _convert_value(123, str) == "123"
        assert _convert_value(3.14, str) == "3.14"
        assert _convert_value(True, str) == "True"
        assert _convert_value(None, str) is None

    def test_convert_to_list(self):
        assert _convert_value("abc", list) == ["abc"]
        assert _convert_value([1, 2, 3], list) == [1, 2, 3]
        assert _convert_value(None, list) == []

    def test_convert_to_generic_list(self):
        # Test List[str]
        list_str_type = list[str]

        assert _convert_value("abc", list_str_type) == ["abc"]
        assert _convert_value(["a", "b", "c"], list_str_type) == ["a", "b", "c"]
        assert _convert_value([1, 2, 3], list_str_type) == ["1", "2", "3"]
        assert _convert_value(None, list_str_type) == []

        # Test List[int]
        list_int_type = list[int]
        assert _convert_value([1, 2, 3], list_int_type) == [1, 2, 3]
        assert _convert_value(["1", "2", "3"], list_int_type) == [1, 2, 3]
        assert _convert_value([1, "2", 3], list_int_type) == [1, 2, 3]
        assert _convert_value("1,2,3", list_int_type) == [1, 2, 3]
        assert _convert_value("123", list_int_type) == [123]
        assert _convert_value(None, list_int_type) == []

        # Test List[bool]
        list_bool_type = list[bool]
        assert _convert_value([True, False], list_bool_type) == [True, False]
        assert _convert_value(["true", "false"], list_bool_type) == [True, False]
        assert _convert_value(None, list_bool_type) == []

    def test_typing_helpers(self):
        # Test that get_origin and get_args work as expected
        assert get_origin(list[str]) is list
        assert get_args(list[str]) == (str,)
        assert get_origin(list[int] | None) is not list
        assert get_origin(list) is None

    def test_convert_to_custom_type(self):
        class CustomType:
            pass

        value = CustomType()
        assert _convert_value(value, CustomType) is value
