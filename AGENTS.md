# AGENTS.md

Guidance for AI coding agents (Claude Code, Codex, Cursor, Copilot, and others) working in
this repository.

## What this repo is

A single Python script, `generate.py`, converts an Omarchy theme's `colors.toml` into a
JetBrains IDE theme plugin (`.jar`). The jar contains a UI theme (`.theme.json`), an editor
color scheme (`.icls`) and a `plugin.xml`. There are no dependencies, packages or test
framework.

## Layout

| Path | Purpose |
|---|---|
| `generate.py` | The whole generator. Sections in order: CLI and palette loading → `mix()` helper → syntax roles `R` and `PROFILES` → `editor_colors` → `attributes` → `icls()` → `theme` (UI JSON) → `PLUGIN_XML` → write the build output |
| `build/<slug>/` | Generated output (git-ignored). Never edit or commit it. |
| `README.md`, `CONTRIBUTING.md` | User and contributor docs. Keep them in sync with CLI or behavior changes. |

## Commands

```bash
python3 generate.py <omarchy-theme-name>         # e.g. asia-neon, forest-night
python3 generate.py path/to/colors.toml --name "Display Name"

# Validate after any change:
for t in asia-neon forest-night; do python3 generate.py "$t"; done
python3 -c "import glob, xml.dom.minidom as m; [m.parse(f) for f in glob.glob('build/*/*.icls')]"
unzip -l build/forest-night/ForestNight.jar
```

Omarchy themes live in `~/.config/omarchy/themes/<slug>/colors.toml`. Upstream VS Code
themes (useful sources for profiles) may be installed under `~/.vscode/extensions/`.

## Conventions

- **Standard library only.** Requires Python 3.11 or newer (`tomllib`). Don't add dependencies.
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
- **Plugin ID** is `io.github.hbabb.omarchy-jetbrains.<slug>`. Changing it makes IDEs treat
  the plugin as a different one, so don't change it casually.
- **JetBrains ignores unknown keys.** A typo doesn't fail, it just does nothing. Check key
  names against the IntelliJ Platform theme docs.

## Boundaries

- Don't commit `build/` output or the IDE's `.idea/` folder.
- Don't change files under `~/.config/omarchy` or the user's IDE config folders unless
  you're asked to.
- Don't present generated themes as official Omarchy or JetBrains products: keep the vendor
  and author fields as they are.
- Follow the commit style in `CONTRIBUTING.md`: imperative subject, with a body that explains why.
