import enum
from typing import Any, Optional, Iterable


@enum.unique
class Status(enum.Enum):
    """
    Status of a Recipe denoting whether (re)evaluation is needed
    """
    Ok = 0  # Recipe does not need (re)evaluation

    # The following all require (re)evaluation
    IngredientDirty = 1  # One or more ingredients of the recipe have changed
    NotEvaluatedYet = 2  # Recipe has not been evaluated yet
    InputsChanged = 3  # One or more inputs to the recipe have changed
    OutputsInvalid = 4  # One or more outputs of the recipe have been changed externally
    BoundFunctionChanged = 5  # The function referenced by the recipe has changed
    CustomDirty = 6  # The recipe has been marked dirty through a custom cleanliness function
    MappedInputsDirty = 7  # One or more mapped inputs to the recipe have changed (only ForeachRecipe)


class Outputs(tuple):
    """
    Class used to model recipe outputs with the following states:

    * None
    * Single return value
    * Tuple of return values
    """
    def __new__(cls, values: Optional[Iterable[Any]]):
        """
        Create a new immutable Outputs instance with the provided values

        :param values: The output(s) to store
        """
        if values is None:
            return tuple.__new__(Outputs, [])
        return tuple.__new__(Outputs, values)

    def __init__(self, values: Optional[Iterable[Any]]):
        """
        Sets the _valid property according to whether the stored output is None

        :param values: The output(s) to store
        """
        self._exists = values is not None

    @property
    def exists(self) -> bool:
        """
        :return: Whether the stored output(s) exist (if not, the output is None)
        """
        return self._exists
