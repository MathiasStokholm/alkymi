#!/usr/bin/env python
import copy
import json
from pathlib import Path
from typing import List

import pytest

import alkymi as alk
from alkymi import serialization, AlkymiConfig, checksums
from alkymi.serialization import OutputWithValue


def test_serialize_item(tmpdir):
    tmpdir = Path(str(tmpdir))

    cache_path_generator = (tmpdir / str(i) for i in range(5))
    result = serialization.serialize_item(Path("/test_path/test.txt"), cache_path_generator)
    assert result.startswith(serialization.PATH_TOKEN)

    test_string = "test_string"
    result = serialization.serialize_item(test_string, cache_path_generator)
    assert result == test_string

    # Test serialization of dicts
    result = serialization.serialize_item(dict(key="value"), cache_path_generator)
    assert isinstance(result, dict)
    assert result["keys"] == ["key"]
    assert result["values"] == ["value"]

    # test serialization of standard types
    items = [0, "1", 2.5, True, None]
    result = serialization.serialize_item(items, cache_path_generator)
    print(items)
    assert result == items


def test_serialize_deserialize_items(tmpdir):
    tmpdir = Path(str(tmpdir))

    json_str = "{'test': 13 []''{}!!"
    items = (Path("test"), "test2", 42, 1337.0, [1, 2, 3], {"key": "value", "key2": 5}, json_str)
    cache_path_generator = (tmpdir / str(i) for i in range(5))
    serialized_items = serialization.serialize_item(items, cache_path_generator)
    assert serialized_items is not None
    assert len(serialized_items) == len(items)
    assert isinstance(serialized_items[0], str)
    assert isinstance(serialized_items[1], str)
    assert isinstance(serialized_items[2], int)
    assert isinstance(serialized_items[3], float)
    assert isinstance(serialized_items[4], list)
    assert len(serialized_items[4]) == len(items[4])
    assert isinstance(serialized_items[5], dict)
    assert isinstance(serialized_items[6], str)

    # Pass through JSON serialization to ensure we can save/load correctly
    serialized_items = json.loads(json.dumps(serialized_items, indent=4))

    deserialized_items = serialization.deserialize_item(serialized_items)
    assert deserialized_items is not None
    assert len(deserialized_items) == len(items)
    for deserialized_item, item in zip(deserialized_items, items):
        assert deserialized_item == item


def test_recipe_serialization(tmpdir):
    AlkymiConfig.get().cache = True
    tmpdir = Path(str(tmpdir))
    AlkymiConfig.get().cache_path = tmpdir  # Use temporary directory for caching

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
    assert read_file_copy.mapped_inputs_checksums == read_file.mapped_inputs_checksums


def test_complex_serialization(tmpdir):
    """
    Test serializing a complex nested structure and checking it for validity (without deserializing) by inspecting Path
    objects in the value hierarchy
    """
    AlkymiConfig.get().cache = True
    tmpdir = Path(str(tmpdir))
    AlkymiConfig.get().cache_path = tmpdir  # Use temporary directory for caching
    subdir = tmpdir / "subdir"
    subdir.mkdir()

    file_a = tmpdir / "file_a.txt"
    with file_a.open("w") as f:
        f.write(f.name)

    file_b = tmpdir / "file_a.txt"
    with file_b.open("w") as f:
        f.write(f.name)

    # Cache object - everything should be valid at this point
    value = (1, 2, 3, ["a", "b", "c"], [file_a, file_b])
    obj = OutputWithValue(value, checksums.checksum(value))
    obj_cached = serialization.cache(obj, subdir)
    assert obj_cached.valid

    # Touching an external file shouldn't cause invalidation
    file_a.touch()
    assert obj_cached.valid

    # Changing one of the "external" files _should_ cause invalidation
    with file_a.open("a") as f:
        f.write("Changed!")
    assert not obj_cached.valid

    # Changing it back to the original value should cause things to work again
    with file_a.open("w") as f:
        f.write(f.name)
    assert obj_cached.valid


class MyClass:
    def __init__(self, value):
        self.value = value


def test_enable_disable_pickling(tmpdir):
    """
    Test turning pickling on/off for serialization and checksumming
    """
    tmpdir = Path(str(tmpdir))
    value = MyClass(5)

    # Test pickling enabled
    AlkymiConfig.get().allow_pickling = True
    cache_path_generator = (tmpdir / str(i) for i in range(5))
    result = serialization.serialize_item(value, cache_path_generator)
    assert result.startswith(serialization.PICKLE_TOKEN)
    assert serialization.deserialize_item(result).value == 5
    assert checksums.checksum(result) is not None

    # Test pickling disabled
    AlkymiConfig.get().allow_pickling = False
    with pytest.raises(RuntimeError):
        serialization.serialize_item(value, cache_path_generator)
    with pytest.raises(RuntimeError):
        serialization.deserialize_item(result)
    with pytest.raises(RuntimeError):
        checksums.checksum(value)

    # Return to default state
    AlkymiConfig.get().allow_pickling = True
