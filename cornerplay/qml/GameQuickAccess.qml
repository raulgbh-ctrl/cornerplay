import QtQuick
import QtQuick.Effects
import QtQuick.Layouts

// Quick access over a running game, like SteamOS's "..." menu: Guide + A (or Share) on a
// controller, or `cornerplay --quick`. A panel down the right edge with the same controls as
// TV mode's (TvControls.qml): sound, brightness, Wi-Fi, Bluetooth, power mode, gamescope's
// frame limit and scaling, and the game itself (back to it, quit, force close, open Cornerplay).
// The controller steers it even while the game keeps the focus; B, Guide or Guide + A close it.
Window {
    id: qa
    required property var theme
    signal openCornerplay()

    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"
    title: qsTr("Cornerplay quick access")
    width: Math.round(Math.min(500, Math.max(380, (screen ? screen.width : 1920) * 0.28)))
    height: screen ? screen.height : 1080
    x: screen ? screen.virtualX + screen.width - width : 0
    y: screen ? screen.virtualY : 0

    readonly property var tint: {
        const c = theme.primary
        const lum = 0.299 * c.r + 0.587 * c.g + 0.114 * c.b
        return Object.assign({}, theme, { onPrimary: lum > 0.55 ? "#1b1b1f" : "#ffffff" })
    }
    property var info: ({})
    property int tab: 0
    property bool open: false
    readonly property var tabs: [
        { id: "game", label: qsTr("This game"), icon: "gamepad-2" },
        { id: "quick", label: qsTr("Quick settings"), icon: "sliders-horizontal" },
        { id: "perf", label: qsTr("Performance"), icon: "gauge" }
    ]
    readonly property string tabId: tabs[tab].id
    property var rows: []
    property var batt: ({})

    function toggle() { if (visible && open) hide(); else show() }
    function show() {
        info = app.overlayInfo()
        batt = info.battery || {}
        tab = info.key ? 0 : 1
        rebuild(); list.first()
        open = true
        visible = true
        raise(); requestActivate()
        app.markOverlay(qa)
        pad.steer(qa)
        app.refreshSystem()
        list.forceActiveFocus()
        app.uiSound("select")
    }
    function hide() {
        if (!open) return
        open = false
        pad.steer(null)
        app.uiSound("back")
        closeTimer.restart()  // slide out, then go
    }
    Timer { id: closeTimer; interval: 230; onTriggered: if (!qa.open) qa.visible = false }
    onVisibleChanged: if (!visible) { open = false; pad.steer(null) }

    function minutesText(m) {
        return m < 60 ? qsTr("%1 min").arg(m) : qsTr("%1 h %2 min").arg(Math.floor(m / 60)).arg(m % 60)
    }
    function gameRows() {
        if (!info.key) return [{ group: qsTr("This game"), label: qsTr("Nothing running"), icon: "gamepad-2", sub: qsTr("Start a game from Cornerplay") },
                               { group: qsTr("Cornerplay"), label: qsTr("Open Cornerplay"), icon: "layout-grid", act: "open" }]
        const g = qsTr("This game")
        return [
            { group: g, label: qsTr("Back to the game"), icon: "play", act: "back" },
            { group: g, label: controls.armed === "quit" ? qsTr("Press again to quit") : qsTr("Quit the game"), icon: "x", act: "quit", danger: controls.armed === "quit" },
            { group: g, label: controls.armed === "kill" ? qsTr("Press again to force close") : qsTr("Force close (if it hangs)"), icon: "x", act: "kill", danger: true },
            { group: qsTr("Cornerplay"), label: qsTr("Open Cornerplay"), icon: "layout-grid", act: "open" },
            { group: qsTr("Cornerplay"), label: qsTr("Game panel"), icon: "info", sub: qsTr("Notes and screenshots (Guide + Y)"), act: "panel" }
        ]
    }
    function rebuild() {
        const i = list.currentIndex
        rows = tabId === "game" ? gameRows()
             : tabId === "perf" ? controls.performance()
             : controls.quick(batt).filter(r => r.act !== "settings")
        list.currentIndex = Math.min(Math.max(0, i), rows.length - 1)
        if (!list.pickable(rows[list.currentIndex])) list.first()
    }
    function setTab(i) {
        tab = (i + tabs.length) % tabs.length
        app.uiSound("move")
        rebuild(); list.first(); list.positionViewAtBeginning()
    }
    function run(row) {
        if (row.act === "back") hide()
        else if (row.act === "open") { hide(); openCornerplay() }
        else if (row.act === "panel") { hide(); app.overlayRequested() }
        else if (row.act === "quit") { if (controls.arm("quit")) { app.quitGame(info.key, false); hide() } }
        else if (row.act === "kill") { if (controls.arm("kill")) { app.quitGame(info.key, true); hide() } }
        else controls.run(row)
    }

    TvControls { id: controls }
    Connections { target: app; enabled: qa.visible
                  function onSystemChanged() { qa.rebuild() }
                  function onSettingsChanged() { Qt.callLater(qa.rebuild) } }
    Connections { target: controls; function onArmedChanged() { if (qa.visible) qa.rebuild() } }
    Timer { interval: 5000; repeat: true; running: qa.open; onTriggered: { app.refreshSystem(); qa.info = app.overlayInfo() } }
    property var now: new Date()
    Timer { interval: 10000; repeat: true; triggeredOnStart: true; running: qa.open; onTriggered: qa.now = new Date() }

    Rectangle {
        id: pane
        width: qa.width
        height: qa.height
        x: qa.open ? 0 : qa.width
        Behavior on x { enabled: !app.still; NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
        color: Qt.alpha(qa.theme.surfaceContainerLow, 0.96)
        Rectangle { width: 1; height: parent.height; color: Qt.alpha("white", 0.08) }
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: w => w.accepted = true }

        Keys.onPressed: event => {
            const k = event.key
            if (k === Qt.Key_F9 || k === Qt.Key_F10) { qa.hide(); event.accepted = true }
            else if (k === Qt.Key_PageUp || k === Qt.Key_PageDown) { qa.setTab(qa.tab + (k === Qt.Key_PageDown ? 1 : -1)); event.accepted = true }
        }

        // The game's art, faint, behind the heading.
        ArtImage {
            width: parent.width; height: 190
            clip: true
            visible: !!qa.info.key && !app.light
            sources: qa.info.heroes && qa.info.heroes.length ? qa.info.heroes : (qa.info.covers || [])
            fillMode: Image.PreserveAspectCrop
            opacity: 0.3
        }
        Rectangle {
            width: parent.width; height: 190
            gradient: Gradient {
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 1.0; color: Qt.alpha(qa.theme.surfaceContainerLow, 0.96) }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 26
            anchors.topMargin: 28
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                Text { text: Qt.formatTime(qa.now, Qt.locale(app.uiLocale).timeFormat(Locale.ShortFormat)); color: qa.theme.onSurface
                       font.pixelSize: 24; font.weight: Font.Medium }
                Item { Layout.fillWidth: true }
                Repeater {
                    model: {
                        const s = app.system, n = s.network || {}, b = s.bluetooth || {}, a = s.audio || {}
                        const out = []
                        if (n.ssid) out.push("wifi")
                        if ((b.devices || []).some(d => d.connected)) out.push("bluetooth")
                        if (a.volume !== undefined) out.push(controls.volumeIcon(a))
                        return out
                    }
                    Icon { required property var modelData; name: modelData; size: 20; color: qa.theme.onSurfaceVariant }
                }
                Text { visible: qa.batt.level !== undefined; text: (qa.batt.level || 0) + "%" + (qa.batt.charging ? " ⚡" : "")
                       color: (qa.batt.level || 100) <= 15 && !qa.batt.charging ? qa.theme.error : qa.theme.onSurfaceVariant; font.pixelSize: 17 }
            }
            // What is being played, and for how long.
            ColumnLayout {
                visible: !!qa.info.key
                spacing: 2
                Text { Layout.fillWidth: true; text: qa.info.title || ""; color: qa.theme.onSurface; font.pixelSize: 26; font.weight: Font.Bold; elide: Text.ElideRight }
                Text { text: qsTr("Playing for ") + qa.minutesText(qa.info.minutes || 0) + (qa.info.shots ? "   ·   " + qa.info.shots + qsTr(" screenshots") : "")
                       color: qa.theme.onSurfaceVariant; font.pixelSize: 16 }
            }
            Row {
                Layout.fillWidth: true
                Layout.topMargin: 4
                spacing: 8
                PadButton { visible: pad.connected; anchors.verticalCenter: parent.verticalCenter; button: "lb"; style: pad.style; size: 24 }
                Repeater {
                    model: qa.tabs
                    Rectangle {
                        id: tabPill
                        required property var modelData
                        required property int index
                        readonly property bool on: index === qa.tab
                        height: 44; radius: 22
                        width: on ? tabName.implicitWidth + 70 : 50
                        Behavior on width { enabled: !app.still; NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                        color: on ? Qt.alpha(qa.theme.primary, 0.22) : Qt.alpha(qa.theme.onSurface, 0.05)
                        border.width: on ? 1 : 0; border.color: qa.theme.primary
                        clip: true
                        Icon { x: 14; anchors.verticalCenter: parent.verticalCenter; name: tabPill.modelData.icon; size: 22
                               color: tabPill.on ? qa.theme.primary : qa.theme.onSurfaceVariant }
                        Text { id: tabName; x: 46; anchors.verticalCenter: parent.verticalCenter; visible: tabPill.on
                               text: tabPill.modelData.label; color: qa.theme.onSurface; font.pixelSize: 16; font.weight: Font.DemiBold }
                        TapHandler { onTapped: { qa.setTab(tabPill.index); list.forceActiveFocus() } }
                    }
                }
                PadButton { visible: pad.connected; anchors.verticalCenter: parent.verticalCenter; button: "rb"; style: pad.style; size: 24 }
            }
            TvRowList {
                id: list
                Layout.fillWidth: true
                Layout.fillHeight: true
                theme: qa.theme
                tint: qa.tint
                rows: qa.rows
                catchBack: true
                catchRight: true
                onBack: qa.hide()
                onEdge: qa.hide()
                onPicked: row => qa.run(row)
                onAlt: row => controls.runAlt(row)
            }
            Row {
                spacing: 20
                Repeater {
                    model: {
                        const r = list.current, adj = r.kind === "slider" || r.kind === "choice"
                        const out = pad.connected
                            ? [{ b: ["a"], t: r.kind === "slider" && r.press ? qsTr("Mute") : qsTr("Choose") }, adj ? { k: "← →", t: qsTr("Change") } : null,
                               { b: ["b"], t: qsTr("Back to the game") }]
                            : [{ k: qsTr("Enter"), t: qsTr("Choose") }, adj ? { k: "← →", t: qsTr("Change") } : null, { k: qsTr("Esc"), t: qsTr("Back to the game") }]
                        return out.filter(h => h)
                    }
                    Row {
                        required property var modelData
                        spacing: 8
                        Repeater { model: parent.modelData.b || []; PadButton { required property string modelData; button: modelData; style: pad.style; size: 24 } }
                        Rectangle { visible: !!parent.modelData.k; height: 24; radius: 6; width: hk.implicitWidth + 14
                                    color: Qt.alpha(qa.theme.surfaceContainerHighest, 0.9); border.width: 1; border.color: qa.theme.outlineVariant
                                    Text { id: hk; anchors.centerIn: parent; text: parent.parent.modelData.k || ""; color: qa.theme.onSurface; font.pixelSize: 12; font.weight: Font.DemiBold } }
                        Text { anchors.verticalCenter: parent.verticalCenter; text: parent.modelData.t; color: qa.theme.onSurfaceVariant; font.pixelSize: 14 }
                    }
                }
            }
        }
    }
}
