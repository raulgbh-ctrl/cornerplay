import QtQuick

// Look > Fireflies (Settings > Appearance): in the evening, while the theme is warmed for the
// night, a few specks of lamplight drift slowly behind the library and glow on and off.
// Cheap by design: a dozen plain circles, one animation each, all stopped when `awake` is false.
Item {
    id: flies
    property var theme: app.theme
    property int count: 12
    property bool awake: true
    readonly property color tint: Qt.lighter(theme.primary, 1.35)
    clip: true

    Repeater {
        model: flies.count
        Item {
            id: fly
            required property int index
            readonly property real seed: ((index * 7919) % 101) / 101
            readonly property real seed2: ((index * 104729) % 89) / 89
            property real t: seed * Math.PI * 2
            NumberAnimation on t {
                running: flies.visible && flies.awake && !app.still
                from: fly.seed * Math.PI * 2; to: fly.seed * Math.PI * 2 + Math.PI * 2
                duration: 26000 + fly.seed2 * 22000; loops: Animation.Infinite
            }
            width: 5 + seed2 * 4; height: width
            // a slow loop around its own spot, wider sideways than up and down
            x: flies.width * (0.06 + 0.88 * seed) + Math.cos(t) * (40 + 60 * seed2) - width / 2
            y: flies.height * (0.15 + 0.75 * seed2) + Math.sin(t * 2) * (18 + 24 * seed) - height / 2
            // glowing on and off with the same clock, each at its own moment
            opacity: Math.max(0, Math.sin(t * 3 + seed * 9)) * 0.85
            Rectangle {  // the soft halo
                anchors.centerIn: parent
                width: parent.width * 4; height: width; radius: width / 2
                color: Qt.alpha(flies.tint, 0.12)
            }
            Rectangle { anchors.fill: parent; radius: width / 2; color: flies.tint }
        }
    }
}
