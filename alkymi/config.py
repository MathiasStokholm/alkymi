import enum
from pathlib import Path
import os
from typing import Optional


@enum.unique
class CacheType(enum.Enum):
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
        self._cache = True
        self._cache_path = None
        self._allow_pickling = True

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

    @property
    def allow_pickling(self) -> bool:
        """
        :return: Whether to allow pickling for serialization, deserialization and checksumming
        """
        return self._allow_pickling

    @allow_pickling.setter
    def allow_pickling(self, allow_pickling: bool) -> None:
        """
        Set whether to allow pickling for serialization, deserialization and checksumming

        :param allow_pickling: Whether to allow pickling for serialization, deserialization and checksumming
        """
        self._allow_pickling = allow_pickling


# Force creation of singleton
ALKYMI_CONFIG = AlkymiConfig.get()
