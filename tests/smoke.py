"""Exercise the real plugin and JARs without changing the user's mise setup."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions", nargs=2, default=["0.79.0", "0.78.0"])
    args = parser.parse_args()
    mise = shutil.which("mise")
    if not mise:
        parser.error("mise must be available on PATH")

    with tempfile.TemporaryDirectory(prefix="mise-flix smoke ' ") as directory:
        root = Path(directory)
        project = root / "project"
        project.mkdir()
        env = os.environ.copy()
        env.update(
            MISE_CONFIG_DIR=str(root / "config"),
            MISE_GLOBAL_CONFIG_FILE=str(root / "config/config.toml"),
            MISE_SYSTEM_CONFIG_DIR=str(root / "system"),
            MISE_DATA_DIR=str(root / "data"),
            MISE_CACHE_DIR=str(root / "cache"),
            MISE_STATE_DIR=str(root / "state"),
            MISE_TRUSTED_CONFIG_PATHS=str(root),
            MISE_USE_VERSIONS_HOST="0",
            MISE_YES="1",
        )
        (root / "config").mkdir()
        (root / "config/config.toml").write_text("")

        def run(*command, java_available=True):
            command_env = env.copy()
            if not java_available:
                command_env["JAVA_HOME"] = str(root / "no-java-installed")
            print("+ mise " + " ".join(command), flush=True)
            result = subprocess.run(
                [mise, *command],
                cwd=project,
                env=command_env,
                text=True,
                capture_output=True,
                timeout=240,
            )
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            if command[0] == "ls-remote":
                print(f"Listed {len(result.stdout.splitlines())} Flix versions.", flush=True)
            elif result.stdout.strip():
                print(result.stdout.strip(), flush=True)
            return result.stdout

        run("plugins", "link", "flix", str(REPO), java_available=False)
        versions = run("ls-remote", "flix", java_available=False).splitlines()
        for version in args.versions:
            assert version in versions, f"Flix {version} missing from version list"
            run("install", "flix@" + version, java_available=False)

        assert not (root / "data/installs/java").exists(), "Java was installed by mise"

        # Select each installed version using a real project config.
        for version in [*args.versions, args.versions[0]]:
            (project / "mise.toml").write_text(f'[tools]\nflix = "{version}"\n')
            output = run("exec", "--", "flix", "--version")
            assert version in output, f"Expected Flix {version}, got: {output}"

        run("exec", "--", "flix", "init")
        (project / "src/Main.flix").write_text(
            'def main(): Unit \\ IO = println("mise-flix smoke test")\n'
        )
        output = run("exec", "--", "flix", "run")
        assert "mise-flix smoke test" in output
        run("exec", "--", "flix", "test")
        print("Smoke test passed without mise-managed Java.", flush=True)


if __name__ == "__main__":
    main()
