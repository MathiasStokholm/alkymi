#!/usr/bin/env python
# coding=utf-8
import logging
from typing import List

from alkymi import Lab, log
from alkymi.recipes import glob_files
from pathlib import Path

# Set up logging
log.addHandler(logging.StreamHandler())

lab = Lab('Import parsing')
input_files = lab.add_recipe(glob_files(Path('alkymi'), '*.py'))


@lab.recipe()
def create_build_dir() -> Path:
    build_dir = Path('build')
    build_dir.mkdir(exist_ok=True)
    return build_dir


@lab.map_recipe(input_files, ingredients=[create_build_dir])
def process_imports(pyfile: Path, build_dir: Path) -> Path:
    output_file = build_dir / str(pyfile.name).replace('.py', '.txt')
    with pyfile.open('r') as fin, output_file.open('w') as fout:
        imports = [line for line in fin.readlines() if 'import' in line]
        fout.write(''.join(imports))
    return output_file


@lab.recipe(ingredients=[process_imports], transient=True)
def print_results(imports: List[Path]) -> None:
    for import_file in imports:
        with import_file.open('r') as f:
            print(f.read())


def main():
    lab.open()


if __name__ == '__main__':
    main()
