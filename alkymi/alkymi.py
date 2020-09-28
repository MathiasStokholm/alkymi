# coding=utf-8
from pathlib import Path
from typing import Iterable, Callable, List, Optional

from .metadata import get_metadata
from .serialization import check_output, load_outputs


class Recipe(object):
    def __init__(self, ingredients: Iterable['Recipe'], func: Callable, name: str, transient: bool,
                 cleanliness_func: Optional[Callable] = None):
        self._ingredients = list(ingredients)
        self._func = func
        self._name = name
        self._transient = transient
        self._cleanliness_func = cleanliness_func
        self._function_hash = hash(func)

        self._outputs = None
        self._output_metadata = None
        self._inputs = None
        self._input_metadata = None

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    def is_clean(self, last_inputs: Optional[List[Path]], input_metadata,
                 last_outputs: Optional[List[Path]], output_metadata, new_inputs: Optional[List[Path]]) -> bool:
        if self._cleanliness_func is not None:
            # Non-pure function may have been changed by external circumstances, use custom check
            return self._cleanliness_func(last_outputs)

        # Handle default pure function
        print('{} -> Last/new inputs: {}/{} - metadata: {}'.format(self._name, last_inputs, new_inputs,
                                                                   input_metadata))

        # Not clean if outputs were never generated
        if last_outputs is None:
            return False

        # Not clean if any output is no longer valid
        if not all(check_output(output) for output in last_outputs):
            return False

        # Compute output metadata and perform equality check
        current_output_metadata = []
        for out in last_outputs:
            current_output_metadata.append(get_metadata(out))

        print('{} -> Output metadata check: {} == {}'.format(self._name, output_metadata, current_output_metadata))
        if output_metadata != current_output_metadata:
            return False

        # If last inputs were non-existent, new inputs have to be non-existent too for equality
        if last_inputs is None or new_inputs is None:
            return last_inputs == new_inputs

        # Compute input metadata and perform equality check
        new_input_metadata = []
        for inp in new_inputs:
            new_input_metadata.append(get_metadata(inp))

        print('Input metadata check: {} == {}'.format(input_metadata, new_input_metadata))
        if input_metadata != new_input_metadata:
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
    def function_hash(self) -> int:
        return hash(self._func)

    @property
    def inputs(self):
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
    def outputs(self):
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
        results = dict(
            input_metadata=self.input_metadata,
            output_metadata=self.output_metadata,
            function_hash=self.function_hash
        )

        if self.inputs is not None:
            inputs = list(self.inputs)
            for i, inp in enumerate(inputs):
                if isinstance(inp, Iterable):
                    inputs[i] = [str(item) for item in inp]
                else:
                    inputs[i] = str(inp)
            results['inputs'] = tuple(inputs)

        if self.outputs is not None:
            outputs = list(self.outputs)
            for i, out in enumerate(outputs):
                if isinstance(out, Iterable):
                    outputs[i] = [str(item) for item in out]
                else:
                    outputs[i] = str(out)
            results['outputs'] = tuple(outputs)
        return results

    def restore_from_dict(self, old_state):
        self._inputs = load_outputs(old_state["inputs"])
        self._input_metadata = old_state["input_metadata"]
        self._outputs = load_outputs(old_state["outputs"])
        self._output_metadata = old_state["output_metadata"]
        print("Restoring {} from dict".format(self._name))
