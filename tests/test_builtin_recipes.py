#!/usr/bin/env python
import time

import pytest
from pathlib import Path
from typing import List, Dict

import alkymi.recipes
from alkymi import AlkymiConfig
from alkymi.core import Status
from alkymi.config import FileChecksumMethod


@pytest.mark.parametrize("file_checksum_method", FileChecksumMethod)
def test_builtin_glob(tmpdir, file_checksum_method: FileChecksumMethod):
    AlkymiConfig.get().cache = False
    AlkymiConfig.get().file_checksum_method = file_checksum_method
    tmpdir = Path(str(tmpdir))
    test_file = Path(tmpdir) / 'test_file.txt'
    with test_file.open('w') as f:
        f.write("test")
    glob_recipe = alkymi.recipes.glob_files("glob_test", Path(tmpdir), '*', recursive=False)

    assert len(glob_recipe.ingredients) == 0
    assert glob_recipe.brew() == [test_file]
    assert glob_recipe.status() == Status.Ok
    assert len(glob_recipe.doc) > 0

    # Altering the file should mark the recipe dirty
    # If using timestamps, ensure that writes doesn't happen at the exact same time
    if file_checksum_method == FileChecksumMethod.ModificationTimestamp:
        time.sleep(0.01)
    with test_file.open('w') as f:
        f.write("something else")
    assert glob_recipe.status() == Status.OutputsInvalid

    # Changing the file back again should make things work again
    # If using timestamps, ensure that writes doesn't happen at the exact same time
    if file_checksum_method == FileChecksumMethod.ModificationTimestamp:
        time.sleep(0.01)
    with test_file.open('w') as f:
        f.write("test")
    expected_status = Status.Ok if file_checksum_method == FileChecksumMethod.HashContents else Status.OutputsInvalid
    assert glob_recipe.status() == expected_status


@pytest.mark.parametrize("file_checksum_method", FileChecksumMethod)
def test_builtin_file(tmpdir, file_checksum_method: FileChecksumMethod):
    AlkymiConfig.get().cache = False
    AlkymiConfig.get().file_checksum_method = file_checksum_method
    tmpdir = Path(str(tmpdir))
    test_file = Path(tmpdir) / 'test_file.txt'
    with test_file.open('w') as f:
        f.write("test")
    file_recipe = alkymi.recipes.file("file_test", test_file)

    assert len(file_recipe.ingredients) == 0
    assert file_recipe.brew() == test_file
    assert file_recipe.status() == Status.Ok
    assert len(file_recipe.doc) > 0

    # Altering the file should mark the recipe dirty
    # If using timestamps, ensure that writes doesn't happen at the exact same time
    if file_checksum_method == FileChecksumMethod.ModificationTimestamp:
        time.sleep(0.01)
    with test_file.open('w') as f:
        f.write("something else")
    assert file_recipe.status() == Status.OutputsInvalid


@pytest.mark.parametrize("file_checksum_method", FileChecksumMethod)
def test_builtin_args(tmpdir, file_checksum_method: FileChecksumMethod):
    tmpdir = Path(str(tmpdir))
    AlkymiConfig.get().cache = False
    AlkymiConfig.get().file_checksum_method = file_checksum_method
    args = alkymi.recipes.arg(("value1", 2), name="args")

    assert len(args.ingredients) == 0
    assert args.status() == Status.NotEvaluatedYet
    results = args.brew()
    assert args.status() == Status.Ok
    assert results is not None
    assert results[0] == "value1"
    assert results[1] == 2

    args.set(("value2", 42))
    assert args.status() == Status.CustomDirty
    results = args.brew()
    assert args.status() == Status.Ok
    assert results is not None
    assert results[0] == "value2"
    assert results[1] == 42

    # Check that altering an external file triggers dirtyness
    file_a = tmpdir / "file_a.txt"
    file_a.write_text(file_a.name)
    file_arg = alkymi.recipes.arg(file_a, name="file_arg")
    assert file_arg.status() == Status.NotEvaluatedYet
    result = file_arg.brew()
    assert file_arg.status() == Status.Ok
    assert result == file_a

    # Now change the file and check that recipe is dirty
    # If using timestamps, ensure that writes doesn't happen at the exact same time
    if file_checksum_method == FileChecksumMethod.ModificationTimestamp:
        time.sleep(0.01)
    file_a.write_text("something_else")
    assert file_arg.status() == Status.OutputsInvalid

    # Changing the file contents back should fix things if using file content hashing
    # If using timestamps, ensure that writes doesn't happen at the exact same time
    if file_checksum_method == FileChecksumMethod.ModificationTimestamp:
        time.sleep(0.01)
    file_a.write_text(file_a.name)
    expected_status = Status.Ok if file_checksum_method == FileChecksumMethod.HashContents else Status.OutputsInvalid
    assert file_arg.status() == expected_status

    # Test that supplying a different type of argument causes an error
    with pytest.raises(TypeError):
        # noinspection PyTypeChecker
        file_arg.set(2)


def test_zip_results():
    """
    Test that the zip_results() built-in recipe generator works as expected (like zip(), but for recipes)
    """
    AlkymiConfig.get().cache = False

    # Test zipping of lists
    @alkymi.recipe()
    def numbers() -> List[int]:
        return [0, 1, 2, 3]

    @alkymi.recipe()
    def strings() -> List[str]:
        return ["0", "1", "2", "3"]

    @alkymi.recipe()
    def spelled() -> List[str]:
        return ["zero", "one", "two", "three"]

    zipped = alkymi.recipes.zip_results("zip_lists", (numbers, strings, spelled))
    assert len(zipped.doc) > 0
    results = zipped.brew()
    assert isinstance(results, list)
    assert all(isinstance(result, tuple) for result in results)
    assert results[0] == (0, "0", "zero")
    assert results[1] == (1, "1", "one")
    assert results[2] == (2, "2", "two")
    assert results[3] == (3, "3", "three")

    @alkymi.recipe()
    def few_items() -> List[int]:
        return [42, 42]

    zipped_should_fail = alkymi.recipes.zip_results("zip_fail_1", (numbers, few_items))
    with pytest.raises(ValueError):
        zipped_should_fail.brew()

    @alkymi.recipe()
    def not_iterable() -> int:
        return 42

    zipped_should_fail_2 = alkymi.recipes.zip_results("zip_fail_2", (numbers, not_iterable))
    with pytest.raises(ValueError):
        zipped_should_fail_2.brew()

    # Now try zipping dictionaries
    @alkymi.recipe()
    def numbers_dict() -> Dict[str, int]:
        return dict(zero=0, one=1, two=2, three=3)

    @alkymi.recipe()
    def strings_dict() -> Dict[str, str]:
        return dict(zero="0", one="1", two="2", three="3")

    zipped_dict = alkymi.recipes.zip_results("zip_dicts", (numbers_dict, strings_dict))
    results_dict = zipped_dict.brew()
    assert isinstance(results_dict, dict)
    assert all(isinstance(result, tuple) for result in results)
    assert results_dict["zero"] == (0, "0")
    assert results_dict["one"] == (1, "1")
    assert results_dict["two"] == (2, "2")
    assert results_dict["three"] == (3, "3")

    # Test that zipping different types fails
    with pytest.raises(ValueError):
        alkymi.recipes.zip_results("zip_fail_3", (numbers, numbers_dict)).brew()
