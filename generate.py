#!/usr/bin/env python3
"""Omarchy Theme Generator for JetBrains IDEs.

Builds a JetBrains IDE theme plugin (UI theme + editor color scheme) from an Omarchy
theme's colors.toml.

Usage:
  python3 generate.py <omarchy-theme-name | path/to/colors.toml> [--name "Display Name"]
  python3 generate.py --current [--install] [--json]

  --current   use the theme Omarchy currently has applied
  --install   copy the jar into every JetBrains IDE config found under
              ~/.local/share/JetBrains/ (as omarchy-theme-<slug>.jar)
  --out DIR   build directory (default: ./build)
  --json      print a machine-readable summary instead of text

Outputs into <out>/<slug>/ : <Pascal>.jar (installable plugin), <Pascal>.theme.json and "<Name>.icls".

Syntax colors default to a generic mapping of the Omarchy palette; themes listed in
PROFILES override individual roles (e.g. to match an upstream VS Code theme).
"""
import argparse
import json
import re
import shutil
import sys
import tomllib
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = Path.home() / ".local/state/omarchy/current"
JETBRAINS_DATA = Path.home() / ".local/share/JetBrains"
ap = argparse.ArgumentParser(description="Omarchy Theme Generator for JetBrains IDEs")
ap.add_argument("theme", nargs="?", help="Omarchy theme name or path to a colors.toml")
ap.add_argument("--name", help="display name (default: derived from the theme name)")
ap.add_argument("--current", action="store_true", help="use the currently applied Omarchy theme")
ap.add_argument("--install", action="store_true", help="install the jar into every JetBrains IDE found")
ap.add_argument("--out", type=Path, default=HERE / "build", help="build directory")
ap.add_argument("--json", action="store_true", help="print a JSON summary")
args = ap.parse_args()


def die(msg):
    if args.json:
        print(json.dumps({"ok": False, "error": msg}))
    else:
        print(f"generate.py: {msg}", file=sys.stderr)
    sys.exit(1)


if args.current:
    SRC = STATE / "theme" / "colors.toml"
    try:
        SLUG = (STATE / "theme.name").read_text().strip()
    except OSError:
        die(f"no current Omarchy theme found at {STATE}")
elif args.theme:
    SRC = Path(args.theme)
    if not SRC.is_file():
        for base in (Path.home() / ".config/omarchy/themes", Path("/usr/share/omarchy/themes")):
            if (base / args.theme / "colors.toml").is_file():
                SRC = base / args.theme / "colors.toml"
                break
    SLUG = SRC.parent.name
else:
    ap.error("give a theme name, a colors.toml path, or --current")
if not SRC.is_file() and (SRC.parent / "alacritty.toml").is_file():
    SRC = SRC.parent / "alacritty.toml"  # older Omarchy themes have no colors.toml
if not SRC.is_file():
    die(f"colors.toml not found: {SRC}")
if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", SLUG):
    SLUG = re.sub(r"[^a-z0-9._-]+", "-", SLUG.lower()).strip("-.") or "theme"
NAME = args.name or SLUG.replace("-", " ").title()
PASCAL = NAME.replace(" ", "")
ID = f"io.github.hbabb.omarchy-jetbrains.{SLUG}"
VERSION = "1.0.0"

