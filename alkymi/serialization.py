import itertools
import pickle
import re
from pathlib import Path
from typing import Optional, Any, Tuple, Iterable, Union, Generator, Sequence, Dict, Type, TypeVar, Generic, Callable, \
    cast
from abc import ABCMeta, abstractmethod

# TODO(mathias): This file needs to be reworked to be less complex/crazy. Some sort of class w/ recursive serialization
#                might help make this a lot more readable

# Shorthands for generator types used below
CachePathGenerator = Generator[Path, None, None]
SerializationGenerator = Generator[Union[str, int, float], None, None]

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
        yield "{}{}".format(PATH_TOKEN, item)
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


def deserialize_item(item: Union[str, int, float, Iterable[Union[str, int, float]]]) -> Generator[Any, None, None]:
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
                # Path encoded as string
                yield Path(item[len(PATH_TOKEN):])
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


T = TypeVar('T')


class Object(Generic[T], metaclass=ABCMeta):
    def __init__(self, checksum: str):
        self._checksum = checksum

    @property
    def checksum(self) -> str:
        return self._checksum

    @abstractmethod
    def value(self) -> T:
        pass


class ObjectWithValue(Object):
    def __init__(self, value: T, checksum: str):
        super().__init__(checksum)
        self._value = value

    def value(self) -> T:
        return self._value


class CachedObject(Object):
    def __init__(self, value: Optional[T], checksum: str, serialized_representation: Any):
        super().__init__(checksum)
        self._value = value
        self._serialized_representation = serialized_representation

    def value(self) -> T:
        if self._value is None:
            if self._serialized_representation is None:
                raise RuntimeError("Serialized representation is None, this should never happen")
            value = from_cache(self._serialized_representation)
            self._value = cast(T, value)
        return self._value

    @property
    def serialized(self) -> Any:
        return self._serialized_representation


def cache(obj: ObjectWithValue, base_path: Path) -> CachedObject:
    cache_path = base_path / obj.checksum
    cache_path.mkdir(exist_ok=True)

    def cache_path_generator() -> Generator[Path, None, None]:
        i = 0
        while True:
            yield cache_path / str(i)
            i += 1

    serialized_items = []
    generator = serialize_item(obj.value(), cache_path_generator())
    if generator is not None:
        for serialized_item in generator:
            serialized_items.append(serialized_item)
    if len(serialized_items) == 1:
        serialized = serialized_items[0]
    else:
        serialized = serialized_items
    return CachedObject(obj.value(), obj.checksum, serialized)


def from_cache(serialized_representation: Any) -> Any:
    if serialized_representation is None:
        return None
    return next(deserialize_item(serialized_representation))
