#!/usr/bin/env python
from alkymi import checksums


def test_function_hash():
    def add_one(a):
        return a + 1

    def func_1(a, b, *args, **kwargs):
        return add_one(a) + b + args[0] + kwargs["test"]

    def func_other_name(a, b, *args, **kwargs):
        return add_one(a) + b + args[0] + kwargs["test"]

    def func_different_args_idx(a, b, *args, **kwargs):
        return add_one(a) + b + args[1] + kwargs["test"]

    def func_different_kwarg_key(a, b, *args, **kwargs):
        return add_one(a) + b + args[0] + kwargs["other"]

    def func_constants(a, b, *args, **kwargs):
        return add_one(a) + b + args[0] + kwargs["test"] + 10

    func_1_hash = checksums.function_hash(func_1)
    assert func_1_hash == checksums.function_hash(func_other_name)
    assert func_1_hash != checksums.function_hash(func_different_args_idx)
    assert func_1_hash != checksums.function_hash(func_different_kwarg_key)
    assert func_1_hash != checksums.function_hash(func_constants)

    def add_one(a):  # NOQA: Redefinition for the purpose of testing
        return a + 2

    def func_different_func_reference(a, b, *args, **kwargs):
        return add_one(a) + b + args[0] + kwargs["test"]

    assert func_1_hash != checksums.function_hash(func_different_func_reference)


class MyClass:
    def __init__(self, public_value, private_value):
        self.public_value = public_value
        self._private_value = private_value


def test_custom_class_checksum():
    class_1_hash = checksums.checksum(MyClass(5, "10"))
    class_2_hash = checksums.checksum(MyClass(5, 10))
    class_3_hash = checksums.checksum(MyClass("5", 10))
    class_4_hash = checksums.checksum(MyClass(5, "10"))
    assert class_1_hash != class_2_hash != class_3_hash
    assert class_1_hash == class_4_hash
