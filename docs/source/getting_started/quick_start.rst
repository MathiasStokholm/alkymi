.. _quick_start:

Quickstart
==========

Creating a basic execution graph using alkymi is as easy as follows:

.. code-block:: python

    import alkymi as alk


    @alk.recipe()
    def long_running_task() -> int:
        # Perform expensive computation here ...
        hard_to_compute_result = 42
        return hard_to_compute_result


    result = long_running_task.brew()  # == 42


If you execute the above script multiple times, alkymi will only call ``long_running_task`` the first time, and then cache
the results for subsequent evaluations. Note that in alkymi lingo, a ``recipe`` is a fully-defined (all inputs known) task
that can be evaluated by calling ``.brew()``. The actual ``long_running_task`` function will be referred to as the `bound
function` (wrapped in a recipe). Note that alkymi is declarative - the bound functions are only executed when requested
through a call to ``.brew()``.

Recipes can return arbitrary data of any type, which can be cached automatically by alkymi (see :ref:`caching`). If
alkymi detects a change in the graph (e.g. a bound function changing between two evaluations), the affected nodes of the
graph will be re-evaluated automatically on the next call to ``.brew()``.

Recipes can depend on other recipes using the *ingredients* argument to ``recipe``:


.. code-block:: python

    import requests

    @alk.recipe()
    def upload_to_cloud(long_running_task: int) -> None:
        r = requests.post('http://httpbin.org/post', json={"hard_to_compute_value": result})
        if r.status_code != 200:
            raise RuntimeError("Post to cloud failed with code: {}".format(r.status_code))

    upload_to_cloud.brew()  # Will only perform POST whenever input (long_running_task), or upload_to_cloud, changes

Whenever ``upload_to_cloud.brew()`` is called, alkymi will automatically traverse the entire dependency chain (in this
case just ``long_running_task``) to see if everything is up-to-date. If not, the needed steps will be evaluated to bring
the graph up-to-data. Note that alkymi will automatically associate the ``long_running_task`` argument with the
previously defined recipe of the same name, equivalent to how pytest resolves fixtures.


.. note::
    Ingredients can also be passed explicitly to a recipe using the ``ingredients`` argument of the ``recipe``
    decorator (instead of relying on the automatic lookup based on argument name <-> recipe name)
