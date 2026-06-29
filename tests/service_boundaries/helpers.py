import ast
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def declared_module_names(source: str) -> set[str]:
    module = ast.parse(source)
    declared_names = set()
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            declared_names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    declared_names.add(target.id)
    return declared_names


def declared_callable_names(source: str) -> set[str]:
    module = ast.parse(source)
    return {
        node.name
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
