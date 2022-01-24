#!/usr/bin/env python
import logging
import shutil
import time
from pathlib import Path
from typing import List, Tuple, Dict, Any

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


def test_recipe_result_forwarding():
    AlkymiConfig.get().cache = False

    @alk.recipe()
    def a_tuple() -> Tuple[str, int]:
        return "a string", 42

    @alk.recipe()
    def as_list(a_tuple: Tuple[str, int]) -> List[Any]:
        return list(a_tuple)

    result = as_list.brew()
    assert isinstance(result, list)
    assert result[0] == "a string"
    assert result[1] == 42


# We use these globals to avoid altering the hashes of bound functions when any of these change
execution_counts = {}  # type: Dict[str, int]
build_dir_global = Path()
file_global = Path()
copied_file_global = Path()


def test_execution(caplog, tmpdir):
    tmpdir = Path(str(tmpdir))
    caplog.set_level(logging.DEBUG)
    AlkymiConfig.get().cache = False

    global execution_counts, build_dir_global, file_global, copied_file_global
    execution_counts = dict(
        build_dir=0,
        a_single_file=0,
        file_and_copy=0,
        content_of_files=0
    )
    build_dir_global = Path(tmpdir) / 'build'  # type: Path
    file_global = build_dir_global / 'file.txt'  # type: Path
    copied_file_global = build_dir_global / 'file_copy.txt'  # type: Path

    @alk.recipe()
    def build_dir() -> Path:
        execution_counts['build_dir'] += 1
        build_dir_global.mkdir(parents=False, exist_ok=True)
        return build_dir_global

    @alk.recipe()
    def a_single_file(build_dir: Path) -> Path:
        execution_counts['a_single_file'] += 1
        with file_global.open('w') as f_out:
            f_out.write('testing')
        return file_global

    @alk.recipe()
    def file_and_copy(a_single_file: Path) -> List[Path]:
        execution_counts['file_and_copy'] += 1
        with file_global.open('r') as infile, copied_file_global.open('w') as outfile:
            outfile.write(infile.read())
        return [file_global, copied_file_global]

    @alk.foreach(file_and_copy, transient=True)
    def content_of_files(test_file: Path) -> None:
        execution_counts['content_of_files'] += 1
        with test_file.open('r') as f_out:
            f_out.read()

    # Upon definition, no functions should have been executed
    assert execution_counts['build_dir'] == 0
    assert execution_counts['a_single_file'] == 0
    assert execution_counts['file_and_copy'] == 0
    assert execution_counts['content_of_files'] == 0

    # On first brew, all functions should have been executed once
    # 'content_of_files' should be executed twice for every triggering - once per file
    content_of_files.brew()
    assert execution_counts['build_dir'] == 1
    assert execution_counts['a_single_file'] == 1
    assert execution_counts['file_and_copy'] == 1
    assert execution_counts['content_of_files'] == 1 * 2

    # On subsequent brews, only the transient "content_of_files" function should be executed again
    for i in range(1, 4):
        content_of_files.brew()
        assert execution_counts['build_dir'] == 1
        assert execution_counts['a_single_file'] == 1
        assert execution_counts['file_and_copy'] == 1
        assert execution_counts['content_of_files'] == (1 + i) * 2

    # Touching an output (but leaving the contents the exact same) should not cause reevaluation of the function that
    # created that output
    time.sleep(0.01)
    file_global.touch(exist_ok=True)
    content_of_files.brew()
    assert execution_counts['build_dir'] == 1
    assert execution_counts['a_single_file'] == 1
    assert execution_counts['file_and_copy'] == 1
    assert execution_counts['content_of_files'] == 5 * 2

    # Changing an output should cause reevaluation of the function that created that output
    time.sleep(0.01)
    with file_global.open("w") as f:
        f.write("something new!")
    content_of_files.brew()
    assert execution_counts['build_dir'] == 1
    assert execution_counts['a_single_file'] == 2
    assert execution_counts['file_and_copy'] == 2
    assert execution_counts['content_of_files'] == 6 * 2

    # Deleting the build dir should cause full reevaluation
    shutil.rmtree(str(build_dir_global))
    content_of_files.brew()
    assert execution_counts['build_dir'] == 2
    assert execution_counts['a_single_file'] == 3
    assert execution_counts['file_and_copy'] == 3
    assert execution_counts['content_of_files'] == 7 * 2
