# coding=utf-8
import itertools
import re
import pickle
from pathlib import Path
from typing import Optional, Any, Tuple, Iterable, Union, Generator, Sequence, Dict

TOKEN_TEMPLATE = "!#{}#!"
TOKEN_REGEX = re.compile("(!#.*#!).*")


def create_token(name):
    return TOKEN_TEMPLATE.format(name)


PATH_TOKEN = create_token("path")
PICKLE_TOKEN = create_token("pickle")
BYTES_TOKEN = create_token("bytes")

CachePathGenerator = Generator[Path, None, None]
SerializationGenerator = Generator[Union[str, int, float], None, None]

# Load additional serializers and deserializers based on available libs
additional_serializers = {}
additional_deserializers = {}
try:
    import numpy as np


    class NdArraySerializer:
        TOKEN = create_token("ndarray")

        @staticmethod
        def serialize(array: np.ndarray, cache_path: Path) -> str:
            path = cache_path.with_suffix(".npy")
            np.save(str(path), array, allow_pickle=False)
            return "{}{}".format(NdArraySerializer.TOKEN, path)

        @staticmethod
        def deserialize(path: Path) -> np.ndarray:
            return np.load(str(path), allow_pickle=False)


    additional_serializers[np.ndarray] = NdArraySerializer
    additional_deserializers[NdArraySerializer.TOKEN] = NdArraySerializer
except ImportError:
    pass


def serialize_item(item: Any, cache_path_generator: CachePathGenerator) -> Optional[SerializationGenerator]:
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
        yield list(itertools.chain.from_iterable(serialize_item(subitem, cache_path_generator) for subitem in item))
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
    if items is None:
        return None

    return tuple(itertools.chain.from_iterable(serialize_item(item, cache_path_generator) for item in items))


def deserialize_item(item: Union[str, int, float, Iterable[Union[str, int, float]]]) -> Generator[Any, None, None]:
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
    if items is None:
        return None
    return tuple(itertools.chain.from_iterable(deserialize_item(item) for item in items))
