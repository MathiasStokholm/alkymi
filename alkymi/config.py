import enum
import os
from pathlib import Path
from typing import Optional

from .types import ProgressType


@enum.unique
class CacheType(enum.Enum):
    """
    Supported caching mechanisms
    """
    Cache = 0  # Enable caching
    NoCache = 1  # Disable caching
    Auto = 2  # Enable or disable caching based on AlkymiConfig.cache setting


@enum.unique
class FileChecksumMethod(enum.Enum):
    """
    Supported ways of calculating the checksum for a Path object representing a file
    """
    HashContents = 0  # Hash the contents of the file
    ModificationTimestamp = 1  # Use timestamp of last modification


class AlkymiConfig:
    """
    Global singleton config for alkymi
    """
    __instance: Optional["AlkymiConfig"] = None

    @staticmethod
    def get() -> 'AlkymiConfig':
        """
        :return: The singleton instance of AlkymiConfig
        """
        if AlkymiConfig.__instance is None:
            AlkymiConfig()
        assert AlkymiConfig.__instance is not None
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
        self._file_checksum_method = FileChecksumMethod.HashContents
        self._progress_type = ProgressType.Fancy

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

    @property
    def file_checksum_method(self) -> FileChecksumMethod:
        """
        :return: The currently used method for calculating file checksums (for Path objects)
        """
        return self._file_checksum_method

    @file_checksum_method.setter
    def file_checksum_method(self, file_checksum_method: FileChecksumMethod) -> None:
        """
        Set the method to use for calculating file checksums (for Path objects)

        :param file_checksum_method: The method to use for calculating file checksums (for Path objects)
        """
        self._file_checksum_method = file_checksum_method

    @property
    def progress_type(self) -> ProgressType:
        """
        :return: The currently used type of progress indication
        """
        return self._progress_type

    @progress_type.setter
    def progress_type(self, progress_type: ProgressType) -> None:
        """
        Set the type of progress indication to use during recipe evaluation

        :param progress_type: The type of progress indication to use
        """
        self._progress_type = progress_type


# Force creation of singleton
ALKYMI_CONFIG = AlkymiConfig.get()
