import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="alkymi",
    version="0.0.1",
    author="Mathias Bøgh Stokholm",
    author_email="mathias.stokholm@gmail.com",
    description="Task management in Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MathiasStokholm/alkymi",
    packages=["alkymi"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.5',
)
