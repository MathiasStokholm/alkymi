.. _built_in_recipes:

Built-in Recipes
================

Some tasks are common enough that alkymi has them included as part of its built-in recipes. A common trend for these
built-in recipes is that they are implemented as functions that create and bind functions to ``Recipe`` instances (and
in some cases, custom cleanliness functions - see :ref:`custom_cleanliness`). The current built-in recipes are:

* ``glob_files``: Finds and returns files in a directory as
  `pathlib.Path <https://docs.python.org/3/library/pathlib.html#pathlib.Path>`_ instances (potentially recursively). If
  the result of globbing changes (e.g. a new file is added to the directory), the recipe will be marked dirty.
* ``file``: Short-hand for returning a single file as a
  `pathlib.Path <https://docs.python.org/3/library/pathlib.html#pathlib.Path>`_ instance.
* ``zip_results``: Zips the outputs from a number of recipes into elements, similar to Python’s built-in
  `zip() <https://docs.python.org/3/library/functions.html#zip>`_ function. Notably, dictionaries are handled a bit
  differently, in that a dictionary is returned with keys mapping to tuples consisting of items from each of the
  different inputs.
* ``arg``: Creates a recipe that outputs a value. The recipe has a special ``set()``
  function that allows the user to later change the argument, potentially resulting in a need for re-evaluation. The
  ``Arg`` type can also be used to accept user input using alkymi's Lab functionality (see
  :ref:`command_line_interface`)

.. note::
    All built-in recipes are described in detail in the :ref:`Built-in Recipes API reference <built_in_recipes_api>`
