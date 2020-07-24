# coding=utf-8
from typing import List

from alkymi import Lab
from alkymi.recipes import glob_files
from pathlib import Path


lab = Lab()
input_files = lab.add_recipe(glob_files(Path('alkymi'), '*.py'))


@lab.recipe()
def create_build_dir() -> Path:
    build_dir = Path('build')
    build_dir.mkdir(exist_ok=True)
    return build_dir


@lab.repeat_recipe(input_files, ingredients=[create_build_dir])
def process_imports(file: Path, build_dir: Path) -> Path:
    output_file = build_dir / str(file.name).replace('.py', '.txt')
    with file.open('r') as fin, output_file.open('w') as fout:
        imports = [line for line in fin.readlines() if 'import' in line]
        fout.write(''.join(imports))
    return output_file


@lab.recipe(ingredients=[process_imports])
def print_results(imports: List[Path]) -> None:
    for import_file in imports:
        with import_file.open('r') as f:
            print(f.read())


def main():
    print(lab)
    lab.brew(print_results)


if __name__ == '__main__':
    main()
