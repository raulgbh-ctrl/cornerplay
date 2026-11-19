import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Shapes
import "glyphs.js" as Glyphs

// Settings > Controllers > Test buttons: the controller drawn on screen, every button and stick
// lighting up as you use it (SDL's view of it, the same games get). While it is open the pad
// steers nothing, so every button can be tried; hold B (or press Esc) to leave.
Rectangle {
    id: pt
    TvShield {}  // clicks on the empty parts stop here, never reaching the covers behind
    required property var theme
    required property var tint
    signal closed()
    visible: false
    color: theme.background
    z: 110

    // The connected controller's own buttons (a PlayStation pad shows ✕ ○ □ △ here even when
    // Button prompts is set to Xbox), so the drawing matches what is in your hands.
    readonly property string padStyle: pad.padStyle || pad.style
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

    // How the drawing looks: the connected controller's own shape, in thin lines like Steam's
    // controller screen. Everything sits on a 160 x 100 grid (k: pixels per step), where it sits
    // on the real pad, and lights up while pressed.
    property string preview: ""   // another pad's drawing instead (design checks: tools/shoot.py)
    readonly property string shape: preview || pad.padShape || "xbox"
    readonly property string xboxBody: "M 46 14 C 60 10, 100 10, 114 14 C 132 18, 146 26, 152 44 C 158 62, 160 84, 150 94 C 142 101, 130 98, 122 88 C 114 78, 108 72, 98 72 L 62 72 C 52 72, 46 78, 38 88 C 30 98, 18 101, 10 94 C 0 84, 2 62, 8 44 C 14 26, 28 18, 46 14 Z"
    readonly property string psBody: "M 40 12 C 60 8, 100 8, 120 12 C 136 15, 146 24, 152 40 C 158 58, 162 86, 152 96 C 144 103, 132 99, 126 90 C 118 78, 112 70, 100 70 L 60 70 C 48 70, 42 78, 34 90 C 28 99, 16 103, 8 96 C -2 86, 2 58, 8 40 C 14 24, 24 15, 40 12 Z"
    readonly property var layouts: ({
        xbox: { body: xboxBody, sy: 6, lb: [34, 6], rb: [126, 6], ls: [40, 38], rs: [100, 58], dpad: [60, 58, 16],
                face: [120, 38, 20, 7], back: [66, 38], start: [94, 38], guide: [80, 26, 9], share: [80, 47] },
        switch: { body: xboxBody, sy: 6, lb: [34, 6], rb: [126, 6], ls: [40, 38], rs: [100, 58], dpad: [60, 58, 16],
                  face: [120, 38, 20, 7], back: [66, 34], start: [94, 34], guide: [88, 46, 7], share: [72, 46] },
        ps: { body: psBody,
              sy: 4, lb: [34, 4], rb: [126, 4], touch: [58, 14, 44, 26], ls: [62, 60], rs: [98, 60], dpad: [36, 40, 16],
              face: [124, 40, 20, 7], back: [50, 20], start: [110, 20], guide: [80, 51, 7], share: [80, 60] },
        steam: { body: xboxBody, sy: 6, lb: [34, 6], rb: [126, 6], pads: [[44, 40, 12, "circle"], [116, 40, 12, "circle"]],
                 dpad: [44, 40, 14], ls: [60, 60], face: [100, 60, 17, 5.5], back: [66, 30], start: [94, 30], guide: [80, 30, 8] },
        handheld: { body: "M 20 20 L 140 20 C 152 20, 159 28, 159 40 L 159 74 C 159 84, 152 90, 142 90 L 18 90 C 8 90, 1 84, 1 74 L 1 40 C 1 28, 8 20, 20 20 Z",
                    sy: 11, lb: [22, 11], rb: [138, 11], screen: [32, 27, 96, 56], ls: [16, 39], dpad: [16, 65, 15],
                    face: [144, 39, 19, 6], rs: [144, 66], back: [26, 83], start: [134, 83], guide: [26, 24, 4], share: [134, 24], paddles: true },
        deck: { body: "M 18 24 L 142 24 C 154 24, 160 32, 160 44 L 160 72 C 160 84, 152 90, 140 90 L 20 90 C 8 90, 0 84, 0 72 L 0 44 C 0 32, 6 24, 18 24 Z",
                sy: 15, lb: [22, 15], rb: [138, 15], screen: [36, 30, 88, 52], dpad: [11, 44, 13], ls: [27, 41],
                pads: [[19, 73, 14, "square"], [141, 73, 14, "square"]], face: [148, 46, 16, 5], rs: [131, 40],
                back: [29, 28], start: [131, 28], guide: [9, 30, 4], share: [151, 30], paddles: true },
        // Stadia, Luna, Shield: sticks side by side low, no touchpad.
        sym: { body: psBody, sy: 4, lb: [34, 4], rb: [126, 4], ls: [62, 60], rs: [98, 60], dpad: [36, 40, 16],
               face: [124, 40, 20, 7], back: [66, 34], start: [94, 34], guide: [80, 26, 8], share: [80, 46] },
        // Two Joy-Cons side by side (Switch's pair, or one held alone).
        joycons: { body: "M 46 16 L 30 16 C 19 16, 13 22, 13 32 L 13 84 C 13 92, 19 98, 30 98 L 46 98 Z M 114 16 L 130 16 C 141 16, 147 22, 147 32 L 147 84 C 147 92, 141 98, 130 98 L 114 98 Z",
                   sy: 8, lb: [26, 8], rb: [134, 8], ls: [31, 36], dpad: [31, 66, 18], face: [129, 36, 21, 7], rs: [129, 68],
                   back: [41, 22], start: [119, 22], guide: [124, 88, 6], share: [36, 88] },
        // GameCube (and Switch / Wii U pads in its shape): the big A, the C stick.
        gamecube: { body: xboxBody, sy: 6, lb: [34, 6], rb: [126, 6], ls: [40, 40], lsR: 9, rs: [100, 62], rsR: 6, dpad: [58, 62, 13],
                    faceAt: [["a", 0, -1, 120, 46, 11], ["b", 1, -1, 108, 51, 6.5], ["x", 2, -1, 135, 40, 7], ["y", 3, -1, 117, 31, 7]],
                    back: [72, 40], start: [80, 40], guide: [88, 40, 5] },
        // SNES-shaped, no sticks: 8BitDo SN30 / Zero / Micro / Lite / M30, Retro-Bit, Nintendo's SNES pad.
        snes: { body: "M 40 24 L 120 24 C 145 24, 158 40, 158 57 C 158 74, 145 90, 120 90 L 40 90 C 15 90, 2 74, 2 57 C 2 40, 15 24, 40 24 Z",
                sy: 16, lb: [34, 16], rb: [126, 16], dpad: [36, 57, 22], face: [124, 57, 26, 9],
                back: [70, 64], start: [90, 64], guide: [80, 46, 6], share: [80, 78] },
        // SNES-shaped with sticks and grips: 8BitDo SN30 Pro / Pro 2 / Pro 3 / Lite 2.
        sn30: { body: "M 38 18 L 122 18 C 146 18, 158 34, 158 50 C 158 62, 156 76, 150 88 C 146 96, 136 98, 130 90 C 124 82, 118 76, 108 76 L 52 76 C 42 76, 36 82, 30 90 C 24 98, 14 96, 10 88 C 4 76, 2 62, 2 50 C 2 34, 14 18, 38 18 Z",
                sy: 10, lb: [34, 10], rb: [126, 10], dpad: [34, 42, 19], face: [126, 42, 22, 7.5], ls: [60, 63], lsR: 7, rs: [100, 63], rsR: 7,
                back: [70, 40], start: [90, 40], guide: [80, 52, 6], share: [80, 30], paddles: true },
        // An arcade stick: the lever and two rows of four buttons.
        arcade: { body: "M 12 22 L 148 22 C 152 22, 155 25, 155 29 L 158 84 C 158 88, 155 92, 150 92 L 10 92 C 5 92, 2 88, 2 84 L 5 29 C 5 25, 8 22, 12 22 Z",
                  noShoulders: true, ls: [36, 60], lsR: 11, lever: true,
                  faceAt: [["x", 2, -1, 78, 50, 10], ["y", 3, -1, 94, 46, 10], ["rb", 10, -1, 110, 46, 10], ["lb", 9, -1, 126, 50, 10],
                           ["a", 0, -1, 76, 68, 10], ["b", 1, -1, 92, 64, 10], ["rt", -1, 5, 108, 64, 10], ["lt", -1, 4, 124, 68, 10]],
                  back: [64, 30], start: [80, 30], guide: [96, 30, 6] }
    })
    readonly property var lay: layouts[shape] || layouts.xbox
    readonly property color ink: Qt.alpha(theme.onSurface, 0.85)
    readonly property real lineW: 2

    // One round face button, its glyph inside.
    component Face: Item {
        property int b: 0
        property string glyph: "a"
        property real d: 7
        property int ax: -1          // a trigger drawn as a button (arcade sticks): lit when pulled
        width: d * stage.k; height: width
        readonly property bool lit: pt.on(b) || (ax >= 0 && pt.axis(ax) > 0.5)
        scale: lit ? 0.88 : 1
        Behavior on scale { NumberAnimation { duration: 70 } }
        Rectangle { anchors.centerIn: parent; width: parent.width * 1.4; height: width; radius: width / 2
                    color: Qt.alpha(pt.tint.primary, 0.4); visible: parent.lit }
        PadButton { anchors.centerIn: parent; button: parent.glyph; style: pt.padStyle; size: Math.round(parent.width) }
    }
    // A small button or a D-pad arm: an outline, filled while pressed.
    component Plain: Rectangle {
        property int b: 0
        property string text: ""
        property real w: pt.u
        readonly property bool lit: pt.on(b)
        width: Math.max(w, plainText.implicitWidth + pt.u * 0.3)
        radius: height / 2
        color: lit ? pt.tint.primary : "transparent"
        border.width: pt.lineW; border.color: lit ? pt.tint.primary : pt.ink
        Behavior on color { ColorAnimation { duration: 70 } }
        Text { id: plainText; anchors.centerIn: parent; text: parent.text; color: parent.lit ? pt.tint.onPrimary : pt.theme.onSurface
               font.pixelSize: Math.max(10, Math.round(parent.height * (parent.text.length > 3 ? 0.42 : 0.55))); font.weight: Font.DemiBold }
    }
    // A stick: its ring, and the cap where the stick is pushed (filled when clicked in).
    component Stick: Item {
        property int ax: 0
        property int b: 7
        property real r: 8
        property bool lever: false   // an arcade lever: the D-pad moves it too
        readonly property real dx: Math.max(-1, Math.min(1, pt.axis(ax) + (lever ? (pt.on(14) ? 1 : 0) - (pt.on(13) ? 1 : 0) : 0)))
        readonly property real dy: Math.max(-1, Math.min(1, pt.axis(ax + 1) + (lever ? (pt.on(12) ? 1 : 0) - (pt.on(11) ? 1 : 0) : 0)))
        width: r * 2 * stage.k; height: width
        Rectangle { anchors.fill: parent; radius: width / 2; color: "transparent"
                    border.width: pt.lineW; border.color: pt.on(parent.b) ? pt.tint.primary : pt.ink }
        Rectangle {
            width: parent.width * 0.56; height: width; radius: width / 2
            x: (parent.width - width) / 2 + parent.dx * (parent.width - width) / 2
            y: (parent.height - height) / 2 + parent.dy * (parent.height - height) / 2
            color: pt.on(parent.b) ? pt.tint.primary : "transparent"
            border.width: pt.lineW
            border.color: Math.abs(parent.dx) + Math.abs(parent.dy) > 0.15 || pt.on(parent.b) ? pt.tint.primary : pt.ink
        }
    }
    // A trigger: its glyph, and a bar for how far it is pulled.
    component Trigger: Row {
        property int ax: 4
        property string glyph: "lt"
        spacing: pt.u * 0.12
        PadButton { anchors.verticalCenter: parent.verticalCenter; button: parent.glyph; style: pt.padStyle; size: Math.round(stage.k * 5)
                    opacity: pt.axis(parent.ax) > 0.5 ? 1 : 0.7 }
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: stage.k * 16; height: stage.k * 3; radius: height / 2
            color: "transparent"; border.width: pt.lineW; border.color: pt.ink
            Rectangle { width: Math.max(height, parent.width * Math.max(0, pt.axis(parent.parent.ax))); height: parent.height; radius: height / 2
                        color: pt.tint.primary; visible: pt.axis(parent.parent.ax) > 0.02 }
        }
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: pt.u * 0.4
        Text { Layout.alignment: Qt.AlignHCenter; text: qsTr("Test your controller"); color: pt.theme.onSurface
               font.pixelSize: Math.round(pt.u * 0.55); font.weight: Font.Bold }
        Text { Layout.alignment: Qt.AlignHCenter
               text: pad.pads.length ? pad.pads.map(p => p.name).join("  ·  ") : qsTr("No controller connected")
               color: pt.theme.onSurfaceVariant; font.pixelSize: Math.round(pt.u * 0.3) }

        // The pad itself, drawn in lines.
        Item {
            id: stage
            readonly property real k: width / 160
            readonly property var lay: pt.lay
            function at(p, w, h) { return { x: p[0] * k - w / 2, y: p[1] * k - h / 2 } }
            // As big as fits between the title and the hint below (the title, hint and gaps take about 3.6 u).
            Layout.preferredWidth: Math.min(pt.u * 12, pt.width - 80, (pt.height - pt.u * 3.6 - 60) * 160 / 100)
            Layout.preferredHeight: Layout.preferredWidth * 100 / 160
            Layout.alignment: Qt.AlignHCenter

            Shape {
                width: 160; height: 100
                scale: stage.k
                transformOrigin: Item.TopLeft
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: pt.ink; strokeWidth: pt.lineW / stage.k
                    fillColor: Qt.alpha(pt.theme.onSurface, 0.035)
                    joinStyle: ShapePath.RoundJoin
                    PathSvg { path: stage.lay.body }
                }
            }
            // A handheld's screen, or a DualSense's touchpad (SDL button 20: it lights when clicked).
            Rectangle {
                readonly property var r: stage.lay.screen || stage.lay.touch
                visible: !!r
                x: r ? r[0] * stage.k : 0; y: r ? r[1] * stage.k : 0
                width: r ? r[2] * stage.k : 0; height: r ? r[3] * stage.k : 0
                radius: stage.k * (stage.lay.screen ? 3 : 5)
                color: pt.on(20) ? Qt.alpha(pt.tint.primary, 0.35) : "transparent"
                border.width: pt.lineW; border.color: pt.ink
            }
            // Trackpads (Steam Deck, Steam Controller).
            Repeater {
                model: stage.lay.pads || []
                Rectangle {
                    required property var modelData
                    readonly property real s: (modelData[3] === "circle" ? modelData[2] * 2 : modelData[2]) * stage.k
                    x: modelData[0] * stage.k - s / 2; y: modelData[1] * stage.k - s / 2
                    width: s; height: s
                    radius: modelData[3] === "circle" ? s / 2 : stage.k * 3
                    color: "transparent"; border.width: pt.lineW; border.color: Qt.alpha(pt.theme.onSurface, 0.5)
                }
            }
            // Shoulders: the trigger (with how far it is pulled) beside the bumper, above each side.
            Row {
                visible: !stage.lay.noShoulders
                readonly property var p: stage.lay.lb ? stage.at(stage.lay.lb, width, height) : ({ x: 0, y: 0 })
                x: Math.max(0, p.x); y: p.y; spacing: stage.k * 2
                Trigger { ax: 4; glyph: "lt" }
                Plain { b: 9; text: Glyphs.label(pt.padStyle, "lb"); w: stage.k * 12; height: stage.k * 5; anchors.verticalCenter: parent.verticalCenter }
            }
            Row {
                visible: !stage.lay.noShoulders
                readonly property var p: stage.lay.rb ? stage.at(stage.lay.rb, width, height) : ({ x: 0, y: 0 })
                x: Math.min(stage.width - width, p.x); y: p.y; spacing: stage.k * 2; layoutDirection: Qt.RightToLeft
                Trigger { ax: 5; glyph: "rt"; layoutDirection: Qt.RightToLeft }
                Plain { b: 10; text: Glyphs.label(pt.padStyle, "rb"); w: stage.k * 12; height: stage.k * 5; anchors.verticalCenter: parent.verticalCenter }
            }
            Stick { ax: 0; b: 7; visible: !!stage.lay.ls; r: stage.lay.lsR || 8; lever: !!stage.lay.lever
                    x: stage.lay.ls ? stage.lay.ls[0] * stage.k - width / 2 : 0; y: stage.lay.ls ? stage.lay.ls[1] * stage.k - height / 2 : 0 }
            Stick { ax: 2; b: 8; visible: !!stage.lay.rs; r: stage.lay.rsR || 8
                    x: stage.lay.rs ? stage.lay.rs[0] * stage.k - width / 2 : 0; y: stage.lay.rs ? stage.lay.rs[1] * stage.k - height / 2 : 0 }
            // D-pad: a cross of four arms.
            Item {
                visible: !!stage.lay.dpad
                readonly property var dp: stage.lay.dpad || [0, 0, 0]
                readonly property real s: dp[2] * stage.k
                x: dp[0] * stage.k - s / 2; y: dp[1] * stage.k - s / 2
                width: s; height: s
                Plain { b: 11; x: parent.width / 3; y: 0; w: parent.width / 3; height: width; radius: stage.k }
                Plain { b: 12; x: parent.width / 3; y: parent.height * 2 / 3; w: parent.width / 3; height: width; radius: stage.k }
                Plain { b: 13; x: 0; y: parent.height / 3; w: parent.width / 3; height: width; radius: stage.k }
                Plain { b: 14; x: parent.width * 2 / 3; y: parent.height / 3; w: parent.width / 3; height: width; radius: stage.k }
            }
            // Face buttons, by position.
            Item {
                visible: !stage.lay.faceAt
                readonly property var f: stage.lay.face || [0, 0, 0, 7]
                readonly property real s: f[2] * stage.k
                readonly property real d: f[3]
                x: f[0] * stage.k - s / 2; y: f[1] * stage.k - s / 2
                width: s; height: s
                Face { b: 3; glyph: "y"; d: parent.d; x: (parent.width - width) / 2; y: 0 }
                Face { b: 0; glyph: "a"; d: parent.d; x: (parent.width - width) / 2; y: parent.height - height }
                Face { b: 2; glyph: "x"; d: parent.d; x: 0; y: (parent.height - height) / 2 }
                Face { b: 1; glyph: "b"; d: parent.d; x: parent.width - width; y: (parent.height - height) / 2 }
            }
            // Pads whose buttons are not a diamond (GameCube, arcade sticks): each where it is.
            Repeater {
                model: stage.lay.faceAt || []
                Face {
                    required property var modelData
                    glyph: modelData[0]; b: modelData[1]; ax: modelData[2]; d: modelData[5]
                    x: modelData[3] * stage.k - width / 2; y: modelData[4] * stage.k - height / 2
                }
            }
            // View / Select, Menu / Start, Guide, Share: small pills (Guide round).
            Plain { b: 4; readonly property var p: stage.at(stage.lay.back, width, height); x: p.x; y: p.y
                    text: ""; w: stage.k * 7; height: stage.k * 3.4 }
            Plain { b: 6; readonly property var p: stage.at(stage.lay.start, width, height); x: p.x; y: p.y
                    text: ""; w: stage.k * 7; height: stage.k * 3.4 }
            Plain { b: 5; readonly property real d: (stage.lay.guide[2] || 8) * stage.k
                    x: stage.lay.guide[0] * stage.k - d / 2; y: stage.lay.guide[1] * stage.k - d / 2
                    text: ""; w: d; height: d }
            Plain { b: 15; visible: !!stage.lay.share
                    readonly property var p: stage.lay.share ? stage.at(stage.lay.share, width, height) : ({ x: 0, y: 0 }); x: p.x; y: p.y
                    text: ""; w: stage.k * 5; height: stage.k * 2.6 }
            // Back buttons (Steam Deck's L4 / L5 / R4 / R5, a handheld's, Xbox Elite's paddles), under the pad.
            Row {
                visible: !!stage.lay.paddles || pt.on(16) || pt.on(17) || pt.on(18) || pt.on(19)
                anchors.horizontalCenter: parent.horizontalCenter
                y: parent.height - height + stage.k * 1
                spacing: stage.k * 2
                Plain { b: 17; text: "L4"; w: stage.k * 9; height: stage.k * 4.5 }
                Plain { b: 19; text: "L5"; w: stage.k * 9; height: stage.k * 4.5 }
                Item { width: stage.k * 8; height: 1 }
                Plain { b: 18; text: "R5"; w: stage.k * 9; height: stage.k * 4.5 }
                Plain { b: 16; text: "R4"; w: stage.k * 9; height: stage.k * 4.5 }
            }
        }

        // Leaving: hold B, with a bar that fills while it is held.
        Row {
            Layout.alignment: Qt.AlignHCenter
            spacing: pt.u * 0.2
            PadButton { anchors.verticalCenter: parent.verticalCenter; button: "b"; style: pt.padStyle; size: 26 }
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
