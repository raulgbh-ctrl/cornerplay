import QtQuick
import QtQuick.Effects
import QtQuick.Shapes

// A little picture for an empty screen, drawn in the logo's soft, rounded strokes and in the
// theme's colours (so it follows the wallpaper). kind: "library" (nothing yet: a screen
// waiting with the mark on it), "list" (an empty list: a stack of cards and a plus), "search"
// (nothing matches: a magnifier with sparks), "cat" (nothing going on: a cat asleep on a
// cushion) or "lamp" (nothing yet: a reading lamp's warm pool of light).
Item {
    id: es
    property string kind: "library"
    property var theme: app.theme
    readonly property color ink: Qt.alpha(theme.onSurfaceVariant, 0.55)
    readonly property color accent: theme.primary
    readonly property real line: 5
    implicitWidth: 240; implicitHeight: 160

    // The season's small touch (Seasonal.qml): snow, leaves, petals or fireflies.
    Seasonal { anchors.fill: parent; anchors.margins: -30; theme: es.theme; count: 10; z: 5 }
    // The floor line all three scenes stand on.
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: Qt.alpha(es.ink, 0.6); strokeWidth: es.line; fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            startX: 46; startY: 146
            PathLine { x: 194; y: 146 }
        }
    }

    // --- nothing in the library yet: a screen with the mark, waiting
    Item {
        anchors.fill: parent
        visible: es.kind === "library"
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {  // the screen
                strokeColor: es.ink; strokeWidth: es.line; fillColor: Qt.alpha(es.theme.surfaceContainerHigh, 0.6)
                joinStyle: ShapePath.RoundJoin
                PathRectangle { x: 62; y: 18; width: 116; height: 82; radius: 18 }
            }
            ShapePath {  // its stand
                strokeColor: es.ink; strokeWidth: es.line; fillColor: "transparent"
                capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
                startX: 120; startY: 102
                PathLine { x: 120; y: 128 }
                PathMove { x: 98; y: 130 }
                PathLine { x: 142; y: 130 }
            }
        }
        BrandMark { x: 120 - size / 2; y: 59 - size / 2; size: 46; theme: es.theme }
    }

    // --- an empty list: a stack of cards, and a plus to add one
    Item {
        anchors.fill: parent
        visible: es.kind === "list"
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: Qt.alpha(es.ink, 0.5); strokeWidth: es.line - 1; fillColor: "transparent"
                PathRectangle { x: 104; y: 18; width: 62; height: 88; radius: 12 }
            }
            ShapePath {
                strokeColor: Qt.alpha(es.ink, 0.75); strokeWidth: es.line - 0.5; fillColor: Qt.alpha(es.theme.surfaceContainerHigh, 0.5)
                PathRectangle { x: 90; y: 28; width: 62; height: 88; radius: 12 }
            }
            ShapePath {
                strokeColor: es.ink; strokeWidth: es.line; fillColor: es.theme.surfaceContainerHigh
                PathRectangle { x: 76; y: 38; width: 62; height: 88; radius: 12 }
            }
            ShapePath {  // the plus, in the accent
                strokeColor: es.accent; strokeWidth: es.line + 1; fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                startX: 107; startY: 68
                PathLine { x: 107; y: 96 }
                PathMove { x: 93; y: 82 }
                PathLine { x: 121; y: 82 }
            }
        }
    }

    // --- nothing matches: a magnifier, and the logo's sparks
    Item {
        anchors.fill: parent
        visible: es.kind === "search"
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {  // the lens
                strokeColor: es.ink; strokeWidth: es.line + 1; fillColor: Qt.alpha(es.theme.surfaceContainerHigh, 0.55)
                PathAngleArc { centerX: 108; centerY: 66; radiusX: 34; radiusY: 34; startAngle: 0; sweepAngle: 360 }
            }
            ShapePath {  // the handle
                strokeColor: es.ink; strokeWidth: es.line + 6; fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                startX: 133; startY: 91
                PathLine { x: 154; y: 114 }
            }
            ShapePath {  // the sparks, like the logo's
                strokeColor: es.accent; strokeWidth: es.line; fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                startX: 152; startY: 30
                PathLine { x: 160; y: 18 }
                PathMove { x: 160; y: 44 }
                PathLine { x: 174; y: 38 }
            }
            ShapePath {  // a small play button inside the lens
                strokeColor: "transparent"; fillColor: Qt.alpha(es.accent, 0.85)
                joinStyle: ShapePath.RoundJoin
                startX: 100; startY: 54
                PathLine { x: 121; y: 66 }
                PathLine { x: 100; y: 78 }
                PathLine { x: 100; y: 54 }
            }
        }
    }

    // --- nothing going on: a cat curled up asleep on a cushion, with a "z" drifting up
    Item {
        anchors.fill: parent
        visible: es.kind === "cat"
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {  // the cushion
                strokeColor: Qt.alpha(es.ink, 0.7); strokeWidth: es.line - 1; fillColor: Qt.alpha(es.accent, 0.18)
                joinStyle: ShapePath.RoundJoin
                PathRectangle { x: 64; y: 116; width: 112; height: 26; radius: 13 }
            }
            ShapePath {  // the body, curled into a loaf
                strokeColor: es.ink; strokeWidth: es.line; fillColor: es.theme.surfaceContainerHigh
                joinStyle: ShapePath.RoundJoin
                startX: 80; startY: 118
                PathCubic { x: 120; y: 70; control1X: 76; control1Y: 88; control2X: 96; control2Y: 70 }
                PathCubic { x: 166; y: 118; control1X: 148; control1Y: 70; control2X: 168; control2Y: 92 }
                PathLine { x: 80; y: 118 }
            }
            ShapePath {  // the head resting on the front, ears up
                strokeColor: es.ink; strokeWidth: es.line; fillColor: es.theme.surfaceContainerHigh
                joinStyle: ShapePath.RoundJoin
                startX: 84; startY: 116
                PathCubic { x: 86; y: 92; control1X: 76; control1Y: 106; control2X: 78; control2Y: 96 }
                PathLine { x: 90; y: 80 }
                PathLine { x: 98; y: 90 }
                PathLine { x: 108; y: 88 }
                PathLine { x: 116; y: 78 }
                PathLine { x: 118; y: 94 }
                PathCubic { x: 112; y: 116; control1X: 124; control1Y: 104; control2X: 120; control2Y: 114 }
                PathLine { x: 84; y: 116 }
            }
            ShapePath {  // closed eyes: two little smiles
                strokeColor: es.ink; strokeWidth: es.line - 2; fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                startX: 91; startY: 102
                PathQuad { x: 99; y: 102; controlX: 95; controlY: 106 }
                PathMove { x: 104; y: 102 }
                PathQuad { x: 112; y: 102; controlX: 108; controlY: 106 }
            }
            ShapePath {  // the tail, wrapped round the front
                strokeColor: es.ink; strokeWidth: es.line; fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                startX: 164; startY: 114
                PathCubic { x: 120; y: 118; control1X: 172; control1Y: 126; control2X: 140; control2Y: 128 }
            }
        }
        Text {  // the "z", in the accent, rising and fading
            id: zz
            text: "z"
            color: es.accent
            font.pixelSize: 20; font.weight: Font.Bold; font.family: "Nunito"
            x: 126; y: 58
            SequentialAnimation on y {
                running: zz.visible && !app.still; loops: Animation.Infinite
                NumberAnimation { from: 62; to: 30; duration: 2600; easing.type: Easing.OutSine }
                PauseAnimation { duration: 600 }
            }
            SequentialAnimation on opacity {
                running: zz.visible && !app.still; loops: Animation.Infinite
                NumberAnimation { from: 0.9; to: 0; duration: 2600 }
                PauseAnimation { duration: 600 }
            }
        }
    }

    // --- nothing yet: a reading lamp and the warm pool of light under it
    Item {
        anchors.fill: parent
        visible: es.kind === "lamp"
        Rectangle {  // the light on the floor
            x: 70; y: 128; width: 120; height: 26; radius: 13
            color: Qt.alpha(es.accent, 0.22)
        }
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {  // the shade, lit from inside
                strokeColor: es.ink; strokeWidth: es.line; fillColor: Qt.alpha(es.accent, 0.35)
                joinStyle: ShapePath.RoundJoin
                startX: 106; startY: 28
                PathLine { x: 154; y: 28 }
                PathLine { x: 168; y: 64 }
                PathLine { x: 92; y: 64 }
                PathLine { x: 106; y: 28 }
            }
            ShapePath {  // the stand and its foot
                strokeColor: es.ink; strokeWidth: es.line; fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                startX: 130; startY: 64
                PathLine { x: 130; y: 140 }
                PathMove { x: 112; y: 142 }
                PathLine { x: 148; y: 142 }
            }
            ShapePath {  // the beam, faint
                strokeColor: "transparent"; fillColor: Qt.alpha(es.accent, 0.10)
                startX: 96; startY: 66
                PathLine { x: 164; y: 66 }
                PathLine { x: 186; y: 136 }
                PathLine { x: 74; y: 136 }
                PathLine { x: 96; y: 66 }
            }
        }
    }
}
