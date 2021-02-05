import itertools
import pickle
import re
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Optional, Any, Tuple, Iterable, Union, Generator, Sequence, Dict, Type, TypeVar, Generic, cast

# Shorthands for generator types used below
from . import checksums

# TODO(mathias): This file needs to be reworked to be less complex/crazy. Some sort of class w/ recursive serialization
#                might help make this a lot more readable

CachePathGenerator = Generator[Path, None, None]
SerializationGenerator = Generator[Union[str, int, float], None, None]
SerializableRepresentation = Union[str, int, float, Iterable[Union[str, int, float]]]

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


class Serializer:
    """
    Abstract base class for classes that enable serialization/deserialization of classes not in the standard library
    """

    @staticmethod
    def serialize(value: Any, cache_path: Path) -> str:
        raise NotImplementedError()

    @staticmethod
    def deserialize(path: Path) -> Any:
        raise NotImplementedError()


# Load additional serializers and deserializers based on available libs
additional_serializers = {}  # type: Dict[Any, Type[Serializer]]
additional_deserializers = {}  # type: Dict[str, Type[Serializer]]
try:
    import numpy as np  # NOQA


    class NdArraySerializer(Serializer):
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


def serialize_item(item: Any, cache_path_generator: CachePathGenerator) -> Optional[SerializationGenerator]:
    """
    Serializes an item (potentially recursively) and returns the result(s) as a generator

    :param item: The item to serialize (may be nested)
    :param cache_path_generator: The generator to use for generating cache paths
    :return: A generator that will yield one or more serialized entries
    """
    serializer = additional_serializers.get(type(item), None)
    if item is None:
        yield None
    elif serializer is not None:
        yield serializer.serialize(item, next(cache_path_generator))
    elif isinstance(item, Path):
        # External path - store the checksum of the file at the current point in time
        file_checksum = checksums.checksum(item)
        yield "{}{}:{}".format(PATH_TOKEN, file_checksum, item)
    elif isinstance(item, str) or isinstance(item, float) or isinstance(item, int):
        yield item
    elif isinstance(item, bytes):
        output_file = next(cache_path_generator)
        with output_file.open("wb") as f:
            f.write(item)
        yield "{}{}".format(BYTES_TOKEN, output_file)
    elif isinstance(item, Sequence):
        items = []
        for subitem in item:
            generator = serialize_item(subitem, cache_path_generator)
            if generator is not None:
                for item in generator:
                    items.append(item)
        yield items
    else:
        # As a last resort, try to dump as pickle
        try:
            output_file = next(cache_path_generator)
            with output_file.open("wb") as f:
                pickle.dump(item, f)
            yield "{}{}".format(PICKLE_TOKEN, output_file)
        except pickle.PicklingError:
            raise Exception("Cannot serialize item of type: {}".format(type(item)))


def serialize_items(items: Optional[Tuple[Any, ...]], cache_path_generator: CachePathGenerator) -> \
        Optional[Tuple[Any, ...]]:
    """
    Serialize items (potentially recursively) and returns the results as a tuple

    :param items: The items to serialize
    :param cache_path_generator: The generator to use for generating cache paths
    :return: The results of serialization as a tuple
    """
    if items is None:
        return None

    serialized_items = []
    for item in items:
        generator = serialize_item(item, cache_path_generator)
        if generator is not None:
            for serialized_item in generator:
                serialized_items.append(serialized_item)
    return tuple(serialized_items)


def deserialize_item(item: SerializableRepresentation) -> Generator[Any, None, None]:
    """
    Deserializes an item (potentially recursively) and returns the result(s) as a generator

    :param item: The item to deserialize (may be nested)
    :return: A generator that will yield one or more deserialized entries
    """
    if isinstance(item, str):
        m = re.match(TOKEN_REGEX, item)
        if m is None:
            # Regular string
            yield item
        else:
            if item.startswith(PATH_TOKEN):
                # Path encoded as string with checksum, e.g. "!#path#!CHECKSUM_HERE:/what/a/path"
                non_token_part = item[len(PATH_TOKEN):]
                _, path_str = non_token_part.split(":", maxsplit=1)
                yield Path(path_str)
            elif item.startswith(BYTES_TOKEN):
                # Bytes dumped to file
                with open(item[len(BYTES_TOKEN):], "rb") as f:
                    yield f.read()
            elif item.startswith(PICKLE_TOKEN):
                # Arbitrary object encoded as pickle
                with open(item[len(PICKLE_TOKEN):], "rb") as f:
                    yield pickle.loads(f.read())
            else:
                found_token = m.group(1)
                deserializer = additional_deserializers.get(found_token, None)
                if deserializer is not None:
                    yield deserializer.deserialize(Path(item[len(found_token):]))
                else:
                    raise RuntimeError("No deserializer found for token: {}".format(found_token))
    elif isinstance(item, float) or isinstance(item, int):
        yield item
    elif isinstance(item, Sequence):
        yield list(itertools.chain.from_iterable(deserialize_item(subitem) for subitem in item))
    else:
        raise Exception("Cannot deserialize item of type: {}".format(type(item)))


def deserialize_items(items: Optional[Tuple[Any, ...]]) -> Optional[Tuple[Any, ...]]:
    """
    Deserialize items (potentially recursively) and returns the results as a tuple

    :param items: The items to deserialize
    :return: The results of deserialization as a tuple
    """
    if items is None:
        return None
    return tuple(itertools.chain.from_iterable(deserialize_item(item) for item in items))


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
        :return: Whether this Output is still valid (e.g. an external file pointed to by a Path instance can have been
        altered)
        """
        return NotImplemented

    @abstractmethod
    def value(self) -> T:
        """
        :return: The value associated with this Output
        """
        pass


class OutputWithValue(Output):
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
        # TODO(mathias): Find out if this is too expensive in general
        return checksums.checksum(self._value) == self.checksum

    def value(self) -> T:
        return self._value


class CachedOutput(Output):
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
            if self._serializable_representation is None:
                raise RuntimeError("Serializable representation is None, this should never happen")
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

    cache_path = base_path / checksum
    cache_path.mkdir(exist_ok=True)

    def cache_path_generator() -> Generator[Path, None, None]:
        i = 0
        while True:
            yield cache_path / str(i)
            i += 1

    serialized_items = []
    generator = serialize_item(value, cache_path_generator())
    if generator is not None:
        for serialized_item in generator:
            serialized_items.append(serialized_item)
    if len(serialized_items) == 1:
        return CachedOutput(value, checksum, serialized_items[0])
    else:
        return CachedOutput(value, checksum, serialized_items)


def from_cache(serializable_representation: SerializableRepresentation) -> Any:
    """
    Deserialize an output from the cache using its serialized representation

    :param serializable_representation: The serialized representation to deserialize
    :return: The deserialized object
    """
    if serializable_representation is None:
        return None
    return next(deserialize_item(serializable_representation))
