#!/usr/bin/env python
from pathlib import Path
import shutil

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


def test_function_hash_default_arg():
    """
    Test that changing the default value of an argument to function also changes the checksum of the function
    """

    def add(value: int, to_be_added: int = 5) -> int:
        return value + to_be_added

    func_hash = checksums.function_hash(add)

    # Redefine function with different default value - this should change the checksum of the function
    def add(value: int, to_be_added: int = 10) -> int:  # NOQA: Redefinition for the purpose of testing
        return value + to_be_added

    assert checksums.function_hash(add) != func_hash


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


def test_path_checksum(tmpdir):
    """
    Test that checksumming of Path objects work as expected
    """
    tmpdir = Path(str(tmpdir))

    # Checksum the directory before adding any data to it
    tmpdir_checksum_empty = checksums.checksum(tmpdir)
    assert tmpdir_checksum_empty is not None

    # Name test file and ensure it doesn't already exist
    test_file = tmpdir / "test_file.txt"
    assert not test_file.exists()

    # Checksum non-existent file
    test_file_checksum_non_existent = checksums.checksum(test_file)
    assert test_file_checksum_non_existent is not None

    # Check that non-existent files with different names have different checksums
    other_file = tmpdir / "other_file.txt"
    assert checksums.checksum(other_file) != test_file_checksum_non_existent

    # Write data to file and check again
    with test_file.open("w") as f:
        f.write("Testing 0")
    test_file_checksum_1 = checksums.checksum(test_file)
    assert test_file_checksum_1 != test_file_checksum_non_existent

    # Change the data a bit and check again
    with test_file.open("w") as f:
        f.write("Testing 1")
    test_file_checksum_2 = checksums.checksum(test_file)
    assert test_file_checksum_2 != test_file_checksum_1

    # And check that directory checksum remains the same
    tmpdir_checksum = checksums.checksum(tmpdir)
    assert tmpdir_checksum == tmpdir_checksum_empty

    # Check that another file (with different name) but same contents has a different checksum
    test_file_2 = test_file.with_name("test_file_2.txt")
    shutil.copy2(test_file, test_file_2)
    assert checksums.checksum(test_file_2) != checksums.checksum(test_file)

    # Finally, ensure that removing the directory causes the directory checksum to change
    shutil.rmtree(str(tmpdir))
    tmpdir_checksum_non_existent = checksums.checksum(tmpdir)
    assert tmpdir_checksum != tmpdir_checksum_non_existent
