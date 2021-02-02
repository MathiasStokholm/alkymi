import json
from collections import OrderedDict
from pathlib import Path
from typing import Iterable, Callable, List, Optional, Union, Tuple, Any

from . import checksums, serialization
from .config import CacheType, AlkymiConfig
from .logging import log
from .serialization import Object, ObjectWithValue, CachedObject

CleanlinessFunc = Callable[[Optional[Tuple[Any, ...]]], bool]


class Recipe:
    """
    Recipe is the basic building block of alkymi's evaluation approach. It binds a function (provided by the user) that
    it then calls when asked to by alkymi's execution engine. The result of the bound function evaluation can be
    automatically cached to disk to allow for checking of cleanliness (whether a Recipe is up-to-date), and to avoid
    invoking the bound function if necessary on subsequent evaluations
    """

    CACHE_DIRECTORY_NAME = ".alkymi_cache"

    def __init__(self, ingredients: Iterable['Recipe'], func: Callable, name: str, transient: bool, cache: CacheType,
                 cleanliness_func: Optional[CleanlinessFunc] = None):
        """
        Create a new Recipe

        :param ingredients: The dependencies of this Recipe - the outputs of these Recipes will be provided as arguments
                            to the bound function when called (following the item from the mapped_inputs sequence)
        :param func: The function to bind to this recipe
        :param name: The name of this Recipe
        :param transient: Whether to always (re)evaluate the created Recipe
        :param cache: The type of caching to use for this Recipe
        :param cleanliness_func: A function to allow a custom cleanliness check
        """
        self._ingredients = list(ingredients)
        self._func = func
        self._name = name
        self._transient = transient
        self._cleanliness_func = cleanliness_func

        # Set cache type based on default value (in AlkymiConfig)
        if cache == CacheType.Auto:
            # Pick based on what is in the config
            self._cache = CacheType.Cache if AlkymiConfig.get().cache else CacheType.NoCache
        else:
            self._cache = cache

        self._outputs = None  # type: Optional[Tuple[Object, ...]]
        self._input_checksums = None  # type: Optional[Tuple[Optional[str], ...]]
        self._last_function_hash = None  # type: Optional[str]

        if self.cache == CacheType.Cache:
            # Try to reload last state
            func_file = Path(self._func.__code__.co_filename)
            module_name = func_file.parent.stem

            # Use the cache path set in the alkymi config, or fall back to current working dir
            cache_root = AlkymiConfig.get().cache_path
            if cache_root is None:
                cache_root = Path(".")
            self.cache_path = cache_root / Recipe.CACHE_DIRECTORY_NAME / module_name / name

            self.cache_file = self.cache_path / '{}.json'.format(self.function_hash)
            if self.cache_file.exists():
                with self.cache_file.open('r') as f:
                    self.restore_from_dict(json.loads(f.read()))

    def __call__(self, *args, **kwargs):
        """
        Calls the bound function directly

        :param args: The arguments to provide to the bound function
        :param kwargs: The keyword arguments to provide to the bound function
        :return: The value returned by the bound function
        """
        return self._func(*args, **kwargs)

    def invoke(self, inputs: Tuple[Any, ...], input_checksums: Tuple[Optional[str], ...]) \
            -> Optional[Tuple[Object, ...]]:
        """
        Evaluate this Recipe using the provided inputs. This will call the bound function on the inputs. If the result
        is already cached, that result will be used instead (the checksum is used to check this). Only the immediately
        previous invoke call will be cached

        :param inputs: The inputs provided by the ingredients (dependencies) of this Recipe
        :param input_checksums: The (possibly new) input checksum to use for checking cleanliness
        :return: The outputs of this Recipe (which correspond to the outputs of the bound function)
        """
        log.debug('Invoking recipe: {}'.format(self.name))
        self.outputs = self._canonical(self(*inputs))
        self._input_checksums = input_checksums
        self._last_function_hash = self.function_hash
        self._save_state()
        return self.outputs

    def brew(self) -> Any:
        """
        Evaluate this Recipe and all dependent inputs - this will build the computational graph and execute any needed
        dependencies to produce the outputs of this Recipe

        :return: The outputs of this Recipe (which correspond to the outputs of the bound function)
        """
        # Lazy import to avoid circular imports
        from .alkymi import evaluate_recipe, compute_recipe_status
        result, _ = evaluate_recipe(self, compute_recipe_status(self))
        if result is None:
            return None

        # Unwrap single item tuples
        # TODO(mathias): Replace tuples with a custom type to avoid issues if someone returns a tuple with one element
        if isinstance(result, tuple) and len(result) == 1:
            return result[0]
        return result

    def status(self):
        """
        :return: The status of this recipe (will evaluate all upstream dependencies)
        """
        # Lazy import to avoid circular imports
        from .alkymi import compute_recipe_status
        return compute_recipe_status(self)[self]

    def _save_state(self) -> None:
        """
        Save the current state of this Recipe to a json file and zero or more extra data files (as needed)
        """
        if self._cache == CacheType.Cache:
            self.cache_path.mkdir(exist_ok=True, parents=True)
            with self.cache_file.open('w') as f:
                f.write(json.dumps(self.to_dict(), indent=4))

    @staticmethod
    def _canonical(outputs: Optional[Union[Tuple, Any]]) -> Optional[Tuple[Any, ...]]:
        """
        Convert a set of outputs to a canonical form (a tuple with 0 ore more entries). This is used to ensure a
        consistent form of recipe inputs and outputs

        :param outputs: The outputs to wrap
        :return: None if no output exist, otherwise a tuple containing the outputs
        """
        if outputs is None:
            return None
        if isinstance(outputs, tuple):
            return outputs
        return outputs,

    @staticmethod
    def _check_output(output: Optional[Any], expected_checksum: Optional[Any]) -> bool:
        """
        Check whether an output is still valid - this is currently only used to check files that may have been deleted

        FIXME(mathias): This doesn't support nested structures, and will just return True in those cases (e.g. list of
                        lists of Paths)

        :param output: The output to check
        :param expected_checksum: The expected checksum of the output
        :return: Whether the output is still valid
        """
        if output is None:
            return False
        if isinstance(output, Path):
            checksum = checksums.checksum(output)
            return checksum == expected_checksum
        return True

    def is_clean(self, new_input_checksums: Tuple[Optional[str], ...]) -> bool:
        """
        Check whether this Recipe is clean (result is cached) based on a set of (potentially new) input checksums

        :param new_input_checksums: The (potentially new) input checksums to use for checking cleanliness
        :return: Whether this recipe is clean (or needs to be reevaluated)
        """
        if self._cleanliness_func is not None:
            # Non-pure function may have been changed by external circumstances, use custom check
            # TODO(mathias): Should we return here, or do we need to still perform the additional checks below?
            return self._cleanliness_func(self.outputs)

        # Handle default pure function
        # Not clean if outputs were never generated
        if self.outputs is None or self.output_checksums is None:
            return False

        # Not clean if any output is no longer valid
        # TODO(mathias): Add this back in somehow
        # if not all(self._check_output(output, output_checksum) for output, output_checksum in
        #            zip(self.outputs, self.output_checksums)):
        #     return False

        # Compute input checksums and perform equality check
        if self.input_checksums != new_input_checksums:
            log.debug('{} -> dirty: input checksums changed'.format(self._name))
            return False

        # Check if bound function has changed
        if self._last_function_hash is not None:
            if self._last_function_hash != self.function_hash:
                return False

        # All checks passed
        return True

    @property
    def name(self) -> str:
        """
        :return: The name of this Recipe
        """
        return self._name

    @property
    def ingredients(self) -> List['Recipe']:
        """
        :return: The dependencies of this Recipe - the outputs of these Recipes will be provided as arguments to the
                 bound function when called (following the item from the mapped_inputs sequence)
        """
        return self._ingredients

    @property
    def transient(self) -> bool:
        """
        :return: Whether to always (re)evaluate the created Recipe
        """
        return self._transient

    @property
    def cache(self) -> CacheType:
        """
        :return: The type of caching to use for this Recipe
        """
        return self._cache

    @property
    def function_hash(self) -> str:
        """
        :return: The hash of the bound function as a string
        """
        return checksums.function_hash(self._func)

    @property
    def input_checksums(self) -> Optional[Tuple[Optional[str], ...]]:
        """
        :return: The checksum(s) for the inputs
        """
        return self._input_checksums

    @property
    def outputs(self) -> Optional[Tuple[Any, ...]]:
        """
        :return: The outputs of this Recipe in canonical form (None or a tuple with zero or more entries)
        """
        if self._outputs is None:
            return None
        return tuple(output.value() for output in self._outputs)

    @outputs.setter
    def outputs(self, outputs: Optional[Tuple[Any, ...]]) -> None:
        """
        Sets the outputs of this Recipe and computes the necessary checksums needed for checking dirtiness

        :param outputs: outputs of this Recipe in canonical form (None or a tuple with zero or more entries)
        """
        if outputs is not None:
            self._outputs = tuple(ObjectWithValue(output, checksums.checksum(output)) for output in outputs)

    @property
    def output_checksums(self) -> Optional[Tuple[Optional[str], ...]]:
        """
        :return: The computed checksums for the outputs (this is set when outputs is set)
        """
        if self._outputs is None:
            return None
        return tuple(output.checksum for output in self._outputs)

    def to_dict(self) -> OrderedDict:
        """
        :return: The Recipe as a dict for serialization purposes
        """
        # Force caching of all outputs (if they aren't already)
        serialized_outputs = None
        if self._outputs is not None:
            outputs = []
            for output in self._outputs:
                if isinstance(output, CachedObject):
                    outputs.append(output)
                elif isinstance(output, ObjectWithValue):
                    outputs.append(serialization.cache(output, self.cache_path))
                else:
                    raise RuntimeError("Output is of wrong type")
            self._outputs = tuple(outputs)
            serialized_outputs = tuple(output.serialized for output in outputs)

        return OrderedDict(
            name=self.name,
            input_checksums=self.input_checksums,
            outputs=serialized_outputs,
            output_checksums=self.output_checksums,
            last_function_hash=self._last_function_hash,
        )

    def restore_from_dict(self, old_state) -> None:
        """
        Restores the state of this Recipe from a previously cached state

        :param old_state: The old cached state to restore
        """
        log.debug("Restoring {} from dict".format(self._name))
        if old_state["input_checksums"] is not None:
            self._input_checksums = tuple(old_state["input_checksums"])
        if old_state["outputs"] is not None and old_state["output_checksums"] is not None:
            self._outputs = tuple(CachedObject(None, checksum, serialized)
                                  for serialized, checksum in
                                  zip(old_state["outputs"], old_state["output_checksums"]))
        self._last_function_hash = old_state["last_function_hash"]
