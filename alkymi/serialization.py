import pickle
import re
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Optional, Any, Iterable, Union, Generator, Sequence, Dict, Type, TypeVar, Generic, cast

from . import checksums, AlkymiConfig

# TODO(mathias): This file needs to be reworked to be less complex/crazy. Some sort of class w/ recursive serialization
#                might help make this a lot more readable

# Shorthands for generator types used below
# Note that this doesn't fully represent the JSON hierarchy due to https://github.com/python/mypy/issues/731
CachePathGenerator = Generator[Path, None, None]
BaseSerializable = Union[str, int, float, None]
SerializableRepresentation = Union[BaseSerializable, Iterable[BaseSerializable], Dict[str, BaseSerializable]]

# Tokens used to signify to the deserializer func how to deserializer a given value
TOKEN_TEMPLATE = "!#{}#!"
TOKEN_REGEX = re.compile("(!#.*#!).*")


def create_token(name) -> str:
    """
    Creates a token using the 'TOKEN_TEMPLATE' to signify to the deserializer func how to deserializer a given value

    :param name: The name of the token
    :return: A new token for the given token name
    """
    return TOKEN_TEMPLATE.format(name)


# Create tokens
PATH_TOKEN = create_token("path")
PICKLE_TOKEN = create_token("pickle")
BYTES_TOKEN = create_token("bytes")

S = TypeVar("S")  # The type that a Serializer subclass acts on


class Serializer(Generic[S]):
    """
    Abstract base class for classes that enable serialization/deserialization of classes not in the standard library
    """

    @staticmethod
    def serialize(value: S, cache_path: Path) -> str:
        raise NotImplementedError()

    @staticmethod
    def deserialize(path: Path) -> S:
        raise NotImplementedError()


# Load additional serializers and deserializers based on available libs
additional_serializers: Dict[Any, Type[Serializer]] = {}
additional_deserializers: Dict[str, Type[Serializer]] = {}
try:
    import numpy as np  # NOQA


    class NdArraySerializer(Serializer[np.ndarray]):
        """
        Numpy array serializer/deserializer
        """
        TOKEN = create_token("ndarray")

        @staticmethod
        def serialize(array: np.ndarray, cache_path: Path) -> str:
            """
            Saves a numpy array to an .npy file

            :param array: The file so save
            :param cache_path: The path to save the array to
            :return: A tokenized path to allow the deserializer to call the "deserialize" function of this module
            """
            path = cache_path.with_suffix(".npy")
            np.save(str(path), array, allow_pickle=False)
            return "{}{}".format(NdArraySerializer.TOKEN, path)

        @staticmethod
        def deserialize(path: Path) -> np.ndarray:
            """
            Loads the numpy .npy file from the provided path

            :param path: The path to the numpy file to load
            :return: The decoded numpy array
            """
            return np.load(str(path), allow_pickle=False)


    additional_serializers[np.ndarray] = NdArraySerializer
    additional_deserializers[NdArraySerializer.TOKEN] = NdArraySerializer
except ImportError:
    pass


def serialize_item(item: Any, cache_path_generator: CachePathGenerator) -> SerializableRepresentation:
    """
    Serializes an item (potentially recursively)

    :param item: The item to serialize (may be nested)
    :param cache_path_generator: The generator to use for generating cache paths
    :return: The serialized item
    """
    if item is None:
        return None

    itype = type(item)
    serializer = additional_serializers.get(itype, None)
    if serializer is not None:
        return serializer.serialize(item, next(cache_path_generator))
    elif isinstance(item, Path):
        # External path - store the checksum of the file at the current point in time
        file_checksum = checksums.checksum(item)
        return "{}{}:{}".format(PATH_TOKEN, file_checksum, item)
    elif itype in (str, float, int, bool):
        return item
    elif isinstance(item, bytes):
        output_file = next(cache_path_generator)
        with output_file.open("wb") as f:
            f.write(item)
        return "{}{}".format(BYTES_TOKEN, output_file)
    elif isinstance(item, Sequence):
        # recursive types are not supported by mypy yet
        return [serialize_item(subitem, cache_path_generator) for subitem in item]  # type: ignore
    elif isinstance(item, dict):
        keys = serialize_item(list(item.keys()), cache_path_generator)
        values = serialize_item(list(item.values()), cache_path_generator)
        return dict(keys=keys, values=values)
    else:
        # As a last resort, try to dump as pickle
        if not AlkymiConfig.get().allow_pickling:
            raise RuntimeError("Pickling disabled - cannot serialize type: {}".format(type(item)))

        try:
            output_file = next(cache_path_generator)
            with output_file.open("wb") as f:
                pickle.dump(item, f, protocol=pickle.HIGHEST_PROTOCOL)
            return "{}{}".format(PICKLE_TOKEN, output_file)
        except pickle.PicklingError:
            raise Exception("Cannot serialize item of type: {}".format(type(item)))


