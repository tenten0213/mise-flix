# mise-flix

A mise plugin for installing and managing the [Flix programming language](https://github.com/flix/flix).

Downloads the official `flix.jar` for each version and provides a `flix` command.
Supports macOS and Linux. Java 21 or newer is required to run Flix.

## Installation

Once this repository is published, replace `<owner>` with its GitHub owner:

```sh
mise plugins install flix https://github.com/<owner>/mise-flix
mise use flix@0.79.0
flix --version
```

Or declare the plugin in your project's `mise.toml`:

```toml
[plugins]
flix = "https://github.com/<owner>/mise-flix"

[tools]
flix = "0.79.0"
```

Run `mise install` to install the configured Flix version. For a reproducible
plugin installation, append `#<full-commit-sha>` to the plugin URL.

## Java and SDKMAN!

Java can be managed with SDKMAN!, mise, or another tool. The plugin neither
installs Java nor changes `JAVA_HOME`.

The `flix` launcher chooses Java **each time it runs**:

1. If `JAVA_HOME` is set, use `$JAVA_HOME/bin/java`.
2. Otherwise, use `java` from `PATH`.
3. Report an error if Java cannot start or is older than Java 21.

Select an installed JDK with `sdk use java <candidate>`, or use `sdk env` with
your project's `.sdkmanrc`. Then run:

```sh
mise exec -- flix --version
mise exec -- flix init
mise exec -- flix run
```

These commands use the Java selected in the current shell. The launcher does not
initialize SDKMAN! itself; initialize it before running Flix, including in CI.
`flix init` and `flix run` operate on the current working directory.

If you prefer mise to manage Java too, optionally add it to `[tools]`:

```toml
[tools]
java = "21"
flix = "0.79.0"
```

The plugin's `depends = { "java" }` declaration orders configured mise tools;
it does not require a mise-managed JDK or choose a Java version for you. Java
configured in another mise config, such as the global config, is still active.

## Versions and downloads

- `mise ls-remote flix` lists stable GitHub releases containing `flix.jar`.
- `mise use flix@latest` selects the latest available stable release.
- GitHub's release asset SHA-256 digest is passed to mise for verification when
  available. Older assets without a digest can still be installed, but their
  downloads are not verified against a publisher-provided checksum.
- If GitHub rate-limits requests, configure `MISE_GITHUB_TOKEN`. mise handles
  GitHub authentication; the plugin does not store credentials.

Windows and prereleases are not supported yet.

## Development

From this repository, link the local plugin:

```sh
mise plugins link flix "$PWD"
mise ls-remote flix
```

Developer checks require Lua 5.1 (or LuaJIT), Python 3.9+, and StyLua 2:

```sh
mise install
mise run check
```

Run the integration test with Java 21+ already configured:

```sh
mise run smoke
```

The smoke test uses temporary mise data, config, cache, and state directories.
It downloads two Flix versions, checks version switching without mise-managed
Java, and runs `flix init`, `flix run`, and `flix test` in a temporary project.
It needs network access to GitHub and Flix's dependency repositories.

See the [mise tool plugin guide](https://mise.jdx.dev/tool-plugin-development.html)
and the [Flix getting started guide](https://doc.flix.dev/getting-started.html).

## License

MIT. Flix itself is distributed by its upstream project under its own license.
