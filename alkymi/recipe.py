import json
from collections import OrderedDict
from pathlib import Path
from typing import Iterable, Callable, List, Optional, Tuple, TypeVar, Generic, cast

from . import checksums, serialization
from .config import CacheType, AlkymiConfig
from .logging import log
from .serialization import OutputWithValue, CachedOutput, Output
from .types import Status, ProgressType

R = TypeVar("R")  # The return type of the bound function

CleanlinessFunc = Callable[[R], bool]


class Recipe(Generic[R]):
    """
    Recipe is the basic building block of alkymi's evaluation approach. It binds a function (provided by the user) that
    it then calls when asked to by alkymi's execution engine. The result of the bound function evaluation can be
    automatically cached to disk to allow for checking of cleanliness (whether a Recipe is up-to-date), and to avoid
    invoking the bound function if necessary on subsequent evaluations
    """

    CACHE_DIRECTORY_NAME = ".alkymi_cache"

    def __init__(self, func: Callable[..., R], ingredients: Iterable['Recipe'], name: str, transient: bool,
                 cache: CacheType, cleanliness_func: Optional[CleanlinessFunc[R]] = None):
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

        self._outputs: Optional[Output[R]] = None
        self._input_checksums: Optional[Tuple[Optional[str], ...]] = None
        self._last_function_hash: Optional[str] = None

        if self.cache == CacheType.Cache:
            # Try to reload last state
            func_file = Path(self._func.__code__.co_filename)
            module_name = func_file.absolute().parent.stem

            # Use the cache path set in the alkymi config, or fall back to current working dir
            cache_root = AlkymiConfig.get().cache_path
            if cache_root is None:
                cache_root = Path(".")
            self.cache_path = (cache_root / Recipe.CACHE_DIRECTORY_NAME / module_name / name).absolute()

            self.cache_file = self.cache_path / 'cache.json'
            if self.cache_file.exists():
                with self.cache_file.open('r') as f:
                    self.restore_from_dict(json.load(f))

    def __call__(self, *args) -> R:
        """
        Calls the bound function directly

        :param args: The arguments to provide to the bound function
        :param kwargs: The keyword arguments to provide to the bound function
        :return: The value returned by the bound function
        """
        return self._func(*args)

    def set_result(self, outputs: R, input_checksums: Tuple[Optional[str], ...]) -> None:
        """
        Stores the provided result in the recipe and caches it to disk if applicable

        :param outputs: The outputs to store in the recipe
        :param input_checksums: The checksums of the inputs that were used to calculate the outputs
        """
        self.outputs = outputs
        self._input_checksums = input_checksums
        self._last_function_hash = self.function_hash
        self._save_state()

    def brew(self, *, jobs: int = 1, progress_type: Optional[ProgressType] = None) -> R:
        """
        Evaluate this Recipe and all dependent inputs - this will build the computational graph and execute any needed
        dependencies to produce the outputs of this Recipe

        :param jobs: The number of jobs to use for evaluating this recipe in parallel, defaults to 1 (no parallelism),
                     zero or negative values will cause alkymi to use the system's default number of jobs
        :param progress_type: The method to use for showing progress, if None will default to setting in alkymi's config
        :return: The outputs of this Recipe (which correspond to the outputs of the bound function)
        """
        # Lazy import to avoid circular imports
        from .core import brew
        return brew(self, jobs=jobs, progress_type=progress_type)

    def status(self) -> Status:
        """
        :return: The status of this recipe (will evaluate all upstream dependencies)
        """
        # Lazy import to avoid circular imports
        from .core import compute_recipe_status, create_graph
        return compute_recipe_status(self, create_graph(self))[self]

    def __str__(self) -> str:
        return self.name

    def _save_state(self) -> None:
        """
        Save the current state of this Recipe to a json file and zero or more extra data files (as needed)
        """
        if self._cache == CacheType.Cache:
            self.cache_path.mkdir(exist_ok=True, parents=True)
            with self.cache_file.open('w') as f:
                f.write(json.dumps(self.to_dict(), indent=4))

    @property
    def outputs_valid(self) -> bool:
        """
        Check whether an output is still valid - this is currently only used to check files that may have been deleted
        or altered outside alkymi's cache. If no outputs have been produced yet, True will be returned.

        :return: Whether all outputs are still valid
        """
        if self._outputs is None:
            return True
        return self._outputs.valid

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
    def outputs(self) -> Optional[R]:
        """
        :return: The outputs of this Recipe
        """
        if self._outputs is None:
            return None
        return self._outputs.value()

    @outputs.setter
    def outputs(self, outputs: R) -> None:
        """
        Sets the outputs of this Recipe and computes the necessary checksums needed for checking dirtiness

        :param outputs: outputs of this Recipe
        """
        self._outputs = OutputWithValue(outputs, checksums.checksum(outputs))

    @property
    def output_checksum(self) -> Optional[str]:
        """
        :return: The computed checksums for the outputs (this is set when outputs are set)
        """
        if self._outputs is None:
            return None
        return self._outputs.checksum

    def to_dict(self) -> OrderedDict:
        """
        :return: The Recipe as a dict for serialization purposes
        """
        # Force caching of all outputs (if they aren't already)
        serialized_outputs = None
        if self._outputs is not None:
            if isinstance(self._outputs, CachedOutput):
                pass
            elif isinstance(self._outputs, OutputWithValue):
                self._outputs = serialization.cache(self._outputs, self.cache_path)
            else:
                raise RuntimeError("Output is of wrong type")
            serialized_outputs = self._outputs.serialized

        return OrderedDict(
            name=self.name,
            input_checksums=self.input_checksums,
            outputs=serialized_outputs,
            output_checksum=self.output_checksum,
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
        if old_state["outputs"] is not None and old_state["output_checksum"] is not None:
            self._outputs = CachedOutput(None, old_state["output_checksum"], old_state["outputs"])
        self._last_function_hash = cast(str, old_state["last_function_hash"])

    def __repr__(self) -> str:
        return self.name
