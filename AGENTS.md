# AGENTS.md

Guidance for AI coding agents (Claude Code, Codex, Cursor, Copilot, and others) working in
this repository.

## What this repo is

**Omarchy Theme Generator for JetBrains IDEs** has two parts:

1. `generate.py`, a dependency-free Python script that converts an Omarchy theme's
   `colors.toml` into a JetBrains IDE theme plugin (`.jar`). The jar contains a UI theme
   (`.theme.json`), an editor color scheme (`.icls`) and a `plugin.xml`.
2. An **Omarchy shell plugin** (`manifest.json` + `Service.qml`, id
   `io.github.hbabb.omarchy-jetbrains`, kind `service`). It watches the applied Omarchy theme
   and runs `generate.py --current --install`. It's installed with `omarchy plugin add` and
   listed on the Omarchy plugin marketplace.

There are no packages and no test framework.

## Layout

| Path | Purpose |
|---|---|
| `generate.py` | The generator. Sections in order: CLI and source resolution → palette loading, normalization and fallbacks (with `mix()`) → syntax roles `R` and `PROFILES` → `editor_colors` → `attributes` → `icls()` → `theme` (UI JSON) → `PLUGIN_XML` → build, install and summary |
| `manifest.json` | Omarchy plugin manifest (schemaVersion 1). The `id` is permanent. Bump `version` on releases. |
| `Service.qml` | Headless Quickshell service: watches `~/.local/state/omarchy/current/theme.name`, debounces, runs the generator, sends a notification, and has an `omarchy-jetbrains` IPC target (`ping`, `sync`, `current`) |
| `i18n/en.json` | Plugin UI strings (Omarchy `Commons.Translations` catalog). Add other languages as `<code>.json`. |
| `build/<slug>/` | Generated output (git-ignored). Never edit or commit it. `.omarchy-jetbrains-build.json` lists the files the generator owns there. |
| `README.md`, `CONTRIBUTING.md` | User and contributor docs. Keep them in sync with CLI or behavior changes. |

## Commands

```bash
python3 generate.py <omarchy-theme-name>         # e.g. asia-neon, forest-night
python3 generate.py path/to/colors.toml --name "Display Name"
python3 generate.py --current --install --json    # what the plugin runs

# Validate after any change:
for t in asia-neon forest-night; do python3 generate.py "$t"; done
python3 -c "import glob, xml.dom.minidom as m; [m.parse(f) for f in glob.glob('build/*/*.icls')]"
unzip -l build/forest-night/ForestNight.jar
omarchy plugin validate .

# Plugin, when installed or linked into ~/.config/omarchy/plugins/:
omarchy-shell omarchy-jetbrains sync
journalctl --user --since -5min | grep omarchy-jetbrains
```

To try `--install` without touching real IDE directories, run with a temporary `HOME` that
contains a copy of `~/.local/state/omarchy/current/`.

Omarchy themes live in `~/.config/omarchy/themes/<slug>/colors.toml`. Upstream VS Code
themes (useful sources for profiles) may be installed under `~/.vscode/extensions/`.

## Conventions

- **Standard library only.** Requires Python 3.11 or newer (`tomllib`). Don't add
  dependencies, and don't use syntax newer than 3.11 (such as reusing the same quote type
  inside an f-string).
- **`--json` output is the plugin's contract.** `Service.qml` parses the last stdout line
  (`ok`, `theme`, `name`, `installed`, `changed`, `refreshed`, or `error`). Keep that shape compatible.
- **Never delete what the generator didn't write.** Build output goes through the ownership
  marker (`.omarchy-jetbrains-build.json`): replace only the files it lists, and refuse a
  `<out>/<slug>` directory you don't own. Don't bring back `rmtree` or any other recursive
  delete.
- **`--name` is display data only.** File and resource names come from `FILE` (the
  sanitized slug). Escape the name with `escape()` or `quoteattr()` in XML, and put it in
  JSON with `json.dumps`. Never interpolate it raw.
- **The color scheme inside the jar must be `.xml`** (`themes/<File>.xml`, referenced by
  `editorScheme`). The IDE ignores `.icls` paths there and logs "refers to unknown color
  scheme". The standalone `.icls` in the build directory is only for manual import.
- **Jars must stay reproducible.** Use fixed `ZipInfo` timestamps, because `changed` relies on
  byte comparison.
- **Colors are 6-digit lowercase hex without `#`** inside the script. Add `#` only when
  writing `.theme.json` values (the `h()` helper).
- **Syntax colors go through roles.** Add a role to the `R` defaults (derived from the
  palette) and use `R["role"]` in `attributes`. Theme-specific values go in
  `PROFILES[slug]`. Never branch on `SLUG` inline.
- **Use the named colors in the UI JSON.** Under `ui`, refer to keys defined in
  `theme["colors"]` (`"bg"`, `"accent"`, `"focus"`, …) instead of repeating hex values.
  Computed blends use `h(mix(...))`.
- **Font types:** `"1"` bold, `"2"` italic, `"3"` bold-italic. **Effect types:** `"1"`
  underline, `"2"` wave, `"3"` strikeout, `"0"` bordered.
- **IDs are permanent.** The JetBrains plugin ID is
  `io.github.hbabb.omarchy-jetbrains.<slug>` and the Omarchy plugin ID is
  `io.github.hbabb.omarchy-jetbrains`. Changing either breaks existing installs and the
  marketplace listing.
- **Omarchy plugin rules:** Use `Style.duration()` for any animation, `Text.PlainText`
  for any dynamic text, and `strings.t()` for user-facing strings. Run commands with
  argument arrays (`Process.command`), never by building a shell string.
- **JetBrains ignores unknown keys.** A typo doesn't fail, it just does nothing. Check key
  names against the IntelliJ Platform theme docs.

## Boundaries

- Don't commit `build/` output or the IDE's `.idea/` folder.
- The plugin may only write `omarchy-theme-*.jar` files into JetBrains plugin directories and
  its own cache (`~/.cache/omarchy-jetbrains`). It must never edit IDE settings (`laf.xml`,
  `colors.scheme.xml`, …) or switch the selected theme, and must never request root privileges or use the
  network. The marketplace submission checklist requires this.
- Don't write the literal names of privilege-escalation commands anywhere in the repo, not
  even to say the plugin doesn't use them. The marketplace security scan flags them for
  manual review. Say "root privileges" instead.
- Don't add symlinks inside the repo. `omarchy plugin validate` rejects them.
- Don't change files under `~/.config/omarchy` or the user's IDE config folders unless
  you're asked to.
- Don't present generated themes as official Omarchy or JetBrains products: keep the vendor
  and author fields as they are.
- Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `chore:`, …) as described in
  `CONTRIBUTING.md`, with a body that explains why. Make changes on a branch and open a PR,
  because `main` is protected.
