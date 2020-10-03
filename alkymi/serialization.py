# coding=utf-8
import itertools
from pathlib import Path
from typing import Optional, Any, Tuple, Iterable, Union, Generator


PATH_TOKEN = "#path:"


def check_output(output: Any) -> bool:
    if output is None:
        return False
    if isinstance(output, Path):
        return output.exists()
    return True


def _serialize_item(item: Any) -> Generator[Union[str, int, float], None, None]:
    if isinstance(item, Path):
        yield "{}{}".format(PATH_TOKEN, item)
    elif isinstance(item, str):
        yield item
    elif isinstance(item, Iterable):
        yield list(itertools.chain.from_iterable(_serialize_item(subitem) for subitem in item))
    elif isinstance(item, float) or isinstance(item, int):
        yield item
    else:
        raise Exception("Cannot serialize item of type: {}".format(type(item)))


def serialize_items(items: Optional[Tuple[Any, ...]]) -> Optional[Tuple[Any, ...]]:
    if items is None:
        return None
    return tuple(itertools.chain.from_iterable(_serialize_item(item) for item in items))


def _deserialize_item(item: Union[str, int, float, Iterable[Union[str, int, float]]]) -> Generator[Any, None, None]:
    if isinstance(item, str):
        if item.startswith(PATH_TOKEN):
            # Path encoded as string
            yield Path(item.split(":", maxsplit=1)[1])
        else:
            # Regular string
            yield item
    elif isinstance(item, Iterable):
        yield list(itertools.chain.from_iterable(_deserialize_item(subitem) for subitem in item))
    elif isinstance(item, float) or isinstance(item, int):
        yield item
    else:
        raise Exception("Cannot deserialize item of type: {}".format(type(item)))


def deserialize_items(items: Optional[Tuple[Any, ...]]) -> Optional[Tuple[Any, ...]]:
    if items is None:
        return None
    return tuple(itertools.chain.from_iterable(_deserialize_item(item) for item in items))
