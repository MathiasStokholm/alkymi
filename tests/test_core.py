#!/usr/bin/env python
import logging
import shutil
import time
from pathlib import Path
from typing import List, Tuple, Dict

import alkymi as alk
from alkymi import AlkymiConfig
from alkymi.foreach_recipe import ForeachRecipe
from alkymi.recipe import Recipe


def test_decorators():
    AlkymiConfig.get().cache = False

    @alk.recipe(transient=True)
    def should_be_a_recipe() -> List[str]:
        return ["example1", "example2"]

    @alk.foreach(should_be_a_recipe)
    def should_be_a_foreach_recipe(value: str) -> str:
        return value.upper()

    assert type(should_be_a_recipe) is Recipe
    assert should_be_a_recipe()[0] == "example1"
    assert should_be_a_recipe()[1] == "example2"
    assert should_be_a_recipe.name == 'should_be_a_recipe'
    assert should_be_a_recipe.transient

    assert type(should_be_a_foreach_recipe) is ForeachRecipe
    assert should_be_a_foreach_recipe.brew()[0] == "EXAMPLE1"
    assert should_be_a_foreach_recipe.brew()[1] == "EXAMPLE2"
    assert should_be_a_foreach_recipe.name == 'should_be_a_foreach_recipe'
    assert should_be_a_foreach_recipe.transient is False


def test_brew():
    AlkymiConfig.get().cache = False

    @alk.recipe()
    def returns_single_item() -> str:
        return "a string"

    assert type(returns_single_item.brew()) == str
    assert returns_single_item.brew() == "a string"

    @alk.recipe()
    def returns_a_tuple() -> Tuple[int, int, int]:
        return 1, 2, 3

    assert type(returns_a_tuple.brew()) == tuple
    assert returns_a_tuple.brew() == (1, 2, 3)

    @alk.recipe()
    def returns_a_list() -> List[int]:
        return [1, 2, 3]

    assert type(returns_a_list.brew()) == list
    assert returns_a_list.brew() == [1, 2, 3]

    @alk.recipe()
    def returns_nothing() -> None:
        pass

    assert returns_nothing.brew() is None

    @alk.recipe()
    def returns_empty_tuple() -> Tuple:
        return tuple()

    assert type(returns_empty_tuple.brew()) == tuple
    assert len(returns_empty_tuple.brew()) == 0


# We use these globals to avoid altering the hashes of bound functions when any of these change
execution_counts = {}  # type: Dict[str, int]
build_dir = Path()
file = Path()
copied_file = Path()


def test_execution(caplog, tmpdir):
    tmpdir = Path(str(tmpdir))
    caplog.set_level(logging.DEBUG)
    AlkymiConfig.get().cache = False

    global execution_counts, build_dir, file, copied_file
    execution_counts = dict(
        produces_build_dir=0,
        produces_a_single_file=0,
        copies_a_file=0,
        reads_a_file=0
    )
    build_dir = Path(tmpdir) / 'build'  # type: Path
    file = build_dir / 'file.txt'  # type: Path
    copied_file = build_dir / 'file_copy.txt'  # type: Path

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

    @alk.foreach(copies_a_file, transient=True)
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

    # Touching an output (but leaving the contents the exact same) should not cause reevaluation of the function that
    # created that output
    time.sleep(0.01)
    file.touch(exist_ok=True)
    reads_a_file.brew()
    assert execution_counts['produces_build_dir'] == 1
    assert execution_counts['produces_a_single_file'] == 1
    assert execution_counts['copies_a_file'] == 1
    assert execution_counts['reads_a_file'] == 5 * 2

    # Changing an output should cause reevaluation of the function that created that output
    time.sleep(0.01)
    with file.open("w") as f:
        f.write("something new!")
    reads_a_file.brew()
    assert execution_counts['produces_build_dir'] == 1
    assert execution_counts['produces_a_single_file'] == 2
    assert execution_counts['copies_a_file'] == 2
    assert execution_counts['reads_a_file'] == 6 * 2

    # Deleting the build dir should cause full reevaluation
    shutil.rmtree(str(build_dir))
    reads_a_file.brew()
    assert execution_counts['produces_build_dir'] == 2
    assert execution_counts['produces_a_single_file'] == 3
    assert execution_counts['copies_a_file'] == 3
    assert execution_counts['reads_a_file'] == 7 * 2
