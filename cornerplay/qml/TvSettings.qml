import QtQuick
import QtQuick.Effects
import QtQuick.Layouts

// TV mode's Settings, like SteamOS's: the sections down the left, their controls on the right.
// Up / down move, right or A goes into a section, left or B comes back out; LB / RB jump
// between sections from anywhere. Everything the PC can do from the sofa (TvControls.qml).
Rectangle {
    id: ts
    objectName: "tvSettings"
    required property var theme
    required property var tint
    required property var controls
    property var batt: ({})
    signal closed()
    visible: false
    color: theme.background

    property int at: 0
    readonly property var sec: controls.sections[at] || ({})
    property var rows: []
    function secId() { return (controls.sections[at] || {}).id || "" }  // not sec: in onAtChanged it may still be the old one
    function rebuild() { if (visible) rows = controls.section(secId(), batt) }
    onAtChanged: { rows = controls.section(secId(), batt); content.first(); content.positionViewAtBeginning() }
    Connections { target: app; enabled: ts.visible
                  function onSystemChanged() { ts.rebuild() }
                  function onSettingsChanged() { Qt.callLater(ts.rebuild) }
                  function onProfilesChanged() { ts.rebuild() } }
    Connections { target: ts.controls; enabled: ts.visible; function onArmedChanged() { ts.rebuild() } }
    // The state is read again now and then: a controller that just connected, a new network.
    Timer { interval: 6000; repeat: true; running: ts.visible; onTriggered: app.refreshSystem() }

    function show(id) {
        const i = controls.sections.findIndex(s => s.id === id)
        app.refreshSystem()
        if (id === "network") app.scanNetworks()
        at = Math.max(0, i)
        rows = controls.section(secId(), batt)
        visible = true
        app.uiSound("select")
        if (i >= 0) { content.first(); content.forceActiveFocus() } else nav.forceActiveFocus()
    }
    function close() { app.uiSound("back"); visible = false; closed() }
    function go(i) {
        if (i === at || i < 0 || i >= controls.sections.length) return
        at = i
        nav.currentIndex = i
        if (secId() === "network") app.scanNetworks()
    }

    // The art of the game you were on, faint, so it still feels like TV mode.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: Qt.alpha(ts.tint.primary, 0.10) }
            GradientStop { position: 0.45; color: "transparent" }
        }
    }
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: w => w.accepted = true }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Math.round(Math.min(64, ts.width * 0.04))
        anchors.bottomMargin: 84
        spacing: Math.round(Math.min(56, ts.width * 0.035))

        // ---------------------------------------------------- sections
        ColumnLayout {
            Layout.preferredWidth: Math.round(Math.min(400, Math.max(270, ts.width * 0.27)))
            Layout.maximumWidth: Layout.preferredWidth
            Layout.fillWidth: false
            Layout.fillHeight: true
            spacing: 22
            RowLayout {
                spacing: 14
                Icon { name: "settings-2"; size: 30; color: ts.tint.primary }
                Text { text: qsTr("Settings"); color: ts.theme.onSurface; font.pixelSize: 34; font.weight: Font.Bold }
            }
            ListView {
                id: nav
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: ts.controls.sections
                currentIndex: ts.at
                spacing: 6
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                keyNavigationEnabled: false
                delegate: Rectangle {
                    id: navRow
                    required property var modelData
                    required property int index
                    readonly property bool cur: index === ts.at
                    readonly property bool lit: cur && nav.activeFocus
                    width: nav.width
                    height: 58
                    radius: 18
                    color: lit ? ts.tint.primary : cur ? Qt.alpha(ts.tint.primary, 0.16) : navHover.hovered ? Qt.alpha(ts.theme.onSurface, 0.06) : "transparent"
                    Behavior on color { enabled: !app.light; ColorAnimation { duration: 110 } }
                    RectangularShadow {
                        z: -1
                        anchors.fill: parent
                        visible: navRow.lit && !app.light && GraphicsInfo.api !== GraphicsInfo.Software
                        radius: parent.radius; blur: 24
                        color: Qt.alpha(ts.tint.primary, 0.45)
                    }
                    Rectangle {  // the open section's mark, while you are in its rows
                        visible: navRow.cur && !navRow.lit
                        anchors { left: parent.left; leftMargin: 4; verticalCenter: parent.verticalCenter }
                        width: 4; height: 26; radius: 2
                        color: ts.tint.primary
                    }
                    Icon {
                        anchors { left: parent.left; leftMargin: 20; verticalCenter: parent.verticalCenter }
                        name: navRow.modelData.icon; size: 22
                        color: navRow.lit ? ts.tint.onPrimary : navRow.cur ? ts.tint.primary : ts.theme.onSurfaceVariant
                    }
                    Text {
                        anchors { left: parent.left; leftMargin: 58; right: parent.right; rightMargin: 16; verticalCenter: parent.verticalCenter }
                        text: navRow.modelData.label
                        color: navRow.lit ? ts.tint.onPrimary : ts.theme.onSurface
                        font.pixelSize: 19; font.weight: navRow.cur ? Font.DemiBold : Font.Medium
                        elide: Text.ElideRight
                    }
                    HoverHandler { id: navHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: { ts.go(navRow.index); content.first(); content.forceActiveFocus() } }
                }
                Keys.onUpPressed: { ts.go(Math.max(0, ts.at - 1)); app.uiSound("move") }
                Keys.onDownPressed: { ts.go(Math.min(ts.controls.sections.length - 1, ts.at + 1)); app.uiSound("move") }
                Keys.onRightPressed: { content.first(); content.forceActiveFocus(); app.uiSound("move") }
                Keys.onReturnPressed: { content.first(); content.forceActiveFocus(); app.uiSound("select") }
                Keys.onEnterPressed: { content.first(); content.forceActiveFocus(); app.uiSound("select") }
                Keys.onEscapePressed: ts.close()
            }
        }

        // ---------------------------------------------------- the section's rows
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 28
            color: Qt.alpha(ts.theme.surfaceContainerLow, 0.8)
            border.width: 1; border.color: Qt.alpha("white", 0.06)
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 28
                spacing: 16
                RowLayout {
                    spacing: 14
                    Icon { name: ts.sec.icon || ""; size: 26; color: ts.tint.primary }
                    Text { text: ts.sec.label || ""; color: ts.theme.onSurface; font.pixelSize: 26; font.weight: Font.DemiBold }
                }
                TvRowList {
                    id: content
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    theme: ts.theme
                    tint: ts.tint
                    rows: ts.rows
                    onPicked: row => ts.controls.run(row)
                    onAlt: row => ts.controls.runAlt(row)
                    catchLeft: true
                    catchBack: true
                    onEdge: { nav.forceActiveFocus(); app.uiSound("move") }
                    onBack: { nav.forceActiveFocus(); app.uiSound("back") }
                }
            }
        }
    }

    // LB / RB: the next section from anywhere; the Guide menus still open over Settings.
    Keys.onPressed: event => {
        if (event.key === Qt.Key_PageUp || event.key === Qt.Key_PageDown) {
            const had = content.activeFocus
            ts.go(Math.max(0, Math.min(controls.sections.length - 1, at + (event.key === Qt.Key_PageDown ? 1 : -1))))
            app.uiSound("move")
            if (had) content.first()
            event.accepted = true
        }
    }

    // What the buttons do here: only what works on the focused row.
    Row {
        anchors { right: parent.right; bottom: parent.bottom; margins: 30 }
        spacing: 22
        Repeater {
            model: {
                const r = content.current, inRows = content.activeFocus
                const adj = inRows && (r.kind === "slider" || r.kind === "choice")
                const out = pad.connected || pad.deck
                    ? [{ b: ["a"], t: inRows ? (r.kind === "slider" && r.press ? qsTr("Mute") : qsTr("Choose")) : qsTr("Open") },
                       adj ? { b: ["↔"], t: qsTr("Change"), pad: true } : null,
                       inRows && r.alt ? { b: ["x"], t: r.alt } : null,
                       { b: ["lb", "rb"], t: qsTr("Section") }, { b: ["b"], t: qsTr("Back") }]
                    : [{ k: qsTr("Enter"), t: qsTr("Choose") }, adj ? { k: "← →", t: qsTr("Change") } : null,
                       inRows && r.alt ? { k: "F2", t: r.alt } : null,
                       { k: qsTr("PgUp / PgDn"), t: qsTr("Section") }, { k: qsTr("Esc"), t: qsTr("Back") }]
                return out.filter(h => h)
            }
            Row {
                required property var modelData
                spacing: 8
                Repeater { model: parent.modelData.pad ? [] : (parent.modelData.b || [])
                           PadButton { required property string modelData; button: modelData; style: pad.style; size: 26 } }
                Rectangle { visible: !!parent.modelData.k || !!parent.modelData.pad; height: 26; radius: 6; width: kk.implicitWidth + 16
                            color: Qt.alpha(ts.theme.surfaceContainerHighest, 0.9); border.width: 1; border.color: ts.theme.outlineVariant
                            Text { id: kk; anchors.centerIn: parent; text: parent.parent.modelData.k || (parent.parent.modelData.pad ? parent.parent.modelData.b[0] : "")
                                   color: ts.theme.onSurface; font.pixelSize: 12; font.weight: Font.DemiBold } }
                Text { anchors.verticalCenter: parent.verticalCenter; text: parent.modelData.t; color: ts.theme.onSurfaceVariant; font.pixelSize: 15 }
            }
        }
    }
}
