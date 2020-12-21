#!/usr/bin/env python
# coding=utf-8
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import alkymi.recipes
from alkymi import AlkymiConfig
from alkymi.alkymi import compute_recipe_status, Status
import alkymi as alk


# Turn of caching for tests
AlkymiConfig.get().cache = False


def test_execution(caplog, tmpdir):
    tmpdir = Path(str(tmpdir))
    caplog.set_level(logging.DEBUG)

    f1 = Path(tmpdir) / "file1.txt"
    f2 = Path(tmpdir) / "file2.txt"
    f3 = Path(tmpdir) / "file3.txt"
    f1.write_text(f1.stem)
    f2.write_text(f2.stem)
    f3.write_text(f3.stem)

    execution_counts = {f1: 0, f2: 0, f3: 0, f1.stem: 0, f2.stem: 0, f3.stem: 0}

    args = alkymi.recipes.args([f1])

    @alk.foreach(args.recipe)
    def read_file(path: Path) -> str:
        execution_counts[path] += 1
        with path.open('r') as f:
            return f.read()

    @alk.recipe(ingredients=[read_file])
    def to_dict(file_contents: List[str]) -> Dict[str, str]:
        return {f: f for f in file_contents}

    @alk.foreach(to_dict)
    def echo(file_content: str) -> str:
        execution_counts[file_content] += 1
        return file_content

    assert compute_recipe_status(read_file)[read_file] == Status.NotEvaluatedYet
    assert compute_recipe_status(echo)[echo] == Status.NotEvaluatedYet
    echo.brew()
    assert compute_recipe_status(read_file)[read_file] == Status.Ok
    assert compute_recipe_status(echo)[echo] == Status.Ok
    assert execution_counts[f1] == 1
    assert execution_counts[f2] == 0
    assert execution_counts[f3] == 0
    assert execution_counts[f1.stem] == 1
    assert execution_counts[f2.stem] == 0
    assert execution_counts[f3.stem] == 0

    args.set_args([f1, f2, f3])
    assert compute_recipe_status(read_file)[read_file] == Status.MappedInputsDirty
    echo.brew()
    assert compute_recipe_status(read_file)[read_file] == Status.Ok
    assert execution_counts[f1] == 1
    assert execution_counts[f2] == 1
    assert execution_counts[f3] == 1
    assert execution_counts[f1.stem] == 1
    assert execution_counts[f2.stem] == 1
    assert execution_counts[f3.stem] == 1

    args.set_args([f3, f2])
    echo.brew()
    assert execution_counts[f1] == 1
    assert execution_counts[f2] == 1
    assert execution_counts[f3] == 1
    assert execution_counts[f1.stem] == 1
    assert execution_counts[f2.stem] == 1
    assert execution_counts[f3.stem] == 1

    args.set_args([f1])
    echo.brew()
    assert execution_counts[f1] == 2
    assert execution_counts[f2] == 1
    assert execution_counts[f3] == 1
    assert execution_counts[f1.stem] == 2
    assert execution_counts[f2.stem] == 1
    assert execution_counts[f3.stem] == 1

    args.set_args([])
    echo.brew()
    assert execution_counts[f1] == 2
    assert execution_counts[f2] == 1
    assert execution_counts[f3] == 1
    assert execution_counts[f1.stem] == 2
    assert execution_counts[f2.stem] == 1
    assert execution_counts[f3.stem] == 1


def test_lists(caplog):
    """
    Test using a list (of non-Path objects) as the input to a foreach recipe
    """
    caplog.set_level(logging.DEBUG)

    execution_counts = [0] * 5
    args = alkymi.recipes.args([0])

    def _check_counts(counts: Tuple[int, int, int, int, int]):
        assert execution_counts[0] == counts[0]
        assert execution_counts[1] == counts[1]
        assert execution_counts[2] == counts[2]
        assert execution_counts[3] == counts[3]
        assert execution_counts[4] == counts[4]

    @alk.foreach(args.recipe)
    def record_execution(idx: int) -> int:
        execution_counts[idx] += 1
        return execution_counts[idx]

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
