import json
from pathlib import Path

def load_codebase_map(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)

def format_module(module):
    lines = []
    lines.append(f"### Module: `{module['path']}`")
    if module.get('docstring'):
        lines.append(f"*Docstring*: {module['docstring']}")
    for cls in module.get('classes', []):
        lines.append(f"- Class `{cls['name']}`: {cls.get('docstring', 'No docstring')}")
        for method in cls.get('methods', []):
            lines.append(f"    - Method `{method['name']}`: {method.get('docstring', 'No docstring')}")
    for func in module.get('functions', []):
        lines.append(f"- Function `{func['name']}`: {func.get('docstring', 'No docstring')}")
    return "\n".join(lines)

def generate_prompt(map_path: Path, output_path: Path):
    data = load_codebase_map(map_path)
    prompt_lines = []
    prompt_lines.append("You are an expert QA engineer tasked with exhaustively testing a Python codebase.")
    prompt_lines.append("For each module, class, function, and method listed below, write a concise test case description that validates its core behavior. Use realistic inputs and assert expected outputs. Include edge‑case scenarios where applicable.")
    prompt_lines.append("Provide the test cases in a Markdown table with columns: `Module`, `Component`, `Test Description`, `Edge Cases`.")
    prompt_lines.append("\n---\n")
    for module in data:
        prompt_lines.append(format_module(module))
        prompt_lines.append("---")
    prompt = "\n".join(prompt_lines)
    output_path.write_text(prompt, encoding='utf-8')
    print(f"Generated test prompt at {output_path}")

if __name__ == '__main__':
    repo_root = Path(__file__).resolve().parents[1]
    map_file = repo_root / 'codebase_map.json'
    out_file = repo_root / 'test_prompt.md'
    generate_prompt(map_file, out_file)
