#!/usr/bin/env python
import copy
from pathlib import Path
from typing import List

import alkymi as alk
from alkymi import serialization, AlkymiConfig


def test_serialize_item(tmpdir):
    tmpdir = Path(str(tmpdir))

    cache_path_generator = (tmpdir / str(i) for i in range(5))
    generator = serialization.serialize_item(Path("/test_path/test.txt"), cache_path_generator)
    assert next(generator).startswith(serialization.PATH_TOKEN)

    test_string = "test_string"
    generator = serialization.serialize_item(test_string, cache_path_generator)
    assert next(generator) == test_string

    # Test serialization of dicts
    generator = serialization.serialize_item(dict(key="value"), cache_path_generator)
    assert next(generator) is not None


def test_serialize_deserialize_items(tmpdir):
    tmpdir = Path(str(tmpdir))

    items = (Path("test"), "test2", 42, 1337.0, [1, 2, 3], {"key": "value", "key2": 5})
    cache_path_generator = (tmpdir / str(i) for i in range(5))
    serialized_items = serialization.serialize_items(items, cache_path_generator)
    assert serialized_items is not None
    assert len(serialized_items) == len(items)
    assert isinstance(serialized_items[0], str)
    assert isinstance(serialized_items[1], str)
    assert isinstance(serialized_items[2], int)
    assert isinstance(serialized_items[3], float)
    assert isinstance(serialized_items[4], list)
    assert len(serialized_items[4]) == len(items[4])

    deserialized_items = serialization.deserialize_items(serialized_items)
    assert deserialized_items is not None
    assert len(deserialized_items) == len(items)
    for deserialized_item, item in zip(deserialized_items, items):
        assert deserialized_item == item


def test_recipe_serialization(tmpdir):
    AlkymiConfig.get().cache = False
    tmpdir = Path(str(tmpdir))

    @alk.recipe()
    def produces_build_dir() -> Path:
        build_dir = Path(tmpdir) / "build"
        build_dir.mkdir(parents=False, exist_ok=True)
        return build_dir

    @alk.recipe(ingredients=[produces_build_dir])
    def files_in_dir(build_dir: Path) -> List[Path]:
        new_file_1 = build_dir / "test.txt"
        new_file_1.touch()
        new_file_2 = build_dir / "test2.txt"
        new_file_2.touch()
        return [new_file_1, new_file_2]

    @alk.foreach(files_in_dir)
    def read_file(f: Path) -> str:
        with f.open('r') as fh:
            return fh.read()

    # Copy before brewing
    produces_build_dir_copy = copy.deepcopy(produces_build_dir)
    files_in_dir_copy = copy.deepcopy(files_in_dir)
    read_file_copy = copy.deepcopy(read_file)
    read_file.brew()

    # Ensure copied state is correct after brew
    for recipe in [produces_build_dir_copy, files_in_dir_copy, read_file_copy]:
        assert recipe.input_checksums is None
        assert recipe.outputs is None
        assert recipe.output_checksums is None
    assert read_file_copy.mapped_inputs is None
    assert read_file_copy.mapped_inputs_checksums is None
    assert read_file_copy.mapped_inputs_checksum is None

    # Test serializing -> deserializing
    produces_build_dir_copy.restore_from_dict(produces_build_dir.to_dict())
    assert produces_build_dir_copy.input_checksums == produces_build_dir.input_checksums
    assert produces_build_dir_copy.outputs == produces_build_dir.outputs
    assert produces_build_dir_copy.output_checksums == produces_build_dir.output_checksums

    files_in_dir_copy.restore_from_dict(files_in_dir.to_dict())
    assert files_in_dir_copy.input_checksums == files_in_dir.input_checksums
    assert files_in_dir_copy.outputs == files_in_dir.outputs
    assert files_in_dir_copy.output_checksums == files_in_dir.output_checksums

    read_file_copy.restore_from_dict(read_file.to_dict())
    assert read_file_copy.input_checksums == read_file.input_checksums
    assert read_file_copy.outputs == read_file.outputs
    assert read_file_copy.output_checksums == read_file.output_checksums
    assert read_file_copy.mapped_inputs == read_file.mapped_inputs
    assert read_file_copy.mapped_inputs_checksums == read_file.mapped_inputs_checksums
