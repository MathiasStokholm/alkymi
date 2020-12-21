#!/usr/bin/env python
# coding=utf-8
import alkymi as alk
import numpy as np


@alk.recipe()
def get_arrays():
    print("Generating arrays")
    arrays = [np.zeros(10) for _ in range(5)]
    return arrays


@alk.foreach(get_arrays)
def add_one(array):
    print("Adding 1")
    return array + 1


@alk.recipe(ingredients=[add_one])
def compute_mean(arrays):
    print("Computing mean")
    return np.mean(arrays)


@alk.recipe(ingredients=[compute_mean], transient=True)
def print_mean(mean):
    print(mean)


def main():
    print_mean.brew()


if __name__ == "__main__":
    main()
