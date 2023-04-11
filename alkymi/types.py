import enum
from typing import Callable, TYPE_CHECKING


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


@enum.unique
class ProgressType(enum.Enum):
    """
    Supported ways of showing progress
    """
    NoProgress = "none"  # Just run functions and log execution to alkymi's log
    Fancy = "fancy"  # Show progress indicators during recipe evaluation

    def __str__(self):
        return self.value


@enum.unique
class EvaluateProgress(enum.Enum):
    Started = 0
    InProgress = 1
    Done = 2


if TYPE_CHECKING:
    from .recipe import Recipe

# The status of the evaluation, the recipe for which the progress is to be updated, the total and current units of work
ProgressCallback = Callable[[EvaluateProgress, "Recipe", int, int], None]
