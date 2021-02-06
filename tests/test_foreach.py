#!/usr/bin/env python
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Union

import alkymi.recipes
from alkymi import AlkymiConfig
from alkymi.alkymi import compute_recipe_status, Status
import alkymi as alk

# We use these globals to avoid altering the hashes of bound functions when any of these change
execution_counts = {}  # type: Dict[Union[Path, str], int]
f1 = Path()
f2 = Path()
f3 = Path()


def test_execution(caplog, tmpdir):
    tmpdir = Path(str(tmpdir))
    caplog.set_level(logging.DEBUG)
    AlkymiConfig.get().cache = False

    global execution_counts, f1, f2, f3

    f1 = Path(tmpdir) / "file1.txt"
    f2 = Path(tmpdir) / "file2.txt"
    f3 = Path(tmpdir) / "file3.txt"
    f1.write_text(f1.stem)
    f2.write_text(f2.stem)
    f3.write_text(f3.stem)

    execution_counts = {f1: 0, f2: 0, f3: 0, f1.stem: 0, f2.stem: 0, f3.stem: 0}

    def _check_counts(counts: Tuple[int, int, int, int, int, int]):
        assert execution_counts[f1] == counts[0]
        assert execution_counts[f2] == counts[1]
        assert execution_counts[f3] == counts[2]
        assert execution_counts[f1.stem] == counts[3]
        assert execution_counts[f2.stem] == counts[4]
        assert execution_counts[f3.stem] == counts[5]

    args = alkymi.recipes.args([f1])

    @alk.foreach(args.recipe)
    def read_file(path: Path) -> str:
        execution_counts[path] += 1
        with path.open('r') as f:
            return f.read()

    @alk.recipe(ingredients=[read_file])
    def to_dict(file_contents: List[str]) -> Dict[str, str]:
        return {f: f for f in file_contents}

    # This is used to check later whether changing an ingredient will correctly change everything
    extra_count_arg = alkymi.recipes.args(0)

    @alk.foreach(to_dict, ingredients=[extra_count_arg.recipe])
    def change_count(file_content: str, extra_count: int) -> str:
        execution_counts[file_content] += 1 + extra_count
        return file_content

    assert compute_recipe_status(read_file)[read_file] == Status.NotEvaluatedYet
    assert compute_recipe_status(change_count)[change_count] == Status.NotEvaluatedYet
    change_count.brew()
    assert compute_recipe_status(read_file)[read_file] == Status.Ok
    assert compute_recipe_status(change_count)[change_count] == Status.Ok
    _check_counts((1, 0, 0, 1, 0, 0))

    args.set_args([f1, f2, f3])
    assert compute_recipe_status(read_file)[read_file] == Status.MappedInputsDirty
    change_count.brew()
    assert compute_recipe_status(read_file)[read_file] == Status.Ok
    _check_counts((1, 1, 1, 1, 1, 1))

    args.set_args([f3, f2])
    change_count.brew()
    _check_counts((1, 1, 1, 1, 1, 1))

    args.set_args([f1])
    change_count.brew()
    _check_counts((2, 1, 1, 2, 1, 1))

    args.set_args([])
    change_count.brew()
    _check_counts((2, 1, 1, 2, 1, 1))

    # Test that changing an ingredient forces reevaluation of all foreach inputs
    args.set_args([f1, f2, f3])
    assert compute_recipe_status(change_count)[change_count] == Status.MappedInputsDirty
    change_count.brew()
    assert compute_recipe_status(change_count)[change_count] == Status.Ok
    _check_counts((3, 2, 2, 3, 2, 2))

    # This should cause a reevaluation of everything (+1 to all counts) and then add 10 from this arg
    extra_count_arg.set_args(10)
    assert compute_recipe_status(change_count)[change_count] == Status.IngredientDirty
    change_count.brew()
    assert compute_recipe_status(change_count)[change_count] == Status.Ok
    _check_counts((3, 2, 2, 14, 13, 13))


execution_counts_list = []  # type: List[int]


def test_lists(caplog):
    """
    Test using a list (of non-Path objects) as the input to a foreach recipe
    """
    caplog.set_level(logging.DEBUG)
    AlkymiConfig.get().cache = False

    global execution_counts_list
    execution_counts_list = [0] * 5
    args = alkymi.recipes.args([0])

    def _check_counts(counts: Tuple[int, int, int, int, int]):
        assert execution_counts_list[0] == counts[0]
        assert execution_counts_list[1] == counts[1]
        assert execution_counts_list[2] == counts[2]
        assert execution_counts_list[3] == counts[3]
        assert execution_counts_list[4] == counts[4]

    @alk.foreach(args.recipe)
    def record_execution(idx: int) -> int:
        execution_counts_list[idx] += 1
        return execution_counts_list[idx]

    # Initial brew should only increment first id
    record_execution.brew()
    _check_counts((1, 0, 0, 0, 0))

    # Re-brew should do nothing
    record_execution.brew()
    _check_counts((1, 0, 0, 0, 0))

    # Also brew ids 1 and 2
    args.set_args([0, 1, 2])
    record_execution.brew()
    _check_counts((1, 1, 1, 0, 0))

    # Now only 3 and 4 - all items should now have been run once
    args.set_args([3, 4])
    record_execution.brew()
    _check_counts((1, 1, 1, 1, 1))

    # Because last execution was 3 and 4, asking for 0 and 1 should cause reevaluation
    args.set_args([0, 1])
    record_execution.brew()
    _check_counts((2, 2, 1, 1, 1))

    # Switching the order should not change anything
    args.set_args([1, 0])
    record_execution.brew()
    _check_counts((2, 2, 1, 1, 1))
