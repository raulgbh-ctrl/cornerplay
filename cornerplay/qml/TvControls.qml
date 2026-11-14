import QtQuick
import "glyphs.js" as Glyphs

// The rows behind TV mode's quick access tabs and its Settings screen (TvRowList.qml), built
// from the PC's state (app.system, syscontrol.py) and Cornerplay's settings: everything you can
// change from the sofa, like SteamOS's Game Mode. One place, so both menus always agree.
QtObject {
    id: c
    // What the rows ask TV mode to do: a password to type, the Settings screen, a power action.
    signal askPassword(string ssid)
    signal openSettings(string section)
    signal power(string what)
    signal leave(string how)   // "exit" (TV mode), "desktop" (end the session), "quit"
    signal padTest()

    readonly property var sys: app.system
    readonly property var busy: sys.busy || []
    readonly property var st: app.settingsMap
    property string armed: ""          // a row waiting for its second press ("power:restart", "wifi:Home")
    property var disarm: Timer { interval: 4000; onTriggered: c.armed = "" }
    function arm(id) { if (armed === id) { armed = ""; return true } armed = id; disarm.restart(); return false }

    function setting(group, label, icon, key, sub) {
        return { group: group, label: label, icon: icon, sub: sub || "", on: !!st[key], set: v => app.setSetting(key, v) }
    }

    // ------------------------------------------------------------ sound
    function volumeIcon(a) { return a.muted || !a.volume ? "volume-x" : a.volume < 50 ? "volume-1" : "volume-2" }
    function sound(group, full) {
        const a = sys.audio || {}
        if (a.volume === undefined)
            return full ? [{ group: group, label: qsTr("Sound controls are not available"), icon: "volume-x", sub: qsTr("PipeWire's wpctl was not found") }] : []
        const out = [{ group: group, kind: "slider", label: qsTr("Volume"), icon: volumeIcon(a), num: a.volume, step: 5, dim: a.muted,
                       valueText: a.muted ? qsTr("Muted") : a.volume + "%",
                       set: v => app.setSystem("volume", v), press: () => app.setSystem("muted", !a.muted) }]
        if (full) out.push({ group: group, label: qsTr("Mute"), icon: "volume-x", on: !!a.muted, set: v => app.setSystem("muted", v) })
        const outs = a.outputs || []
        if (outs.length > 1)
            out.push({ group: group, kind: "choice", label: qsTr("Output"), icon: "headphones", cur: a.output,
                       options: outs.map(o => ({ v: o.id, t: shortName(o.name) })), set: v => app.setSystem("output", v) })
        if (a.micMuted !== undefined)
            out.push({ group: group, label: qsTr("Microphone"), icon: a.micMuted ? "mic-off" : "mic", sub: a.micMuted ? qsTr("Muted") : qsTr("On"),
                       on: !a.micMuted, set: v => app.setSystem("mic", !v) })
        return out
    }
    function shortName(n) {  // "Apple Audio Device Speakers" -> "Speakers": the part that tells them apart
        const outs = (sys.audio || {}).outputs || []
        if (outs.length < 2) return n
        const words = outs.map(o => o.name.split(" "))
        let same = 0
        while (words.every(w => w.length > same + 1 && w[same] === words[0][same])) same++
        const s = n.split(" ").slice(same).join(" ")
        return s.length > 26 ? s.slice(0, 25) + "…" : s
    }

    // ------------------------------------------------------------ screen and performance
    function brightness(group) {
        if (sys.brightness === undefined || sys.brightness === null) return []
        return [{ group: group, kind: "slider", label: qsTr("Brightness"), icon: "sun", num: sys.brightness, min: 5, step: 5,
                  set: v => app.setSystem("brightness", v) }]
    }
    readonly property var profileNames: ({ "power-saver": qsTr("Battery saver"), balanced: qsTr("Balanced"), performance: qsTr("Performance") })
    function powerMode(group) {
        const p = sys.power || {}
        if (!p.profile) return []
        return [{ group: group, kind: "choice", label: qsTr("Power mode"), icon: "zap", cur: p.profile,
                  options: (p.profiles || []).slice().reverse().map(n => ({ v: n, t: profileNames[n] || n })),
                  set: v => app.setSystem("power", v) }]
    }
    function fpsOptions(r) {
        const s = new Set([r, Math.round(r / 2), Math.round(r / 3), Math.round(r / 4), 30, 40, 45, 60, 90, 120])
        return [{ v: 0, t: qsTr("Off") }].concat([...s].filter(f => f >= 15 && f <= r).sort((a, b) => a - b).map(f => ({ v: f, t: f + " fps" })))
    }
    function gamescope(group) {
        const g = sys.gamescope || {}
        if (!g.active)
            return [{ group: group, label: qsTr("Frame limit and scaling"), icon: "monitor",
                      sub: app.hasGamescope ? qsTr("In the Cornerplay (TV) session")
                                            : qsTr("Needs gamescope and the TV session") }]
        const out = [{ group: group, kind: "choice", label: qsTr("Frame limit"), icon: "timer", cur: g.fpsLimit,
                       options: fpsOptions(g.refresh || 60), set: v => app.setSystem("gs_fps_limit", v) }]
        if ((g.rates || []).length > 1)
            out.push({ group: group, kind: "choice", label: qsTr("Refresh rate"), icon: "monitor", cur: g.refreshTarget || 0,
                       options: [{ v: 0, t: qsTr("Default") }].concat(g.rates.map(r => ({ v: r, t: r + " Hz" }))),
                       set: v => app.setSystem("gs_refresh", v) })
        out.push({ group: group, label: qsTr("Allow tearing"), icon: "zap", sub: qsTr("Lower input lag; the picture may split"),
                   on: !!g.tearing, set: v => app.setSystem("gs_tearing", v) })
        out.push({ group: group, kind: "choice", label: qsTr("Scaling filter"), icon: "contrast", cur: g.filter,
                   options: [{ v: "linear", t: qsTr("Linear") }, { v: "nearest", t: qsTr("Nearest") }, { v: "fsr", t: "AMD FSR" },
                             { v: "nis", t: "NVIDIA NIS" }, { v: "pixel", t: qsTr("Sharp pixels") }],
                   set: v => app.setSystem("gs_filter", v) })
        if (g.filter === "fsr" || g.filter === "nis")
            out.push({ group: group, kind: "slider", label: qsTr("Sharpness"), icon: "sparkles", num: g.sharpness, min: 0, max: 20, step: 1,
                       unit: "", set: v => app.setSystem("gs_sharpness", v) })
        out.push({ group: group, kind: "choice", label: qsTr("Scaling mode"), icon: "maximize", cur: g.scaler,
                   options: [{ v: "auto", t: qsTr("Auto") }, { v: "integer", t: qsTr("Integer") }, { v: "fit", t: qsTr("Fit") },
                             { v: "fill", t: qsTr("Fill") }, { v: "stretch", t: qsTr("Stretch") }],
                   set: v => app.setSystem("gs_scaler", v) })
        if (g.hdrSupported)
            out.push({ group: group, label: qsTr("HDR"), icon: "sun", on: !!g.hdr, set: v => app.setSystem("gs_hdr", v) })
        return out
    }
    function games(group) {
        const g = sys.gamescope || {}
        const out = [
            { group: group, kind: "choice", label: qsTr("Game profile"), icon: "gauge", cur: st.perf || "",
              options: [{ v: "", t: qsTr("No change") }, { v: "battery", t: qsTr("Battery saver") }, { v: "balanced", t: qsTr("Balanced") }, { v: "quality", t: qsTr("Max quality") }],
              set: v => app.setSetting("perf", v) },
            setting(group, qsTr("FPS counter"), "gauge", "show_fps"),
            setting(group, qsTr("MangoHud overlay"), "cpu", "mangohud"),
            setting(group, qsTr("GameMode"), "zap", "gamemode", qsTr("Feral's CPU and GPU boost while you play"))
        ]
        const w = qsTr("While you play")
        out.push(setting(w, qsTr("Do not disturb"), "bell", "focus_dnd", qsTr("Notifications wait (on Ryoku: its Game Mode)")))
        out.push(setting(w, qsTr("Keep awake"), "sun", "focus_awake", qsTr("No screen blanking or sleep mid-game")))
        out.push(setting(w, qsTr("Performance power mode"), "zap", "focus_power", qsTr("Back to yours when the game closes")))
        out.push(setting(w, qsTr("Pause downloads"), "download", "focus_downloads", qsTr("They carry on when the game closes")))
        if (app.hasGamescope && !g.active)
            out.push({ group: group, kind: "choice", label: qsTr("gamescope"), icon: "monitor", cur: st.gamescope || "",
                       options: [{ v: "", t: qsTr("Off") }, { v: "fullscreen", t: qsTr("Full screen") }, { v: "fsr", t: qsTr("FSR upscaling") }],
                       set: v => app.setSetting("gamescope", v) })
        return out
    }

    // ------------------------------------------------------------ Wi-Fi
    function wifiSub(n) {
        return n.ssid ? qsTr("Connected to ") + n.ssid : n.wired ? qsTr("Wired network connected") : n.wifi ? qsTr("Not connected") : qsTr("Off")
    }
    function wifiSwitch(group) {
        const n = sys.network || {}
        if (n.wifi === undefined) return []
        return [{ group: group, label: qsTr("Wi-Fi"), icon: n.wifi ? "wifi" : "wifi-off", sub: wifiSub(n), on: !!n.wifi,
                  busy: busy.indexOf("wifi") !== -1, set: v => app.setSystem("wifi", v) }]
    }
    function network(group) {
        const n = sys.network || {}
        if (n.wifi === undefined)
            return [{ group: group, label: qsTr("Network controls are not available"), icon: "wifi-off", sub: qsTr("NetworkManager's nmcli was not found") }]
        const out = wifiSwitch(group)
        if (!n.wifi) return out
        for (const w of n.networks || []) {
            const id = "wifi:" + w.ssid
            out.push({ group: qsTr("Networks"), label: armed === id ? qsTr("Press again to disconnect") : w.ssid, icon: w.secure ? "lock" : "wifi",
                       sub: w.active ? qsTr("Connected") : w.saved ? qsTr("Saved") : w.secure ? qsTr("Needs a password") : qsTr("Open network"),
                       value: w.signal + "%", busy: busy.indexOf(id) !== -1, act: "wifi", net: w, alt: w.saved ? qsTr("Forget") : "" })
        }
        out.push({ group: qsTr("Networks"), label: busy.indexOf("wifi-scan") !== -1 ? qsTr("Searching…") : qsTr("Search again"), icon: "refresh-cw",
                   busy: busy.indexOf("wifi-scan") !== -1, act: "wifiscan" })
        return out
    }

    // ------------------------------------------------------------ Bluetooth
    function deviceIcon(name) {
        if (/controller|gamepad|xbox|dualsense|dualshock|joy-?con|8bitdo|pro controller|stadia|legion/i.test(name)) return "gamepad-2"
        if (/buds|beats|pods|head|ear|jbl|bose|sony wh|wf-|wh-|soundcore|speaker/i.test(name)) return "headphones"
        if (/keyboard/i.test(name)) return "keyboard"
        return "bluetooth"
    }
    function btSwitch(group) {
        const b = sys.bluetooth || {}
        if (b.on === undefined) return []
        const on = (b.devices || []).filter(d => d.connected).map(d => d.name)
        return [{ group: group, label: qsTr("Bluetooth"), icon: "bluetooth", on: !!b.on, busy: busy.indexOf("bluetooth") !== -1,
                  sub: !b.on ? qsTr("Off") : on.length ? on.join(", ") : qsTr("Nothing connected"), set: v => app.setSystem("bluetooth", v) }]
    }
    function bluetooth(group) {
        const b = sys.bluetooth || {}
        if (b.on === undefined)
            return [{ group: group, label: qsTr("No Bluetooth adapter found"), icon: "bluetooth", sub: qsTr("Or bluetoothctl is not installed") }]
        const out = btSwitch(group)
        if (!b.on) return out
        for (const d of b.devices || [])
            out.push({ group: qsTr("Your devices"), label: d.name, icon: deviceIcon(d.name), sub: d.connected ? qsTr("Connected") : qsTr("Not connected"),
                       busy: busy.indexOf("bt:" + d.mac) !== -1, act: "bt", dev: d, alt: qsTr("Forget") })
        const scanning = busy.indexOf("bt-scan") !== -1
        out.push({ group: qsTr("Add a device"), label: scanning ? qsTr("Searching…") : qsTr("Pair a new device"), icon: "plus", busy: scanning,
                   sub: qsTr("Put the controller or headphones in pairing mode first"), act: "btscan" })
        for (const d of sys.nearby || [])
            out.push({ group: qsTr("Add a device"), label: d.name, icon: deviceIcon(d.name), sub: qsTr("Choose to pair"),
                       busy: busy.indexOf("bt:" + d.mac) !== -1, act: "btpair", dev: d })
        return out
    }

    // ------------------------------------------------------------ controllers
    readonly property var layoutNames: ({ "": qsTr("Standard"), none: qsTr("Standard"), swap_ab: qsTr("Swap A and B"), nintendo: qsTr("Nintendo"),
                                          southpaw: qsTr("Southpaw"), shoulders: qsTr("Swap bumpers and triggers") })
    readonly property var layoutOrder: ["", "swap_ab", "nintendo", "southpaw", "shoulders"]
    function controllers() {
        const pads = pad.pads || []
        const out = []
        for (const p of pads)
            out.push({ group: qsTr("Connected"), label: p.name, icon: "gamepad-2",
                       sub: Glyphs.of(p.style).name + (p.wired ? qsTr(" · wired") : ""),
                       value: p.battery >= 0 ? p.battery + "%" : "" })
        if (!pads.length)
            out.push({ group: qsTr("Connected"), label: pad.deck ? qsTr("Steam Deck controls") : qsTr("No controller connected"), icon: "gamepad-2",
                       sub: pad.deck ? qsTr("Steam turns them into keys here; Game Mode passes them on")
                                     : pad.available ? qsTr("Turn one on, or pair it under Bluetooth") : qsTr("SDL2 is not available yet"),
                       act: pad.deck ? "" : "settings", section: "bluetooth" })
        const g = "Cornerplay"
        out.push({ group: g, label: qsTr("Test buttons"), icon: "gamepad-2", sub: qsTr("See every button and stick as games see them"), act: "padtest" })
        out.push({ group: g, kind: "choice", label: qsTr("Button prompts"), icon: "eye", cur: st.pad_glyphs || "",
                   options: [{ v: "", t: qsTr("Auto") + " (" + Glyphs.of(pad.style).name + ")" }].concat(Glyphs.choices()),
                   set: v => { app.setSetting("pad_glyphs", v); pad.reload() } })
        out.push({ group: g, kind: "choice", label: qsTr("Choose with"), icon: "check", cur: !!st.pad_swap_confirm,
                   options: [{ v: false, t: qsTr("Bottom button") }, { v: true, t: qsTr("Right button") }],
                   set: v => { app.setSetting("pad_swap_confirm", v); pad.reload() } })
        out.push(setting(g, qsTr("Rumble in menus"), "zap", "tv_rumble"))
        out.push({ group: g, label: qsTr("Test rumble"), icon: "zap", act: "buzz" })
        out.push({ group: qsTr("Games"), kind: "choice", label: qsTr("Layout"), icon: "layout-grid", cur: st.pad_layout || "",
                   options: layoutOrder.map(v => ({ v: v, t: layoutNames[v] })), set: v => app.setSetting("pad_layout", v) })
        out.push({ group: qsTr("Games"), label: qsTr("How layouts work"), icon: "info",
                   sub: qsTr("For games started here that use SDL (most Proton and native games). Each game can have its own (More > Options). Steam games use Steam Input.") })
        return out
    }

    // ------------------------------------------------------------ accessibility
    function accessibility(group) {
        return [
            { group: group, kind: "choice", label: qsTr("Interface size"), icon: "maximize", cur: st.ui_scale || 0,
              options: [0, 1.0, 1.15, 1.3, 1.5, 2.0].map(v => ({ v: v, t: v ? Math.round(v * 100) + "%" : qsTr("Automatic") })),
              set: v => { app.setSetting("ui_scale", v); app.toast(qsTr("The new size applies the next time Cornerplay starts")) } },
            setting(group, qsTr("High contrast"), "contrast", "a11y_contrast", qsTr("Text, outlines and edges toward black and white")),
            { group: group, kind: "choice", label: qsTr("Colour-blind friendly"), icon: "eye", cur: st.a11y_colours || "",
              options: [{ v: "", t: qsTr("Off") }, { v: "redgreen", t: qsTr("Red-green") }, { v: "blueyellow", t: qsTr("Blue-yellow") }],
              set: v => app.setSetting("a11y_colours", v) },
            setting(qsTr("Moving"), qsTr("Reduce motion"), "pause", "a11y_motion", qsTr("No sliding, zooming, drifting art or trailers")),
            { group: qsTr("Hearing"), label: qsTr("Read aloud"), icon: "volume-2", on: !!st.a11y_speak,
              sub: app.speechAvailable ? qsTr("Says what is selected as you move") : qsTr("Needs a voice: get one below"),
              set: v => { app.setSetting("a11y_speak", v); if (v) Qt.callLater(() => app.say(qsTr("Read aloud is on"))) } }
        ].concat(!app.speechAvailable && app.canGetVoice
            ? [{ group: qsTr("Hearing"), label: busy.indexOf("voice") !== -1 ? qsTr("Downloading a voice…") : qsTr("Get a voice"),
                 icon: "download", sub: qsTr("eSpeak NG, 10 MB, every language (no password needed)"), act: "getvoice", busy: busy.indexOf("voice") !== -1 }]
            : [])
    }

    // ------------------------------------------------------------ TV mode, people, power
    function tvMode(group) {
        return [
            setting(group, qsTr("Sounds"), "music", "tv_sounds", qsTr("Soft clicks when moving and choosing")),
            setting(group, qsTr("Music"), "music", "tv_music", qsTr("A calm ambient loop on the home screen")),
            setting(group, qsTr("Trailers"), "play", "tv_trailers", qsTr("The focused game's trailer, muted, after a moment")),
            setting(group, qsTr("Animated art"), "sparkles", "tv_animated", qsTr("Moving covers and banners when plugged in")),
            setting(group, qsTr("Rumble"), "gamepad-2", "tv_rumble", qsTr("A light buzz when moving and choosing")),
            setting(group, qsTr("Reflections"), "eye", "tv_reflection"),
            setting(group, qsTr("Start-up animation"), "sparkles", "tv_intro"),
            setting(group, qsTr("Who's playing?"), "user-round", "tv_who", qsTr("Ask at start when several people use this PC")),
            { group: group, kind: "choice", label: qsTr("Screensaver"), icon: "moon", cur: st.tv_screensaver || 0,
              options: [0, 1, 3, 5, 10, 20, 30].map(m => ({ v: m, t: m ? m + qsTr(" min") : qsTr("Never") })),
              set: v => app.setSetting("tv_screensaver", v) }
        ]
    }
    function people(group) {
        if (app.profiles.length < 2) return []
        return [{ group: group, kind: "choice", label: qsTr("Who's playing"), icon: "user-round", cur: app.profile,
                  options: app.profiles.map(p => ({ v: p, t: p })), set: v => app.switchProfile(v) }]
    }
    function battery(group, batt) {
        if (!batt || batt.level === undefined) return []
        return [{ group: group, label: qsTr("Battery"), icon: batt.charging ? "battery-charging" : "battery",
                  value: batt.level + "%", sub: batt.charging ? qsTr("Charging") : qsTr("On battery") }]
    }
    function powerRows(group) {
        const p = (what, label, ask, icon, danger) => ({ group: group, label: armed === "power:" + what ? ask : label, icon: icon,
                                                         act: "power", what: what, danger: danger })
        return [p("suspend", qsTr("Sleep"), qsTr("Press again to sleep"), "moon", false),
                p("restart", qsTr("Restart"), qsTr("Press again to restart"), "refresh-cw", true),
                p("shutdown", qsTr("Shut down"), qsTr("Press again to shut down"), "power", true)]
    }
    function leaveRows(group) {
        return app.inSession ? [{ group: group, label: qsTr("Switch to desktop"), icon: "log-out", act: "leave", how: "desktop" }]
                             : [{ group: group, label: qsTr("Exit TV mode"), icon: "log-out", act: "leave", how: "exit" },
                                { group: group, label: qsTr("Quit Cornerplay"), icon: "x", act: "leave", how: "quit", danger: true }]
    }
    function about(group) {
        const g = sys.gamescope || {}
        return [{ group: group, label: "Cornerplay " + app.appVersion, icon: "info",
                  sub: g.active ? qsTr("Running in gamescope at ") + (g.refresh || 60) + " Hz" : app.inSession ? qsTr("Session mode") : qsTr("TV mode") }]
    }

    // ------------------------------------------------------------ what the menus show
    // Quick access tabs (the right-hand menu, Guide + A).
    function quick(batt) {
        return [].concat(sound(qsTr("Sound"), false), brightness(qsTr("Screen")),
                         wifiSwitch(qsTr("Connections")), btSwitch(qsTr("Connections")),
                         powerMode(qsTr("Power")), battery(qsTr("Power"), batt),
                         [{ group: qsTr("More"), label: qsTr("All settings"), icon: "settings-2", act: "settings", section: "display" }])
    }
    function performance() {
        return [].concat(gamescope(qsTr("Display")), powerMode(qsTr("Power")), games(qsTr("Games you start here")))
    }
    function tvQuick() { return tvMode(qsTr("TV mode")) }

    // Settings: the sections down the left and what each one holds.
    readonly property var sections: [
        { id: "display", label: qsTr("Display & performance"), icon: "monitor" },
        { id: "sound", label: qsTr("Sound"), icon: "volume-2" },
        { id: "network", label: qsTr("Wi-Fi"), icon: "wifi" },
        { id: "bluetooth", label: qsTr("Bluetooth"), icon: "bluetooth" },
        { id: "controllers", label: qsTr("Controllers"), icon: "gamepad-2" },
        { id: "games", label: qsTr("Games"), icon: "play" },
        { id: "tv", label: qsTr("TV mode"), icon: "tv" },
        { id: "a11y", label: qsTr("Accessibility"), icon: "eye" },
        { id: "system", label: qsTr("System & power"), icon: "power" }
    ]
    function section(id, batt) {
        if (id === "display") return [].concat(brightness(qsTr("Screen")), gamescope(qsTr("gamescope")), powerMode(qsTr("Power")))
        if (id === "sound") return sound(qsTr("Sound"), true)
        if (id === "network") return network(qsTr("Wi-Fi"))
        if (id === "bluetooth") return bluetooth(qsTr("Bluetooth"))
        if (id === "controllers") return controllers()
        if (id === "games") return games(qsTr("Games you start from Cornerplay"))
        if (id === "tv") return tvMode(qsTr("TV mode"))
        if (id === "a11y") return accessibility(qsTr("Seeing"))
        if (id === "system") return [].concat(people(qsTr("People")), battery(qsTr("Power"), batt), powerMode(qsTr("Power")),
                                              powerRows(qsTr("Power")), leaveRows(qsTr("Cornerplay")), about(qsTr("About")))
        return []
    }

    // A row's own action (A), and its second one (X).
    function run(row) {
        if (row.act === "settings") openSettings(row.section || "")
        else if (row.act === "power") { if (arm("power:" + row.what)) power(row.what) }
        else if (row.act === "leave") leave(row.how)
        else if (row.act === "wifiscan") app.scanNetworks()
        else if (row.act === "padtest") padTest()
        else if (row.act === "getvoice") app.getVoice()
        else if (row.act === "buzz") pad.buzz(80)
        else if (row.act === "wifi") {
            const w = row.net
            if (w.active) { if (arm("wifi:" + w.ssid)) app.wifiDisconnect(w.ssid) }
            else if (w.saved || !w.secure) app.wifiConnect(w.ssid, "", w.saved)
            else askPassword(w.ssid)
        }
        else if (row.act === "btscan") { if (busy.indexOf("bt-scan") === -1) app.btScan() }
        else if (row.act === "bt") app.btConnect(row.dev.mac, !row.dev.connected)
        else if (row.act === "btpair") app.btPair(row.dev.mac)
    }
    function runAlt(row) {
        if (row.act === "wifi" && row.net.saved) app.wifiForget(row.net.ssid)
        else if (row.act === "bt") app.btForget(row.dev.mac)
    }
}
