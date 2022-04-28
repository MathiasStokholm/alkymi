#!/usr/bin/env python
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Union

import alkymi.recipes
from alkymi import AlkymiConfig
from alkymi.alkymi import Status
import alkymi as alk

# We use these globals to avoid altering the hashes of bound functions when any of these change
execution_counts: Dict[Union[Path, str], int] = {}
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

    arg = alkymi.recipes.arg([f1], name="arg")

    @alk.foreach(arg)
    def file_contents(path: Path) -> str:
        execution_counts[path] += 1
        with path.open('r') as f:
            return f.read()

    @alk.recipe()
    def to_dict(file_contents: List[str]) -> Dict[str, str]:
        return {f: f for f in file_contents}

    # This is used to check later whether changing an ingredient will correctly change everything
    extra_count = alkymi.recipes.arg(0, name="extra_count_arg")

    @alk.foreach(to_dict)
    def change_count(file_content: str, extra_count: int) -> str:
        execution_counts[file_content] += 1 + extra_count
        return file_content

    assert file_contents.status() == Status.NotEvaluatedYet
    assert change_count.status() == Status.NotEvaluatedYet
    change_count.brew()
    assert file_contents.status() == Status.Ok
    assert change_count.status() == Status.Ok
    _check_counts((1, 0, 0, 1, 0, 0))

    arg.set([f1, f2, f3])
    assert file_contents.status() == Status.MappedInputsDirty
    change_count.brew()
    assert file_contents.status() == Status.Ok
    _check_counts((1, 1, 1, 1, 1, 1))

    arg.set([f3, f2])
    change_count.brew()
    _check_counts((1, 1, 1, 1, 1, 1))

    arg.set([f1])
    change_count.brew()
    _check_counts((2, 1, 1, 2, 1, 1))

    arg.set([])
    change_count.brew()
    _check_counts((2, 1, 1, 2, 1, 1))

    # Test that changing an ingredient forces reevaluation of all foreach inputs
    arg.set([f1, f2, f3])
    assert change_count.status() == Status.MappedInputsDirty
    change_count.brew()
    assert change_count.status() == Status.Ok
    _check_counts((3, 2, 2, 3, 2, 2))

    # This should cause a reevaluation of everything (+1 to all counts) and then add 10 from this arg
    extra_count.set(10)
    assert change_count.status() == Status.IngredientDirty
    change_count.brew()
    assert change_count.status() == Status.Ok
    _check_counts((3, 2, 2, 14, 13, 13))


execution_counts_list: List[int] = []


def test_lists(caplog):
    """
    Test using a list (of non-Path objects) as the input to a foreach recipe
    """
    caplog.set_level(logging.DEBUG)
    AlkymiConfig.get().cache = False

    global execution_counts_list
    execution_counts_list = [0] * 5
    arg = alkymi.recipes.arg([0], name="args")

    def _check_counts(counts: Tuple[int, int, int, int, int]):
        assert execution_counts_list[0] == counts[0]
        assert execution_counts_list[1] == counts[1]
        assert execution_counts_list[2] == counts[2]
        assert execution_counts_list[3] == counts[3]
        assert execution_counts_list[4] == counts[4]

    @alk.foreach(arg)
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
    arg.set([0, 1, 2])
    record_execution.brew()
    _check_counts((1, 1, 1, 0, 0))

    # Now only 3 and 4 - all items should now have been run once
    arg.set([3, 4])
    record_execution.brew()
    _check_counts((1, 1, 1, 1, 1))

    # Because last execution was 3 and 4, asking for 0 and 1 should cause reevaluation
    arg.set([0, 1])
    record_execution.brew()
    _check_counts((2, 2, 1, 1, 1))

    # Switching the order should not change anything
    arg.set([1, 0])
    record_execution.brew()
    _check_counts((2, 2, 1, 1, 1))


def test_bound_function_changed(caplog):
    """
    Test that changing the bound function of a ForeachRecipe causes a full re-evaluation
    """
    caplog.set_level(logging.DEBUG)
    AlkymiConfig.get().cache = False

    inputs = alk.arg([1, 2, 3, 4, 5], "inputs")
    power = 2  # Note that power is captured in 'raised_inputs' - changing it changes the function hash

    @alk.foreach(inputs)
    def raised_inputs(val: int) -> int:
        return val ** power

    squared_inputs = raised_inputs.brew()
    assert squared_inputs == [1, 4, 9, 16, 25]

    # Changing power to something else should cause full re-evaluation due to the bound function changing
    power = 3
    cubed_inputs = raised_inputs.brew()
    assert cubed_inputs == [1, 8, 27, 64, 125]


def test_invalid_foreach_outputs(caplog, tmpdir):
    """
    Test that outputs of a ForeachRecipe will be re-evaluated on request if invalid (i.e. an external file pointed to by
    a Path has been deleted)
    """
    tmpdir = Path(str(tmpdir))
    caplog.set_level(logging.DEBUG)
    AlkymiConfig.get().cache = False

    inputs = alk.arg([1, 2, 3], "inputs")

    @alk.foreach(inputs)
    def files_with_values(val: int) -> Path:
        f = Path(tmpdir) / (str(val) + ".txt")
        f.write_text(str(val))
        return f

    # Initial evaluation should create all files
    files: List[Path] = files_with_values.brew()
    assert all([file.is_file() for file in files])

    # If one of output files is deleted, a subsequent brew() should recreate it
    files[0].unlink()
    assert files_with_values.status() == Status.OutputsInvalid
    files: List[Path] = files_with_values.brew()
    assert all([file.is_file() for file in files])
