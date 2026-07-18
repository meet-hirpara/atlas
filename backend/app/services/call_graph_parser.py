"""Parse Python and JS/TS files to build call/import graphs."""

import ast
import os
import re
from typing import Dict, List, Set, Tuple

CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", "coverage", ".pytest_cache", ".mypy_cache",
}


def _node_id(file_path: str, name: str) -> str:
    return f"{file_path}::{name}"


def parse_python_file(file_path: str, content: str) -> Tuple[List[dict], List[dict]]:
    nodes: List[dict] = []
    edges: List[dict] = []
    seen_nodes: Set[str] = set()

    def add_node(name: str, node_type: str):
        nid = _node_id(file_path, name)
        if nid not in seen_nodes:
            seen_nodes.add(nid)
            nodes.append({"id": nid, "label": name, "type": node_type, "file": file_path})

    def add_edge(source: str, target: str, edge_type: str):
        edges.append({"source": source, "target": target, "type": edge_type})

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return nodes, edges

    module_id = _node_id(file_path, "<module>")
    seen_nodes.add(module_id)
    nodes.append({"id": module_id, "label": os.path.basename(file_path), "type": "module", "file": file_path})

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                add_node(alias.name, "import")
                add_edge(module_id, _node_id(file_path, alias.name), "imports")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            add_node(mod, "import")
            add_edge(module_id, _node_id(file_path, mod), "imports")
            for alias in node.names:
                full = f"{mod}.{alias.name}" if mod else alias.name
                add_node(full, "import")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add_node(node.name, "function")
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    callee = _resolve_call(child.func)
                    if callee:
                        add_node(callee, "function")
                        add_edge(_node_id(file_path, node.name), _node_id(file_path, callee), "calls")
        elif isinstance(node, ast.ClassDef):
            add_node(node.name, "class")

    return nodes, edges


def _resolve_call(func) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


_JS_FN = re.compile(
    r"(?:export\s+)?(?:async\s+)?function\s+(\w+)|"
    r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[\w]+)\s*=>|"
    r"(?:export\s+)?(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{",
    re.MULTILINE,
)
_JS_IMPORT = re.compile(
    r"import\s+(?:[\w*{}\s,]+\s+from\s+)?['\"]([^'\"]+)['\"]|"
    r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
)
_JS_CALL = re.compile(r"(?<![.\w])(\w+)\s*\(")


def parse_js_file(file_path: str, content: str) -> Tuple[List[dict], List[dict]]:
    nodes: List[dict] = []
    edges: List[dict] = []
    seen_nodes: Set[str] = set()

    def add_node(name: str, node_type: str):
        nid = _node_id(file_path, name)
        if nid not in seen_nodes:
            seen_nodes.add(nid)
            nodes.append({"id": nid, "label": name, "type": node_type, "file": file_path})

    module_id = _node_id(file_path, "<module>")
    seen_nodes.add(module_id)
    nodes.append({"id": module_id, "label": os.path.basename(file_path), "type": "module", "file": file_path})

    for m in _JS_IMPORT.finditer(content):
        imp = m.group(1) or m.group(2) or ""
        if imp:
            add_node(imp, "import")
            edges.append({"source": module_id, "target": _node_id(file_path, imp), "type": "imports"})

    fn_names: Set[str] = set()
    for m in _JS_FN.finditer(content):
        name = m.group(1) or m.group(2) or m.group(3)
        if name:
            fn_names.add(name)
            add_node(name, "function")

    for fn in fn_names:
        fn_id = _node_id(file_path, fn)
        fn_start = content.find(f"function {fn}")
        if fn_start == -1:
            fn_start = content.find(f"{fn}(")
        if fn_start == -1:
            continue
        brace = content.find("{", fn_start)
        if brace < 0:
            continue
        depth, end = 1, brace + 1
        while end < len(content) and depth > 0:
            if content[end] == "{":
                depth += 1
            elif content[end] == "}":
                depth -= 1
            end += 1
        body = content[brace:end]
        for cm in _JS_CALL.finditer(body):
            callee = cm.group(1)
            if callee in fn_names and callee != fn:
                add_edge(fn_id, _node_id(file_path, callee), "calls")

    return nodes, edges


def parse_file(file_path: str, content: str) -> Tuple[List[dict], List[dict]]:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".py":
        return parse_python_file(file_path, content)
    if ext in {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}:
        return parse_js_file(file_path, content)
    return [], []


def build_repo_graph(root_dir: str) -> dict:
    all_nodes: Dict[str, dict] = {}
    all_edges: List[dict] = []
    edge_keys: Set[str] = set()

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in CODE_EXTENSIONS:
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root_dir).replace("\\", "/")
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except OSError:
                continue
            nodes, edges = parse_file(rel, content)
            for n in nodes:
                all_nodes[n["id"]] = n
            for e in edges:
                key = f"{e['source']}|{e['target']}|{e['type']}"
                if key not in edge_keys:
                    edge_keys.add(key)
                    all_edges.append(e)

    return {"nodes": list(all_nodes.values()), "edges": all_edges}
