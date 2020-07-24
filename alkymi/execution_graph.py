# coding=utf-8
from inspect import signature
from enum import Enum
import os.path
from typing import Callable, Optional, Iterable, List


class Status(Enum):
    Ok = 0
    IngredientDirty = 1
    NotEvaluatedYet = 2
    Dirty = 3
    BoundFunctionChanged = 4


class Recipe(object):
    def __init__(self, ingredients: Iterable['Recipe'], func: Callable, name: str, transient: bool):
        self._ingredients = []
        for ingredient in ingredients:
            self._ingredients.append(ingredient)
        self._func = func
        self._name = name
        self._transient = transient
        self._outputs = None
        print('Func {} signature: {}'.format(name, signature(func)))

    @property
    def status(self) -> Status:
        # This recipe is dirty if:
        # 1. One or more ingredients are dirty and need to be reevaluated
        # 2. There's no cached output for this recipe
        # 3. The cached output for this recipe is older than the output of any ingredient
        # 3. The bound function has changed (later)
        for ingredient in self._ingredients:
            if ingredient.status != Status.Ok:
                return Status.IngredientDirty

            if self.output_timestamps is not None and len(self.output_timestamps) > 0:
                stamps = ingredient.output_timestamps
                if stamps is not None:
                    for stamp in stamps:
                        if stamp > self.output_timestamps[0]:
                            return Status.Dirty

        if self._transient or self._outputs is None:
            return Status.NotEvaluatedYet

        # TODO(mathias): Add handling of bound function hash change

    @property
    def output_timestamps(self) -> Optional[List[float]]:
        if self._outputs is None:
            return None
        return [os.path.getmtime(str(path)) for path in self._outputs]

    def __call__(self, *args, **kwargs):
        self._outputs = self._func(*args, **kwargs)
        return self._outputs

    def brew(self):
        # Evaluate DAG to get output
        dag = ExecutionGraph(self)
        return dag.run()

    @property
    def name(self) -> str:
        return self._name

    @property
    def ingredients(self) -> Iterable['Recipe']:
        return self._ingredients

    def __str__(self):
        return '{}: {}'.format(self.name, self.status)


class RepeatedRecipe(Recipe):
    def __init__(self, inputs: Callable[[], Iterable[Recipe]], ingredients: Iterable[Recipe], func: Callable, name: str,
                 transient: bool):
        super().__init__(ingredients, func, name, transient)
        self._inputs = inputs

    @property
    def inputs(self):
        return self._inputs


class ExecutionGraph(object):
    def __init__(self, recipe: Recipe):
        self._recipe = recipe

    @staticmethod
    def evaluate_recipe(recipe):
        print('Evaluating recipe: {}'.format(recipe.name))

        if len(recipe.ingredients) <= 0:
            return recipe()

        # Load ingredient inputs
        ingredient_inputs = []
        for ingredient in recipe.ingredients:
            ingredient_inputs.append(ExecutionGraph.evaluate_recipe(ingredient))

        # Process repeated inputs
        if isinstance(recipe, RepeatedRecipe):
            results = []
            recipe_inputs = recipe.inputs()
            for item in recipe_inputs:
                if len(ingredient_inputs) > 0:
                    results.append(recipe(item, *ingredient_inputs))
                else:
                    results.append(recipe(item))
            return results

        # Process non-repeated input
        return recipe(*ingredient_inputs)

    def run(self):
        return ExecutionGraph.evaluate_recipe(self._recipe)
