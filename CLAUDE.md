# CLAUDE.md

@AGENTS.md

All agent guidance for this repo (layout, commands, conventions, boundaries) is in
[AGENTS.md](AGENTS.md), which is imported above. These notes are for Claude Code only.

## Claude Code notes

- After changing `generate.py`, run the validation commands in AGENTS.md before you report
  the work as done.
- You can't see an IDE. When you change colors, tell the user which theme to rebuild and
  reinstall to check it, and don't claim a visual result you haven't seen.
- For Omarchy shell or plugin questions, load the `omarchy` skill if it's available, and
  read `$OMARCHY_PATH` (`/usr/share/omarchy`) for reference. Never edit it.
- Running the plugin's sync writes jars into the user's real IDE directories. Use a
  temporary `HOME` for experiments unless the user asks for a real install.
- To match an Omarchy theme to its upstream VS Code theme, read the `tokenColors` and
  `colors` from `~/.vscode/extensions/<publisher>.<name>-<version>/themes/*.json` and turn
  them into a `PROFILES` entry.
