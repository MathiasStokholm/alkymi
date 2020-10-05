# coding=utf-8
from collections import OrderedDict
from hashlib import md5
from typing import Iterable, Callable, List, Optional, Union, Tuple, Any

from .logging import log
from .metadata import get_metadata
from .serialization import check_output, deserialize_items, serialize_items


class Recipe(object):
    def __init__(self, ingredients: Iterable['Recipe'], func: Callable, name: str, transient: bool,
                 cleanliness_func: Optional[Callable] = None):
        self._ingredients = list(ingredients)
        self._func = func
        self._name = name
        self._transient = transient
        self._cleanliness_func = cleanliness_func

        self._outputs = None
        self._output_metadata = None
        self._inputs = None
        self._input_metadata = None

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    def invoke(self, *inputs: Optional[Tuple[Any, ...]]):
        self.inputs = inputs
        self.outputs = self._canonical(self(*inputs))
        return self.outputs

    @staticmethod
    def _canonical(outputs: Optional[Union[Tuple, Any]]) -> Tuple[Any, ...]:
        if outputs is None:
            return tuple()
        if isinstance(outputs, tuple):
            return outputs
        return outputs,

    def is_clean(self, new_inputs: Tuple[Any, ...]) -> bool:
        if self._cleanliness_func is not None:
            # Non-pure function may have been changed by external circumstances, use custom check
            return self._cleanliness_func(self.outputs)

        # Handle default pure function
        # Not clean if outputs were never generated
        if self.outputs is None:
            return False

        # Not clean if any output is no longer valid
        if not all(check_output(output) for output in self.outputs):
            return False

        # Compute output metadata to ensure that outputs haven't changed
        current_output_metadata = [get_metadata(out) for out in self.outputs]
        if self.output_metadata != current_output_metadata:
            log.debug('{} -> dirty: output metadata did not match'.format(self._name))
            return False

        # If last inputs were non-existent, new inputs have to be non-existent too for equality
        if self.inputs is None or new_inputs is None:
            log.debug('{} -> dirty: inputs changed'.format(self._name))
            return self.inputs == new_inputs

        # Compute input metadata and perform equality check
        new_input_metadata = [get_metadata(inp) for inp in new_inputs]
        if self.input_metadata != new_input_metadata:
            log.debug('{} -> dirty: input metadata changed'.format(self._name))
            return False

        # All checks passed
        return True

    @property
    def name(self) -> str:
        return self._name

    @property
    def ingredients(self) -> List['Recipe']:
        return self._ingredients

    @property
    def transient(self) -> bool:
        return self._transient

    @property
    def function_hash(self) -> str:
        return md5(self._func.__code__.co_code).hexdigest()  # noqa

    @property
    def inputs(self) -> Optional[Tuple[Any, ...]]:
        return self._inputs

    @inputs.setter
    def inputs(self, inputs):
        if inputs is None:
            return

        self._input_metadata = []
        for inp in inputs:
            self._input_metadata.append(get_metadata(inp))
        self._inputs = inputs

    @property
    def input_metadata(self):
        return self._input_metadata

    @property
    def outputs(self) -> Optional[Tuple[Any, ...]]:
        return self._outputs

    @outputs.setter
    def outputs(self, outputs):
        if outputs is None:
            return

        self._output_metadata = []
        for out in outputs:
            self._output_metadata.append(get_metadata(out))
        self._outputs = outputs

    @property
    def output_metadata(self):
        return self._output_metadata

    def __str__(self):
        return self.name

    def to_dict(self):
        return OrderedDict(
            name=self.name,
            inputs=serialize_items(self.inputs),
            input_metadata=self.input_metadata,
            outputs=serialize_items(self.outputs),
            output_metadata=self.output_metadata,
        )

    def restore_from_dict(self, old_state):
        log.debug("Restoring {} from dict".format(self._name))
        self._inputs = deserialize_items(old_state["inputs"])
        self._input_metadata = old_state["input_metadata"]
        self._outputs = deserialize_items(old_state["outputs"])
        self._output_metadata = old_state["output_metadata"]
