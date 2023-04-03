from typing import Dict, Optional, Iterable

import networkx as nx
import rich

from rich.progress import TaskID, TextColumn, TimeElapsedColumn, BarColumn
from rich.rule import Rule
from rich.console import Group

from .recipe import Recipe
from .types import Status, EvaluateProgress


class FancyProgress(rich.progress.Progress):
    def __init__(self, graph: nx.DiGraph, statuses: Dict[Recipe, Status], target_recipe: Recipe,
                 console: Optional[rich.console.Console] = None) -> None:
        """
        Prepare a progress object for the provided execution graph and statuses. Once created, call "start()" to begin
        showing the output, and "stop" to finish the output.

        :param graph: The graph to visualize progress for
        :param statuses: A dictionary of statuses per recipe
        :param target_recipe: The recipe that is the final target of the progress (last to run)
        :param console: An optional console object to use for output
        """
        self._console = rich.console.Console() if console is None else console
        self._recipe_name = target_recipe.name

        # Define the columns to use for progress table
        super().__init__(TextColumn("[deep_sky_blue2]{task.description}"),
                         BarColumn(),
                         TextColumn("{task.completed}/{task.total} ({task.percentage}%)"),
                         TextColumn("•"),
                         TimeElapsedColumn(),
                         console=self._console, redirect_stdout=True, redirect_stderr=True)

        # Build the progress table by adding all required tasks sorted topographically (target recipe at the bottom)
        self._recipe_tasks: Dict[Recipe, TaskID] = {
            recipe: self.add_task(recipe.name, start=False, total=1, completed=0)
            for recipe in nx.topological_sort(graph)
        }

        # For all recipes that are already cached (Ok), mark them as completed from the beginning
        for recipe, task_id in self._recipe_tasks.items():
            if statuses[recipe] == Status.Ok:
                self.update(task_id, description=recipe.name + " [dim cyan](cached)[/dim cyan]", completed=1)
                self.stop_task(task_id)

    def get_renderables(self) -> Iterable[rich.console.RenderableType]:
        """
        Helper function used to render a horizontal rule with the target recipe name above the actual progress bars
        """
        rule = Rule(title=f"Brewing {self._recipe_name}")
        yield Group(rule, self.make_tasks_table(self.tasks))

    def __call__(self, evaluate_progress: EvaluateProgress, recipe: Recipe, units_total: int, units_done: int) -> None:
        """
        Callable provided to execution engine. Will be called whenever a recipe has started progress, made progress (in
        the case of a ForeachRecipe) or finished evaluation. Note that this will only be called from a single thread, so
        we don't have to worry about race conditions.

        :param evaluate_progress: The type of progress being reported
        :param recipe: The recipe for which the evaluation progress is being reported
        :param units_total: The total units of work (always 1 for regular recipes)
        :param units_done: The currently finished units of work
        """
        if evaluate_progress == EvaluateProgress.Started:
            self.start_task(self._recipe_tasks[recipe])
        elif evaluate_progress == EvaluateProgress.InProgress:
            self.update(self._recipe_tasks[recipe], total=units_total, completed=units_done)
        elif evaluate_progress == EvaluateProgress.Done:
            self.update(self._recipe_tasks[recipe], total=units_total, completed=units_done)
            self.stop_task(self._recipe_tasks[recipe])
