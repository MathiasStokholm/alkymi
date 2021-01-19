from enum import Enum
from pathlib import Path
import os
from typing import Optional


class CacheType(Enum):
    """
    Supported caching mechanisms
    """
    Cache = 0  # Enable caching
    NoCache = 1  # Disable caching
    Auto = 2  # Enable or disable caching based on AlkymiConfig.cache setting


class AlkymiConfig:
    """
    Global singleton config for alkymi
    """
    __instance = None  # type: AlkymiConfig

    @staticmethod
    def get() -> 'AlkymiConfig':
        """
        :return: The singleton instance of AlkymiConfig
        """
        if AlkymiConfig.__instance is None:
            AlkymiConfig()
        return AlkymiConfig.__instance

    def __init__(self):
        """
        Private initializer that creates and sets the singleton instance
        """
        if AlkymiConfig.__instance is not None:
            raise Exception("This class is a singleton!")

        # Set default values in config
        AlkymiConfig.__instance = self
        self._cache = True  # type: bool
        self._cache_path = None  # type: Optional[Path]

    @property
    def cache(self) -> bool:
        """
        :return: Whether to enable alkymi caching globally (see CacheType.Auto)
        """
        return self._cache

    @cache.setter
    def cache(self, enable_cache: bool) -> None:
        """
        Set whether to enable alkymi caching globally (see CacheType.Auto)

        :param enable_cache: Whether to enable alkymi caching globally
        """
        self._cache = enable_cache

    @property
    def cache_path(self) -> Optional[Path]:
        """
        :return: A user-provided location to place the cache
        """
        return self._cache_path

    @cache_path.setter
    def cache_path(self, cache_path: Path) -> None:
        """
        Set a custom cache path to override the default caching location

        :param cache_path: The custom location to place the cache
        """
        if not cache_path.is_dir():
            raise ValueError("Cache path '{}' must be a directory".format(cache_path))
        if not os.access(str(cache_path), os.W_OK):
            raise ValueError("Cache path '{}' must be writeable".format(cache_path))
        self._cache_path = cache_path


# Force creation of singleton
ALKYMI_CONFIG = AlkymiConfig.get()
