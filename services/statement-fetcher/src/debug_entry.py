import os
import runpy
import sys


def find_project_root(target_dir_name: str) -> str:
    """
    Recursively searches for the root directory of a project by looking for a directory
    """
    current_dir = os.path.abspath(os.path.dirname(__file__))

    while True:
        if os.path.basename(current_dir) == target_dir_name:
            return current_dir

        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError(f"{target_dir_name} not found in the directory tree.")

        current_dir = parent_dir


if __name__ != "__main__":
    raise RuntimeError("This script is for debugging only. Do not import it.")

project_root = find_project_root("statement-fetcher")
os.chdir(project_root)
sys.path.insert(0, project_root)

print("Current working directory:", os.getcwd())
print("Current __file__ path:", os.path.abspath(__file__))
print("Added to sys.path:", sys.path[0])
print("=============================")
print("Running the module...")

runpy.run_module("finchie_statement_fetcher", run_name="__main__")
