#!/usr/bin/env python3
import time
from typing import Tuple, List

import alkymi as alk
from alkymi import AlkymiConfig

AlkymiConfig.get().cache = False


@alk.recipe()
def generate_data() -> Tuple[int, int, int, int]:
    time.sleep(2)
    return 1, 2, 3, 4


@alk.recipe(ingredients=[generate_data])
def to_list(val1, val2, val3, val4) -> List[int]:
    time.sleep(2)
    return [val1, val2, val3, val4]


@alk.foreach(to_list)
def square(value):
    time.sleep(1)
    return value ** 2


def main():
    lab = alk.Lab("cli_test")
    lab.add_recipes(generate_data, to_list, square)
    lab.brew(square)


if __name__ == "__main__":
    main()
