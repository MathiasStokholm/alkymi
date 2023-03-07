import enum


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
