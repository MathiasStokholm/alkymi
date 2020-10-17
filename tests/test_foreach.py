#!/usr/bin/env python
# coding=utf-8
import logging
from pathlib import Path

from alkymi import Lab
import alkymi.recipes
from alkymi.alkymi import compute_recipe_status, Status


def test_execution(caplog, tmpdir):
    tmpdir = Path(str(tmpdir))
    caplog.set_level(logging.DEBUG)
    lab = Lab('test', disable_caching=True)

    f1 = Path(tmpdir) / "file1.txt"
    f2 = Path(tmpdir) / "file2.txt"
    f3 = Path(tmpdir) / "file3.txt"
    f1.write_text(f1.stem)
    f2.write_text(f2.stem)
    f3.write_text(f3.stem)

    execution_counts = {f1: 0, f2: 0, f3: 0}

    args = alkymi.recipes.args([f1])
    lab.add_recipe(args.recipe)

    @lab.map_recipe(args.recipe)
    def read_file(path: Path) -> str:
        logging.warning("Running read_file for path: {}".format(path))
        execution_counts[path] += 1
        with path.open('r') as f:
            return f.read()

    assert compute_recipe_status(read_file)[read_file] == Status.NotEvaluatedYet
    lab.brew(read_file)
    assert compute_recipe_status(read_file)[read_file] == Status.Ok
    assert execution_counts[f1] == 1
    assert execution_counts[f2] == 0
    assert execution_counts[f3] == 0

    args.set_args([f1, f2, f3])
    assert compute_recipe_status(read_file)[read_file] == Status.MappedInputsDirty
    lab.brew(read_file)
    assert compute_recipe_status(read_file)[read_file] == Status.Ok
    assert execution_counts[f1] == 1
    assert execution_counts[f2] == 1
    assert execution_counts[f3] == 1

    args.set_args([f3, f2])
    lab.brew(read_file)
    assert execution_counts[f1] == 1
    assert execution_counts[f2] == 1
    assert execution_counts[f3] == 1

    args.set_args([f1])
    lab.brew(read_file)
    assert execution_counts[f1] == 2
    assert execution_counts[f2] == 1
    assert execution_counts[f3] == 1

    args.set_args([])
    lab.brew(read_file)
    assert execution_counts[f1] == 2
    assert execution_counts[f2] == 1
    assert execution_counts[f3] == 1
