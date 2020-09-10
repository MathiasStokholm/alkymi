#!/usr/bin/env python
# coding=utf-8
from typing import List

from alkymi import Lab
from alkymi.recipes import glob_files
from pathlib import Path


lab = Lab('Import parsing')
input_files = lab.add_recipe(glob_files(Path('alkymi'), '*.py'))


@lab.recipe()
def create_build_dir() -> Path:
    build_dir = Path('build')
    build_dir.mkdir(exist_ok=True)
    return build_dir


@lab.recipe(ingredients=[input_files, create_build_dir])
def process_imports(files: List[Path], build_dir: Path) -> List[Path]:
    output_files = []
    for file in files:
        output_file = build_dir / str(file.name).replace('.py', '.txt')
        with file.open('r') as fin, output_file.open('w') as fout:
            imports = [line for line in fin.readlines() if 'import' in line]
            fout.write(''.join(imports))
        output_files.append(output_file)
    return output_files


@lab.recipe(ingredients=[process_imports], transient=True)
def print_results(imports: List[Path]) -> None:
    for import_file in imports:
        with import_file.open('r') as f:
            print(f.read())


def main():
    lab.open()


if __name__ == '__main__':
    main()
