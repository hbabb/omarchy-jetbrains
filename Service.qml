import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons

// Omarchy Theme Generator for JetBrains IDEs.
//
// A headless service that keeps a JetBrains theme plugin in step with the Omarchy
// theme. Omarchy rewrites ~/.local/state/omarchy/current/theme.name whenever a theme
// is applied; this service watches that file and runs generate.py --current --install,
// which builds a UI theme + editor color scheme jar from the applied colors.toml and
// copies it into every JetBrains IDE data dir as omarchy-theme-<slug>.jar.
//
// It never changes which theme an IDE uses and never edits IDE settings: the new
// theme shows up under Settings > Appearance after the IDE restarts. Reinstalling an
// unchanged theme is a no-op (the jar is byte-identical), so nothing is rewritten on
// every shell start.
//
// Settings, inline on this plugin's entry in ~/.config/omarchy/shell.json:
//   { "id": "io.github.hbabb.omarchy-jetbrains", "notify": true }
Item {
  id: service

  // Injected by omarchy-shell.
  property var shell: null
  property var manifest: null

  readonly property string home: Quickshell.env("HOME")
  readonly property string pluginId: manifest && manifest.id ? String(manifest.id) : "io.github.hbabb.omarchy-jetbrains"
  readonly property string pluginDir: String(Qt.resolvedUrl(".")).replace(/^file:\/\//, "").replace(/\/$/, "")
  readonly property string cacheDir: (Quickshell.env("XDG_CACHE_HOME") || (home + "/.cache")) + "/omarchy-jetbrains"
  readonly property string themeNamePath: home + "/.local/state/omarchy/current/theme.name"

  property bool notify: true
  // Theme synced during this shell session. The first sync after startup stays
  // silent; later ones announce a newly installed or updated theme.
  property string lastTheme: ""
  property bool rerun: false

  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  function applySettings(raw) {
    try {
      var cfg = JSON.parse(raw || "{}")
      var list = Array.isArray(cfg.plugins) ? cfg.plugins : []
      for (var i = 0; i < list.length; i++) {
        var e = list[i]
        if (!e || e.id !== service.pluginId) continue
        if (e.notify !== undefined) notify = e.notify !== false
        return
      }
    } catch (err) {}
  }

  function sync() {
    if (syncProc.running) { rerun = true; return }
    syncProc.running = true
  }

  function handleResult(output) {
    var lines = String(output || "").trim().split("\n")
    var r
    try { r = JSON.parse(lines[lines.length - 1]) } catch (err) {
      console.warn("omarchy-jetbrains: unexpected generator output:", output)
      return
    }
    if (!r || r.ok !== true) {
      console.warn("omarchy-jetbrains:", r && r.error ? r.error : "generator failed")
      return
    }
    var first = lastTheme === ""
    lastTheme = String(r.theme)
    var count = Array.isArray(r.installed) ? r.installed.length : 0
    if (first || !r.changed || !notify || count === 0) return
    notifyProc.command = [
      "omarchy-notification-send", "-u", "low",
      strings.t("notify.title"),
      strings.tn("notify.body", count).arg(String(r.name)).arg(Commons.I18n.formatNumber(count))
    ]
    notifyProc.running = true
  }

  // Theme switches touch several files in quick succession; wait for them to settle.
  Timer {
    id: debounce
    interval: 1500
    onTriggered: service.sync()
  }

  FileView {
    id: themeName
    path: service.themeNamePath
    watchChanges: true
    printErrors: false
    onLoaded: debounce.restart()
    onFileChanged: reload()
  }

  FileView {
    id: shellConfig
    path: service.home + "/.config/omarchy/shell.json"
    watchChanges: true
    printErrors: false
    onLoaded: service.applySettings(text())
    onFileChanged: reload()
  }

  Process {
    id: syncProc
    command: ["python3", service.pluginDir + "/generate.py", "--current", "--install", "--json", "--out", service.cacheDir]
    stdout: StdioCollector { onStreamFinished: service.handleResult(text) }
    stderr: StdioCollector { onStreamFinished: if (text.length) console.warn("omarchy-jetbrains:", text) }
    onExited: {
      if (service.rerun) { service.rerun = false; service.sync() }
    }
  }

  Process { id: notifyProc }

  IpcHandler {
    target: "omarchy-jetbrains"
    function ping(): string { return "ok" }
    function sync(): string { service.sync(); return "ok" }
    function current(): string { return service.lastTheme }
  }
}
