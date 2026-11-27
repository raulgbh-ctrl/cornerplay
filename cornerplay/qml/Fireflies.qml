import QtQuick
import QtQuick.Effects

// Look > Fireflies (Settings > Appearance): in the evening, while the theme is warmed for the
// night, a few specks of lamplight drift slowly behind the library and glow on and off.
// Cheap by design: a dozen plain circles on one slow clock, stopped when `awake` is false.
Item {
    id: flies
    property var theme: app.theme
    property int count: 9
    property bool awake: true
    readonly property color tint: Qt.lighter(theme.primary, 1.35)
    clip: true
    property real clock: 0   // seconds
    Timer {
        interval: 83; repeat: true
        running: flies.visible && flies.awake && !app.still
        onTriggered: flies.clock += 0.083
    }

    Repeater {
        model: flies.count
        Item {
            id: fly
            required property int index
            readonly property real seed: ((index * 7919) % 101) / 101
            readonly property real seed2: ((index * 104729) % 89) / 89
            // One shared slow clock (below) moves them all: 12 steps a second instead of the
            // screen's 60, so the window is redrawn a fifth as often. They drift too slowly to tell.
            readonly property real t: seed * Math.PI * 2 + flies.clock * Math.PI * 2 / (26 + seed2 * 22)
            width: 7 + seed2 * 5; height: width
            // a slow loop around its own spot, wider sideways than up and down
            x: flies.width * (0.06 + 0.88 * seed) + Math.cos(t) * (40 + 60 * seed2) - width / 2
            y: flies.height * (0.15 + 0.75 * seed2) + Math.sin(t * 2) * (18 + 24 * seed) - height / 2
            // glowing on and off with the same clock, each at its own moment
            opacity: Math.max(0, Math.sin(t * 3 + seed * 9)) * 0.85
            RectangularShadow {  // the soft glow around it, fading out to nothing
                anchors.fill: parent
                radius: width / 2
                blur: width * 2.2
                spread: 2
                color: Qt.alpha(flies.tint, 0.75)
            }
            Rectangle { anchors.fill: parent; radius: width / 2; color: flies.tint }
        }
    }
}