raw = tomllib.loads(SRC.read_text())
if SRC.name == "alacritty.toml":
    ac = raw.get("colors", {})
    raw = {**ac.get("primary", {}), "accent": ac.get("cursor", {}).get("cursor", "")}
    raw.update({k: v for k, v in ac.get("normal", {}).items() if k not in ("black", "white")})
    raw.update({f"bright_{k}": v for k, v in ac.get("bright", {}).items() if k not in ("black", "white")})
    raw["muted"] = ac.get("bright", {}).get("black", "")
    lum = sum(int(raw.get("background", "#000000").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    raw["mode"] = "light" if lum > 384 else "dark"
DARK = str(raw.get("mode", "dark")).lower() != "light"
c = {k: v.lstrip("#").lower() for k, v in raw.items() if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v)}


def mix(a, b, t):
    """Blend hex color a toward b by t (0..1)."""
    pa = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    pb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


# Older Omarchy themes only ship terminal colors (color0..color15); map them to names.
for i, name in enumerate(["", "red", "green", "yellow", "blue", "magenta", "cyan", "", "muted",
                          "bright_red", "bright_green", "bright_yellow", "bright_blue",
                          "bright_magenta", "bright_cyan", "bright_foreground"]):
    if name and f"color{i}" in c:
        c.setdefault(name, c[f"color{i}"])
REQUIRED = ["background", "foreground", "red", "green", "yellow", "blue", "magenta", "cyan"]
missing = [k for k in REQUIRED if k not in c]
if missing:
    die(f"{SRC} is missing colors: {', '.join(missing)}")
# Fill in anything optional from what the theme does define.
_bg, _fg, _shade = c["background"], c["foreground"], "000000"
c.setdefault("accent", c["blue"])
c.setdefault("dark_background", mix(_bg, _shade, 0.2 if DARK else 0.04))
c.setdefault("darker_background", mix(_bg, _shade, 0.35 if DARK else 0.09))
c.setdefault("lighter_background", mix(_bg, _fg, 0.1))
c.setdefault("dark_foreground", mix(_fg, _bg, 0.35))
c.setdefault("light_foreground", _fg)
c.setdefault("bright_foreground", _fg)
c.setdefault("muted", mix(_fg, _bg, 0.55))
c.setdefault("selection", mix(_bg, c["accent"], 0.3))
c.setdefault("orange", mix(c["red"], c["yellow"], 0.5))
c.setdefault("brown", mix(c["orange"], _bg, 0.4))
for base in ("red", "yellow", "green", "cyan", "blue", "magenta"):
    c.setdefault(f"bright_{base}", c[base])


bg, bg_dark, bg_darker, bg_light = c["background"], c["dark_background"], c["darker_background"], c["lighter_background"]
fg, fg_dim, accent, sel, muted = c["foreground"], c["dark_foreground"], c["accent"], c["selection"], c["muted"]
red, orange, yellow, green = c["red"], c["orange"], c["yellow"], c["green"]
cyan, blue, magenta, brown = c["cyan"], c["blue"], c["magenta"], c["brown"]
b_red, b_yellow, b_green = c["bright_red"], c["bright_yellow"], c["bright_green"]
b_cyan, b_blue, b_magenta = c["bright_cyan"], c["bright_blue"], c["bright_magenta"]

bg_hover = mix(bg, bg_light, 0.55)
border = mix(bg_light, muted, 0.25)
caret_row = mix(bg, bg_light, 0.45)

# --------------------------------------------------------------------------
# Syntax roles: defaults derived from the Omarchy palette, overridable per theme
# --------------------------------------------------------------------------
R = dict(
    keyword=magenta, string=green, escape=cyan, number=orange, constant=orange,
    comment=muted, doc=mix(muted, fg_dim, 0.5), doc_tag=accent, py_doc=b_green,
    func_decl=b_blue, func_call=blue, builtin=cyan, builtin_font=None,
    klass=yellow, type_hint=b_yellow, param=b_red, self=b_magenta, field=b_red,
    static_field=orange, global_var=b_magenta, kwarg=orange, decorator=cyan,
    operator=b_cyan, punct=fg_dim, braces=fg_dim, fstring=green, regex=b_cyan,
    tag=red, attr=yellow, attr_value=green, prop_key=b_blue, md_header=accent,
    md_link=cyan, caret=accent, line_active=accent, button=accent, focus=accent,
    link=cyan, css_prop=b_blue, css_value=green, yaml_key=b_blue, md_h2=magenta, md_h3=b_blue,
    sql_kw_font=None, button_fg=bg_darker, progress=accent, progress_end=magenta,
)
PROFILES = {
    # Mirrors "Forest Night - Ethereal" VS Code theme (forrest-knight.forest-night-theme)
    "forest-night": dict(
        keyword="f39c12", string="4ecdc4", escape="f39c12", number="8fbc8f", constant="8fbc8f",
        comment="4a5568", doc="6b7280", doc_tag="4ecdc4", py_doc="4ecdc4",
        func_decl="9b59b6", func_call="9b59b6", builtin="9b59b6", builtin_font="1",
        klass="c78a7a", type_hint="c78a7a", param="c9d1d9", self="c78a7a", field="66d9ef",
        static_field="8fbc8f", global_var="c9d1d9", kwarg="c9d1d9", decorator="f39c12",
        operator="c9d1d9", punct="8fa1b3", braces="c9d1d9", fstring="66d9ef", regex="c78a7a",
        tag="f39c12", attr="4ecdc4", attr_value="66d9ef", prop_key="66d9ef", md_header="f39c12",
        md_link="66d9ef", caret="6b8fa3", line_active="6b8fa3", button="9b59b6", focus="6b8fa3",
        link="66d9ef", css_prop="4ecdc4", css_value="8fbc8f", yaml_key="4ecdc4",
        md_h2="f39c12", md_h3="f39c12", sql_kw_font="1", button_fg="ffffff",
        progress="9b59b6", progress_end="8fbc8f",
    ),
}
R.update(PROFILES.get(SLUG, {}))

# --------------------------------------------------------------------------
# Editor color scheme (.icls)
# --------------------------------------------------------------------------
editor_colors = {
    "CARET_COLOR": R["caret"],
    "CARET_ROW_COLOR": caret_row,
    "CONSOLE_BACKGROUND_KEY": bg_dark,
    "DOCUMENTATION_COLOR": bg_dark,
    "GUTTER_BACKGROUND": bg,
    "INDENT_GUIDE": bg_light,
    "SELECTED_INDENT_GUIDE": muted,
    "LINE_NUMBERS_COLOR": mix(muted, bg, 0.25),
    "LINE_NUMBER_ON_CARET_ROW_COLOR": R["line_active"],
    "METHOD_SEPARATORS_COLOR": bg_light,
    "RIGHT_MARGIN_COLOR": bg_light,
    "VISUAL_INDENT_GUIDE": bg_light,
    "SELECTION_BACKGROUND": sel,
    "SELECTION_FOREGROUND": "",
    "TEARLINE_COLOR": bg_light,
    "SELECTED_TEARLINE_COLOR": muted,
    "WHITESPACES": mix(bg_light, muted, 0.3),
    "SOFT_WRAP_SIGN_COLOR": muted,
    "LOOKUP_COLOR": bg_dark,
    "INFORMATION_HINT": bg_light,
    "QUESTION_HINT": bg_light,
    "ERROR_HINT": mix(bg, red, 0.25),
    "NOTIFICATION_BACKGROUND": bg_light,
    "READONLY_BACKGROUND": bg_dark,
    "READONLY_FRAGMENT_BACKGROUND": bg_dark,
    "FOLDED_TEXT_BORDER_COLOR": muted,
    "ANNOTATIONS_COLOR": muted,
    "ADDED_LINES_COLOR": green,
    "MODIFIED_LINES_COLOR": blue,
    "DELETED_LINES_COLOR": red,
    "WHITESPACES_MODIFIED_LINES_COLOR": mix(blue, bg, 0.4),
    "IGNORED_ADDED_LINES_BORDER_COLOR": mix(green, bg, 0.4),
    "IGNORED_MODIFIED_LINES_BORDER_COLOR": mix(blue, bg, 0.4),
    "IGNORED_DELETED_LINES_BORDER_COLOR": mix(red, bg, 0.4),
    "DIFF_SEPARATORS_BACKGROUND": bg_light,
    "BREADCRUMBS_CURRENT_FG": fg,
    "BREADCRUMBS_DEFAULT_FG": fg_dim,
    "BREADCRUMBS_HOVERED_FG": accent,
    "BREADCRUMBS_HOVERED_BG": bg_light,
    "TAB_UNDERLINE": accent,
    "TAB_UNDERLINE_INACTIVE": muted,
    "ScrollBar.Mac.thumbColor": mix(bg_light, muted, 0.4),
    "ScrollBar.Mac.hoverThumbColor": muted,
    "ScrollBar.thumbColor": mix(bg_light, muted, 0.4),
    "ScrollBar.hoverThumbColor": muted,
    "FILESTATUS_ADDED": green,
    "FILESTATUS_DELETED": red,
    "FILESTATUS_MODIFIED": b_blue,
    "FILESTATUS_MERGED": magenta,
    "FILESTATUS_UNKNOWN": orange,
    "FILESTATUS_IDEA_FILESTATUS_IGNORED": muted,
    "FILESTATUS_NOT_CHANGED_IMMEDIATE": b_blue,
    "FILESTATUS_NOT_CHANGED_RECURSIVE": b_blue,
    "FILESTATUS_SWITCHED": yellow,
    "FILESTATUS_IDEA_FILESTATUS_MERGED_WITH_CONFLICTS": red,
    "FILESTATUS_IDEA_FILESTATUS_DELETED_FROM_FILE_SYSTEM": brown,
    "VCS_ANNOTATIONS_COLOR_1": mix(accent, bg, 0.55),
    "VCS_ANNOTATIONS_COLOR_2": mix(accent, bg, 0.65),
    "VCS_ANNOTATIONS_COLOR_3": mix(accent, bg, 0.75),
    "VCS_ANNOTATIONS_COLOR_4": mix(accent, bg, 0.82),
    "VCS_ANNOTATIONS_COLOR_5": mix(accent, bg, 0.88),
}


def A(fgc=None, bgc=None, font=None, effect=None, effect_type=None, stripe=None):
    return {"FOREGROUND": fgc, "BACKGROUND": bgc, "FONT_TYPE": font,
            "EFFECT_COLOR": effect, "EFFECT_TYPE": effect_type, "ERROR_STRIPE_COLOR": stripe}


BOLD, ITALIC, BOLD_ITALIC = "1", "2", "3"
# EFFECT_TYPE: 1=underline 2=wave 3=strikeout 0=bordered 5=bold dotted
attributes = {
    "TEXT": A(fg, bg),
    "DEFAULT_IDENTIFIER": A(fg),
    "DEFAULT_KEYWORD": A(R["keyword"]),
    "DEFAULT_STRING": A(R["string"]),
    "DEFAULT_VALID_STRING_ESCAPE": A(R["escape"]),
    "DEFAULT_INVALID_STRING_ESCAPE": A(red, effect=red, effect_type="2"),
    "DEFAULT_NUMBER": A(R["number"]),
    "DEFAULT_CONSTANT": A(R["constant"]),
    "DEFAULT_LINE_COMMENT": A(R["comment"], font=ITALIC),
    "DEFAULT_BLOCK_COMMENT": A(R["comment"], font=ITALIC),
    "DEFAULT_DOC_COMMENT": A(R["doc"], font=ITALIC),
    "DEFAULT_DOC_COMMENT_TAG": A(R["doc_tag"], font=ITALIC),
    "DEFAULT_DOC_COMMENT_TAG_VALUE": A(R["field"], font=ITALIC),
    "DEFAULT_DOC_MARKUP": A(R["doc_tag"]),
    "DEFAULT_OPERATION_SIGN": A(R["operator"]),
    "DEFAULT_BRACES": A(R["braces"]),
    "DEFAULT_BRACKETS": A(R["braces"]),
    "DEFAULT_PARENTHS": A(R["braces"]),
    "DEFAULT_COMMA": A(R["punct"]),
    "DEFAULT_DOT": A(R["punct"]),
    "DEFAULT_SEMICOLON": A(R["punct"]),
    "DEFAULT_FUNCTION_DECLARATION": A(R["func_decl"]),
    "DEFAULT_FUNCTION_CALL": A(R["func_call"]),
    "DEFAULT_INSTANCE_METHOD": A(R["func_call"]),
    "DEFAULT_STATIC_METHOD": A(R["func_call"], font=ITALIC),
    "DEFAULT_CLASS_NAME": A(R["klass"]),
    "DEFAULT_CLASS_REFERENCE": A(R["klass"]),
    "DEFAULT_INTERFACE_NAME": A(R["type_hint"]),
    "DEFAULT_PARAMETER": A(R["param"]),
    "DEFAULT_LOCAL_VARIABLE": A(fg),
    "DEFAULT_REASSIGNED_LOCAL_VARIABLE": A(fg, effect=muted, effect_type="1"),
    "DEFAULT_GLOBAL_VARIABLE": A(R["global_var"]),
    "DEFAULT_INSTANCE_FIELD": A(R["field"]),
    "DEFAULT_STATIC_FIELD": A(R["static_field"], font=ITALIC),
    "DEFAULT_PREDEFINED_SYMBOL": A(R["builtin"]),
    "DEFAULT_METADATA": A(R["decorator"]),
    "DEFAULT_LABEL": A(R["klass"]),
    "DEFAULT_TAG": A(R["tag"]),
    "DEFAULT_ATTRIBUTE": A(R["attr"]),
    "DEFAULT_ENTITY": A(R["constant"]),
    "DEFAULT_TEMPLATE_LANGUAGE_COLOR": A(fg),
    "DEFAULT_HIGHLIGHTED_REFERENCE": A(bgc=mix(bg, accent, 0.18)),

    # Python
    "PY.KEYWORD": A(R["keyword"]),
    "PY.KEYWORD_ARGUMENT": A(R["kwarg"]),
    "PY.BUILTIN_NAME": A(R["builtin"], font=R["builtin_font"]),
    "PY.PREDEFINED_DEFINITION": A(R["builtin"], font=R["builtin_font"]),
    "PY.PREDEFINED_USAGE": A(R["builtin"], font=R["builtin_font"]),
    "PY.SELF_PARAMETER": A(R["self"], font=ITALIC),
    "PY.PARAMETER": A(R["param"]),
    "PY.DECORATOR": A(R["decorator"]),
    "PY.FUNC_DEFINITION": A(R["func_decl"]),
    "PY.NESTED_FUNC_DEFINITION": A(R["func_decl"]),
    "PY.FUNCTION_CALL": A(R["func_call"]),
    "PY.METHOD_CALL": A(R["func_call"]),
    "PY.CLASS_DEFINITION": A(R["klass"], font=BOLD),
    "PY.STRING.U": A(R["string"]),
    "PY.STRING.B": A(R["string"]),
    "PY.FSTRING": A(R["fstring"]),
    "PY.DOC_COMMENT": A(R["py_doc"], font=ITALIC),
    "PY.DOC_COMMENT_TAG": A(R["doc_tag"], font=ITALIC),
    "PY.NUMBER": A(R["number"]),
    "PY.LINE_COMMENT": A(R["comment"], font=ITALIC),
    "PY.OPERATION_SIGN": A(R["operator"]),
    "PY.ANNOTATION": A(R["type_hint"]),
    "PY.TYPE_HINT": A(R["type_hint"]),
    "PY.VALID_STRING_ESCAPE": A(R["escape"]),
    "PY.INVALID_STRING_ESCAPE": A(red, effect=red, effect_type="2"),
    "PY.BRACES": A(R["braces"]),
    "PY.BRACKETS": A(R["braces"]),
    "PY.PARENTHS": A(R["braces"]),
    "PY.DOT": A(R["punct"]),
    "PY.COMMA": A(R["punct"]),
    "REGEXP.CHAR_CLASS": A(R["regex"]),

    # Markup / web / data
    "HTML_TAG_NAME": A(R["tag"]),
    "HTML_ATTRIBUTE_NAME": A(R["attr"]),
    "HTML_ATTRIBUTE_VALUE": A(R["attr_value"]),
    "XML_TAG_NAME": A(R["tag"]),
    "XML_ATTRIBUTE_NAME": A(R["attr"]),
    "CSS.PROPERTY_NAME": A(R["css_prop"]),
    "CSS.PROPERTY_VALUE": A(R["css_value"]),
    "CSS.TAG_NAME": A(R["tag"]),
    "CSS.IDENT": A(R["klass"]),
    "JSON.PROPERTY_KEY": A(R["prop_key"]),
    "YAML_SCALAR_KEY": A(R["yaml_key"]),
    "TOML_KEY": A(R["prop_key"]),
    "MARKDOWN_HEADER_LEVEL_1": A(R["md_header"], font=BOLD),
    "MARKDOWN_HEADER_LEVEL_2": A(R["md_h2"], font=BOLD),
    "MARKDOWN_HEADER_LEVEL_3": A(R["md_h3"], font=BOLD),
    "MARKDOWN_CODE_SPAN": A(R["string"]),
    "MARKDOWN_LINK_TEXT": A(R["md_link"], effect=R["md_link"], effect_type="1"),
    "SQL_KEYWORD": A(R["keyword"], font=R["sql_kw_font"]),
    "SQL_STRING": A(R["string"]),
    "SQL_NUMBER": A(R["number"]),
    "SQL_COLUMN": A(R["field"]),
    "SQL_TABLE": A(R["klass"]),
    "BASH.EXTERNAL_COMMAND": A(R["func_call"]),
    "BASH.VAR_USE": A(R["param"]),

    # Editor state
    "CARET_ROW": A(bgc=caret_row),
    "IDENTIFIER_UNDER_CARET_ATTRIBUTES": A(bgc=mix(bg, accent, 0.22), stripe=accent),
    "WRITE_IDENTIFIER_UNDER_CARET_ATTRIBUTES": A(bgc=mix(bg, magenta, 0.25), stripe=magenta),
    "SEARCH_RESULT_ATTRIBUTES": A(bgc=mix(bg, cyan, 0.28), stripe=cyan),
    "WRITE_SEARCH_RESULT_ATTRIBUTES": A(bgc=mix(bg, magenta, 0.28), stripe=magenta),
    "TEXT_SEARCH_RESULT_ATTRIBUTES": A(bg, yellow, stripe=yellow),
    "MATCHED_BRACE_ATTRIBUTES": A(b_cyan, mix(bg, cyan, 0.25), BOLD),
    "UNMATCHED_BRACE_ATTRIBUTES": A(red, mix(bg, red, 0.25)),
    "TODO_DEFAULT_ATTRIBUTES": A(yellow, font=BOLD_ITALIC, stripe=yellow),
    "HYPERLINK_ATTRIBUTES": A(cyan, effect=cyan, effect_type="1"),
    "FOLLOWED_HYPERLINK_ATTRIBUTES": A(magenta, effect=magenta, effect_type="1"),
    "FOLDED_TEXT_ATTRIBUTES": A(fg_dim, bg_light),
    "LIVE_TEMPLATE_ATTRIBUTES": A(effect=accent, effect_type="0"),
    "BREAKPOINT_ATTRIBUTES": A(bgc=mix(bg, red, 0.2), stripe=red),
    "EXECUTIONPOINT_ATTRIBUTES": A(bgc=mix(bg, blue, 0.3)),
    "INLINE_PARAMETER_HINT": A(fg_dim, bg_light),
    "INLINE_PARAMETER_HINT_CURRENT": A(fg, sel),
    "INLAY_DEFAULT": A(fg_dim, bg_light),
    "INLAY_TEXT_WITHOUT_BACKGROUND": A(muted),
    "ERRORS_ATTRIBUTES": A(effect=red, effect_type="2", stripe=red),
    "WARNING_ATTRIBUTES": A(effect=orange, effect_type="2", stripe=orange),
    "WEAK_WARNING_ATTRIBUTES": A(effect=yellow, effect_type="2", stripe=yellow),
    "INFO_ATTRIBUTES": A(effect=cyan, effect_type="2"),
    "WRONG_REFERENCES_ATTRIBUTES": A(red),
    "NOT_USED_ELEMENT_ATTRIBUTES": A(muted),
    "DEPRECATED_ATTRIBUTES": A(effect=fg_dim, effect_type="3"),
    "MARKED_FOR_REMOVAL_ATTRIBUTES": A(effect=red, effect_type="3"),
    "TYPO": A(effect=muted, effect_type="2"),
    "BAD_CHARACTER": A(red, mix(bg, red, 0.2)),
    "CTRL_CLICKABLE": A(cyan, effect=cyan, effect_type="1"),
    "INJECTED_LANGUAGE_FRAGMENT": A(bgc=bg_dark),
    "DIFF_INSERTED": A(bgc=mix(bg, green, 0.16), stripe=green),
    "DIFF_MODIFIED": A(bgc=mix(bg, blue, 0.18), stripe=blue),
    "DIFF_DELETED": A(bgc=mix(bg, red, 0.16), stripe=red),
    "DIFF_CONFLICT": A(bgc=mix(bg, orange, 0.18), stripe=orange),

    # Console & ANSI
    "CONSOLE_NORMAL_OUTPUT": A(fg),
    "CONSOLE_SYSTEM_OUTPUT": A(fg_dim),
    "CONSOLE_ERROR_OUTPUT": A(red),
    "CONSOLE_USER_INPUT": A(green, font=ITALIC),
    "LOG_ERROR_OUTPUT": A(red),
    "LOG_WARNING_OUTPUT": A(orange),
    "LOG_INFO_OUTPUT": A(cyan),
    "LOG_DEBUG_OUTPUT": A(muted),
    "LOG_VERBOSE_OUTPUT": A(fg_dim),
    "CONSOLE_BLACK_OUTPUT": A(bg_light),
    "CONSOLE_RED_OUTPUT": A(red),
    "CONSOLE_GREEN_OUTPUT": A(green),
    "CONSOLE_YELLOW_OUTPUT": A(yellow),
    "CONSOLE_BLUE_OUTPUT": A(blue),
    "CONSOLE_MAGENTA_OUTPUT": A(magenta),
    "CONSOLE_CYAN_OUTPUT": A(cyan),
    "CONSOLE_GRAY_OUTPUT": A(fg_dim),
    "CONSOLE_DARKGRAY_OUTPUT": A(muted),
    "CONSOLE_RED_BRIGHT_OUTPUT": A(b_red),
    "CONSOLE_GREEN_BRIGHT_OUTPUT": A(b_green),
    "CONSOLE_YELLOW_BRIGHT_OUTPUT": A(b_yellow),
    "CONSOLE_BLUE_BRIGHT_OUTPUT": A(b_blue),
    "CONSOLE_MAGENTA_BRIGHT_OUTPUT": A(b_magenta),
    "CONSOLE_CYAN_BRIGHT_OUTPUT": A(b_cyan),
    "CONSOLE_WHITE_OUTPUT": A(c["bright_foreground"]),
}


def icls():
    parent = "Darcula" if DARK else "Default"
    out = [f'<scheme name="{NAME}" version="142" parent_scheme="{parent}">',
           '  <metaInfo>', f'    <property name="created">2026-11-20</property>',
           f'    <property name="originalScheme">{NAME}</property>', '  </metaInfo>', '  <colors>']
    for k, v in editor_colors.items():
        if v:
            out.append(f'    <option name="{k}" value="{v}" />')
    out += ['  </colors>', '  <attributes>']
    for k, a in attributes.items():
        out.append(f'    <option name="{k}">')
        out.append('      <value>')
        for prop, val in a.items():
            if val:
                out.append(f'        <option name="{prop}" value="{val}" />')
        out += ['      </value>', '    </option>']
    out += ['  </attributes>', '</scheme>', '']
    return "\n".join(out)


# --------------------------------------------------------------------------
# UI theme (.theme.json)
# --------------------------------------------------------------------------
h = lambda x: "#" + x
theme = {
    "name": NAME,
    "dark": DARK,
    "author": "hbabb",
    "editorScheme": f"/themes/{PASCAL}.icls",
    "colors": {
        "bg": h(bg), "bgDark": h(bg_dark), "bgDarker": h(bg_darker), "bgLight": h(bg_light),
        "hover": h(bg_hover), "border": h(border), "fg": h(fg), "fgDim": h(fg_dim),
        "accent": h(accent), "sel": h(sel), "muted": h(muted),
        "focus": h(R["focus"]), "button": h(R["button"]), "buttonFg": h(R["button_fg"]), "caret": h(R["caret"]),
        "link": h(R["link"]), "progress": h(R["progress"]), "progressEnd": h(R["progress_end"]),
        "red": h(red), "orange": h(orange), "yellow": h(yellow), "green": h(green),
        "cyan": h(cyan), "blue": h(blue), "magenta": h(magenta),
    },
    "ui": {
        "*": {
            "background": "bg",
            "foreground": "fg",
            "infoForeground": "fgDim",
            "disabledForeground": "muted",
            "disabledBackground": "bg",
            "inactiveBackground": "bg",
            "inactiveForeground": "fgDim",
            "selectionBackground": "sel",
            "selectionForeground": "fg",
            "selectionInactiveBackground": h(mix(sel, bg, 0.4)),
            "selectionBackgroundInactive": h(mix(sel, bg, 0.4)),
            "selectionInactiveForeground": "fg",
            "hoverBackground": "hover",
            "borderColor": "border",
            "separatorColor": "border",
            "focusColor": "focus",
            "focusedBorderColor": "focus",
            "lightSelectionBackground": "hover",
            "acceleratorForeground": "accent",
            "acceleratorSelectionForeground": "fg",
            "caretForeground": "caret",
            "underlinedTabBackground": "bgLight",
            "underlineColor": "accent",
            "underlinedTabForeground": "fg",
            "inactiveUnderlineColor": "muted",
            "arc": 8,
        },
        "MainWindow.background": "bgDark",
        "MainToolbar.background": "bgDark",
        "MainToolbar.inactiveBackground": "bgDark",
        "MainToolbar.Dropdown.hoverBackground": "hover",
        "MainToolbar.Icon.hoverBackground": "hover",
        "MainToolbar.Button.hoverBackground": "hover",
        "TitlePane.background": "bgDark",
        "TitlePane.inactiveBackground": "bgDark",
        "StatusBar.background": "bgDark",
        "StatusBar.borderColor": "border",
        "StatusBar.Widget.hoverBackground": "hover",
        "StatusBar.Breadcrumbs.foreground": "fgDim",
        "StatusBar.Breadcrumbs.hoverBackground": "hover",
        "StatusBar.Breadcrumbs.floatingBackground": "bgLight",
        "ToolWindow.Stripe.background": "bgDark",
        "ToolWindow.Button.selectedBackground": "sel",
        "ToolWindow.Button.selectedForeground": "accent",
        "ToolWindow.Button.hoverBackground": "hover",
        "ToolWindow.Header.background": "bg",
        "ToolWindow.Header.inactiveBackground": "bg",
        "ToolWindow.HeaderTab.selectedInactiveBackground": "bgLight",
        "ToolWindow.HeaderTab.hoverBackground": "hover",
        "ToolWindow.HeaderTab.underlineColor": "accent",
        "ToolWindow.background": "bg",
        "EditorTabs.background": "bgDark",
        "EditorTabs.underlinedTabBackground": "bg",
        "EditorTabs.underlinedTabForeground": "fg",
        "EditorTabs.inactiveUnderlineColor": "muted",
        "EditorTabs.underlineColor": "accent",
        "EditorTabs.underlineHeight": 2,
        "EditorTabs.hoverBackground": "hover",
        "EditorTabs.borderColor": "bgDark",
        "DefaultTabs.background": "bgDark",
        "DefaultTabs.underlineColor": "accent",
        "DefaultTabs.underlinedTabBackground": "bgLight",
        "DefaultTabs.hoverBackground": "hover",
        "DefaultTabs.inactiveUnderlineColor": "muted",
        "Editor.background": "bg",
        "Editor.foreground": "fg",
        "Editor.SearchField.background": "bgDark",
        "EditorPane.background": "bg",
        "EditorPane.inactiveBackground": "bg",
        "Panel.background": "bg",
        "Tree.background": "bg",
        "Tree.rowHeight": 24,
        "Tree.selectionBackground": "sel",
        "Tree.selectionInactiveBackground": h(mix(sel, bg, 0.4)),
        "Tree.modifiedItemForeground": "blue",
        "Tree.hash": "bgLight",
        "List.background": "bg",
        "Table.background": "bg",
        "Table.stripeColor": "bgDark",
        "Table.gridColor": "border",
        "TableHeader.background": "bgDark",
        "Popup.background": "bgDark",
        "Popup.borderColor": "accent",
        "Popup.inactiveBorderColor": "border",
        "Popup.Header.activeBackground": "bgDark",
        "Popup.Header.inactiveBackground": "bgDark",
        "Popup.separatorColor": "border",
        "Popup.Advertiser.background": "bgDarker",
        "Popup.Advertiser.foreground": "fgDim",
        "PopupMenu.background": "bgDark",
        "PopupMenu.selectionBackground": "sel",
        "Menu.background": "bgDark",
        "Menu.selectionBackground": "sel",
        "MenuItem.background": "bgDark",
        "MenuItem.selectionBackground": "sel",
        "MenuItem.acceleratorForeground": "muted",
        "MenuBar.background": "bgDark",
        "MenuBar.borderColor": "border",
        "SearchEverywhere.Header.background": "bgDark",
        "SearchEverywhere.Tab.selectedBackground": "sel",
        "SearchEverywhere.Tab.selectedForeground": "fg",
        "SearchEverywhere.SearchField.background": "bgDarker",
        "SearchEverywhere.SearchField.borderColor": "border",
        "SearchEverywhere.List.separatorForeground": "muted",
        "SearchEverywhere.List.separatorColor": "border",
        "SearchEverywhere.Advertiser.background": "bgDarker",
        "SearchMatch.startBackground": "accent",
        "SearchMatch.endBackground": "magenta",
        "SearchMatch.startColor": "accent",
        "SearchMatch.endColor": "magenta",
        "CompletionPopup.background": "bgDark",
        "CompletionPopup.selectionBackground": "sel",
        "CompletionPopup.selectionInactiveBackground": "bgLight",
        "CompletionPopup.matchForeground": "cyan",
        "CompletionPopup.matchSelectionForeground": "cyan",
        "CompletionPopup.Advertiser.background": "bgDarker",
        "ParameterInfo.background": "bgDark",
        "ParameterInfo.currentParameterForeground": "accent",
        "ParameterInfo.infoForeground": "fgDim",
        "ToolTip.background": "bgLight",
        "ToolTip.foreground": "fg",
        "ToolTip.borderColor": "border",
        "ToolTip.Actions.background": "bgDark",
        "GotItTooltip.background": "sel",
        "GotItTooltip.borderColor": "accent",
        "GotItTooltip.linkForeground": "cyan",
        "Notification.background": "bgLight",
        "Notification.borderColor": "border",
        "Notification.ToolWindow.informativeBackground": "sel",
        "Notification.ToolWindow.warningBackground": h(mix(bg, orange, 0.25)),
        "Notification.ToolWindow.errorBackground": h(mix(bg, red, 0.25)),
        "Banner.infoBackground": h(mix(bg, accent, 0.15)),
        "Banner.infoBorderColor": "accent",
        "Banner.warningBackground": h(mix(bg, orange, 0.15)),
        "Banner.warningBorderColor": "orange",
        "Banner.errorBackground": h(mix(bg, red, 0.15)),
        "Banner.errorBorderColor": "red",
        "Banner.successBackground": h(mix(bg, green, 0.15)),
        "Banner.successBorderColor": "green",
        "Button.background": "bgLight",
        "Button.foreground": "fg",
        "Button.startBorderColor": "border",
        "Button.endBorderColor": "border",
        "Button.focusedBorderColor": "focus",
        "Button.default.foreground": "buttonFg",
        "Button.default.startBackground": "button",
        "Button.default.endBackground": "button",
        "Button.default.startBorderColor": "button",
        "Button.default.endBorderColor": "button",
        "Button.default.focusedBorderColor": "focus",
        "Button.default.focusColor": "focus",
        "ActionButton.hoverBackground": "hover",
        "ActionButton.hoverBorderColor": "hover",
        "ActionButton.pressedBackground": "sel",
        "ActionButton.pressedBorderColor": "sel",
        "TextField.background": "bgDarker",
        "TextField.borderColor": "border",
        "TextField.focusedBorderColor": "focus",
        "TextArea.background": "bgDarker",
        "FormattedTextField.background": "bgDarker",
        "PasswordField.background": "bgDarker",
        "ComboBox.background": "bgDarker",
        "ComboBox.nonEditableBackground": "bgLight",
        "ComboBox.ArrowButton.background": "bgLight",
        "ComboBox.ArrowButton.nonEditableBackground": "bgLight",
        "ComboBox.selectionBackground": "sel",
        "ComboBoxButton.background": "bgLight",
        "Component.borderColor": "border",
        "Component.focusColor": "focus",
        "Component.focusedBorderColor": "focus",
        "Component.hoverBorderColor": "muted",
        "Component.errorFocusColor": "red",
        "Component.inactiveErrorFocusColor": h(mix(red, bg, 0.4)),
        "Component.warningFocusColor": "orange",
        "Component.inactiveWarningFocusColor": h(mix(orange, bg, 0.4)),
        "Component.iconColor": "fgDim",
        "Component.hoverIconColor": "fg",
        "Checkbox.Background.Default": "bgDarker",
        "Checkbox.Background.Selected": "accent",
        "Checkbox.Border.Default": "muted",
        "Checkbox.Border.Selected": "accent",
        "Checkbox.Foreground.Selected": h(bg_darker),
        "Checkbox.Focus.Wide": "accent",
        "Link.activeForeground": "link",
        "Link.hoverForeground": "link",
        "Link.pressedForeground": "magenta",
        "Link.visitedForeground": "magenta",
        "Label.foreground": "fg",
        "Label.infoForeground": "fgDim",
        "Label.disabledForeground": "muted",
        "Label.errorForeground": "red",
        "Label.successForeground": "green",
        "Label.selectedForeground": "fg",
        "ProgressBar.progressColor": "progress",
        "ProgressBar.indeterminateStartColor": "progress",
        "ProgressBar.indeterminateEndColor": "progressEnd",
        "ProgressBar.trackColor": "bgLight",
        "ProgressBar.passedColor": "green",
        "ProgressBar.passedEndColor": "cyan",
        "ProgressBar.failedColor": "red",
        "ProgressBar.failedEndColor": "orange",
        "ScrollBar.background": "bg",
        "ScrollBar.trackColor": "bg",
        "ScrollBar.thumbColor": h(mix(bg_light, muted, 0.4)),
        "ScrollBar.hoverThumbColor": "muted",
        "ScrollBar.Transparent.thumbColor": h(mix(bg_light, muted, 0.4)),
        "ScrollBar.Transparent.hoverThumbColor": "muted",
        "ScrollBar.Mac.thumbColor": h(mix(bg_light, muted, 0.4)),
        "ScrollBar.Mac.hoverThumbColor": "muted",
        "ScrollBar.Mac.Transparent.thumbColor": h(mix(bg_light, muted, 0.4)),
        "ScrollBar.Mac.Transparent.hoverThumbColor": "muted",
        "Separator.separatorColor": "border",
        "SidePanel.background": "bgDark",
        "TabbedPane.underlineColor": "accent",
        "TabbedPane.hoverColor": "hover",
        "TabbedPane.focusColor": "bgLight",
        "TabbedPane.contentAreaColor": "border",
        "ToggleButton.onBackground": "accent",
        "ToggleButton.onForeground": h(bg_darker),
        "ToggleButton.offBackground": "bgLight",
        "ToggleButton.buttonColor": "fg",
        "Counter.background": "accent",
        "Counter.foreground": h(bg_darker),
        "Tag.background": "bgLight",
        "ValidationTooltip.errorBackground": h(mix(bg, red, 0.25)),
        "ValidationTooltip.errorBorderColor": "red",
        "ValidationTooltip.warningBackground": h(mix(bg, orange, 0.25)),
        "ValidationTooltip.warningBorderColor": "orange",
        "VersionControl.Log.Commit.currentBranchBackground": h(mix(bg, accent, 0.12)),
        "VersionControl.Log.Commit.unmatchedForeground": "muted",
        "VersionControl.FileHistory.Commit.selectedBranchBackground": h(mix(bg, accent, 0.12)),
        "VersionControl.GitLog.headIconColor": "yellow",
        "VersionControl.GitLog.localBranchIconColor": "green",
        "VersionControl.GitLog.remoteBranchIconColor": "magenta",
        "VersionControl.GitLog.tagIconColor": "cyan",
        "VersionControl.GitLog.otherIconColor": "fgDim",
        "VersionControl.RefLabel.foreground": "fg",
        "VersionControl.RefLabel.backgroundBase": "accent",
        "FileColor.Blue": h(mix(bg, blue, 0.14)),
        "FileColor.Green": h(mix(bg, green, 0.12)),
        "FileColor.Orange": h(mix(bg, orange, 0.12)),
        "FileColor.Rose": h(mix(bg, red, 0.12)),
        "FileColor.Violet": h(mix(bg, magenta, 0.12)),
        "FileColor.Yellow": h(mix(bg, yellow, 0.1)),
        "FileColor.Gray": "bgLight",
        "NavBar.borderColor": "border",
        "OnePixelDivider.background": "border",
        "Borders.color": "border",
        "Borders.ContrastBorderColor": "border",
        "WelcomeScreen.background": "bgDark",
        "WelcomeScreen.Projects.background": "bg",
        "WelcomeScreen.Projects.selectionBackground": "sel",
        "WelcomeScreen.Projects.actions.background": "bgLight",
        "WelcomeScreen.SidePanel.background": "bgDark",
        "WelcomeScreen.separatorColor": "border",
        "Island.inactiveAlpha": 0.6,
        "Island.borderColor": "border",
        "Island.arc": 12,
        "Plugins.background": "bg",
        "Plugins.SearchField.background": "bgDarker",
        "Plugins.Tab.selectedBackground": "sel",
        "Plugins.Tab.hoverBackground": "hover",
        "Plugins.Button.installForeground": "accent",
        "Plugins.Button.installBorderColor": "accent",
        "Plugins.Button.installFillBackground": "accent",
        "Plugins.Button.installFillForeground": h(bg_darker),
        "Plugins.tagBackground": "bgLight",
        "Plugins.tagForeground": "fgDim",
        "DragAndDrop.areaBackground": h(mix(bg, accent, 0.15)),
        "DragAndDrop.areaBorderColor": "accent",
        "Debugger.Variables.valueForeground": "orange",
        "Debugger.Variables.stringForeground": "green",
        "Debugger.Variables.numberForeground": "orange",
        "Debugger.Variables.keywordForeground": "magenta",
        "Debugger.Variables.collectingDataForeground": "muted",
        "Debugger.Variables.errorMessageForeground": "red",
        "Debugger.Variables.modifyingValueForeground": "cyan",
        "Debugger.Variables.changedValueForeground": "yellow",
        "Debugger.Variables.evaluatingExpressionForeground": "fgDim",
        "Debugger.Variables.typeForeground": "fgDim",
        "Debugger.Variables.valueForeground.inactive": "fgDim",
        "RunWidget.background": h(mix(bg, accent, 0.3)),
        "RunWidget.foreground": "fg",
        "RunWidget.runningBackground": h(mix(bg, green, 0.35)),
        "RunWidget.hoverBackground": h(mix(bg, accent, 0.4)),
        "RunWidget.pressedBackground": h(mix(bg, accent, 0.5)),
        "RunWidget.separatorColor": "border",
        "HelpTooltip.background": "bgLight",
        "HelpTooltip.borderColor": "border",
        "HelpTooltip.shortcutForeground": "accent",
        "Window.border": "border",
        "Profiler.CPU.foreground": "magenta",
    },
    "icons": {
        "ColorPalette": {
            "Actions.Grey": h(fg_dim),
            "Actions.Red": h(red),
            "Actions.Yellow": h(yellow),
            "Actions.Green": h(green),
            "Actions.Blue": h(blue),
            "Actions.GreyInline.Dark": h(muted),
            "Objects.Grey": h(fg_dim),
            "Objects.RedStatus": h(red),
            "Objects.Red": h(red),
            "Objects.Pink": h(magenta),
            "Objects.Yellow": h(yellow),
            "Objects.Green": h(green),
            "Objects.Blue": h(blue),
            "Objects.Purple": h(accent),
            "Objects.BlackText": h(bg_darker),
            "Objects.YellowDark": h(orange),
            "Objects.GreenAndroid": h(green),
            "Checkbox.Background.Default.Dark": h(bg_darker),
            "Checkbox.Border.Default.Dark": h(muted),
            "Checkbox.Foreground.Selected.Dark": h(bg_darker),
            "Checkbox.Background.Selected.Dark": h(accent),
            "Checkbox.Border.Selected.Dark": h(accent),
            "Checkbox.Focus.Wide.Dark": h(accent),
            "Checkbox.Focus.Thin.Default.Dark": h(accent),
            "Checkbox.Focus.Thin.Selected.Dark": h(magenta),
        }
    },
}

PLUGIN_XML = f"""<idea-plugin>
  <id>{ID}</id>
  <name>{NAME} Theme (Omarchy)</name>
  <version>{VERSION}</version>
  <vendor url="https://github.com/hbabb/omarchy-jetbrains">hbabb</vendor>
  <description><![CDATA[
    <p>{NAME} &mdash; a dark UI theme and editor color scheme ported from the
    Omarchy <i>{NAME}</i> theme.</p>
  ]]></description>
  <idea-version since-build="242"/>
  <depends>com.intellij.modules.platform</depends>
  <extensions defaultExtensionNs="com.intellij">
    <themeProvider id="{ID}" path="/themes/{PASCAL}.theme.json"/>
  </extensions>
</idea-plugin>
"""

out = args.out / SLUG
shutil.rmtree(out, ignore_errors=True)
out.mkdir(parents=True)
scheme = icls()
theme_json = json.dumps(theme, indent=2)
(out / f"{NAME}.icls").write_text(scheme)
(out / f"{PASCAL}.theme.json").write_text(theme_json)
jar = out / f"{PASCAL}.jar"
with zipfile.ZipFile(jar, "w", zipfile.ZIP_DEFLATED) as z:
    # Fixed timestamps keep the jar byte-identical across runs, so --install can tell
    # whether anything actually changed.
    for name, data in (("META-INF/plugin.xml", PLUGIN_XML),
                       (f"themes/{PASCAL}.theme.json", theme_json),
                       (f"themes/{PASCAL}.icls", scheme)):
        info = zipfile.ZipInfo(name, date_time=(2024, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, data)


def ide_dirs():
    """JetBrains IDE data dirs, e.g. ~/.local/share/JetBrains/PyCharm2026.3."""
    if not JETBRAINS_DATA.is_dir():
        return []
    return sorted(d for d in JETBRAINS_DATA.iterdir()
                  if d.is_dir() and re.fullmatch(r"[A-Za-z]+\d{4}\.\d+", d.name))


installed, changed = [], False
if args.install:
    payload = jar.read_bytes()
    for d in ide_dirs():
        dest = d / f"omarchy-theme-{SLUG}.jar"
        if not dest.exists() or dest.read_bytes() != payload:
            tmp = dest.with_suffix(".jar.tmp")
            tmp.write_bytes(payload)
            tmp.replace(dest)
            changed = True
        installed.append(d.name)

if args.json:
    print(json.dumps({"ok": True, "theme": SLUG, "name": NAME, "dark": DARK, "jar": str(jar),
                      "installed": installed, "changed": changed}))
else:
    print(f"Built {jar} and {out / (NAME + '.icls')}")
    if args.install:
        if installed:
            print(f"Installed into {len(installed)} IDE(s): {', '.join(installed)}"
                  + ("" if changed else " (already up to date)"))
        else:
            print(f"No JetBrains IDEs found under {JETBRAINS_DATA}")
