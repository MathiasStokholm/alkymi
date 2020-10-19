#!/usr/bin/env python
# coding=utf-8
import logging
import shutil
import time
from pathlib import Path
from typing import List

import alkymi as alk
from alkymi.recipe import Recipe


def test_recipe_decorator():
    @alk.recipe(transient=True)
    def should_be_a_recipe():
        return "example"

    assert type(should_be_a_recipe) is Recipe
    assert should_be_a_recipe() == "example"
    assert should_be_a_recipe.name == 'should_be_a_recipe'
    assert should_be_a_recipe.transient


def test_execution(caplog, tmpdir):
    tmpdir = Path(str(tmpdir))
    caplog.set_level(logging.DEBUG)

    execution_counts = dict(
        produces_build_dir=0,
        produces_a_single_file=0,
        copies_a_file=0,
        reads_a_file=0
    )

    build_dir = Path(tmpdir) / 'build'
    file = build_dir / 'file.txt'
    copied_file = build_dir / 'file_copy.txt'

    @alk.recipe()
    def produces_build_dir() -> Path:
        execution_counts['produces_build_dir'] += 1
        build_dir.mkdir(parents=False, exist_ok=True)
        return build_dir

    @alk.recipe(ingredients=[produces_build_dir])
    def produces_a_single_file(_: Path) -> Path:
        execution_counts['produces_a_single_file'] += 1
        with file.open('w') as f:
            f.write('testing')
        return file

    @alk.recipe(ingredients=[produces_a_single_file])
    def copies_a_file(_: Path) -> List[Path]:
        execution_counts['copies_a_file'] += 1
        with file.open('r') as infile, copied_file.open('w') as outfile:
            outfile.write(infile.read())
        return [file, copied_file]

    @alk.map_recipe(copies_a_file, transient=True)
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
    # 'reads_a_file' should be executed twice for every triggering - once per file
    reads_a_file.brew()
    assert execution_counts['produces_build_dir'] == 1
    assert execution_counts['produces_a_single_file'] == 1
    assert execution_counts['copies_a_file'] == 1
    assert execution_counts['reads_a_file'] == 1 * 2

    # On subsequent brews, only the transient "reads_a_file" function should be executed again
    for i in range(1, 4):
        reads_a_file.brew()
        assert execution_counts['produces_build_dir'] == 1
        assert execution_counts['produces_a_single_file'] == 1
        assert execution_counts['copies_a_file'] == 1
        assert execution_counts['reads_a_file'] == (1 + i) * 2

    # Changing an output should cause reevaluation of the function that created that output (and everything after)
    time.sleep(0.01)
    file.touch(exist_ok=True)
    reads_a_file.brew()
    assert execution_counts['produces_build_dir'] == 1
    assert execution_counts['produces_a_single_file'] == 2
    assert execution_counts['copies_a_file'] == 2
    assert execution_counts['reads_a_file'] == 5 * 2

    # Deleting the build dir should cause full reevaluation
    shutil.rmtree(str(build_dir))
    reads_a_file.brew()
    assert execution_counts['produces_build_dir'] == 2
    assert execution_counts['produces_a_single_file'] == 3
    assert execution_counts['copies_a_file'] == 3
    assert execution_counts['reads_a_file'] == 6 * 2
