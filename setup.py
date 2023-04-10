import setuptools

with open("README.md", encoding='utf-8') as f:
    long_description = f.read()

version = {}
with open('alkymi/version.py') as fp:
    exec(fp.read(), version)

setuptools.setup(
    name="alkymi",
    description="alkymi - Pythonic task automation",
    version=version['__version__'],
    license="MIT",
    author="Mathias Bøgh Stokholm",
    author_email="mathias.stokholm@gmail.com",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MathiasStokholm/alkymi",
    packages=["alkymi"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Environment :: Console",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "Intended Audience :: System Administrators",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Scientific/Engineering",
    ],
    keywords=["automation", "pipeline", "validation", "preprocessing", "make", "build", "task"],
    project_urls={
        "Source": "https://github.com/MathiasStokholm/alkymi/",
        "Tracker": "https://github.com/MathiasStokholm/alkymi/issues",
        "Documentation": "https://alkymi.readthedocs.io/en/latest/",
    },
    python_requires=">=3.7",
    install_requires=[
        "networkx>=2.0",
        "rich>=10.7"
    ],
    extras_require={
        "xxhash": ["xxhash>=2.0.0"]
    },
    package_data={
        "alkymi": ["py.typed"],
    },
)
