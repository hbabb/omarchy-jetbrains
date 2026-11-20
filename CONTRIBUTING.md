# Contributing

Thanks for helping. Most contributions are one of these:

- **A profile for another Omarchy theme**, so its syntax colors look right.
- **New JetBrains keys** (UI or editor attributes) that the generator doesn't style yet.
- **Bug fixes**: unreadable contrast, a key that has no effect, or a build or install problem.

## Development setup

You only need Python 3.11 or newer. There are no dependencies.

```bash
git clone git@github.com:hbabb/omarchy-jetbrains.git
cd omarchy-jetbrains
python3 generate.py asia-neon          # or any theme in ~/.config/omarchy/themes
```

Install the jar from `build/<slug>/` in a JetBrains IDE (Plugins → ⚙ → *Install Plugin from
Disk…*) and look at your changes. Restart the IDE after you replace a jar.

### Working on the Omarchy plugin

To run your checkout as the live plugin, link it into the plugins directory and enable it:

```bash
ln -s "$PWD" ~/.config/omarchy/plugins/io.github.hbabb.omarchy-jetbrains
omarchy-shell shell rescanPlugins
omarchy plugin enable io.github.hbabb.omarchy-jetbrains
```

Saving `Service.qml` reloads the plugin automatically. Use `omarchy-shell omarchy-jetbrains sync`
to force a rebuild, and follow the shell log with `journalctl --user -f | grep omarchy-jetbrains`.
Before pushing, check the manifest:

```bash
omarchy plugin validate .
```

## Before opening a pull request

1. **Regenerate every theme you touched** and check that each build succeeds:
   ```bash
   for t in asia-neon forest-night; do python3 generate.py "$t"; done
   ```
2. **If you changed the palette handling, build every theme:**
   ```bash
   for d in ~/.config/omarchy/themes/*/ /usr/share/omarchy/themes/*/; do
     python3 generate.py "$(basename "$d")" --out /tmp/omarchy-jetbrains-all --json >/dev/null || echo "FAIL $d"
   done
   ```
3. **Check the XML** in the generated scheme:
   ```bash
   python3 -c "import glob, xml.dom.minidom as m; [m.parse(f) for f in glob.glob('build/*/*.icls')]"
   ```
4. **Validate the plugin manifest:** `omarchy plugin validate .`
5. **Look at it in an IDE.** Include a screenshot of the editor and a tool window in the PR
   if you changed colors.
6. **Don't commit `build/`.** It's generated output and is git-ignored.
7. **Bump `version` in `manifest.json`** for any change users should receive.

## Guidelines

- **Keep it one dependency-free script.** Use only the standard library and Python 3.11
  syntax.
- **Keep the plugin's footprint small.** The service may only write
  `omarchy-theme-*.jar` files into JetBrains plugin directories and its own cache. It must
  never change IDE settings or which theme is selected, request root privileges or use the network, or
  interpolate untrusted values into shell commands. Pass arguments as an array.
- **Put user-facing plugin strings in `i18n/en.json`** and read them with
  `strings.t()` or `strings.tn()`.
- **Use roles, not raw colors.** Syntax colors in `attributes` should read from `R[...]`, so
  profiles can override them. To add a role, give it a palette default in `R` and use it.
- **Profiles override only what they need.** Name the source (for example, the upstream VS
  Code theme) in a comment above the profile.
- **Don't add theme-specific checks** (`if SLUG == ...`). Add a role and set it in the profile.
- **Keep contrast readable.** Body text and comments should stay legible on `background`.
  Check with a contrast checker if you're unsure.
- **Unknown keys are ignored** by JetBrains, so a key with no visible effect may just be
  misspelled. The [IntelliJ theme docs](https://plugins.jetbrains.com/docs/intellij/themes-customize.html)
  and the *UI Inspector* (Tools → Internal Actions, with `idea.is.internal=true`) help you
  find the right names.

## Commits and pull requests

- **This repo prefers [Conventional Commits](https://www.conventionalcommits.org/).** Write
  the subject as `<type>(<optional scope>): <short imperative summary>`, for example:
  - `feat(profiles): add Tokyo Night profile`
  - `fix(plugin): refresh legacy themes on install`
  - `docs: add restart instructions`

  Common types are `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`, `ci` and
  `chore`. Mark breaking changes with `!` (for example `feat!:`) or a `BREAKING CHANGE:`
  footer. Changing a plugin ID or the `--json` output counts as breaking.
- Explain *why* in the commit body when it isn't obvious.
- Keep each PR to one topic.
- Fill in what changed, which themes and IDE versions you tested, and screenshots for
  visual changes.

## Reporting issues

Open an issue with the Omarchy theme name, your IDE and version, what you expected, and a
screenshot. If a color is wrong, give the UI element or token and the IDE's key for it if
you know it.

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