def deserialize_item(item: SerializableRepresentation) -> Any:
    """
    Deserializes an item (potentially recursively)

    :param item: The item to deserialize (may be nested)
    :return: The deserialized item
    """
    if item is None:
        return None

    if isinstance(item, str):
        m = re.match(TOKEN_REGEX, item)
        if m is None:
            # Regular string
            return item
        else:
            if item.startswith(PATH_TOKEN):
                # Path encoded as string with checksum, e.g. "!#path#!CHECKSUM_HERE:/what/a/path"
                non_token_part = item[len(PATH_TOKEN):]
                _, path_str = non_token_part.split(":", maxsplit=1)
                return Path(path_str)
            elif item.startswith(BYTES_TOKEN):
                # Bytes dumped to file
                with open(item[len(BYTES_TOKEN):], "rb") as f:
                    return f.read()
            elif item.startswith(PICKLE_TOKEN):
                # Arbitrary object encoded as pickle
                if not AlkymiConfig.get().allow_pickling:
                    raise RuntimeError("Pickling disabled - cannot deserialize item: {}".format(item))
                with open(item[len(PICKLE_TOKEN):], "rb") as f:
                    return pickle.loads(f.read())
            else:
                found_token = m.group(1)
                deserializer = additional_deserializers.get(found_token, None)
                if deserializer is not None:
                    return deserializer.deserialize(Path(item[len(found_token):]))
                else:
                    raise RuntimeError("No deserializer found for token: {}".format(found_token))
    elif isinstance(item, float) or isinstance(item, int):
        return item
    elif isinstance(item, Sequence):
        return list(deserialize_item(subitem) for subitem in item)
    elif isinstance(item, dict):
        # These should never be triggered, because we always store keys and values as lists in serialize_item(), but
        # this makes the type-checker happy
        if not isinstance(item["keys"], Iterable):
            raise ValueError("'keys' entry must be a list")
        if not isinstance(item["values"], Iterable):
            raise ValueError("'values' entry must be a list")
        keys = list(deserialize_item(key) for key in item["keys"])
        values = list(deserialize_item(val) for val in item["values"])
        return {key: value for key, value in zip(keys, values)}
    else:
        raise Exception("Cannot deserialize item of type: {}".format(type(item)))


def is_valid_serialized(item: SerializableRepresentation) -> bool:
    """
    Recursively check validity of a serialized representation. Currently just looks for external files represented by
    Path objects, and then compares the stored checksum of each such item with the current checksum (computed from the
    current file contents)

    :param item: The serialized representation to check validity for
    :return: True if the input is still valid
    """
    if isinstance(item, str):
        if item.startswith(PATH_TOKEN):
            # Path encoded as string with checksum, e.g. "!#path#!CHECKSUM_HERE:/what/a/path"
            non_token_part = item[len(PATH_TOKEN):]
            stored_checksum, path_str = non_token_part.split(":", maxsplit=1)
            current_checksum = checksums.checksum(Path(path_str))
            return stored_checksum == current_checksum
    elif isinstance(item, Sequence):
        return all(is_valid_serialized(subitem) for subitem in item)

    # Other types are always valid
    return True


T = TypeVar('T')


class Output(Generic[T], metaclass=ABCMeta):
    """
    Abstract base class for keeping track of outputs of Recipes
    """

    def __init__(self, checksum: str):
        """
        Create a new Output and assign the checksum

        :param checksum: The checksum for the object
        """
        self._checksum = checksum

    @property
    def checksum(self) -> str:
        """
        :return: The checksum of this Output
        """
        return self._checksum

    @property
    def valid(self) -> bool:
        """
        :return: Whether this Output is still valid (e.g. an external file pointed to by a Path can have been altered)
        """
        return NotImplemented

    @abstractmethod
    def value(self) -> T:
        """
        :return: The value associated with this Output
        """
        pass


class OutputWithValue(Output[T]):
    """
    An Output that is guaranteed to have an in-memory value - all outputs start out as this before being cached
    """

    def __init__(self, value: T, checksum: str):
        """
        Create a new OutputWithValue

        :param value: The value of the output
        :param checksum: The checksum of the output
        """
        super().__init__(checksum)
        self._value = value

    @Output.valid.getter  # type: ignore # see https://github.com/python/mypy/issues/1465
    def valid(self) -> bool:
        if self._value is None:
            return True
        # TODO(mathias): Find out if this is too expensive in general
        return checksums.checksum(self._value) == self.checksum

    def value(self) -> T:
        return self._value


class CachedOutput(Output[T]):
    """
    An Output that has been cached - may or may not have it's associated value in-memory
    """

    def __init__(self, value: Optional[T], checksum: str, serializable_representation: SerializableRepresentation):
        """
        Create a new CachedOutput

        :param value: The value of the output
        :param checksum: The checksum of the output
        :param serializable_representation: The serialized representation of the output
        """
        super().__init__(checksum)
        self._value = value
        self._serializable_representation = serializable_representation

    @Output.valid.getter  # type: ignore # see https://github.com/python/mypy/issues/1465
    def valid(self) -> bool:
        return is_valid_serialized(self._serializable_representation)

    def value(self) -> T:
        # Deserialize the value if it isn't already in memory
        if self._value is None:
            value = from_cache(self._serializable_representation)
            self._value = cast(T, value)
        return self._value

    @property
    def serialized(self) -> SerializableRepresentation:
        """
        :return: A serializable representation of the value of this output
        """
        return self._serializable_representation


def cache(output: OutputWithValue, base_path: Path) -> CachedOutput:
    """
    Cache an in-memory OutputWithValue, thus converting it to a CachedOutput. The resulting output will retain the value
    in-memory

    :param output: The Output to cache
    :param base_path: The directory to use for this serialization. A subdirectory will be created to store complex
        serialized objects
    :return: The cached output
    """
    value = output.value()  # type: ignore  # Make all Output types fully generic for this to work
    checksum = output.checksum
    if value is None:
        return CachedOutput(value, checksum, None)

    cache_path = base_path / checksum
    cache_path.mkdir(exist_ok=True)

    def cache_path_generator() -> Generator[Path, None, None]:
        i = 0
        while True:
            yield cache_path / str(i)
            i += 1

    return CachedOutput(value, checksum, serialize_item(value, cache_path_generator()))


def from_cache(serializable_representation: SerializableRepresentation) -> Any:
    """
    Deserialize an output from the cache using its serialized representation

    :param serializable_representation: The serialized representation to deserialize
    :return: The deserialized object
    """
    return deserialize_item(serializable_representation)
