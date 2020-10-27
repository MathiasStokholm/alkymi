
import alkymi as alk
import numpy as np


@alk.recipe()
def get_array():
    print("Generating array")
    return np.array([1, 5, 10])


@alk.recipe(ingredients=[get_array], transient=True)
def print_array(arr):
    print(arr)


print_array.brew()
