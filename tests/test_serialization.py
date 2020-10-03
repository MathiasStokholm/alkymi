#!/usr/bin/env python
# coding=utf-8
import copy
import tempfile
from pathlib import Path
from typing import Tuple

from alkymi import Lab


def test_recipe_serialization():
    lab = Lab('test', disable_caching=True)

    with tempfile.TemporaryDirectory() as tempdir:
        @lab.recipe()
        def produces_build_dir() -> Path:
            build_dir = Path(tempdir) / "build"
            build_dir.mkdir(parents=False, exist_ok=True)
            return build_dir

        @lab.recipe(ingredients=[produces_build_dir])
        def files_in_dir(build_dir: Path) -> Tuple[Path, ...]:
            new_file_1 = build_dir / "test.txt"
            new_file_1.touch()
            new_file_2 = build_dir / "test2.txt"
            new_file_2.touch()
            return new_file_1, new_file_2

        # Copy before brewing
        produces_build_dir_copy = copy.deepcopy(produces_build_dir)
        files_in_dir_copy = copy.deepcopy(files_in_dir)
        lab.brew(files_in_dir)

        # Ensure copied state is correct after brew
        for recipe in [produces_build_dir_copy, files_in_dir_copy]:
            assert recipe.inputs is None
            assert recipe.input_metadata is None
            assert recipe.outputs is None
            assert recipe.output_metadata is None

        # Test serializing -> deserializing
        produces_build_dir_copy.restore_from_dict(produces_build_dir.to_dict())
        assert produces_build_dir_copy.inputs == produces_build_dir.inputs
        assert produces_build_dir_copy.input_metadata == produces_build_dir.input_metadata
        assert produces_build_dir_copy.outputs == produces_build_dir.outputs
        assert produces_build_dir_copy.output_metadata == produces_build_dir.output_metadata

        files_in_dir_copy.restore_from_dict(files_in_dir.to_dict())
        assert files_in_dir_copy.inputs == files_in_dir.inputs
        assert files_in_dir_copy.input_metadata == files_in_dir.input_metadata
        assert files_in_dir_copy.outputs == files_in_dir.outputs
        assert files_in_dir_copy.output_metadata == files_in_dir.output_metadata
