# omarchy-jetbrains

Turn [Omarchy](https://omarchy.org) desktop themes into matching JetBrains IDE themes
(PyCharm, IntelliJ IDEA, WebStorm, GoLand, CLion, RustRover, DataGrip, PhpStorm, …).

One script reads an Omarchy theme's `colors.toml` and builds an installable plugin `.jar` that
contains:

- **A UI theme** (`.theme.json`) that styles the IDE's windows, tool windows, tabs, popups,
  buttons, inputs, progress bars, notifications, version control and debugger colors.
- **An editor color scheme** (`.icls`) with syntax colors (Python plus shared defaults, HTML/XML,
  CSS, JSON/YAML/TOML, Markdown, SQL, shell), console and ANSI colors, diff and VCS markers,
  search highlights, and error and warning effects.

The UI theme links to its color scheme, so picking the theme also switches the editor colors.

## Supported themes

Any Omarchy theme that has a `colors.toml` works. These two have been tuned:

| Omarchy theme | Syntax colors |
|---|---|
| `asia-neon` | Default palette mapping: magenta keywords, neon-green strings, blue functions, yellow classes, cyan decorators |
| `forest-night` | Profile copied from the *Forest Night – Ethereal* VS Code theme: amber keywords, teal strings, purple functions, rose types, sage constants |

## Requirements

- Python 3.11 or newer (uses the standard-library `tomllib`; nothing else to install)
- Omarchy themes in `~/.config/omarchy/themes/`, or a path to any `colors.toml`
- A JetBrains IDE, build 242 (2024.2) or newer

## Usage

```bash
# By Omarchy theme name (looked up in ~/.config/omarchy/themes/<name>/colors.toml)
python3 generate.py asia-neon
python3 generate.py forest-night

# Or point at any colors.toml, with an optional display name
python3 generate.py path/to/colors.toml --name "My Theme"
```

Output goes to `build/<theme-slug>/`:

```
build/forest-night/
├── ForestNight.jar          # installable plugin (UI theme + color scheme)
├── ForestNight.theme.json   # the UI theme, for inspection
└── Forest Night.icls        # color scheme only, importable on its own
```

## Installing in your IDE

**From disk (recommended):** open Settings → Plugins → ⚙ → *Install Plugin from Disk…*, pick
the `.jar`, and restart. Then choose the theme under Settings → Appearance & Behavior →
Appearance → *Theme*.

**By copying:** put the jar in the IDE's plugin folder and restart, for example:

```bash
cp build/forest-night/ForestNight.jar ~/.local/share/JetBrains/PyCharm2026.3/
```

**Color scheme only:** Settings → Editor → Color Scheme → ⚙ → *Import Scheme…* and pick the
`.icls`.

## How it works

1. The `colors.toml` palette (backgrounds, foregrounds, accent, selection, muted and the
   16 terminal colors) is loaded and blended to get hover, border and caret-row shades.
2. Syntax colors are set by **role** in the `R` dict (`keyword`, `string`, `func_decl`,
   `klass`, `decorator`, …), with defaults taken from the palette.
3. If the theme's folder name appears in `PROFILES`, that profile overrides any of those roles.
   Use a profile when a palette repeats colors (Forest Night's `blue` is the same as its
   `cyan`), or when you want to match an existing editor theme exactly.
4. The roles feed the `.icls` attributes and the named colors in `.theme.json`. Both files are
   packed into a jar with a `plugin.xml` that registers a `themeProvider`.

### Adding a profile for a new theme

```python
PROFILES = {
    "my-theme": dict(
        keyword="ff7a93", string="9ece6a", func_decl="7aa2f7",
        # ...only the roles you want to change
    ),
}
```

If the Omarchy theme comes from a VS Code theme, copy its `tokenColors` and use them as the
source for the profile (see the `forest-night` entry).

## Credits

- [Omarchy](https://omarchy.org) for the theme system and `colors.toml` format.
- [Asia Neon](https://github.com/sspaeti/omarchy-asia-neon-theme) by sspaeti.
- [Forest Night](https://github.com/ForrestKnight/omarchy-forest-night-theme) and its
  *Forest Night – Ethereal* VS Code theme by ForrestKnight.

This project is not affiliated with Omarchy, JetBrains or the theme authors.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
