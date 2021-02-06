#!/usr/bin/env python
from pathlib import Path

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
    assert glob_recipe.status() == Status.Dirty

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
    assert file_recipe.status() == Status.Dirty


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
    assert args.recipe.status() == Status.Dirty
    results = args.recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert results is not None
    assert results[0] == "3"

    args.set_args()
    assert args.recipe.status() == Status.Dirty
    results = args.recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert results is not None
    assert len(results) == 0

    # Check that altering an external file triggers dirtyness
    file_a = tmpdir / "file_a.txt"
    file_a.write_text(file_a.name)
    args.set_args(file_a)
    assert args.recipe.status() == Status.Dirty
    result = args.recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert result == file_a

    # Now change the file and check that recipe is dirty
    file_a.write_text("something_else")
    assert args.recipe.status() == Status.Dirty

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
    assert args.recipe.status() == Status.Dirty
    results = args.recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert results is not None
    assert results["argument3"] == "3"

    args.set_args()
    assert args.recipe.status() == Status.Dirty
    results = args.recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert results is not None
    assert len(results) == 0

    # Check that altering an external file triggers dirtyness
    file_a = tmpdir / "file_a.txt"
    file_a.write_text(file_a.name)
    args.set_args(path=file_a)
    assert args.recipe.status() == Status.Dirty
    results = args.recipe.brew()
    assert args.recipe.status() == Status.Ok
    assert results["path"] == file_a

    # Now change the file and check that recipe is dirty
    file_a.write_text("something_else")
    assert args.recipe.status() == Status.Dirty

    # Changing the file contents back should fix things
    file_a.write_text(file_a.name)
    assert args.recipe.status() == Status.Ok
