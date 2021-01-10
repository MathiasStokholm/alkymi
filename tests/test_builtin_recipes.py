#!/usr/bin/env python
from pathlib import Path

import alkymi.recipes
from alkymi import AlkymiConfig
from alkymi.alkymi import compute_recipe_status, Status


# Turn of caching for tests
AlkymiConfig.get().cache = False


def test_builtin_glob(tmpdir):
    tmpdir = Path(str(tmpdir))
    test_file = Path(tmpdir) / 'test_file.txt'
    with test_file.open('w') as f:
        f.write("test")
    glob_recipe = alkymi.recipes.glob_files(Path(tmpdir), '*', recursive=False)

    assert len(glob_recipe.ingredients) == 0
    assert glob_recipe.brew() == [test_file]
    assert glob_recipe.status() == Status.Ok

    # Altering the file should NOT mark the recipe dirty - we only care about finding the files
    with test_file.open('w') as f:
        f.write("something else")
    assert glob_recipe.status() == Status.Ok


def test_builtin_file(tmpdir):
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


def test_builtin_args():
    args = alkymi.recipes.args("value1", 2)
    args_recipe = args.recipe

    assert len(args_recipe.ingredients) == 0
    assert compute_recipe_status(args_recipe)[args.recipe] == Status.NotEvaluatedYet
    results = args.recipe.brew()
    assert compute_recipe_status(args_recipe)[args.recipe] == Status.Ok
    assert results is not None
    assert results[0] == "value1"
    assert results[1] == 2

    args.set_args("3")
    assert compute_recipe_status(args_recipe)[args.recipe] == Status.Dirty
    results = args.recipe.brew()
    assert compute_recipe_status(args_recipe)[args.recipe] == Status.Ok
    assert results is not None
    assert results[0] == "3"

    args.set_args()
    assert compute_recipe_status(args_recipe)[args.recipe] == Status.Dirty
    results = args.recipe.brew()
    assert compute_recipe_status(args_recipe)[args.recipe] == Status.Ok
    assert results is not None
    assert len(results) == 0


def test_builtin_kwargs():
    args = alkymi.recipes.kwargs(argument1="value1", argument2=2)
    args_recipe = args.recipe

    assert len(args_recipe.ingredients) == 0
    assert compute_recipe_status(args_recipe)[args.recipe] == Status.NotEvaluatedYet
    results = args_recipe.brew()
    assert compute_recipe_status(args_recipe)[args.recipe] == Status.Ok
    assert results is not None
    assert results["argument1"] == "value1"
    assert results["argument2"] == 2

    args.set_args(argument3="3")
    assert compute_recipe_status(args_recipe)[args.recipe] == Status.Dirty
    results = args.recipe.brew()
    assert compute_recipe_status(args_recipe)[args.recipe] == Status.Ok
    assert results is not None
    assert results["argument3"] == "3"

    args.set_args()
    assert compute_recipe_status(args_recipe)[args.recipe] == Status.Dirty
    results = args.recipe.brew()
    assert compute_recipe_status(args_recipe)[args.recipe] == Status.Ok
    assert results is not None
    assert len(results) == 0
