import os
import ast
import json
from pathlib import Path

def get_module_info(file_path: Path):
    """Parse a Python file and return its classes, functions and docstrings."""
    try:
        with file_path.open('r', encoding='utf-8', errors='replace') as f:
            source = f.read()
    except Exception:
        return None
    try:
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None
    module = {
        "path": str(file_path),
        "docstring": ast.get_docstring(tree),
        "classes": [],
        "functions": []
    }
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            cls = {
                "name": node.name,
                "docstring": ast.get_docstring(node),
                "methods": []
            }
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    cls["methods"].append({
                        "name": sub.name,
                        "docstring": ast.get_docstring(sub)
                    })
            module["classes"].append(cls)
        elif isinstance(node, ast.FunctionDef):
            module["functions"].append({
                "name": node.name,
                "docstring": ast.get_docstring(node)
            })
    return module

def walk_repo(root: Path):
    """Walk the repo and collect module info for all .py files."""
    modules = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith('.py'):
                file_path = Path(dirpath) / fn
                info = get_module_info(file_path)
                if info:
                    modules.append(info)
    return modules

def main():
    repo_root = Path(__file__).resolve().parents[1]  # assuming script in scripts/ folder
    data = walk_repo(repo_root)
    output_path = repo_root / 'codebase_map.json'
    with output_path.open('w', encoding='utf-8') as out:
        json.dump(data, out, indent=2)
    print(f"Generated codebase map at {output_path}")

if __name__ == '__main__':
    main()
