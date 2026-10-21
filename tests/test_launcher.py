import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


REPO = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mise-flix test ' ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / "install"
        (self.install / "bin").mkdir(parents=True)
        (self.install / "lib").mkdir()
        self.launcher = self.install / "bin/flix"
        shutil.copyfile(REPO / "scripts/flix", self.launcher)
        self.launcher.chmod(0o755)
        (self.install / "lib/flix.jar").touch()
        self.project = self.root / "project with spaces"
        self.project.mkdir()
        self.capture = self.root / "capture.json"
        self.path_bin = self.root / "path-bin"
        self.path_bin.mkdir()
        for tool in ("sed", "dirname"):
            (self.path_bin / tool).symlink_to(shutil.which(tool))
        self.env = os.environ.copy()
        self.env.pop("JAVA_HOME", None)
        self.env.update(PATH=str(self.path_bin), FLIX_TEST_CAPTURE=str(self.capture))

    def java(self, name, version="21.0.2", version_status=0, status=0):
        home = self.root / name
        (home / "bin").mkdir(parents=True)
        java = home / "bin/java"
        java.write_text(
            f"#!{sys.executable}\n"
            + textwrap.dedent(
                f"""\
                import json, os, sys
                from pathlib import Path
                if sys.argv[1:] == ['-version']:
                    print('openjdk version "{version}"', file=sys.stderr)
                    sys.exit({version_status})
                Path(os.environ['FLIX_TEST_CAPTURE']).write_text(json.dumps({{
                    'java': {name!r}, 'args': sys.argv[1:], 'cwd': os.getcwd()
                }}))
                sys.exit({status})
                """
            )
        )
        java.chmod(0o755)
        return home

    def launch(self, *args):
        return subprocess.run(
            [str(self.launcher), *args],
            cwd=self.project,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def result(self):
        return json.loads(self.capture.read_text())

    def test_java_home_takes_priority_over_path(self):
        self.env["JAVA_HOME"] = str(self.java("SDKMAN JDK"))
        path_java = self.java("other JDK")
        (self.path_bin / "java").symlink_to(path_java / "bin/java")
        result = self.launch("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.result()["java"], "SDKMAN JDK")

    def test_path_java_when_java_home_is_unset(self):
        java = self.java("PATH JDK")
        (self.path_bin / "java").symlink_to(java / "bin/java")
        result = self.launch("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.result()["java"], "PATH JDK")

    def test_empty_java_home_uses_path(self):
        self.env["JAVA_HOME"] = ""
        java = self.java("PATH JDK")
        (self.path_bin / "java").symlink_to(java / "bin/java")
        self.assertEqual(self.launch().returncode, 0)

    def test_reselects_java_after_sdkman_switches_the_current_symlink(self):
        first = self.java("JDK 21", version="21.0.2")
        second = self.java("JDK 25", version="25.0.1")
        current = self.root / "current"
        current.symlink_to(first, target_is_directory=True)
        self.env["JAVA_HOME"] = str(current)
        self.assertEqual(self.launch().returncode, 0)
        self.assertEqual(self.result()["java"], "JDK 21")
        current.unlink()
        current.symlink_to(second, target_is_directory=True)
        self.assertEqual(self.launch().returncode, 0)
        self.assertEqual(self.result()["java"], "JDK 25")

    def test_preserves_arguments_cwd_and_jar_location(self):
        self.env["JAVA_HOME"] = str(self.java("SDKMAN JDK"))
        args = ["run", "a b", "", "$(touch unexpected)", "'quoted'", "--flag"]
        result = self.launch(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        captured = self.result()
        self.assertEqual(captured["args"][0], "-jar")
        self.assertEqual(
            Path(captured["args"][1]).resolve(), (self.install / "lib/flix.jar").resolve()
        )
        self.assertEqual(captured["args"][2:], args)
        self.assertEqual(captured["cwd"], str(self.project.resolve()))
        self.assertFalse((self.project / "unexpected").exists())

    def test_propagates_flix_exit_code(self):
        self.env["JAVA_HOME"] = str(self.java("SDKMAN JDK", status=42))
        self.assertEqual(self.launch("run").returncode, 42)

    def test_reports_missing_java(self):
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Java 21 or newer is required", result.stderr)

    def test_reports_invalid_java_home(self):
        self.env["JAVA_HOME"] = str(self.root / "missing JDK")
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("JAVA_HOME does not contain", result.stderr)

    def test_rejects_old_java(self):
        for version in ("1.8.0_412", "17.0.10", "20.0.2"):
            with self.subTest(version=version):
                self.env["JAVA_HOME"] = str(self.java("JDK " + version, version=version))
                result = self.launch()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Java 21 or newer is required", result.stderr)
                self.assertIn(version, result.stderr)
                self.assertFalse(self.capture.exists())

    def test_accepts_newer_and_early_access_java(self):
        for version in ("25.0.1", "26-ea"):
            with self.subTest(version=version):
                self.env["JAVA_HOME"] = str(self.java("JDK " + version, version=version))
                result = self.launch()
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_reports_a_java_startup_failure(self):
        self.env["JAVA_HOME"] = str(self.java("broken JDK", version_status=1))
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Could not start Java", result.stderr)

    def test_reports_an_unrecognized_version(self):
        self.env["JAVA_HOME"] = str(self.java("unknown JDK", version="unknown"))
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Could not determine the Java version", result.stderr)


if __name__ == "__main__":
    unittest.main()
