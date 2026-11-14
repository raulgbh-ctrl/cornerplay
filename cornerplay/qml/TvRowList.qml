import QtQuick
import QtQuick.Effects

// A list of rows for TV mode's menus (quick access, Settings), driven by a controller like
// SteamOS's: up / down move (skipping rows that only tell you something), A chooses, left /
// right move a slider or step through a choice, X does a row's second thing (Forget...).
//
// A row: { label, icon, sub, group, value (text on the right), danger, busy,
//          on: a switch, kind: "slider" (num, min, max, step, unit, press) or "choice" (options [{v, t}], cur),
//          set: function(newValue) for switches, sliders and choices, act: anything else to choose, alt: X's label }
// The model is the rows' count, and each delegate reads its row: new values (a volume step,
// a download's progress) update the rows in place instead of rebuilding the list.
ListView {
    id: rl
    required property var theme
    required property var tint
    property var rows: []
    signal picked(var row)
    signal alt(var row)
    // Left / right past a row that does not use them, and B: the owner decides (close a menu,
    // go back to Settings' sections). Without a catcher the key goes on to the parent.
    property bool catchLeft: false
    property bool catchRight: false
    property bool catchBack: false
    signal edge(int dir)
    signal back()

    model: rows.length
    clip: true
    spacing: 6
    boundsBehavior: Flickable.StopAtBounds
    keyNavigationEnabled: false
    highlightMoveDuration: app.still ? 0 : 120
    preferredHighlightBegin: 40
    preferredHighlightEnd: height - 40
    highlightRangeMode: ListView.ApplyRange

    function pickable(r) { return !!r && !!(r.act || r.set || r.press) }
    readonly property var current: rows[currentIndex] || ({})
    function first() { const i = rows.findIndex(r => pickable(r)); currentIndex = Math.max(0, i) }
    function step(d) {
        let i = currentIndex
        for (let n = 0; n < rows.length; n++) {
            i = (i + d + rows.length) % rows.length
            if (pickable(rows[i])) { currentIndex = i; return true }
        }
        return false
    }
    // Left / right on a slider or a choice: true when it moved something.
    function adjust(d) {
        const r = current
        if (!r.set) return false
        if (r.kind === "slider") {
            const lo = r.min || 0, hi = r.max === undefined ? 100 : r.max, s = r.step || 5
            const v = Math.max(lo, Math.min(hi, Math.round(((r.num || 0) + d * s) / s) * s))
            if (v !== r.num) { r.set(v); app.uiSound("move"); app.say(String(v)) }
            return true
        }
        if (r.kind === "choice") {
            const opts = r.options || []
            if (opts.length < 2) return true
            const i = opts.findIndex(o => o.v === r.cur)
            const next = opts[(i + d + opts.length) % opts.length]
            r.set(next.v)
            app.uiSound("move")
            app.say(next.t)
            return true
        }
        return false
    }
    function choose() {
        const r = current
        if (!pickable(r)) return
        app.uiSound("select")
        if (r.press) r.press()
        else if (r.kind === "choice") adjust(1)
        else if (r.on !== undefined && r.set) r.set(!r.on)
        else picked(r)
    }

    onCurrentIndexChanged: if (activeFocus) { app.uiSound("move"); speak() }
    onActiveFocusChanged: if (activeFocus) speak()
    // Read aloud (Accessibility): the row, and its value or switch.
    function speak() {
        const r = current
        if (!r.label) return
        let v = ""
        if (r.kind === "slider") v = r.valueText || ((r.num || 0) + (r.unit === undefined ? " percent" : ""))
        else if (r.kind === "choice") v = ((r.options || []).find(o => o.v === r.cur) || { t: "" }).t
        else if (r.on !== undefined) v = r.on ? qsTr("on") : qsTr("off")
        else v = r.value || r.sub || ""
        app.say(r.label + (v ? ", " + v : ""))
    }
    Keys.onUpPressed: event => { event.accepted = step(-1) || true }
    Keys.onDownPressed: event => { event.accepted = step(1) || true }
    Keys.onLeftPressed: event => { if (!adjust(-1)) { if (catchLeft) edge(-1); else event.accepted = false } }
    Keys.onRightPressed: event => { if (!adjust(1)) { if (catchRight) edge(1); else event.accepted = false } }
    Keys.onEscapePressed: event => { if (catchBack) back(); else event.accepted = false }
    Keys.onReturnPressed: choose()
    Keys.onEnterPressed: choose()
    Keys.onPressed: event => {
        if (event.key === Qt.Key_F2 && current.alt) { app.uiSound("select"); alt(current); event.accepted = true }
    }

    delegate: Column {
        id: cell
        required property int index
        readonly property var row: rl.rows[index] || ({})
        readonly property bool lit: ListView.isCurrentItem && rl.activeFocus
        readonly property bool header: !!row.group && (index === 0 || (rl.rows[index - 1] || {}).group !== row.group)
        width: rl.width

        Text {  // the group's name above its first row
            visible: cell.header
            width: parent.width
            height: visible ? (cell.index === 0 ? 30 : 46) : 0
            verticalAlignment: Text.AlignBottom
            bottomPadding: 8
            leftPadding: 4
            text: (cell.row.group || "").toUpperCase()
            color: rl.theme.outline; font.pixelSize: 13; font.weight: Font.DemiBold; font.letterSpacing: 1.4
        }
        Rectangle {
            id: body
            width: parent.width
            height: cell.row.kind === "slider" ? 78 : cell.row.sub ? 66 : 56
            radius: 16
            color: cell.lit ? rl.tint.primary : cell.row.kind === "slider" ? Qt.alpha(rl.theme.onSurface, 0.05) : "transparent"
            Behavior on color { enabled: !app.still; ColorAnimation { duration: 100 } }
            opacity: rl.pickable(cell.row) ? 1 : 0.72
            RectangularShadow {
                z: -1
                anchors.fill: parent
                visible: cell.lit && !app.light && GraphicsInfo.api !== GraphicsInfo.Software
                radius: parent.radius; blur: 24
                color: Qt.alpha(rl.tint.primary, 0.45)
            }
            readonly property color ink: cell.lit ? rl.tint.onPrimary : cell.row.danger ? rl.theme.error : rl.theme.onSurface
            readonly property color soft: cell.lit ? Qt.alpha(rl.tint.onPrimary, 0.8) : rl.theme.onSurfaceVariant

            Icon {
                id: rowIcon
                anchors { left: parent.left; leftMargin: 16; top: parent.top; topMargin: cell.row.kind === "slider" ? 14 : (body.height - 22) / 2 }
                name: cell.row.icon || "ellipsis"; size: 22
                color: cell.lit ? rl.tint.onPrimary : cell.row.danger ? rl.theme.error : rl.theme.onSurfaceVariant
            }
            Text {
                anchors { left: parent.left; leftMargin: 54; right: rowEnd.left; rightMargin: 12; verticalCenter: rowIcon.verticalCenter
                          verticalCenterOffset: cell.row.sub && cell.row.kind !== "slider" ? -9 : 0 }
                text: cell.row.label || ""
                color: body.ink
                font.pixelSize: 19; font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            Text {  // a second, small line (the network you are on, a download's speed)
                visible: !!cell.row.sub && cell.row.kind !== "slider"
                anchors { left: parent.left; leftMargin: 54; right: rowEnd.left; rightMargin: 12; verticalCenter: rowIcon.verticalCenter; verticalCenterOffset: 12 }
                text: cell.row.sub || ""
                color: body.soft
                font.pixelSize: 14
                elide: Text.ElideRight
            }

            // What sits on the right: a switch, a value, a choice with arrows, or "working".
            Item {
                id: rowEnd
                anchors { right: parent.right; rightMargin: 16; verticalCenter: rowIcon.verticalCenter }
                width: cell.row.busy ? 22 : cell.row.on !== undefined ? 44 : cell.row.kind === "choice" ? choiceRow.implicitWidth : valueText.implicitWidth
                height: 26
                Icon {
                    id: spinner
                    visible: !!cell.row.busy
                    anchors.centerIn: parent
                    name: "loader"; size: 20
                    color: body.soft
                    RotationAnimator on rotation { running: spinner.visible; from: 0; to: 360; duration: 900; loops: Animation.Infinite }
                }
                Text {
                    id: valueText
                    visible: !cell.row.busy && cell.row.on === undefined && cell.row.kind !== "choice"
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right
                    text: cell.row.kind === "slider" ? (cell.row.valueText || ((cell.row.num || 0) + (cell.row.unit === undefined ? "%" : cell.row.unit)))
                                                     : (cell.row.value || "")
                    color: cell.row.kind === "slider" ? body.ink : body.soft
                    font.pixelSize: cell.row.kind === "slider" ? 18 : 16
                    font.weight: cell.row.kind === "slider" ? Font.DemiBold : Font.Normal
                    font.features: { "tnum": 1 }
                }
                Row {
                    id: choiceRow
                    visible: !cell.row.busy && cell.row.kind === "choice"
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8
                    readonly property int at: (cell.row.options || []).findIndex(o => o.v === cell.row.cur)
                    Icon { anchors.verticalCenter: parent.verticalCenter; name: "chevron-right"; size: 16; rotation: 180
                           color: body.soft; opacity: cell.lit ? 1 : 0.35 }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: ((cell.row.options || [])[choiceRow.at] || { t: "" }).t
                        color: body.ink
                        font.pixelSize: 17; font.weight: Font.DemiBold
                    }
                    Icon { anchors.verticalCenter: parent.verticalCenter; name: "chevron-right"; size: 16
                           color: body.soft; opacity: cell.lit ? 1 : 0.35 }
                }
                Rectangle {  // a switch
                    visible: !cell.row.busy && cell.row.on !== undefined
                    anchors.fill: parent
                    radius: 13
                    color: cell.row.on ? (cell.lit ? rl.tint.onPrimary : rl.tint.primary) : Qt.alpha(rl.theme.onSurface, 0.18)
                    Behavior on color { enabled: !app.still; ColorAnimation { duration: 140 } }
                    Rectangle {
                        width: 20; height: 20; radius: 10
                        anchors.verticalCenter: parent.verticalCenter
                        x: cell.row.on ? parent.width - width - 3 : 3
                        Behavior on x { enabled: !app.still; NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                        color: cell.row.on ? (cell.lit ? rl.tint.primary : rl.tint.onPrimary) : rl.theme.onSurface
                    }
                }
            }

            // A slider's track, under its label: drag or tap it too.
            Item {
                visible: cell.row.kind === "slider"
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 54; rightMargin: 18; bottomMargin: 14 }
                height: 22
                readonly property real frac: {
                    const lo = cell.row.min || 0, hi = cell.row.max === undefined ? 100 : cell.row.max
                    return hi > lo ? Math.max(0, Math.min(1, ((cell.row.num || 0) - lo) / (hi - lo))) : 0
                }
                Rectangle {
                    id: track
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
                    height: 6; radius: 3
                    color: cell.lit ? Qt.alpha(rl.tint.onPrimary, 0.28) : Qt.alpha(rl.theme.onSurface, 0.16)
                    Rectangle {
                        width: Math.max(height, parent.width * parent.parent.frac)
                        height: parent.height; radius: 3
                        color: cell.lit ? rl.tint.onPrimary : rl.tint.primary
                        opacity: cell.row.dim ? 0.4 : 1
                        Behavior on width { enabled: !app.still; NumberAnimation { duration: 90 } }
                    }
                }
                Rectangle {  // the knob
                    width: 18; height: 18; radius: 9
                    anchors.verticalCenter: parent.verticalCenter
                    x: Math.max(0, Math.min(track.width - width, track.width * parent.frac - width / 2))
                    Behavior on x { enabled: !app.still; NumberAnimation { duration: 90 } }
                    color: cell.lit ? rl.tint.onPrimary : rl.theme.onSurface
                    border.width: cell.lit ? 0 : 3
                    border.color: rl.tint.primary
                }
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -8
                    function to(mx) {
                        const r = cell.row, lo = r.min || 0, hi = r.max === undefined ? 100 : r.max, s = r.step || 5
                        const v = Math.round((lo + Math.max(0, Math.min(1, (mx - 8) / track.width)) * (hi - lo)) / s) * s
                        if (v !== r.num && r.set) r.set(v)
                    }
                    onPressed: mouse => { rl.currentIndex = cell.index; rl.forceActiveFocus(); to(mouse.x) }
                    onPositionChanged: mouse => { if (pressed) to(mouse.x) }
                }
            }
            TapHandler {
                onTapped: { rl.currentIndex = cell.index; rl.forceActiveFocus(); if (cell.row.kind !== "slider") rl.choose() }
            }
        }
    }
}
