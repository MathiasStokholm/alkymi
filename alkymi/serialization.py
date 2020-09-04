from pathlib import Path
from typing import Optional, List, Any, Tuple, Iterable


def check_output(output: Any) -> bool:
    if output is None:
        return False
    if isinstance(output, Path):
        return output.exists()
    return True


def load_output(output: Any) -> Any:
    if isinstance(output, str):
        path = Path(output)
        return path if check_output(path) else None
    return output


def load_outputs(outputs: Optional[List[Any]]) -> Optional[Tuple[Any]]:
    if outputs is None:
        return None
    loaded_outputs = []
    for output in outputs:
        if isinstance(output, Iterable) and not isinstance(output, str):
            loaded_outputs.append([load_output(item) for item in output])
        else:
            loaded_outputs.append(load_output(output))
    return tuple(loaded_outputs)
