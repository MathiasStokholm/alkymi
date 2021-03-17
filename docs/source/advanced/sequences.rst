.. _sequences:

Sequences
=========

When working with data pipelines, a common task is to perform some transformation on a set of homogeneous data, such as
resizing many images to a common size - Python's built-in `map <https://docs.python.org/3/library/functions.html#map>`_
function is one example of applying a function to each element in a sequence, resulting in a sequence of new items.

Sequences might be altered by adding a few extra items, or removing an item that we don't need anymore. Having to call
the (potentially) expensive function on every item whenever the sequence changes can be quite expensive. Thus, alkymi
has special support for this use-case. By using a :ref:`foreach_recipe` (often through the ``alk.foreach()`` decorator),
we can request that alkymi apply a function to a sequence of inputs to produce a corresponding sequence of outputs:

.. code-block:: python

    import alkymi as alk

    # Assume that "produce_int_list" is an alkymi recipe that produces a list of ints

    @alk.foreach(produce_int_list)
    def convert_to_string(int_value: int) -> str:
        return str(int_value)

    list_of_strings = convert_to_string.brew()

When using the ``foreach()`` decorator, alkymi will apply the bound function to each item in the input sequence, and
cache the resulting output, as well as input and output checksums per item. On subsequent evaluations, alkymi can
quickly check if an input sequence has been altered, and if so, which items have been altered (or added/removed). Input
items that have already been evaluated are simply returned from the cache, and new items are processed as needed.

As an example, let's say you wrap a function that resizes images to a certain size. If you call ``.brew()`` on the
recipe, all images in the input list will be resized (the bound function will be called exactly once per item). If you
later add a new image to the list, calling ``.brew()`` again will only call the bound function for that new item.

Currently, :ref:`foreach_recipe` supports mapping over the following types of inputs (this will likely be expanded upon
in future releases):

* `list <https://docs.python.org/3/library/stdtypes.html#list>`_
* `dict <https://docs.python.org/3/library/stdtypes.html#dict>`_

Note that using ``foreach()`` still shares all the functionality of the regular ``recipe()`` decorator - alkymi will
still check whether your bound function or dependencies have changed, and mark the recipe dirty in that case
(see :ref:`execution`) for an exhaustive list of up-to-date checks.
