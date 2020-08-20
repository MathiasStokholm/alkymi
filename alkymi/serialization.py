from pathlib import Path
from typing import Optional, List, Any


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


def load_outputs(outputs: Optional[List[Any]]) -> Optional[List[Any]]:
    if outputs is None:
        return None
    return [load_output(item) for item in outputs]
