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
