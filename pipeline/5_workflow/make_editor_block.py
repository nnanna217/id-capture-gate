"""Generate the editor-safe variant of the verdict block: ONE function, `run`, with every import, constant and helper nested inside.

The Roboflow Workflow editor's code box is built around a single `run` function; verdict_block.py keeps module-level helpers and
constants (which the JSON-spec route accepts). This script rewrites the SAME source into the single-function form so it can be
pasted into the editor. Writes workflows/verdict_block_editor.py. Verify it with:
    VERDICT_SRC=workflows/verdict_block_editor.py python -I pipeline/5_workflow/test_verdict_block.py
Run from the repo root: python -I pipeline/5_workflow/make_editor_block.py
"""
import ast
from pathlib import Path

tree = ast.parse(Path("pipeline/5_workflow/verdict_block.py").read_text())
imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
consts = [n for n in tree.body if isinstance(n, ast.Assign)]
helpers = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name != "run"]
run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run")
doc = ast.Expr(ast.Constant("Capture-quality verdict. Generated from verdict_block.py by make_editor_block.py: do not edit by hand."))
run.body = [doc] + imports + consts + helpers + run.body
module = ast.Module(body=[run], type_ignores=[])
ast.fix_missing_locations(module)
out = Path("workflows/verdict_block_editor.py")
out.write_text(ast.unparse(module) + "\n")
print(f"wrote {out}: {len(out.read_text().splitlines())} lines, {len(out.read_text())} characters")
