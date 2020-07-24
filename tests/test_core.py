#!/usr/bin/env python
# coding=utf-8
from pathlib import Path

import alkymi as alk
import tempfile

from alkymi.execution_graph import Status


def test_builtin_glob():
    with tempfile.TemporaryDirectory() as tempdir:
        test_file = Path(tempdir) / 'test_file.txt'
        with test_file.open('w') as f:
            f.write("test")
        glob_recipe = alk.glob_files(Path(tempdir), '*')

        assert glob_recipe.status == Status.NotEvaluatedYet
        assert glob_recipe.output_timestamps is None
        assert len(glob_recipe.ingredients) == 0
        result = glob_recipe.brew()
        assert result[0] == test_file


def test_recipe_decorator():
    @alk.recipe()
    def should_be_a_recipe():
        return "example"

    assert type(should_be_a_recipe) is alk.Recipe
    assert should_be_a_recipe() == "example"


def test_execution():
    execution_counts = dict(
        produces_build_dir=0,
        produces_a_single_file=0,
        reads_a_file=0
    )

    build_dir = Path('build')
    file = Path('build') / 'file.txt'

    @alk.recipe()
    def produces_build_dir():
        execution_counts['produces_build_dir'] += 1
        build_dir.mkdir(parents=False, exist_ok=True)
        return build_dir

    @alk.recipe(ingredients=[produces_build_dir])
    def produces_a_single_file(_):
        execution_counts['produces_a_single_file'] += 1
        with file.open('w') as f:
            f.write('testing')
        return file

    @alk.recipe(ingredients=[produces_a_single_file], transient=True)
    def reads_a_file(test_file):
        execution_counts['reads_a_file'] += 1
        with test_file.open('r') as f:
            print(f.read())

    reads_a_file.brew()
    assert execution_counts['produces_build_dir'] == 1
    assert execution_counts['produces_a_single_file'] == 1
    assert execution_counts['reads_a_file'] == 1

    reads_a_file.brew()
    assert execution_counts['produces_build_dir'] == 1
    assert execution_counts['produces_a_single_file'] == 1
    assert execution_counts['reads_a_file'] == 1
