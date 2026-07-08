import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(ROOT))  # import the repo as a package too

if "folder_paths" not in sys.modules:
    fp = types.ModuleType("folder_paths")
    fp.get_output_directory = lambda: os.path.join(ROOT, "tests", "_out")
    fp.get_input_directory = lambda: os.path.join(ROOT, "tests", "_in")
    fp.get_save_image_path = None  # not used by core tests
    sys.modules["folder_paths"] = fp
