from typing import Dict, Optional

import networkx as nx
import rich

from rich.progress import Progress, TaskID, TextColumn, TimeElapsedColumn, BarColumn
from rich.rule import Rule
from rich.console import Group

from .recipe import Recipe
from .types import Status, EvaluateProgress


class FancyProgress(Progress):
    def __init__(self, graph: nx.DiGraph, statuses: Dict[Recipe, Status], target_recipe: Recipe,
                 console: Optional[rich.console.Console] = None):
        self._console = rich.console.Console() if console is None else console
        self._recipe_name = target_recipe.name

        # Define the columns to use for progress table
        super().__init__(TextColumn("[deep_sky_blue2]{task.description}"),
                         BarColumn(),
                         TextColumn("{task.completed}/{task.total} ({task.percentage}%)"),
                         TextColumn("•"),
                         TimeElapsedColumn(),
                         console=self._console)

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

    def get_renderables(self):
        rule = Rule(title=f"Brewing {self._recipe_name}")
        yield Group(rule, self.make_tasks_table(self.tasks))

    def __enter__(self) -> 'FancyProgress':
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def __call__(self, evaluate_progress: EvaluateProgress, recipe: Recipe, units_total: int, units_done: int) -> None:
        if evaluate_progress == EvaluateProgress.Started:
            self.start_task(self._recipe_tasks[recipe])
        elif evaluate_progress == EvaluateProgress.InProgress:
            self.update(self._recipe_tasks[recipe], total=units_total, completed=units_done)
        elif evaluate_progress == EvaluateProgress.Done:
            self.update(self._recipe_tasks[recipe], total=units_total, completed=units_done)
            self.stop_task(self._recipe_tasks[recipe])
