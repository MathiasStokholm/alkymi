#!/usr/bin/env python
# coding=utf-8
import shutil
from pathlib import Path

import alkymi as alk
import tempfile

from alkymi import Lab


def test_builtin_glob():
    with tempfile.TemporaryDirectory() as tempdir:
        test_file = Path(tempdir) / 'test_file.txt'
        with test_file.open('w') as f:
            f.write("test")
        glob_recipe = alk.recipes.glob_files(Path(tempdir), '*')

        assert len(glob_recipe.ingredients) == 0
        assert glob_recipe()[0] == test_file


def test_recipe_decorator():
    lab = Lab('test')

    @lab.recipe(transient=True)
    def should_be_a_recipe():
        return "example"

    assert type(should_be_a_recipe) is alk.Recipe
    assert should_be_a_recipe() == "example"
    assert should_be_a_recipe.name == 'should_be_a_recipe'
    assert should_be_a_recipe.transient


def test_execution():
    lab = Lab('test', disable_caching=True)

    execution_counts = dict(
        produces_build_dir=0,
        produces_a_single_file=0,
        copies_a_file=0,
        reads_a_file=0
    )

    build_dir = Path('build')
    file = Path('build') / 'file.txt'
    copied_file = Path('build') / 'file_copy.txt'

    @lab.recipe()
    def produces_build_dir() -> Path:
        execution_counts['produces_build_dir'] += 1
        build_dir.mkdir(parents=False, exist_ok=True)
        return build_dir

    @lab.recipe(ingredients=[produces_build_dir])
    def produces_a_single_file(_: Path) -> Path:
        execution_counts['produces_a_single_file'] += 1
        with file.open('w') as f:
            f.write('testing')
        return file

    @lab.recipe(ingredients=[produces_a_single_file])
    def copies_a_file(_: Path) -> Path:
        execution_counts['copies_a_file'] += 1
        with file.open('r') as infile, copied_file.open('w') as outfile:
            outfile.write(infile.read())
        return copied_file

    @lab.recipe(ingredients=[copies_a_file], transient=True)
    def reads_a_file(test_file: Path) -> None:
        execution_counts['reads_a_file'] += 1
        with test_file.open('r') as f:
            f.read()

    # Upon definition, no functions should have been executed
    assert execution_counts['produces_build_dir'] == 0
    assert execution_counts['produces_a_single_file'] == 0
    assert execution_counts['copies_a_file'] == 0
    assert execution_counts['reads_a_file'] == 0

    # On first brew, all functions should have been executed once
    lab.brew(reads_a_file)
    assert execution_counts['produces_build_dir'] == 1
    assert execution_counts['produces_a_single_file'] == 1
    assert execution_counts['copies_a_file'] == 1
    assert execution_counts['reads_a_file'] == 1

    # On subsequent brews, only the transient "reads_a_file" function should be executed again
    for i in range(1, 4):
        lab.brew(reads_a_file)
        assert execution_counts['produces_build_dir'] == 1
        assert execution_counts['produces_a_single_file'] == 1
        assert execution_counts['copies_a_file'] == 1
        assert execution_counts['reads_a_file'] == 1 + i

    # Changing an output should cause reevaluation
    file.touch(exist_ok=True)
    lab.brew(reads_a_file)
    assert execution_counts['produces_build_dir'] == 1
    assert execution_counts['produces_a_single_file'] == 1
    assert execution_counts['copies_a_file'] == 2
    assert execution_counts['reads_a_file'] == 5

    # Deleting the build dir should cause full reevaluation
    shutil.rmtree(build_dir)
    lab.brew(reads_a_file)
    assert execution_counts['produces_build_dir'] == 2
    assert execution_counts['produces_a_single_file'] == 2
    assert execution_counts['copies_a_file'] == 3
    assert execution_counts['reads_a_file'] == 6
