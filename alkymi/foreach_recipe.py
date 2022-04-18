from collections import OrderedDict
from typing import Iterable, Callable, Optional, Tuple, Any, List, Dict, Union, cast, TypeVar

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
        self._mapped_recipe = mapped_recipe
        self._mapped_inputs: Optional[MappedInputs] = None
        self._mapped_inputs_type: Optional[type] = None
        self._mapped_inputs_checksums: Optional[MappedInputsChecksums] = None
        self._mapped_inputs_checksum: Optional[str] = None
        self._mapped_outputs: Optional[MappedOutputs] = None
        self._mapped_outputs_checksum: Optional[str] = None
        super().__init__(func, ingredients, name, transient, cache, cleanliness_func)

    @property
    def mapped_recipe(self) -> Recipe:
        """
        :return: The dependent Recipe that produces the input sequence to map the bound function to
        """
        return self._mapped_recipe

    @property
    def mapped_inputs_type(self) -> Optional[type]:
        return self._mapped_inputs_type

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

    def invoke_mapped(self, mapped_inputs: MappedInputs, mapped_inputs_checksum: Optional[str],
                      inputs: Tuple[Any, ...], input_checksums: Tuple[Optional[str], ...]) -> Optional[MappedOutputs]:
        """
        Evaluate this ForeachRecipe using the provided inputs. This will apply the bound function to each item in the
        "mapped_inputs". If the result for any item is already cached, that result will be used instead (the checksum
        is used to check this). Only items from the immediately previous invoke call will be cached

        :param mapped_inputs: The (possibly new) sequence of inputs to apply the bound function to
        :param mapped_inputs_checksum: A single checksum for all the mapped inputs, used to quickly check
            whether anything has changed
        :param inputs: The inputs provided by the ingredients (dependencies) of this ForeachRecipe
        :param input_checksums: The (possibly new) input checksum to use for checking cleanliness
        :return: The outputs of this ForeachRecipe
        """
        log.debug("Invoking recipe: {}".format(self.name))
        if not (isinstance(mapped_inputs, list) or isinstance(mapped_inputs, dict)):
            raise RuntimeError("Cannot handle type in invoke(): {}".format(type(mapped_inputs)))

        mapped_inputs_of_same_type = self.mapped_inputs_type == type(mapped_inputs)

        # Check if a full reevaluation across all mapped inputs is needed
        needs_full_eval = self.transient or not mapped_inputs_of_same_type

        # Check if ingredient inputs have changed - this should also cause a full reevaluation
        if not needs_full_eval:
            if self.input_checksums:
                needs_full_eval = self.input_checksums != input_checksums
            else:
                if input_checksums:
                    needs_full_eval = True

        # Check if bound function has changed - this should cause a full reevaluation
        if not needs_full_eval:
            if self.function_hash != self._last_function_hash:
                needs_full_eval = True

        # Check if we actually need to do any work (in case everything remains the same as last invocation)
        if not needs_full_eval:
            if mapped_inputs_checksum == self.mapped_inputs_checksum:
                # Outputs have to be valid for us to return them
                if self._mapped_outputs is not None and all(output.valid for output in self._mapped_outputs):
                    log.debug("Returning early since mapped inputs did not change since last evaluation")
                    return self._mapped_outputs

        # Catch up on already done work
        # TODO(mathias): Refactor this insanity to avoid the list/dict type checking
        outputs: MappedOutputs = [] if isinstance(mapped_inputs, list) else {}
        evaluated: MappedInputs = [] if isinstance(mapped_inputs, list) else {}
        not_evaluated: MappedInputs = [] if isinstance(mapped_inputs, list) else {}
        if needs_full_eval or self._mapped_outputs is None:
            not_evaluated = mapped_inputs
        else:
            if isinstance(mapped_inputs, list) and isinstance(outputs, list) \
                    and isinstance(evaluated, list) and isinstance(not_evaluated, list):
                for item in mapped_inputs:
                    # Try to look up cached result for this input
                    try:
                        new_checksum = checksums.checksum(item)
                        idx = self.mapped_inputs_checksums.index(new_checksum)  # type: ignore
                        found_checksum = self.mapped_inputs_checksums[idx]  # type: ignore
                        if new_checksum == found_checksum:
                            found_output = self._mapped_outputs[idx]
                            if found_output.valid:
                                outputs.append(found_output)
                                evaluated.append(item)
                                continue
                    except ValueError:
                        pass
                    not_evaluated.append(item)
            elif isinstance(mapped_inputs, dict):
                for key, item in mapped_inputs.items():
                    # Try to look up cached result for this input
                    found_checksum = self.mapped_inputs_checksums.get(key, None)  # type: ignore
                    if found_checksum is not None:
                        new_checksum = checksums.checksum(key)
                        if new_checksum == found_checksum:
                            found_output = self._mapped_outputs[key]
                            if found_output.valid:
                                outputs[key] = found_output
                                evaluated[key] = item
                                continue
                    not_evaluated[key] = item

        def _checkpoint(all_done: bool, save_state: bool = True) -> None:
            self._input_checksums = input_checksums
            self.mapped_inputs = evaluated
            self._mapped_outputs = outputs
            self._mapped_outputs_checksum = checksums.checksum(outputs)
            self._last_function_hash = self.function_hash
            if all_done:
                self._mapped_inputs_checksum = mapped_inputs_checksum
            else:
                self._mapped_inputs_checksum = "0xmissing_mapped_inputs_eval"
            if save_state:
                self._save_state()

        log.debug("Num already cached results: {}/{}".format(len(evaluated), len(mapped_inputs)))
        if len(evaluated) == len(mapped_inputs):
            log.debug("Returning early since all items were already cached")
            _checkpoint(all_done=True, save_state=False)
            return self._mapped_outputs

        # Perform remaining work - store state every time an evaluation is successful
        if isinstance(not_evaluated, list) and isinstance(outputs, list) and isinstance(evaluated, list):
            for item in not_evaluated:
                result = self(item, *inputs)
                outputs.append(OutputWithValue(result, checksums.checksum(result)))
                evaluated.append(item)
                _checkpoint(False)
        elif isinstance(not_evaluated, dict):
            for key, item in not_evaluated.items():
                result = self(item, *inputs)
                outputs[key] = OutputWithValue(result, checksums.checksum(result))
                evaluated[key] = item
                _checkpoint(False)

        _checkpoint(True)
        return self._mapped_outputs

    @property
    def outputs_valid(self) -> bool:
        """
        Check whether an output is still valid - this is currently only used to check files that may have been deleted
        or altered outside of alkymi's cache. If no outputs have been produced yet, True will be returned.

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
        self._last_function_hash = old_state["last_function_hash"]
        self._mapped_inputs_checksums = old_state["mapped_inputs_checksums"]
        self._mapped_inputs_checksum = old_state["mapped_inputs_checksum"]
        self._mapped_outputs_checksum = old_state["mapped_outputs_checksum"]
