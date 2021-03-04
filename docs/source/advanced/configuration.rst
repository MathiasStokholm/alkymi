.. _configuration:

Configuration
=============

In order to configure alkymi, the :ref:`alkymi_config` singleton can be used. To set a value, simply retrieve the
singleton instance and set the appropriate configuration field:

.. code-block:: python

    # Example of turning off caching
    config = AlkymiConfig.get()
    config.cache = False

The following settings are currently configurable:

* **cache**: Whether to enable alkymi caching globally. Setting this to false will disable caching to disk for all
  recipes.
* **cache_path**: A user-provided location to place the cache.
