import json
from collections import OrderedDict
from pathlib import Path
from typing import Iterable, Callable, List, Optional, Union, Tuple, Any, TypeVar, Generic, cast

from . import checksums, serialization
from .config import CacheType, AlkymiConfig
from .logging import log
from .serialization import OutputWithValue, CachedOutput
from .types import Outputs, Status

R = TypeVar("R")  # The return type of the bound function

CleanlinessFunc = Callable[[Optional[Outputs]], bool]


class Recipe(Generic[R]):
    """
    Recipe is the basic building block of alkymi's evaluation approach. It binds a function (provided by the user) that
    it then calls when asked to by alkymi's execution engine. The result of the bound function evaluation can be
    automatically cached to disk to allow for checking of cleanliness (whether a Recipe is up-to-date), and to avoid
    invoking the bound function if necessary on subsequent evaluations
    """

    CACHE_DIRECTORY_NAME = ".alkymi_cache"

    def __init__(self, func: Callable[..., R], ingredients: Iterable['Recipe'], name: str, transient: bool,
                 cache: CacheType, cleanliness_func: Optional[CleanlinessFunc] = None):
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
        self._func = func
        self._ingredients = list(ingredients)
        self._name = name
        self._transient = transient
        self._cleanliness_func = cleanliness_func

        # Set cache type based on default value (in AlkymiConfig)
        if cache == CacheType.Auto:
            # Pick based on what is in the config
            self._cache = CacheType.Cache if AlkymiConfig.get().cache else CacheType.NoCache
        else:
            self._cache = cache

        self._outputs = None  # type: Optional[Outputs]
        self._input_checksums = None  # type: Optional[Tuple[Tuple[Optional[str], ...], ...]]
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

            self.cache_file = self.cache_path / 'cache.json'
            if self.cache_file.exists():
                with self.cache_file.open('r') as f:
                    self.restore_from_dict(json.loads(f.read()))

    def __call__(self, *args) -> R:
        """
        Calls the bound function directly

        :param args: The arguments to provide to the bound function
        :param kwargs: The keyword arguments to provide to the bound function
        :return: The value returned by the bound function
        """
        return self._func(*args)

    def invoke(self, inputs: Tuple[Any, ...], input_checksums: Tuple[Tuple[Optional[str], ...], ...]) -> Outputs:
        """
        Evaluate this Recipe using the provided inputs. This will call the bound function on the inputs. If the result
        is already cached, that result will be used instead (the checksum is used to check this). Only the immediately
        previous invoke call will be cached

        :param inputs: The inputs provided by the ingredients (dependencies) of this Recipe
        :param input_checksums: The (possibly new) input checksum to use for checking cleanliness
        :return: The outputs of this Recipe (which correspond to the outputs of the bound function)
        """
        log.debug('Invoking recipe: {}'.format(self.name))
        outputs = self._canonical(self(*inputs))
        self.outputs = outputs
        self._input_checksums = input_checksums
        self._last_function_hash = self.function_hash
        self._save_state()
        return outputs

    def brew(self) -> R:
        """
        Evaluate this Recipe and all dependent inputs - this will build the computational graph and execute any needed
        dependencies to produce the outputs of this Recipe

        :return: The outputs of this Recipe (which correspond to the outputs of the bound function)
        """
        # Lazy import to avoid circular imports
        from .alkymi import brew
        return cast(R, brew(self))

    def status(self) -> Status:
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
    def _canonical(outputs: Optional[Union[Tuple, Any]]) -> Outputs:
        """
        Convert a set of outputs to a canonical form (an Outputs instance). This is used to ensure a
        consistent form of recipe inputs and outputs

        :param outputs: The outputs to wrap
        :return: None if no output exist, otherwise a tuple containing the outputs
        """
        if outputs is not None and not isinstance(outputs, tuple):
            return Outputs([outputs])
        return Outputs(outputs)

    @property
    def outputs_valid(self) -> bool:
        """
        Check whether an output is still valid - this is currently only used to check files that may have been deleted
        or altered outside of alkymi's cache. If no outputs have been produced yet, True will be returned.

        :return: Whether all outputs are still valid
        """
        if self._outputs is None:
            return True
        return all(output.valid for output in self._outputs)

    @property
    def custom_cleanliness_func(self) -> Optional[CleanlinessFunc]:
        return self._cleanliness_func

    @property
    def last_function_hash(self) -> Optional[str]:
        return self._last_function_hash

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
    def outputs(self) -> Optional[Outputs]:
        """
        :return: The outputs of this Recipe in canonical form
        """
        if self._outputs is None:
            return None
        if self._outputs.exists:
            return Outputs(output.value() for output in self._outputs)
        return self._outputs

    @outputs.setter
    def outputs(self, outputs: Outputs) -> None:
        """
        Sets the outputs of this Recipe and computes the necessary checksums needed for checking dirtiness

        :param outputs: outputs of this Recipe in canonical form
        """
        if outputs.exists:
            self._outputs = Outputs(OutputWithValue(output, checksums.checksum(output)) for output in outputs)
        else:
            self._outputs = outputs

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
                if isinstance(output, CachedOutput):
                    outputs.append(output)
                elif isinstance(output, OutputWithValue):
                    outputs.append(serialization.cache(output, self.cache_path))
                else:
                    raise RuntimeError("Output is of wrong type")
            self._outputs = Outputs(outputs)
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
            self._outputs = Outputs(CachedOutput(None, checksum, serialized)
                                    for serialized, checksum in
                                    zip(old_state["outputs"], old_state["output_checksums"]))
        self._last_function_hash = old_state["last_function_hash"]
