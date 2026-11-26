import QtQuick
import QtQuick.Controls.Basic

// The scrollbar, in the same family as KSlider: at rest a quiet thin pill; pointed at, a soft
// sunk track appears and the thumb swells and takes the slider's warm accent gradient; held, it
// gets the slider's halo. Vertical or horizontal alike.
ScrollBar {
    id: sb
    readonly property var theme: app.theme
    readonly property bool upright: orientation === Qt.Vertical
    readonly property bool lively: hovered || pressed
    readonly property real thick: pressed ? 12 : hovered ? 10 : 6
    implicitWidth: upright ? thick + 2 * padding : 100
    implicitHeight: upright ? 100 : thick + 2 * padding
    visible: size < 0.995  // nothing to scroll: no bar at all
    padding: 3
    minimumSize: 0.06       // a long list still gets a thumb you can grab
    Behavior on implicitWidth { enabled: !app.still && sb.upright; NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
    Behavior on implicitHeight { enabled: !app.still && !sb.upright; NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }

    background: Rectangle {  // the track, a little sunk in, only while pointed at or held
        x: sb.upright ? (parent.width - width) / 2 : sb.leftPadding
        y: sb.upright ? sb.topPadding : (parent.height - height) / 2
        width: sb.upright ? sb.thick : sb.availableWidth
        height: sb.upright ? sb.availableHeight : sb.thick
        radius: Math.min(width, height) / 2
        color: Qt.alpha(sb.theme.onSurface, 0.08)
        border.width: 1
        border.color: Qt.alpha(sb.theme.onSurface, 0.05)
        opacity: sb.lively ? 1 : 0
        Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 200 } }
    }

    contentItem: Item {
        implicitWidth: sb.thick
        implicitHeight: sb.thick
        opacity: sb.active || sb.lively ? 1 : 0.45
        Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 250 } }

        Rectangle {  // the slider's halo while the thumb is held
            anchors.centerIn: thumb
            width: thumb.width + 10; height: thumb.height + 10
            radius: Math.min(width, height) / 2
            color: Qt.alpha(sb.theme.primary, 0.16)
            opacity: sb.pressed ? 1 : 0
            Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 160 } }
        }
        Rectangle {
            id: thumb
            anchors.centerIn: parent
            width: sb.upright ? sb.thick : parent.width
            height: sb.upright ? parent.height : sb.thick
            radius: Math.min(width, height) / 2
            // At rest a neutral pill; in use the slider's gradient, from soft to full accent.
            gradient: Gradient {
                orientation: sb.upright ? Gradient.Vertical : Gradient.Horizontal
                GradientStop { position: 0.0; color: sb.lively ? Qt.alpha(sb.theme.primary, 0.55) : Qt.alpha(sb.theme.onSurface, 0.30) }
                GradientStop { position: 1.0; color: sb.lively ? sb.theme.primary : Qt.alpha(sb.theme.onSurface, 0.30) }
            }
        }
    }
}
