#!/usr/bin/env python
import copy
import dataclasses
import json
import time
from pathlib import Path
from typing import List

import pytest

import alkymi as alk
from alkymi import serialization, AlkymiConfig, checksums
from alkymi.config import FileChecksumMethod
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
    items = (Path("test"), "test2", 42, 1337.0, [1, 2, 3], {"key": "value", "key2": 5}, json_str, None)
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
    assert serialized_items[7] is None

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
    def build_dir() -> Path:
        d = Path(tmpdir) / "build"
        d.mkdir(parents=False, exist_ok=True)
        return d

    @alk.recipe()
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
    produces_build_dir_copy = copy.deepcopy(build_dir)
    files_in_dir_copy = copy.deepcopy(files_in_dir)
    read_file_copy = copy.deepcopy(read_file)
    read_file.brew()

    # Ensure copied state is correct after brew
    for recipe in [produces_build_dir_copy, files_in_dir_copy, read_file_copy]:
        assert recipe.input_checksums is None
        assert recipe.outputs is None
        assert recipe.output_checksum is None
    assert read_file_copy.mapped_inputs is None
    assert read_file_copy.mapped_inputs_checksums is None
    assert read_file_copy.mapped_inputs_checksum is None

    # Test serializing -> deserializing
    produces_build_dir_copy.restore_from_dict(build_dir.to_dict())
    assert produces_build_dir_copy.input_checksums == build_dir.input_checksums
    assert produces_build_dir_copy.outputs == build_dir.outputs
    assert produces_build_dir_copy.output_checksum == build_dir.output_checksum

    files_in_dir_copy.restore_from_dict(files_in_dir.to_dict())
    assert files_in_dir_copy.input_checksums == files_in_dir.input_checksums
    assert files_in_dir_copy.outputs == files_in_dir.outputs
    assert files_in_dir_copy.output_checksum == files_in_dir.output_checksum

    read_file_copy.restore_from_dict(read_file.to_dict())
    assert read_file_copy.input_checksums == read_file.input_checksums
    assert read_file_copy.outputs == read_file.outputs
    assert read_file_copy.output_checksum == read_file.output_checksum
    assert read_file_copy.mapped_inputs_checksums == read_file.mapped_inputs_checksums


@pytest.mark.parametrize("file_checksum_method", FileChecksumMethod)
def test_complex_serialization(tmpdir, file_checksum_method: FileChecksumMethod):
    """
    Test serializing a complex nested structure and checking it for validity (without deserializing) by inspecting Path
    objects in the value hierarchy
    """
    AlkymiConfig.get().cache = True
    AlkymiConfig.get().file_checksum_method = file_checksum_method
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

    # If using timestamps, ensure that writes doesn't happen at the exact same time
    if file_checksum_method == FileChecksumMethod.ModificationTimestamp:
        time.sleep(0.01)

    file_a.touch()
    if file_checksum_method == FileChecksumMethod.HashContents:
        # Touching an external file shouldn't cause invalidation if using content hash
        assert obj_cached.valid
    elif file_checksum_method == FileChecksumMethod.ModificationTimestamp:
        # Touching an external file should cause invalidation if using modification timestamp
        assert not obj_cached.valid

    # Changing one of the "external" files _should_ cause invalidation
    # If using timestamps, ensure that writes doesn't happen at the exact same time
    if file_checksum_method == FileChecksumMethod.ModificationTimestamp:
        time.sleep(0.01)
    with file_a.open("a") as f:
        f.write("Changed!")
    assert not obj_cached.valid

    # If using timestamps, ensure that writes doesn't happen at the exact same time
    if file_checksum_method == FileChecksumMethod.ModificationTimestamp:
        time.sleep(0.1)
    with file_a.open("w") as f:
        f.write(f.name)
    if file_checksum_method == FileChecksumMethod.HashContents:
        # Changing the file back should make the path valid again if using the content hash
        assert obj_cached.valid
    elif file_checksum_method == FileChecksumMethod.ModificationTimestamp:
        # Changing the file back shouldn't make the path valid again if using modification timestamp
        assert not obj_cached.valid


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


def test_dataclass_serialization(tmp_path: Path) -> None:
    # Inline classes can't be pickled, so this will only work if dataclass serialization works as expected
    @dataclasses.dataclass
    class Data:
        a_string: str
        a_number: int

    instance = Data(a_string="test", a_number=42)
    cache_path_generator = (tmp_path / str(i) for i in range(5))
    serialized = serialization.serialize_item(instance, cache_path_generator)

    # Pass through JSON serialization to ensure we can save/load correctly
    json_encoded = json.loads(json.dumps(serialized, indent=4))
    deserialized = serialization.deserialize_item(json_encoded)
    assert deserialized == instance
