import QtQuick

// A grey placeholder shape with a soft light sweeping across it: where something is about to
// appear (a cover, a row, a line of text), so the screen keeps its shape while it loads.
Rectangle {
    id: sk
    required property var theme
    radius: 10
    color: Qt.alpha(sk.theme.onSurface, 0.07)
    clip: true
    Rectangle {
        visible: !app.still
        width: sk.width * 0.6; height: sk.height
        rotation: 0
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.5; color: Qt.alpha(sk.theme.onSurface, 0.07) }
            GradientStop { position: 1.0; color: "transparent" }
        }
        NumberAnimation on x {
            running: sk.visible && !app.still
            from: -sk.width * 0.6; to: sk.width
            duration: 1300; loops: Animation.Infinite; easing.type: Easing.InOutSine
        }
    }
}
