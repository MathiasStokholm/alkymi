import alkymi as alk
from pathlib import Path


input_files = alk.glob_files(Path('alkymi'), '*.py')


@alk.recipe()
def create_build_dir():
    build_dir = Path('build')
    build_dir.mkdir(exist_ok=True)
    return build_dir


@alk.repeat_recipe(input_files, ingredients=[create_build_dir])
def process_imports(file: Path, build_dir: Path):
    output_file = build_dir / str(file.name).replace('.py', '.txt')
    with file.open('r') as fin, output_file.open('w') as fout:
        imports = [line for line in fin.readlines() if 'import' in line]
        fout.write(''.join(imports))
    return output_file


@alk.recipe(ingredients=[process_imports])
def print_results(imports):
    for import_file in imports:
        with import_file.open('r') as f:
            print(f.read())


def main():
    alk.brew(print_results)


if __name__ == '__main__':
    main()
