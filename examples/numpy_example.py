#!/usr/bin/env python
# coding=utf-8
import alkymi as alk
import numpy as np


@alk.recipe()
def get_arrays():
    print("Generating arrays")
    arrays = {i: np.random.random(10) for i in range(5)}
    return arrays


@alk.map_recipe(get_arrays)
def add_one(array):
    print("Adding 1")
    return array + 1


@alk.recipe(ingredients=[add_one])
def compute_mean(arrays):
    print("Computing mean")
    return np.mean(list(arrays.values()))


@alk.recipe(ingredients=[compute_mean], transient=True)
def print_mean(mean):
    print(mean)


def main():
    print_mean.brew()


if __name__ == "__main__":
    main()
