import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "nodes_prompt_list", Path(__file__).resolve().parents[1] / "nodes_prompt_list.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
PromptListFromFolder = _mod.PromptListFromFolder
resolve_folder = _mod.resolve_folder


class TestPromptListFromFolder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.node = PromptListFromFolder()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, content):
        p = self.folder / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_loads_prompts_in_name_order(self):
        self.write("b_second.txt", "second prompt\n")
        self.write("a_first.txt", "first prompt")
        self.write("ignored.md", "not a prompt")
        prompts, names, count, combined = self.node.load(
            str(self.folder), "name", False, True, 0, 0
        )
        self.assertEqual(prompts, ["first prompt", "second prompt"])
        self.assertEqual(names, ["a_first.txt", "b_second.txt"])
        self.assertEqual(count, 2)
        self.assertEqual(combined, "first prompt\nsecond prompt")

    def test_skip_empty(self):
        self.write("empty.txt", "   \n")
        self.write("real.txt", "hello")
        _, _, count, _ = self.node.load(str(self.folder), "name", False, True, 0, 0)
        self.assertEqual(count, 1)
        _, _, count, _ = self.node.load(str(self.folder), "name", False, False, 0, 0)
        self.assertEqual(count, 2)

    def test_max_prompts_cap(self):
        for i in range(5):
            self.write(f"{i}.txt", f"prompt {i}")
        prompts, names, count, combined = self.node.load(
            str(self.folder), "name", False, True, 0, 2
        )
        self.assertEqual(prompts, ["prompt 0", "prompt 1"])
        self.assertEqual(names, ["0.txt", "1.txt"])
        self.assertEqual(count, 2)
        self.assertEqual(combined, "prompt 0\nprompt 1")
        _, _, count, _ = self.node.load(str(self.folder), "name", False, True, 0, 0)
        self.assertEqual(count, 5)

    def test_cap_counts_prompts_not_files(self):
        self.write("empty.txt", "   \n")
        for i in range(3):
            self.write(f"{i}.txt", f"prompt {i}")
        prompts, _, count, _ = self.node.load(str(self.folder), "name", False, True, 0, 2)
        self.assertEqual(count, 2)
        self.assertEqual(prompts, ["prompt 0", "prompt 1"])

    def test_cap_applies_after_shuffle(self):
        for i in range(6):
            self.write(f"{i:02d}.txt", f"prompt {i}")
        capped_a = self.node.load(str(self.folder), "random", False, True, 123, 2)[0]
        capped_b = self.node.load(str(self.folder), "random", False, True, 123, 2)[0]
        self.assertEqual(capped_a, capped_b)
        self.assertEqual(len(capped_a), 2)
        full = self.node.load(str(self.folder), "random", False, True, 123, 0)[0]
        self.assertEqual(capped_a, full[:2])

    def test_recursive_and_seeded_shuffle(self):
        sub = self.folder / "sub"
        sub.mkdir()
        self.write("1.txt", "one")
        (sub / "2.txt").write_text("two", encoding="utf-8")
        _, _, count, _ = self.node.load(str(self.folder), "name", True, True, 0, 0)
        self.assertEqual(count, 2)
        shuffled_a = self.node.load(str(self.folder), "random", True, True, 42, 0)[0]
        shuffled_b = self.node.load(str(self.folder), "random", True, True, 42, 0)[0]
        self.assertEqual(shuffled_a, shuffled_b)

    def test_quoted_path(self):
        self.write("x.txt", "x")
        _, _, count, _ = self.node.load(f'"{self.folder}"', "name", False, True, 0, 0)
        self.assertEqual(count, 1)

    def test_missing_folder_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.node.load(str(self.folder / "nope"), "name", False, True, 0, 0)

    def test_resolve_folder_finds_relative_path(self):
        self.write("marker.txt", "m")
        old_cwd = os.getcwd()
        try:
            os.chdir(self.folder.parent)
            self.assertEqual(resolve_folder(self.folder.name), self.folder)
        finally:
            os.chdir(old_cwd)

    def test_empty_path_raises(self):
        with self.assertRaises(ValueError):
            self.node.load("   ", "name", False, True, 0, 0)


if __name__ == "__main__":
    unittest.main()
