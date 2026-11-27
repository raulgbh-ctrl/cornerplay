import QtQuick

// A small seasonal touch over the empty-screen scenes and the splash (Settings > Appearance,
// on by default), drawn in the theme's colours: snow and a string of little lights in winter
// (December to 6 January), falling leaves in autumn (15 October to 10 November; orange and
// violet for Halloween, 24 to 31 October, the same dates as theme.season), drifting petals
// in spring (20 March to May). Otherwise nothing.
Item {
    id: season
    property var theme: app.theme
    property int count: 14
    property string force: ""
    property bool awake: true   // false: everything holds still (the window is in the background, a game is on)   // a season to show whatever the date (for trying it out)
    readonly property string kind: {
        if (force) return force
        if (!app.settingsMap.seasonal) return ""
        const d = new Date(), m = d.getMonth() + 1, day = d.getDate()
        if (m === 12 || (m === 1 && day <= 6)) return "winter"
        if (m === 10 && day >= 24) return "halloween"
        if ((m === 10 && day >= 15) || (m === 11 && day <= 10)) return "autumn"
        if ((m === 3 && day >= 20) || m === 4 || m === 5) return "spring"
        return ""
    }
    readonly property bool leafy: kind === "autumn" || kind === "halloween" || kind === "spring"
    visible: kind !== ""
    clip: true

    // Winter: a string of little lights along the top, twinkling one after another.
    Row {
        visible: season.kind === "winter"
        anchors.horizontalCenter: parent.horizontalCenter
        y: 6
        spacing: Math.max(10, season.width / 14)
        Repeater {
            model: season.kind === "winter" ? Math.max(4, Math.floor(season.width / Math.max(10, season.width / 14)) - 1) : 0
            Rectangle {
                required property int index
                width: 7; height: 9; radius: 4
                y: Math.sin(index * 0.9) * 4
                color: [season.theme.primary, Qt.lighter(season.theme.primary, 1.4), season.theme.onSurfaceVariant][index % 3]
                SequentialAnimation on opacity {
                    running: season.visible && season.awake && !app.still; loops: Animation.Infinite
                    PauseAnimation { duration: (index * 230) % 1600 }
                    NumberAnimation { to: 0.3; duration: 700 }
                    NumberAnimation { to: 1.0; duration: 700 }
                }
            }
        }
    }

    // Falling and drifting things: snow, leaves or petals.
    Repeater {
        model: season.kind !== "" ? season.count : 0
        Item {
            id: bit
            required property int index
            readonly property real seed: ((index * 7919) % 97) / 97
            width: season.kind === "winter" ? 5 + seed * 4 : 9 + seed * 6
            height: width
            x: seed * season.width
            y: -20
            opacity: 0.85
            Rectangle {  // snow: dots; leaves and petals: a rounded leaf shape
                anchors.fill: parent
                radius: season.kind === "winter" ? width / 2 : width * 0.1
                rotation: 45
                color: season.kind === "winter" ? Qt.alpha(season.theme.onSurface, 0.75)
                     : season.kind === "autumn" ? [season.theme.primary, Qt.darker(season.theme.primary, 1.3), "#c8813a"][bit.index % 3]
                     : season.kind === "halloween" ? ["#ff7a1a", "#9b5de5", "#ffb347"][bit.index % 3]
                     : Qt.alpha(Qt.tint(season.theme.primary, "#80ffb1c8"), 0.85)  // spring
                // a leaf's point: one square corner, the others rounded
                Rectangle { visible: season.leafy; width: parent.width / 2; height: width
                            color: parent.color; anchors { right: parent.right; top: parent.top } }
            }
            // Falling: down, with a sway.
            SequentialAnimation on y {
                running: season.visible && season.awake && !app.still; loops: Animation.Infinite
                PauseAnimation { duration: bit.seed * 6000 }
                NumberAnimation { from: -20; to: season.height + 20; duration: 7000 + bit.seed * 6000 }
            }
            SequentialAnimation on x {
                running: season.visible && season.awake && !app.still; loops: Animation.Infinite
                NumberAnimation { from: bit.seed * season.width; to: bit.seed * season.width + 26; duration: 2200; easing.type: Easing.InOutSine }
                NumberAnimation { from: bit.seed * season.width + 26; to: bit.seed * season.width; duration: 2200; easing.type: Easing.InOutSine }
            }
            RotationAnimation on rotation {
                running: season.visible && season.awake && season.leafy && !app.still
                loops: Animation.Infinite; from: 0; to: 360; duration: 5000 + bit.seed * 4000
            }
        }
    }
}
