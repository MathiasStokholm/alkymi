import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="alkymi",
    description="alkymi - Pythonic task automation",
    version="0.0.1",
    license="MIT",
    author="Mathias Bøgh Stokholm",
    author_email="mathias.stokholm@gmail.com",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MathiasStokholm/alkymi",
    packages=["alkymi"],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "License :: OSI Approved :: MIT License",
        "Environment :: Console",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "Intended Audience :: System Administrators",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Scientific/Engineering",
    ],
    keywords="make build automation pipeline task",
    project_urls={
        "Source": "https://github.com/MathiasStokholm/alkymi/",
        "Tracker": "https://github.com/MathiasStokholm/alkymi/issues",
    },
    python_requires=">=3.5",
)
