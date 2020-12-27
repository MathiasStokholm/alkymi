# coding=utf-8
from typing import Iterable, Callable, Optional, Tuple, Any, List, Dict, Union

from .logging import log
from .metadata import get_metadata
from .recipe import Recipe, CacheType
from .serialization import serialize_item, deserialize_item


class ForeachRecipe(Recipe):
    def __init__(self, mapped_recipe: Recipe, ingredients: Iterable['Recipe'], func: Callable, name: str,
                 transient: bool, cache: CacheType,
                 cleanliness_func: Optional[Callable] = None):
        self._mapped_recipe = mapped_recipe
        self._mapped_inputs = None
        self._mapped_inputs_metadata = None
        super().__init__(ingredients, func, name, transient, cache, cleanliness_func)

    @property
    def mapped_recipe(self) -> Recipe:
        return self._mapped_recipe

    @property
    def mapped_inputs(self) -> List[Any]:
        return self._mapped_inputs

    @mapped_inputs.setter
    def mapped_inputs(self, mapped_inputs: Union[List[Any], Dict[Any, Any]]):
        if mapped_inputs is None:
            return

        if isinstance(mapped_inputs, list):
            self._mapped_inputs_metadata = []
            for inp in mapped_inputs:
                self._mapped_inputs_metadata.append(get_metadata(inp))
        elif isinstance(mapped_inputs, dict):
            self._mapped_inputs_metadata = {}
            for key, inp in mapped_inputs.items():
                self._mapped_inputs_metadata[key] = get_metadata(inp)
        else:
            raise RuntimeError("Cannot handle mapped input of type: {}".format(type(mapped_inputs)))
        self._mapped_inputs = mapped_inputs

    @property
    def mapped_inputs_metadata(self) -> Union[List[Any], Dict[Any, Any]]:
        return self._mapped_inputs_metadata

    def invoke(self, mapped_inputs: Union[List[Any], Dict[Any, Any]], *inputs: Optional[Tuple[Any, ...]]):
        log.debug("Invoking recipe: {}".format(self.name))
        mapped_inputs_of_same_type = type(self.mapped_inputs) == type(mapped_inputs)
        if isinstance(mapped_inputs, list):
            outputs = []
            for item in mapped_inputs:
                if not self.transient and self.outputs is not None and mapped_inputs_of_same_type:
                    try:
                        new_metadata = get_metadata(item)
                        idx = self.mapped_inputs_metadata.index(new_metadata)
                        found_metadata = self.mapped_inputs_metadata[idx]
                        log.debug("Comparing metadata: {} / {}".format(new_metadata, found_metadata))
                        if new_metadata == found_metadata:
                            outputs.append(self.outputs[0][idx])
                            continue
                    except ValueError:
                        pass
                outputs.append(self(item, *inputs))
        elif isinstance(mapped_inputs, dict):
            outputs = {}
            for key, item in mapped_inputs.items():
                if not self.transient and self.outputs is not None and mapped_inputs_of_same_type:
                    found_metadata = self.mapped_inputs_metadata.get(key, None)
                    if found_metadata is not None:
                        new_metadata = get_metadata(key)
                        log.debug('Comparing metadata: {} / {}'.format(new_metadata, found_metadata))
                        if new_metadata == found_metadata:
                            outputs[key] = self.outputs[0][key]
                            continue
                outputs[key] = self(item, *inputs)
        else:
            raise RuntimeError("Cannot handle type in invoke(): {}".format(type(mapped_inputs)))

        self.inputs = inputs
        self.mapped_inputs = mapped_inputs
        self.outputs = self._canonical(outputs)
        self._save_state()
        return self.outputs

    def is_mapped_clean(self, new_mapped_inputs: Union[List[Any], Dict[Any, Any]]) -> bool:
        # Compute mapped input metadata and perform equality check
        if isinstance(new_mapped_inputs, list):
            new_mapped_input_metadata = [get_metadata(inp) for inp in new_mapped_inputs]
            if self.mapped_inputs_metadata != new_mapped_input_metadata:
                log.debug('{} -> dirty: mapped inputs metadata changed'.format(self._name))
                return False
        elif isinstance(new_mapped_inputs, dict):
            for key, item in new_mapped_inputs.items():
                if self.mapped_inputs_metadata[key] != get_metadata(item):
                    log.debug('{} -> dirty: mapped inputs metadata changed'.format(self._name))
                    return False
        else:
            raise RuntimeError(
                "Cleanliness not supported  for mapped inputs w/ type: {}".format(type(new_mapped_inputs)))
        return True

    def to_dict(self):
        def cache_path_generator():
            i = 0
            while True:
                yield self.cache_path / "m{}".format(i)
                i += 1

        dictionary = super().to_dict()
        dictionary["mapped_inputs"] = next(serialize_item(self.mapped_inputs, cache_path_generator()))
        dictionary["mapped_inputs_metadata"] = self.mapped_inputs_metadata
        return dictionary

    def restore_from_dict(self, old_state):
        super(ForeachRecipe, self).restore_from_dict(old_state)
        self._mapped_inputs = next(deserialize_item(old_state["mapped_inputs"]))
        self._mapped_inputs_metadata = old_state["mapped_inputs_metadata"]
