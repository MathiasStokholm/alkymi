.. _execution:

Execution
=========

The core of alkymi is the ability to avoid doing work when possible - this is achieved by caching outputs of recipes
(see :ref:`caching`), and by establishing the conditions that caused a bound function to return a given set of outputs.
Furthermore, alkymi also takes into account whether the dependencies of a recipe will result in the need for
re-evaluation.

.. rubric:: Determining Status

Whenever ``.status()`` (or ``.brew()``) is called on a ``Recipe`` instance, alkymi will traverse the graph
of dependencies all the way down to determine the status for the recipe itself, as well as for all dependent nodes in
the graph. The status can take on the following states:

* ``Ok``: Recipe is up-to-date and does not need (re)evaluation
* ``IngredientDirty``: One or more ingredients of the recipe have changed
* ``NotEvaluatedYet``: Recipe has not been evaluated yet
* ``InputsChanged``: One or more inputs to the recipe have changed
* ``OutputsInvalid``: One or more outputs of the recipe have been changed externally
  (see :ref:`checksums_external_files`)
* ``BoundFunctionChanged``: The function referenced by the recipe has changed
* ``CustomDirty``: The recipe has been marked dirty through a custom cleanliness function

Throughout the documentation, "clean" will be used to refer to the ``Ok`` status, in which everything is up-to-date, and
no work needs to be done; and "dirty", which is all the status states that require some sort of (re)evaluation.

To facilitate computing the status for a recipe, each recipe stores the following information after an evaluation
(the information is always stored in the state of the recipe, but is also cached to disk if caching is enabled, see
:ref:`caching`):

* Input checksums
* Output checksums
* Bound function checksum

Once these are known, checking cleanliness can be done very efficiently by simply comparing output checksums to input
checksums (string comparisons) recursively throughout the graph.

If alkymi determines that a recipe's inputs remain the same as for the last evaluation, the next step is to check
whether the bound function has changed since the last evaluation. This is slightly more expensive, since a checksum for
the current bound function needs to be computed for the comparison.

Finally, if the bound function is unchanged, alkymi will check if any "external" files outside alkymi's
cache have been changed. This is expensive, since alkymi needs to read and compute a checksum for each external file
that is referenced (see :ref:`checksums_external_files`). This step is needed to support traditional "Make"-like
behavior.

.. rubric:: Evaluation

When ``.brew()`` is called on a recipe, alkymi will compute the status of nodes in the graph, and then continue on to
actually evaluating the recipes that are dirty. When starting this procedure, alkymi will traverse the graph back to the
first recipe(s) that have the ``Ok`` status, grab the corresponding outputs, and then proceed back up the graph toward
the target recipe. As described in the :ref:`Caching` section, alkymi will only load cached outputs when they are
actually needed for calling a bound function. For each node that is visited as part of the evaluation, alkymi will call
the bound function and cache the outputs if enabled, before proceeding to the next node. When the target recipe has been
evaluated, the outputs are returned from the ``.brew()`` call to the caller.

Note that when a sequence of similar values (e.g. a list of strings) needs to have a function applied to each of them
(similar to Python's built-in ``map`` function), alkymi can perform partial evaluation and caching of the results (see
:ref:`sequences`)

.. _custom_cleanliness:
.. rubric:: Custom Cleanliness Functions

Normally, alkymi operates under the assumption that bound functions are "pure", in that they take some inputs, and
produce some outputs without affecting state outside of the function [#variable_references]_. However, in some cases it
might be beneficial to allow an additional "custom" check to see if a recipe should be re-evaluated, e.g.:

* Finding all files in a directory - impure because the filesystem can be changed
* Downloading a file from the internet - the file contents may have changed since the initial download

To facilitate "impure" use cases such as those above, alkymi supports using a custom cleanliness function when wrapping
a bound function in a recipe [#cleanliness_arg]_, e.g.:

.. code-block:: python

    def impure_func() -> List[Path]:
        # Find all files in 'my_directory'
        return list(Path("my_directory").rglob())

    def check_clean(last_output: List[Path]) -> bool:
        # Rerun glob and see if list of files has changed
        return _glob_recipe() == last_output

    return Recipe([], impure_func, "read_my_directory", transient=False, cache=CacheType.Auto,
            cleanliness_func=check_clean)

.. [#variable_references] Note that variables referenced in a bound function will influence the checksum of the bound
    function, potentially resulting in the associated recipe being marked "dirty" due to the checksum of the function
    changing.
.. [#cleanliness_arg] Note that the ``recipe`` decorator currently doesn't expose the ``cleanliness_func`` argument.
