from enum import Enum


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


# Force creation of singleton
ALKYMI_CONFIG = AlkymiConfig.get()
