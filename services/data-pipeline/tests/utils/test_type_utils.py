from dataclasses import dataclass

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
        assert to_string(None) == ("", False)
        assert to_string(None, "default") == ("default", False)

    def test_various_types(self):
        assert to_string(123) == ("123", True)
        assert to_string(3.14) == ("3.14", True)
        assert to_string(True) == ("True", True)
        assert to_string([1, 2, 3]) == ("[1, 2, 3]", True)

    def test_empty_values(self):
        assert to_string("") == ("", True)
        assert to_string({}) == ("{}", True)
        assert to_string([]) == ("[]", True)


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
        assert to_bool(None) == (False, False)
        assert to_bool(None, True) == (True, False)

    def test_bool_values(self):
        assert to_bool(True) == (True, True)
        assert to_bool(False) == (False, True)

    def test_numeric_values(self):
        assert to_bool(1) == (True, True)
        assert to_bool(0) == (False, True)
        assert to_bool(42) == (True, True)
        assert to_bool(-1) == (True, True)
        assert to_bool(0.0) == (False, True)
        assert to_bool(0.1) == (True, True)

    def test_string_values(self):
        assert to_bool("true") == (True, True)
        assert to_bool("TRUE") == (True, True)
        assert to_bool("True") == (True, True)
        assert to_bool("yes") == (True, True)
        assert to_bool("Y") == (True, True)
        assert to_bool("1") == (True, True)
        assert to_bool("false") == (False, True)
        assert to_bool("FALSE") == (False, True)
        assert to_bool("no") == (False, True)
        assert to_bool("N") == (False, True)
        assert to_bool("0") == (False, True)
        assert to_bool("invalid") == (False, False)

    def test_string_with_whitespace(self):
        assert to_bool(" true ") == (True, True)
        assert to_bool(" false ") == (False, True)
        assert to_bool(" yes ") == (True, True)
        assert to_bool(" no ") == (False, True)

    def test_other_values(self):
        assert to_bool([]) == (False, False)
        assert to_bool({}) == (False, False)
        assert to_bool(object()) == (False, False)
        assert to_bool([1, 2, 3]) == (False, False)


class TestToInt:
    def test_none_value(self):
        assert to_int(None) == (0, False)
        assert to_int(None, 10) == (10, False)

    def test_int_values(self):
        assert to_int(0) == (0, True)
        assert to_int(42) == (42, True)
        assert to_int(-10) == (-10, True)

    def test_float_values(self):
        assert to_int(3.14) == (3, True)
        assert to_int(-2.7) == (-2, True)

    def test_string_values(self):
        assert to_int("0") == (0, True)
        assert to_int("42") == (42, True)
        assert to_int("-10") == (-10, True)
        assert to_int("3.14") == (0, False)
        assert to_int("invalid") == (0, False)

    def test_string_with_whitespace(self):
        assert to_int(" 42 ") == (42, True)

    def test_edge_cases(self):
        assert to_int("") == (0, False)
        assert to_int("0.0") == (0, False)
        assert to_int("inf") == (0, False)

    def test_other_values(self):
        assert to_int(True) == (1, True)
        assert to_int(False) == (0, True)
        assert to_int([]) == (0, False)
        assert to_int({}) == (0, False)


class TestToFloat:
    def test_none_value(self):
        assert to_float(None) == (0.0, False)
        assert to_float(None, 10.5) == (10.5, False)

    def test_numeric_values(self):
        assert to_float(0) == (0.0, True)
        assert to_float(42) == (42.0, True)
        assert to_float(-10) == (-10.0, True)
        assert to_float(3.14) == (3.14, True)
        assert to_float(-2.7) == (-2.7, True)

    def test_string_values(self):
        assert to_float("0") == (0.0, True)
        assert to_float("42") == (42.0, True)
        assert to_float("-10") == (-10.0, True)
        assert to_float("3.14") == (3.14, True)
        assert to_float("invalid") == (0.0, False)

    def test_string_with_whitespace(self):
        assert to_float(" 3.14 ") == (3.14, True)

    def test_edge_cases(self):
        assert to_float("") == (0.0, False)
        assert to_float("inf") == (float("inf"), True)

    def test_other_values(self):
        assert to_float(True) == (1.0, True)
        assert to_float(False) == (0.0, True)
        assert to_float([]) == (0.0, False)
        assert to_float({}) == (0.0, False)


