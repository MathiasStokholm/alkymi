#!/usr/bin/env python
# coding=utf-8
from alkymi import metadata


def test_function_hash():
    def func_1(a, b, *args, **kwargs):
        return a + b + args[0] + kwargs["test"]

    def func_other_name(a, b, *args, **kwargs):
        return a + b + args[0] + kwargs["test"]

    def func_different_args_idx(a, b, *args, **kwargs):
        return a + b + args[1] + kwargs["test"]

    def func_different_kwarg_key(a, b, *args, **kwargs):
        return a + b + args[0] + kwargs["other"]

    def func_constants(a, b, *args, **kwargs):
        return a + b + args[0] + kwargs["test"] + 10

    assert metadata.function_hash(func_1) == metadata.function_hash(func_other_name)
    assert metadata.function_hash(func_1) != metadata.function_hash(func_different_args_idx)
    assert metadata.function_hash(func_1) != metadata.function_hash(func_different_kwarg_key)
    assert metadata.function_hash(func_1) != metadata.function_hash(func_constants)
