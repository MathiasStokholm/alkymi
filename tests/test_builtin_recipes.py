#!/usr/bin/env python
import pytest
from pathlib import Path
from typing import List, Dict

import alkymi.recipes
from alkymi import AlkymiConfig
from alkymi.alkymi import Status


def test_builtin_glob(tmpdir):
    AlkymiConfig.get().cache = False
    tmpdir = Path(str(tmpdir))
    test_file = Path(tmpdir) / 'test_file.txt'
    with test_file.open('w') as f:
        f.write("test")
    glob_recipe = alkymi.recipes.glob_files(Path(tmpdir), '*', recursive=False)

    assert len(glob_recipe.ingredients) == 0
    assert glob_recipe.brew() == [test_file]
    assert glob_recipe.status() == Status.Ok

    # Altering the file should mark the recipe dirty
    with test_file.open('w') as f:
        f.write("something else")
    assert glob_recipe.status() == Status.OutputsInvalid

    # Changing the file back again should make things work again
    with test_file.open('w') as f:
        f.write("test")
    assert glob_recipe.status() == Status.Ok


def test_builtin_file(tmpdir):
    AlkymiConfig.get().cache = False
    tmpdir = Path(str(tmpdir))
    test_file = Path(tmpdir) / 'test_file.txt'
    with test_file.open('w') as f:
        f.write("test")
    file_recipe = alkymi.recipes.file(test_file)

    assert len(file_recipe.ingredients) == 0
    assert file_recipe.brew() == test_file
    assert file_recipe.status() == Status.Ok

    # Altering the file should mark the recipe dirty
    with test_file.open('w') as f:
        f.write("something else")
    assert file_recipe.status() == Status.OutputsInvalid


def test_builtin_args(tmpdir):
    tmpdir = Path(str(tmpdir))
    AlkymiConfig.get().cache = False
    args = alkymi.recipes.args("value1", 2)
    args_recipe = args.recipe

    assert len(args_recipe.ingredients) == 0
    assert args.recipe.status() == Status.NotEvaluatedYet
    results = args.recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert results is not None
    assert results[0] == "value1"
    assert results[1] == 2

    args.set_args("3")
    assert args.recipe.status() == Status.CustomDirty
    results = args.recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert results is not None
    assert results[0] == "3"

    args.set_args()
    assert args.recipe.status() == Status.CustomDirty
    results = args.recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert results is not None
    assert len(results) == 0

    # Check that altering an external file triggers dirtyness
    file_a = tmpdir / "file_a.txt"
    file_a.write_text(file_a.name)
    args.set_args(file_a)
    assert args.recipe.status() == Status.CustomDirty
    result = args.recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert result == file_a

    # Now change the file and check that recipe is dirty
    file_a.write_text("something_else")
    assert args.recipe.status() == Status.OutputsInvalid

    # Changing the file contents back should fix things
    file_a.write_text(file_a.name)
    assert args.recipe.status() == Status.Ok


def test_builtin_kwargs(tmpdir):
    tmpdir = Path(str(tmpdir))
    AlkymiConfig.get().cache = False
    args = alkymi.recipes.kwargs(argument1="value1", argument2=2)
    args_recipe = args.recipe

    assert len(args_recipe.ingredients) == 0
    assert args.recipe.status() == Status.NotEvaluatedYet
    results = args_recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert results is not None
    assert results["argument1"] == "value1"
    assert results["argument2"] == 2

    args.set_args(argument3="3")
    assert args.recipe.status() == Status.CustomDirty
    results = args.recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert results is not None
    assert results["argument3"] == "3"

    args.set_args()
    assert args.recipe.status() == Status.CustomDirty
    results = args.recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert results is not None
    assert len(results) == 0

    # Check that altering an external file triggers dirtyness
    file_a = tmpdir / "file_a.txt"
    file_a.write_text(file_a.name)
    args.set_args(path=file_a)
    assert args.recipe.status() == Status.CustomDirty
    results = args.recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert results["path"] == file_a

    # Now change the file and check that recipe is dirty
    file_a.write_text("something_else")
    assert args.recipe.status() == Status.OutputsInvalid

    # Changing the file contents back should fix things
    file_a.write_text(file_a.name)
    assert args.recipe.status() == Status.Ok


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

    zipped = alkymi.recipes.zip_results((numbers, strings, spelled))
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

    zipped_should_fail = alkymi.recipes.zip_results((numbers, few_items))
    with pytest.raises(ValueError):
        zipped_should_fail.brew()

    @alkymi.recipe()
    def not_iterable() -> int:
        return 42

    zipped_should_fail_2 = alkymi.recipes.zip_results((numbers, not_iterable))
    with pytest.raises(ValueError):
        zipped_should_fail_2.brew()

    # Now try zipping dictionaries
    @alkymi.recipe()
    def numbers_dict() -> Dict[str, int]:
        return dict(zero=0, one=1, two=2, three=3)

    @alkymi.recipe()
    def strings_dict() -> Dict[str, str]:
        return dict(zero="0", one="1", two="2", three="3")

    zipped_dict = alkymi.recipes.zip_results((numbers_dict, strings_dict))
    results_dict = zipped_dict.brew()
    assert isinstance(results_dict, dict)
    assert all(isinstance(result, tuple) for result in results)
    assert results_dict["zero"] == (0, "0")
    assert results_dict["one"] == (1, "1")
    assert results_dict["two"] == (2, "2")
    assert results_dict["three"] == (3, "3")

    # Test that zipping different types fails
    with pytest.raises(ValueError):
        alkymi.recipes.zip_results((numbers, numbers_dict)).brew()
