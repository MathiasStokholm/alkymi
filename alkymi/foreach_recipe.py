from collections import OrderedDict
from typing import Iterable, Callable, Optional, Tuple, Any, List, Dict, Union, cast, TypeVar
from itertools import chain

from . import checksums, serialization
from .logging import log
from .recipe import Recipe, CacheType, CleanlinessFunc
from .serialization import Output, OutputWithValue, CachedOutput

MappedInputs = Union[List[Any], Dict[Any, Any]]
MappedOutputs = Union[List[Output], Dict[Any, Output]]
MappedOutputsCached = Union[List[CachedOutput], Dict[Any, CachedOutput]]
MappedInputsChecksums = Union[List[Optional[str]], Dict[Any, Optional[str]]]

R = TypeVar("R")  # The return type of the bound function


class ForeachRecipe(Recipe[R]):
    """
    Special type of Recipe that applies its bound function to each input from a list or dictionary (similar to Python's
    built-in map() function). Evaluations of the bound function are cached and used to avoid reevaluation previously
    seen inputs, this means that changing the inputs to a ForeachRecipe may only trigger reevaluation of the bound
    function for some inputs, avoiding the overhead of recomputing things
    """

    def __init__(self, mapped_recipe: Recipe, ingredients: Iterable[Recipe], func: Callable[..., R], name: str,
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
        self._mapped_inputs: Optional[MappedInputs] = None
        self._mapped_inputs_type: Optional[type] = None
        self._mapped_inputs_checksums: Optional[MappedInputsChecksums] = None
        self._mapped_inputs_checksum: Optional[str] = None
        self._mapped_outputs: Optional[MappedOutputs] = None
        self._mapped_outputs_checksum: Optional[str] = None
        super().__init__(func, chain([mapped_recipe], ingredients), name, transient, cache, cleanliness_func)

    @property
    def mapped_inputs_type(self) -> Optional[type]:
        return self._mapped_inputs_type

    @property
    def mapped_inputs_checksums(self) -> Optional[MappedInputsChecksums]:
        """
        :return: The computed checksums for the sequence of mapped inputs (this is set when mapped_inputs is set)
        """
        return self._mapped_inputs_checksums

    @property
    def mapped_inputs_checksum(self) -> Optional[str]:
        """
        :return: The summary of the mapped inputs checksum
        """
        return self._mapped_inputs_checksum

    @property
    def mapped_inputs(self) -> Optional[MappedInputs]:
        """
        :return: The sequence of inputs to apply the bound function to
        """
        return self._mapped_inputs

    @mapped_inputs.setter
    def mapped_inputs(self, mapped_inputs: MappedInputs) -> None:
        """
        Sets the sequence of inputs to apply the bound function to and computes the necessary checksums needed for
        checking dirtiness

        :param mapped_inputs: The sequence of inputs to apply the bound function to
        """
        if mapped_inputs is None:
            return

        # FIXME(mathias): This does unnecessary work by checksumming the same items multiple times during evaluation
        if isinstance(mapped_inputs, list):
            self._mapped_inputs_checksums = []
            for inp in mapped_inputs:
                self._mapped_inputs_checksums.append(checksums.checksum(inp))
        elif isinstance(mapped_inputs, dict):
            self._mapped_inputs_checksums = {}
            for key, inp in mapped_inputs.items():
                self._mapped_inputs_checksums[key] = checksums.checksum(inp)
        else:
            raise RuntimeError("Cannot handle mapped input of type: {}".format(type(mapped_inputs)))
        self._mapped_inputs = mapped_inputs
        self._mapped_inputs_type = type(self._mapped_inputs)

    @Recipe.outputs.getter  # type: ignore # see https://github.com/python/mypy/issues/1465
    def outputs(self) -> Optional[Union[Dict, List]]:
        """
        :return: The outputs of this ForeachRecipe in canonical form (None or a tuple with zero or more entries)
        """
        if self._mapped_outputs is None:
            return None
        if isinstance(self._mapped_outputs, list):
            return [output.value() for output in self._mapped_outputs]
        elif isinstance(self._mapped_outputs, dict):
            return {key: output.value() for key, output in self._mapped_outputs.items()}
        raise RuntimeError("Invalid type for mapped outputs")

    @property
    def output_checksum(self) -> Optional[str]:
        """
        :return: The computed checksums for the outputs (this is set when outputs are set)
        """
        if self._mapped_outputs_checksum is None:
            return None
        return self._mapped_outputs_checksum

    @property
    def mapped_outputs(self) -> Optional[MappedOutputs]:
        return self._mapped_outputs

    @property
    def mapped_outputs_checksums(self) -> Optional[MappedInputsChecksums]:
        """
        :return: The computed checksums for the sequence of mapped outputs
        """
        if self._mapped_outputs is None:
            return None
        if isinstance(self._mapped_outputs, list):
            return [output.checksum for output in self._mapped_outputs]
        elif isinstance(self._mapped_outputs, dict):
            return {key: output.checksum for key, output in self._mapped_outputs.items()}
        raise RuntimeError("Invalid type for mapped outputs")

    @property
    def outputs_valid(self) -> bool:
        """
        Check whether an output is still valid - this is currently only used to check files that may have been deleted
        or altered outside alkymi's cache. If no outputs have been produced yet, True will be returned.

        :return: Whether all outputs are still valid
        """
        if self._mapped_outputs is None:
            return True
        if isinstance(self._mapped_outputs, list):
            return all(output.valid for output in self._mapped_outputs)
        elif isinstance(self._mapped_outputs, dict):
            return all(output.valid for output in self._mapped_outputs.values())
        else:
            raise ValueError("Invalid type of mapped_outputs")

    def set_current_result(self, evaluated: MappedInputs, outputs: MappedOutputs, mapped_inputs_checksum: Optional[str],
                           other_input_checksums: Tuple[Optional[str], ...], completed: bool) -> None:
        """
        Stores the provided results in the recipe and caches them to disk if applicable

        :param evaluated: The inputs that were used to generate the provided outputs
        :param outputs: The outputs to store in this recipe
        :param mapped_inputs_checksum: The checksum of all mapped inputs
        :param other_input_checksums: The checksums of other (non-mapped) inputs
        :param completed: Bool indicating whether all mapped inputs have been processed
        """
        self.mapped_inputs = evaluated
        self._mapped_outputs = outputs
        self._mapped_outputs_checksum = checksums.checksum(outputs)
        self._last_function_hash = self.function_hash
        if completed:
            self._mapped_inputs_checksum = mapped_inputs_checksum
        else:
            # If not completed, use a dummy value to mark the inputs dirty
            self._mapped_inputs_checksum = "0xmissing_mapped_inputs_eval"
        self._input_checksums = (self._mapped_inputs_checksum,) + other_input_checksums
        self._save_state()

    def to_dict(self) -> OrderedDict:
        """
        :return: The ForeachRecipe as a dict for serialization purposes
        """
        # Force caching of all outputs (if they aren't already)
        serialized_mapped_outputs: Optional[Union[Dict, List]] = None
        if self._mapped_outputs is not None:
            if isinstance(self._mapped_outputs, list):
                outputs_list: List[CachedOutput] = []
                for output in self._mapped_outputs:
                    if isinstance(output, CachedOutput):
                        outputs_list.append(output)
                    elif isinstance(output, OutputWithValue):
                        outputs_list.append(serialization.cache(output, self.cache_path))
                    else:
                        raise RuntimeError("Output is of wrong type")
                serialized_mapped_outputs = [output.serialized for output in outputs_list]
                self._mapped_outputs = cast(List[Output], outputs_list)
            elif isinstance(self._mapped_outputs, dict):
                outputs_dict: Dict[Any, CachedOutput] = {}
                for key, output in self._mapped_outputs.items():
                    if isinstance(output, CachedOutput):
                        outputs_dict[key] = output
                    elif isinstance(output, OutputWithValue):
                        outputs_dict[key] = serialization.cache(output, self.cache_path)
                    else:
                        raise RuntimeError("Output is of wrong type")
                serialized_mapped_outputs = {key: output.serialized for key, output in outputs_dict.items()}
                self._mapped_outputs = cast(Dict[Any, Output], outputs_dict)

        return OrderedDict(
            name=self.name,
            input_checksums=self.input_checksums,
            mapped_outputs=serialized_mapped_outputs,
            mapped_outputs_checksums=self.mapped_outputs_checksums,
            mapped_outputs_checksum=self._mapped_outputs_checksum,
            output_checksum=self.output_checksum,
            last_function_hash=self._last_function_hash,
            mapped_inputs_checksums=self.mapped_inputs_checksums,
            mapped_inputs_checksum=self.mapped_inputs_checksum,
            mapped_type="dict" if self.mapped_inputs_type == dict else "list"
        )


    def restore_from_dict(self, old_state: Dict) -> None:
        """
        Restores the state of this ForeachRecipe from a previously cached state

        :param old_state: The old cached state to restore
        """
        log.debug("Restoring {} from dict".format(self._name))
        if old_state["input_checksums"] is not None:
            self._input_checksums = tuple(old_state["input_checksums"])
        mapped_type = old_state["mapped_type"]
        if mapped_type == "list":
            self._mapped_inputs_type = list
            self._mapped_outputs = [CachedOutput(None, checksum, serialized)
                                    for serialized, checksum in
                                    zip(old_state["mapped_outputs"], old_state["mapped_outputs_checksums"])]
        elif mapped_type == "dict":
            self._mapped_inputs_type = dict
            self._mapped_outputs = {key: CachedOutput(None, checksum, serialized)
                                    for (key, serialized), checksum in
                                    zip(old_state["mapped_outputs"].items(), old_state["mapped_outputs_checksums"])}
        else:
            raise ValueError("Unknown mapped type: {}".format(mapped_type))
        self._last_function_hash = cast(str, old_state["last_function_hash"])
        self._mapped_inputs_checksums = cast(MappedInputsChecksums, old_state["mapped_inputs_checksums"])
        self._mapped_inputs_checksum = cast(str, old_state["mapped_inputs_checksum"])
        self._mapped_outputs_checksum = cast(str, old_state["mapped_outputs_checksum"])
