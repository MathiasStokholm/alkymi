#!/usr/bin/env python
from alkymi import metadata


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

    func_1_hash = metadata.function_hash(func_1)
    assert func_1_hash == metadata.function_hash(func_other_name)
    assert func_1_hash != metadata.function_hash(func_different_args_idx)
    assert func_1_hash != metadata.function_hash(func_different_kwarg_key)
    assert func_1_hash != metadata.function_hash(func_constants)

    def add_one(a):  # NOQA: Redefinition for the purpose of testing
        return a + 2

    def func_different_func_reference(a, b, *args, **kwargs):
        return add_one(a) + b + args[0] + kwargs["test"]

    assert func_1_hash != metadata.function_hash(func_different_func_reference)
