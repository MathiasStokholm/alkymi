from typing import Iterable, Callable, Set

from alkymi import Recipe, RepeatedRecipe


class Lab:
    def __init__(self):
        self._recipes = set()
        self._outputs = dict()

    def recipe(self, ingredients: Iterable[Recipe] = (), transient: bool = False):
        def _decorator(func: Callable):
            recipe = Recipe(ingredients, func, func.__name__, transient)
            self._recipes.add(recipe)
            return recipe

        return _decorator

    def add_recipe(self, recipe: Recipe) -> Recipe:
        self._recipes.add(recipe)
        return recipe

    def repeat_recipe(self, inputs: Callable[[], Iterable[Recipe]], ingredients: Iterable[Recipe] = (),
                      transient: bool = False):
        def _decorator(func: Callable):
            recipe = RepeatedRecipe(inputs, ingredients, func, func.__name__, transient)
            self._recipes.add(recipe)
            return recipe

        return _decorator

    def brew(self, target_recipe: Recipe):
        for recipe in self._recipes:
            if recipe.name == target_recipe.name:
                return recipe.brew()

    @property
    def recipes(self) -> Set[Recipe]:
        return self._recipes

    def __repr__(self) -> str:
        return 'Lab with recipes: \n\t' + '\n\t'.join((str(recipe) for recipe in self.recipes))
