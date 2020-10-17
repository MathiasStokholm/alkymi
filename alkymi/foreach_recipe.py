# coding=utf-8

from typing import Iterable, Callable, Optional, Tuple, Any, List

from .logging import log
from .metadata import get_metadata
from .recipe import Recipe
from .serialization import serialize_item, deserialize_item


class ForeachRecipe(Recipe):
    def __init__(self, mapped_recipe: Recipe, ingredients: Iterable['Recipe'], func: Callable, name: str,
                 transient: bool,
                 cleanliness_func: Optional[Callable] = None):
        super().__init__(ingredients, func, name, transient, cleanliness_func)
        self._mapped_recipe = mapped_recipe
        self._mapped_inputs = None
        self._mapped_inputs_metadata = None

    @property
    def mapped_recipe(self) -> Recipe:
        return self._mapped_recipe

    @property
    def mapped_inputs(self) -> List[Any]:
        return self._mapped_inputs

    @mapped_inputs.setter
    def mapped_inputs(self, mapped_inputs: List[Any]):
        if mapped_inputs is None:
            return

        self._mapped_inputs_metadata = []
        for inp in mapped_inputs:
            self._mapped_inputs_metadata.append(get_metadata(inp))
        self._mapped_inputs = mapped_inputs

    @property
    def mapped_inputs_metadata(self) -> List[Any]:
        return self._mapped_inputs_metadata

    def invoke(self, mapped_inputs: List[Any], *inputs: Optional[Tuple[Any, ...]]):
        log.debug('Invoking recipe: {}'.format(self.name))
        outputs = []
        for item in mapped_inputs:
            if not self.transient and self.outputs is not None:
                try:
                    metadata = get_metadata(item)
                    idx = self.mapped_inputs_metadata.index(metadata)
                    log.debug('Comparing metadata: {} / {}'.format(metadata, self.mapped_inputs_metadata[idx]))
                    if metadata == self.mapped_inputs_metadata[idx]:
                        outputs.append(self.outputs[0][idx])
                        continue
                except ValueError:
                    pass
            outputs.append(self(item, *inputs))
        self.inputs = inputs
        self.mapped_inputs = mapped_inputs
        self.outputs = self._canonical(outputs)

        return self.outputs

    def is_mapped_clean(self, new_mapped_inputs: List[Any]) -> bool:
        # Compute mapped input metadata and perform equality check
        new_mapped_input_metadata = [get_metadata(inp) for inp in new_mapped_inputs]
        if self.mapped_inputs_metadata != new_mapped_input_metadata:
            log.debug('{} -> dirty: mapped inputs metadata changed'.format(self._name))
            return False
        return True

    def to_dict(self):
        dictionary = super().to_dict()
        dictionary["mapped_inputs"] = next(serialize_item(self.mapped_inputs))
        dictionary["mapped_inputs_metadata"] = self.mapped_inputs_metadata
        return dictionary

    def restore_from_dict(self, old_state):
        super(ForeachRecipe, self).restore_from_dict(old_state)
        self._mapped_inputs = next(deserialize_item(old_state["mapped_inputs"]))
        self._mapped_inputs_metadata = old_state["mapped_inputs_metadata"]
