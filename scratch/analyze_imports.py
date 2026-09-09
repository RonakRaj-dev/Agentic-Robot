import os
import ast
import sys
import importlib.metadata

std_libs = set(sys.builtin_module_names) | {
    "os", "sys", "re", "json", "time", "asyncio", "math", "typing", "collections",
    "functools", "datetime", "pathlib", "random", "logging", "uuid", "hashlib",
    "inspect", "copy", "traceback", "enum", "contextlib", "abc", "io", "base64",
    "struct", "threading", "tempfile", "shutil", "glob", "platform", "unittest"
}

imported_top_modules = set()

for root, dirs, files in os.walk("."):
    if any(ignored in root for ignored in [".git", ".venv", "venv", "__pycache__", "brain", "scratch"]):
        continue
    for file in files:
        if file.endswith(".py"):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    tree = ast.parse(f.read(), filename=filepath)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            top = alias.name.split(".")[0]
                            imported_top_modules.add(top)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.level == 0:
                            top = node.module.split(".")[0]
                            imported_top_modules.add(top)
            except Exception as e:
                print(f"Error parsing {filepath}: {e}")

local_modules = {
    "agents", "ai_teacher_robot", "api", "config", "core", "data", "database",
    "docs", "evaluations", "models", "pipelines", "repository", "schemas",
    "scripts", "services", "state", "supervisor", "utils", "vector_store"
}

third_party = sorted([m for m in imported_top_modules if m not in std_libs and m not in local_modules])

print("Detected Third Party Top-Level Imports:")
print(third_party)

print("\nPackage Mappings & Installed Versions:")
module_to_dist = {
    "agentscope": "agentscope",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "pydantic": "pydantic",
    "pymongo": "pymongo",
    "redis": "redis",
    "loguru": "loguru",
    "dotenv": "python-dotenv",
    "pypdf": "pypdf",
    "easyocr": "easyocr",
    "numpy": "numpy",
    "torch": "torch",
    "sentence_transformers": "sentence-transformers",
    "qdrant_client": "qdrant-client",
    "docx": "python-docx",
    "PIL": "pillow",
    "cv2": "opencv-python",
    "bs4": "beautifulsoup4",
    "requests": "requests",
    "httpx": "httpx",
    "pytest": "pytest",
    "opentelemetry": "opentelemetry-api",
    "prometheus_client": "prometheus-client",
    "websockets": "websockets"
}

for mod in third_party:
    dist_name = module_to_dist.get(mod, mod)
    try:
        ver = importlib.metadata.version(dist_name)
        print(f"✅ {mod} -> {dist_name} ({ver})")
    except importlib.metadata.PackageNotFoundError:
        try:
            ver = importlib.metadata.version(mod)
            print(f"✅ {mod} -> {mod} ({ver})")
        except importlib.metadata.PackageNotFoundError:
            print(f"❌ {mod} -> NOT INSTALLED (Dist name: {dist_name})")
