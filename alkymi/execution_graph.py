

class Recipe(object):
    def __init__(self, ingredients, func, name):
        self._ingredients = []
        for ingredient in ingredients:
            self._ingredients.append(ingredient)
        self._func = func
        self._name = name

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    def brew(self):
        # Evaluate DAG to get output
        dag = ExecutionGraph(self)
        return dag.run()

    @property
    def name(self):
        return self._name

    @property
    def ingredients(self):
        return self._ingredients


class RepeatedRecipe(Recipe):
    def __init__(self, inputs, ingredients, func, name):
        super().__init__(ingredients, func, name)
        self._inputs = inputs

    @property
    def inputs(self):
        return self._inputs


class ExecutionGraph(object):
    def __init__(self, recipe):
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
