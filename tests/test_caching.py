#!/usr/bin/env python
from pathlib import Path
from alkymi import AlkymiConfig
import alkymi as alk
from alkymi.alkymi import Status
from alkymi.recipe import Recipe


def test_caching(caplog, tmpdir):
    """
    Test that a cache is created (in the set location), and that recipe can be restored correctly
    """
    tmpdir = Path(str(tmpdir))
    AlkymiConfig.get().cache = True
    AlkymiConfig.get().cache_path = tmpdir

    # Manually wrap the function
    def should_cache() -> int:
        return 42

    should_cache_recipe = alk.recipe()(should_cache)

    should_cache_recipe.brew()
    assert should_cache_recipe.status() == Status.Ok
    assert (tmpdir / Recipe.CACHE_DIRECTORY_NAME / "tests" / "should_cache").is_dir()

    # Create a "copy" to force reloading from cache
    should_cache_recipe_copy = alk.recipe()(should_cache)
    assert should_cache_recipe_copy.status() == Status.Ok
