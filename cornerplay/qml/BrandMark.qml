import QtQuick
import QtQuick.Shapes

// The Cornerplay mark: a C around a play button, flat, in the theme's colours (the same
// shapes as cornerplay.svg, on a 512 grid). play() animates it in (splash, TV intro): the C
// turns into place, then the play button grows. Animators run on Qt's render thread, so the
// start-up animation stays smooth while the library loads.
Item {
    id: bm
    property int size: 36
    property var theme: app.theme
    readonly property color accent: theme.primary  // the wallpaper's accent, grey included
    readonly property real u: size / 512
    width: size; height: size

    readonly property alias playing: intro.running
    function play() {
        if (app.light) return
        intro.stop()
        cLayer.rotation = -90; cLayer.opacity = 0; tri.scale = 0
        intro.start()
    }

    Rectangle {
        anchors.fill: parent
        radius: bm.size * 0.227
        // Dark themes: a lifted surface. Light themes: a deep tile, so the light C still reads.
        color: bm.theme.dark === false ? Qt.darker(bm.accent, 3.2) : bm.theme.surfaceContainerHighest
    }
    Shape {
        id: cLayer
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: "transparent"
            strokeColor: bm.theme.dark === false ? "#f4ede4" : bm.theme.onSurface
            strokeWidth: 56 * bm.u
            capStyle: ShapePath.RoundCap
            PathAngleArc { centerX: 256 * bm.u; centerY: 256 * bm.u; radiusX: 128 * bm.u; radiusY: 128 * bm.u
                           startAngle: 45; sweepAngle: 270 }
        }
    }
    Shape {
        id: tri
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        transformOrigin: Item.Center
        ShapePath {
            fillColor: bm.accent
            strokeColor: bm.accent
            strokeWidth: 22 * bm.u
            joinStyle: ShapePath.RoundJoin
            startX: 238 * bm.u; startY: 206 * bm.u
            PathLine { x: 238 * bm.u; y: 306 * bm.u }
            PathLine { x: 318 * bm.u; y: 256 * bm.u }
            PathLine { x: 238 * bm.u; y: 206 * bm.u }
        }
    }

    SequentialAnimation {
        id: intro
        ParallelAnimation {
            RotationAnimator { target: cLayer; from: -90; to: 0; duration: 520; easing.type: Easing.OutCubic }
            OpacityAnimator { target: cLayer; from: 0; to: 1; duration: 260 }
        }
        ScaleAnimator { target: tri; from: 0; to: 1; duration: 320; easing.type: Easing.OutBack; easing.overshoot: 1.6 }
    }
}
