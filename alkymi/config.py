from enum import Enum


class CacheType(Enum):
    Cache = 0
    Auto = 1
    NoCache = 2


class AlkymiConfig:
    __instance = None

    @staticmethod
    def get() -> 'AlkymiConfig':
        if AlkymiConfig.__instance is None:
            AlkymiConfig()
        return AlkymiConfig.__instance

    def __init__(self):
        if AlkymiConfig.__instance is not None:
            raise Exception("This class is a singleton!")

        # Set default values in config
        AlkymiConfig.__instance = self
        self._cache = True

    @property
    def cache(self) -> bool:
        return self._cache

    @cache.setter
    def cache(self, value):
        self._cache = value


# Force creation of singleton
ALKYMI_CONFIG = AlkymiConfig.get()
