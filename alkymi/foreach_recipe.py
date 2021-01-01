from collections import OrderedDict
from pathlib import Path
from typing import Iterable, Callable, Optional, Tuple, Any, List, Dict, Union, Generator

from .logging import log
from .metadata import get_metadata
from .recipe import Recipe, CacheType, CleanlinessFunc
from .serialization import serialize_item, deserialize_item

MappedInputs = Union[List[Any], Dict[Any, Any]]
MappedInputsMetadata = Union[List[Optional[str]], Dict[Any, Optional[str]]]


class ForeachRecipe(Recipe):
    """
    Special type of Recipe that applies its bound function to each input from a list or dictionary (similar to Python's
    built-in map() function). Evaluations of the bound function are cached and used to avoid reevaluation previously
    seen inputs, this means that changing the inputs to a ForeachRecipe may only trigger reevaluation of the bound
    function for some inputs, avoiding the overhead of recomputing things
    """

    def __init__(self, mapped_recipe: Recipe, ingredients: Iterable['Recipe'], func: Callable, name: str,
                 transient: bool, cache: CacheType, cleanliness_func: Optional[CleanlinessFunc] = None):
        """
        Create a new ForeachRecipe

        :param mapped_recipe: A single Recipe to whose output (a list or dictionary) the bound function will be applied
                              to generate the new outputs (similar to Python's built-in map() function)
        :param ingredients: The dependencies of this Recipe - the outputs of these Recipes will be provided as arguments
                            to the bound function when called (following the item from the mapped_inputs sequence)
        :param func: The function to bind to this recipe
        :param name: The name of this Recipe
        :param transient: Whether to always (re)evaluate the created Recipe
        :param cache: The type of caching to use for this Recipe
        :param cleanliness_func: A function to allow a custom cleanliness check
        """
        self._mapped_recipe = mapped_recipe
        self._mapped_inputs = None  # type: Optional[MappedInputs]
        self._mapped_inputs_metadata = None  # type: Optional[MappedInputsMetadata]
        super().__init__(ingredients, func, name, transient, cache, cleanliness_func)

    @property
    def mapped_recipe(self) -> Recipe:
        """
        :return: The dependent Recipe that produces the input sequence to map the bound function to
        """
        return self._mapped_recipe

    @property
    def mapped_inputs(self) -> Optional[MappedInputs]:
        """
        :return: The sequence of inputs to apply the bound function to
        """
        return self._mapped_inputs

    @mapped_inputs.setter
    def mapped_inputs(self, mapped_inputs: MappedInputs) -> None:
        """
        Sets the sequence of inputs to apply the bound function to and computes the necessary metadata needed for
        checking dirtiness

        :param mapped_inputs: The sequence of inputs to apply the bound function to
        """
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
    def mapped_inputs_metadata(self) -> Optional[MappedInputsMetadata]:
        """
        :return: The computed metadata for the sequence of mapped inputs (this is set when mapped_inputs is set)
        """
        return self._mapped_inputs_metadata

    def invoke_mapped(self, mapped_inputs: MappedInputs, *inputs: Optional[Tuple[Any, ...]]):
        """
        Evaluate this ForeachRecipe using the provided inputs. This will apply the bound function to each item in the
        "mapped_inputs". If the result for any item is already cached, that result will be used instead (the metadata
        is used to check this). Only items from the immediately previous invoke call will be cached

        FIXME(mathias): As of right now, the evaluation state is only saved to the cache once all inputs have been
                        processed. This is obviously not ideal if one of the bound function evaluations fails and causes
                        the program to exit

        :param mapped_inputs: The (possibly new) sequence of inputs to apply the bound function to
        :param inputs: The inputs provided by the ingredients (dependencies) of this ForeachRecipe
        :return: The outputs of this ForeachRecipe
        """
        log.debug("Invoking recipe: {}".format(self.name))
        mapped_inputs_of_same_type = type(self.mapped_inputs) == type(mapped_inputs)
        outputs = None  # type: Optional[MappedInputs]  # This is needed to make mypy happy in Python 3.5

        if isinstance(mapped_inputs, list):
            # Handle list input
            outputs_list = []  # type: List[Any]
            for item in mapped_inputs:
                if not self.transient and self.outputs is not None and mapped_inputs_of_same_type:
                    try:
                        new_metadata = get_metadata(item)
                        idx = self.mapped_inputs_metadata.index(new_metadata)  # type: ignore
                        found_metadata = self.mapped_inputs_metadata[idx]  # type: ignore
                        log.debug("Comparing metadata: {} / {}".format(new_metadata, found_metadata))
                        if new_metadata == found_metadata:
                            outputs_list.append(self.outputs[0][idx])
                            continue
                    except ValueError:
                        pass
                outputs_list.append(self(item, *inputs))
            outputs = outputs_list
        elif isinstance(mapped_inputs, dict):
            # Handle dict input
            outputs_dict = {}  # type: Dict[Any, Any]
            for key, item in mapped_inputs.items():
                if not self.transient and self.outputs is not None and mapped_inputs_of_same_type:
                    found_metadata = self.mapped_inputs_metadata.get(key, None)  # type: ignore
                    if found_metadata is not None:
                        new_metadata = get_metadata(key)
                        log.debug('Comparing metadata: {} / {}'.format(new_metadata, found_metadata))
                        if new_metadata == found_metadata:
                            outputs_dict[key] = self.outputs[0][key]
                            continue
                outputs_dict[key] = self(item, *inputs)
            outputs = outputs_dict
        else:
            raise RuntimeError("Cannot handle type in invoke(): {}".format(type(mapped_inputs)))

        # Store the provided inputs and the resulting outputs and commit to cache
        self.inputs = inputs
        self.mapped_inputs = mapped_inputs
        self.outputs = self._canonical(outputs)
        self._save_state()
        return self.outputs

    def is_foreach_clean(self, new_mapped_inputs: Union[List[Any], Dict[Any, Any]]) -> bool:
        """
        Check whether this ForeachRecipe is clean (in addition to the regular recipe cleanliness checks). This is done
        by computing the metadata for each input item and checking whether it matches the metadata from the last
        invoke evaluation

        :param new_mapped_inputs: The (possibly new) sequence of inputs to check
        :return: Whether the metadata of the (possibly new) new inputs match that of the previous evaluation
        """
        # Compute mapped input metadata and perform equality check
        if isinstance(new_mapped_inputs, list):
            new_mapped_input_metadata = [get_metadata(inp) for inp in new_mapped_inputs]
            if self.mapped_inputs_metadata != new_mapped_input_metadata:
                log.debug('{} -> dirty: mapped inputs metadata changed'.format(self._name))
                return False
        elif isinstance(new_mapped_inputs, dict):
            for key, item in new_mapped_inputs.items():
                if self.mapped_inputs_metadata[key] != get_metadata(item):  # type: ignore
                    log.debug('{} -> dirty: mapped inputs metadata changed'.format(self._name))
                    return False
        else:
            raise RuntimeError(
                "Cleanliness not supported for mapped inputs w/ type: {}".format(type(new_mapped_inputs)))
        return True

    def to_dict(self) -> OrderedDict:
        """
        :return: The ForeachRecipe as a dict for serialization purposes
        """
        def cache_path_generator() -> Generator[Path, None, None]:
            """
            :return: A generator that provides paths for storing serialized (cached) data to the recipe cache dir
            """
            i = 0
            while True:
                yield self.cache_path / "m{}".format(i)
                i += 1

        dictionary = super().to_dict()
        serialized_items = serialize_item(self.mapped_inputs, cache_path_generator())
        if serialized_items is not None:
            dictionary["mapped_inputs"] = next(serialized_items)
        dictionary["mapped_inputs_metadata"] = self.mapped_inputs_metadata
        return dictionary

    def restore_from_dict(self, old_state: Dict) -> None:
        """
        Restores the state of this ForeachRecipe from a previously cached state

        :param old_state: The old cached state to restore
        """
        super(ForeachRecipe, self).restore_from_dict(old_state)
        self._mapped_inputs = next(deserialize_item(old_state["mapped_inputs"]))
        self._mapped_inputs_metadata = old_state["mapped_inputs_metadata"]