class TestToList:
    def test_none_value(self):
        assert to_list(None) == []

    def test_list_values(self):
        assert to_list([]) == []
        assert to_list([1, 2, 3]) == [1, 2, 3]
        assert to_list(["a", "b", "c"]) == ["a", "b", "c"]

    def test_non_list_values(self):
        assert to_list("abc") == ["abc"]
        assert to_list(123) == [123]
        assert to_list({"a": 123}) == ["a"]

    def test_nested_lists(self):
        assert to_list([1, [2, 3]]) == [1, [2, 3]]
        assert to_list([[1, 2], [3, 4]]) == [[1, 2], [3, 4]]


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

    def test_coerce_basic_types(self):
        assert coerce_to_instance(42, int) == 42  # 已經是正確類型的實例

    def test_coerce_to_dataclass(self):
        @dataclass
        class Person:
            name: str
            age: int

        data = {"name": "John", "age": "30"}
        result = coerce_to_instance(data, Person)
        assert isinstance(result, Person)
        assert result.name == "John"
        assert result.age == 30

    def test_nested_dataclass(self):
        @dataclass
        class Address:
            street: str
            city: str

        @dataclass
        class Person:
            name: str
            address: Address

        data = {"name": "John", "address": {"street": "123 Main St", "city": "Anytown"}}

        # 當前實現不支持嵌套 dataclass 的遞歸轉換
        # 需要手動處理嵌套結構
        address_data = data["address"]
        address = Address(**address_data)
        data_with_address = {"name": data["name"], "address": address}

        result = coerce_to_instance(data_with_address, Person)
        assert isinstance(result, Person)
        assert isinstance(result.address, Address)
        assert result.address.street == "123 Main St"

    def test_coerce_list(self):
        @dataclass
        class Item:
            id: int
            name: str

        @dataclass
        class Container:
            items: list[Item]

        # 當前實現不支持列表中元素的自動轉換
        # 需要手動轉換列表內的元素
        items = [Item(id=1, name="Item 1"), Item(id=2, name="Item 2")]

        data = {"items": items}

        result = coerce_to_instance(data, Container)
        assert isinstance(result, Container)
        assert len(result.items) == 2
        assert isinstance(result.items[0], Item)
        assert result.items[0].id == 1
        assert result.items[1].name == "Item 2"


class TestConvertValue:
    def test_convert_to_bool(self):
        assert _convert_value("true", bool) == (True, True)
        assert _convert_value("false", bool) == (False, True)
        assert _convert_value("invalid", bool) == (None, False)
        assert _convert_value(None, bool) == (None, False)
        assert _convert_value(1, bool) == (True, True)
        assert _convert_value(0, bool) == (False, True)

    def test_convert_to_int(self):
        assert _convert_value("42", int) == (42, True)
        assert _convert_value("-10", int) == (-10, True)
        assert _convert_value("invalid", int) == (None, False)
        assert _convert_value(None, int) == (None, False)
        assert _convert_value(3.14, int) == (3, True)

    def test_convert_to_float(self):
        assert _convert_value("3.14", float) == (3.14, True)
        assert _convert_value("-2.5", float) == (-2.5, True)
        assert _convert_value("invalid", float) == (None, False)
        assert _convert_value(None, float) == (None, False)
        assert _convert_value(42, float) == (42.0, True)

    def test_convert_to_string(self):
        assert _convert_value(123, str) == ("123", True)
        assert _convert_value(3.14, str) == ("3.14", True)
        assert _convert_value(True, str) == ("True", True)
        assert _convert_value(None, str) == (None, False)

    def test_convert_to_list(self):
        assert _convert_value("abc", list) == (["abc"], True)
        assert _convert_value([1, 2, 3], list) == ([1, 2, 3], True)
        assert _convert_value(None, list) == ([], True)

    def test_convert_to_typed_list(self):
        assert _convert_value(["1", "2", "3"], list[int]) == ([1, 2, 3], True)
        assert _convert_value([1, 2, 3], list[str]) == (["1", "2", "3"], True)

    def test_convert_to_union_type(self):
        assert _convert_value("42", int | str) == ("42", True)
        assert _convert_value("abc", int | str) == ("abc", True)
        assert _convert_value("42", int | None) == (42, True)
        assert _convert_value(None, int | None) == (None, True)
        assert _convert_value({}, int | str) == ("{}", True)

    def test_convert_to_custom_type(self):
        class CustomType:
            pass

        value = CustomType()
        assert _convert_value(value, CustomType) == (value, True)
