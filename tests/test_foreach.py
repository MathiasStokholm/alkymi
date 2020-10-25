#!/usr/bin/env python
# coding=utf-8
import logging
from pathlib import Path
from typing import Dict, List

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

    @alk.map_recipe(args.recipe)
    def read_file(path: Path) -> str:
        execution_counts[path] += 1
        with path.open('r') as f:
            return f.read()

    @alk.recipe(ingredients=[read_file])
    def to_dict(file_contents: List[str]) -> Dict[str, str]:
        return {f: f for f in file_contents}

    @alk.map_recipe(to_dict)
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
