import logging
from typing import List
import time


import alkymi as alk

alk.config.AlkymiConfig.get().cache = False

# Print alkymi logging to stderr
alk.log.addHandler(logging.StreamHandler())
alk.log.setLevel(logging.DEBUG)


@alk.recipe()
def names() -> List[str]:
    time.sleep(2)
    return ["Marco", "Sebastian", "Mathias", "Job"]


@alk.foreach(names)
def print_names(name: str) -> None:
    alk.utils.call(["echo", name])
    time.sleep(0.5)


@alk.recipe()
def all(print_names: List[None]) -> None:
    time.sleep(0.5)
    print("All done!")


def main():
    lab = alk.Lab("CLI Example")
    lab.add_recipes(names, print_names, all)
    lab.open()


if __name__ == "__main__":
    main()
