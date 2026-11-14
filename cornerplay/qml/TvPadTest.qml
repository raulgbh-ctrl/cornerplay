import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import "glyphs.js" as Glyphs

// Settings > Controllers > Test buttons: the controller drawn on screen, every button and stick
// lighting up as you use it (SDL's view of it, the same games get). While it is open the pad
// steers nothing, so every button can be tried; hold B (or press Esc) to leave.
Rectangle {
    id: pt
    required property var theme
    required property var tint
    signal closed()
    visible: false
    color: theme.background
    z: 110

    property var down: ({})            // SDL button number -> pressed
    property var axes: [0, 0, 0, 0, 0, 0]
    property real holdB: 0             // 0..1 while B is held

    function show() { down = ({}); axes = [0, 0, 0, 0, 0, 0]; holdB = 0; pad.capture = true; visible = true; forceActiveFocus(); app.uiSound("select") }
    function close() { pad.capture = false; visible = false; holdTimer.stop(); app.uiSound("back"); closed() }
    Keys.onEscapePressed: close()
    Keys.onPressed: event => { event.accepted = true }

    Connections {
        target: pad
        enabled: pt.visible
        function onRawButton(b, isDown) {
            const d = Object.assign({}, pt.down); d[b] = isDown; pt.down = d
            if (b === 1) { if (isDown) { pt.holdB = 0; holdTimer.start() } else { holdTimer.stop(); pt.holdB = 0 } }
        }
        function onRawAxis(a, v) { if (a < 6) { const x = pt.axes.slice(); x[a] = v; pt.axes = x } }
    }
    Timer { id: holdTimer; interval: 30; repeat: true
            onTriggered: { pt.holdB = Math.min(1, pt.holdB + 0.03); if (pt.holdB >= 1) pt.close() } }

    readonly property real u: Math.min(width / 16, height / 10)   // the drawing's unit
    function on(b) { return !!down[b] }
    function axis(a) { return (axes[a] || 0) / 32767 }

    // One round button on the drawing.
    component Face: Item {
        property int b: 0
        property string glyph: "a"
        width: pt.u * 0.95; height: width
        readonly property bool lit: pt.on(b)
        scale: lit ? 0.88 : 1
        Behavior on scale { NumberAnimation { duration: 70 } }
        Rectangle { anchors.centerIn: parent; width: parent.width * 1.35; height: width; radius: width / 2
                    color: Qt.alpha(pt.tint.primary, 0.35); visible: parent.lit }
        PadButton { anchors.centerIn: parent; button: parent.glyph; style: pad.style; size: Math.round(parent.width) }
    }
    component Plain: Rectangle {
        property int b: 0
        property string text: ""
        property real w: pt.u
        readonly property bool lit: pt.on(b)
        width: Math.max(w, plainText.implicitWidth + pt.u * 0.35)
        radius: height / 2
        color: lit ? pt.tint.primary : Qt.alpha(pt.theme.onSurface, 0.12)
        border.width: 1; border.color: Qt.alpha("white", 0.12)
        Behavior on color { ColorAnimation { duration: 70 } }
        Text { id: plainText; anchors.centerIn: parent; text: parent.text; color: parent.lit ? pt.tint.onPrimary : pt.theme.onSurface
               font.pixelSize: Math.round(pt.u * (parent.text.length > 4 ? 0.22 : 0.3)); font.weight: Font.DemiBold }
    }
    component Stick: Rectangle {
        property int ax: 0
        property int b: 7
        width: pt.u * 1.9; height: width; radius: width / 2
        color: Qt.alpha(pt.theme.onSurface, 0.08)
        border.width: 2; border.color: pt.on(b) ? pt.tint.primary : Qt.alpha("white", 0.15)
        Rectangle {
            width: parent.width * 0.5; height: width; radius: width / 2
            x: (parent.width - width) / 2 + pt.axis(parent.ax) * (parent.width - width) / 2
            y: (parent.height - height) / 2 + pt.axis(parent.ax + 1) * (parent.height - height) / 2
            color: pt.on(parent.b) ? pt.tint.primary : pt.theme.onSurface
            opacity: Math.abs(pt.axis(parent.ax)) + Math.abs(pt.axis(parent.ax + 1)) > 0.15 || pt.on(parent.b) ? 1 : 0.55
        }
    }
    component Trigger: Column {
        property int ax: 4
        property string glyph: "lt"
        spacing: pt.u * 0.12
        Rectangle {
            width: pt.u * 1.6; height: pt.u * 0.22; radius: height / 2
            color: Qt.alpha(pt.theme.onSurface, 0.12)
            Rectangle { width: Math.max(height, parent.width * Math.max(0, pt.axis(parent.parent.ax))); height: parent.height; radius: height / 2
                        color: pt.tint.primary; visible: pt.axis(parent.parent.ax) > 0.02 }
        }
        PadButton { anchors.horizontalCenter: parent.horizontalCenter; button: parent.glyph; style: pad.style; size: Math.round(pt.u * 0.5)
                    opacity: pt.axis(parent.ax) > 0.5 ? 1 : 0.6 }
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: pt.u * 0.4
        Text { Layout.alignment: Qt.AlignHCenter; text: qsTr("Test your controller"); color: pt.theme.onSurface
               font.pixelSize: Math.round(pt.u * 0.55); font.weight: Font.Bold }
        Text { Layout.alignment: Qt.AlignHCenter
               text: pad.pads.length ? pad.pads.map(p => p.name).join("  ·  ") : qsTr("No controller connected")
               color: pt.theme.onSurfaceVariant; font.pixelSize: Math.round(pt.u * 0.3) }

        // The pad: a rounded body with everything where it sits on a real one.
        Item {
            Layout.preferredWidth: pt.u * 11
            Layout.preferredHeight: pt.u * 6.4
            Layout.alignment: Qt.AlignHCenter
            Rectangle {
                anchors.fill: parent
                anchors.topMargin: pt.u * 1.1
                radius: pt.u * 2
                color: Qt.alpha(pt.theme.surfaceContainerHigh, 0.9)
                border.width: 1; border.color: Qt.alpha("white", 0.08)
            }
            // Shoulders: triggers (with how far they are pulled) above the bumpers.
            Row {
                x: pt.u * 1.1; y: 0; spacing: pt.u * 0.4
                Trigger { ax: 4; glyph: "lt" }
                Plain { b: 9; text: Glyphs.label(pad.style, "lb"); w: pt.u * 1.3; height: pt.u * 0.55; anchors.bottom: parent.bottom }
            }
            Row {
                anchors.right: parent.right; anchors.rightMargin: pt.u * 1.1; y: 0; spacing: pt.u * 0.4; layoutDirection: Qt.RightToLeft
                Trigger { ax: 5; glyph: "rt" }
                Plain { b: 10; text: Glyphs.label(pad.style, "rb"); w: pt.u * 1.3; height: pt.u * 0.55; anchors.bottom: parent.bottom }
            }
            Stick { ax: 0; b: 7; x: pt.u * 1.3; y: pt.u * 1.9 }
            // D-pad
            Item {
                x: pt.u * 2.9; y: pt.u * 4.0; width: pt.u * 1.8; height: width
                Plain { b: 11; x: parent.width / 3; y: 0; w: parent.width / 3; height: width; radius: pt.u * 0.12 }
                Plain { b: 12; x: parent.width / 3; y: parent.height * 2 / 3; w: parent.width / 3; height: width; radius: pt.u * 0.12 }
                Plain { b: 13; x: 0; y: parent.height / 3; w: parent.width / 3; height: width; radius: pt.u * 0.12 }
                Plain { b: 14; x: parent.width * 2 / 3; y: parent.height / 3; w: parent.width / 3; height: width; radius: pt.u * 0.12 }
            }
            // Middle: View / Select, Guide, Menu / Start, Share
            Row {
                anchors.horizontalCenter: parent.horizontalCenter; y: pt.u * 2.3; spacing: pt.u * 0.3
                Plain { b: 4; text: Glyphs.label(pad.style, "back"); w: pt.u * 0.85; height: pt.u * 0.45 }
                Plain { b: 5; text: Glyphs.label(pad.style, "guide"); w: pt.u * 1.0; height: pt.u * 0.8; anchors.verticalCenter: parent.verticalCenter }
                Plain { b: 6; text: Glyphs.label(pad.style, "start"); w: pt.u * 0.85; height: pt.u * 0.45 }
            }
            Plain { b: 15; visible: Glyphs.label(pad.style, "share") !== "" || pt.on(15); text: Glyphs.label(pad.style, "share") || qsTr("Share"); w: pt.u * 0.9; height: pt.u * 0.4; anchors.horizontalCenter: parent.horizontalCenter; y: pt.u * 3.3 }
            // Face buttons, by position
            Item {
                x: parent.width - pt.u * 3.5; y: pt.u * 1.75; width: pt.u * 2.5; height: width
                Face { b: 3; glyph: "y"; x: (parent.width - width) / 2; y: 0 }
                Face { b: 0; glyph: "a"; x: (parent.width - width) / 2; y: parent.height - height }
                Face { b: 2; glyph: "x"; x: 0; y: (parent.height - height) / 2 }
                Face { b: 1; glyph: "b"; x: parent.width - width; y: (parent.height - height) / 2 }
            }
            // Back buttons (Steam Deck's L4 / L5 / R4 / R5, Xbox Elite's paddles), on pads that have them.
            Row {
                visible: Glyphs.of(pad.style).name === "Steam Deck" || pt.on(16) || pt.on(17) || pt.on(18) || pt.on(19)
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom; anchors.bottomMargin: pt.u * 0.35
                spacing: pt.u * 0.25
                Plain { b: 17; text: "L4"; w: pt.u * 0.8; height: pt.u * 0.4 }
                Plain { b: 19; text: "L5"; w: pt.u * 0.8; height: pt.u * 0.4 }
                Item { width: pt.u * 0.6; height: 1 }
                Plain { b: 18; text: "R5"; w: pt.u * 0.8; height: pt.u * 0.4 }
                Plain { b: 16; text: "R4"; w: pt.u * 0.8; height: pt.u * 0.4 }
            }
            Stick { ax: 2; b: 8; x: parent.width - pt.u * 4.8; y: pt.u * 4.2 }
        }

        // Leaving: hold B, with a bar that fills while it is held.
        Row {
            Layout.alignment: Qt.AlignHCenter
            spacing: pt.u * 0.2
            PadButton { anchors.verticalCenter: parent.verticalCenter; button: "b"; style: pad.style; size: 26 }
            Text { anchors.verticalCenter: parent.verticalCenter; text: qsTr("Hold to go back"); color: pt.theme.onSurfaceVariant; font.pixelSize: 16 }
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: pt.u * 1.6; height: 6; radius: 3
                color: Qt.alpha(pt.theme.onSurface, 0.15)
                Rectangle { width: parent.width * pt.holdB; height: parent.height; radius: 3; color: pt.tint.primary }
            }
            Text { anchors.verticalCenter: parent.verticalCenter; leftPadding: pt.u * 0.3; text: qsTr("or Esc"); color: pt.theme.outline; font.pixelSize: 14 }
        }
    }
}
