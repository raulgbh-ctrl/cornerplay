import QtQuick
import QtQuick.Controls.Basic

// The scrollbar, in the same family as KSlider: at rest a quiet thin pill; pointed at, a soft
// sunk track appears and the thumb swells and takes the slider's warm accent gradient; held, it
// glows a little. Never wider than 14 px, since it sits over the edge of what it scrolls.
ScrollBar {
    id: sb
    readonly property var theme: app.theme
    readonly property bool upright: orientation === Qt.Vertical
    readonly property bool lively: hovered || pressed
    // Never wider than the old bar (14 px with its padding): it sits over the content's edge.
    readonly property real thick: lively ? 10 : 6
    implicitWidth: upright ? thick + 2 * padding : 100
    implicitHeight: upright ? 100 : thick + 2 * padding
    visible: size < 0.995  // nothing to scroll: no bar at all

    // Its own lane: where the scrolled view is anchored to its container (the library, the game
    // page, most lists), the view gives up a strip on its right and the bar sits there, beside the
    // content instead of over it (Qt's documented "scroll bar outside the Flickable" pattern).
    // A view sized some other way (a dialog's content) keeps the bar at its edge.
    property bool ownLane: true
    readonly property int laneWidth: 14
    Component.onCompleted: Qt.callLater(takeLane)
    function takeLane() {
        const f = parent
        if (!ownLane || !upright || !f || !f.parent || !f.anchors)
            return
        // A layout or positioner places its children itself: the bar cannot join one.
        if (/^QQuick(Column|Row|Grid|Stack)Layout|^QQuick(Column|Row|Grid|Flow)(_QML|\(|$)/.test(String(f.parent)))
            return
        const bar = sb
        if (f.anchors.fill || f.anchors.right) {  // anchored: the view gives up a strip for the bar
            f.anchors.rightMargin = Math.max(f.anchors.rightMargin, laneWidth + 2)
            parent = f.parent
            anchors.top = f.top
            anchors.bottom = f.bottom
            anchors.left = f.right
            anchors.leftMargin = 1
            return
        }
        // Sized by its container (a page or dialog's content): the bar moves into the container's
        // padding on the right when there is room for it there, else stays at the view's edge.
        parent = f.parent
        y = Qt.binding(() => f.y)
        height = Qt.binding(() => f.height)
        x = Qt.binding(() => {
            const room = f.parent.width - f.x - f.width
            return room >= bar.laneWidth + 4 ? f.x + f.width + Math.min(8, (room - bar.laneWidth) / 2)
                                             : f.x + f.width - bar.width
        })
    }
    padding: 2
    minimumSize: 0.06       // a long list still gets a thumb you can grab
    Behavior on implicitWidth { enabled: !app.still && sb.upright; NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
    Behavior on implicitHeight { enabled: !app.still && !sb.upright; NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }

    background: Rectangle {  // the track, a little sunk in: faint at rest, clearer while used
        x: sb.upright ? (parent.width - width) / 2 : sb.leftPadding
        y: sb.upright ? sb.topPadding : (parent.height - height) / 2
        width: sb.upright ? sb.thick : sb.availableWidth
        height: sb.upright ? sb.availableHeight : sb.thick
        radius: Math.min(width, height) / 2
        color: Qt.alpha(sb.theme.onSurface, 0.08)
        border.width: 1
        border.color: Qt.alpha(sb.theme.onSurface, 0.05)
        opacity: sb.lively ? 1 : 0.55  // always a faint lane, clearer while used
        Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 200 } }
    }

    contentItem: Item {
        implicitWidth: sb.thick
        implicitHeight: sb.thick
        opacity: sb.active || sb.lively ? 1 : 0.45
        Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 250 } }

        Rectangle {  // the slider's halo while the thumb is held, kept inside the bar's own room
            anchors.centerIn: thumb
            width: thumb.width + (sb.upright ? 4 : 0); height: thumb.height + (sb.upright ? 0 : 4)
            radius: Math.min(width, height) / 2
            color: Qt.alpha(sb.theme.primary, 0.22)
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
