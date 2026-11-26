import QtQuick
import QtQuick.Controls.Basic

// A soft, rounded slider in the theme's colours: a warm filled track, a pebble-like knob that
// swells a little under the pointer, and a small bubble with the value while it is dragged.
Slider {
    id: s
    required property var theme
    property string unit: ""                                  // shown after the value ("px", "%")
    property var format: v => Math.round(v) + s.unit           // the bubble's text
    readonly property bool lively: s.hovered || s.pressed || s.visualFocus
    implicitHeight: 34
    topPadding: 6; bottomPadding: 6
    leftPadding: 10; rightPadding: 10

    background: Item {
        x: s.leftPadding
        y: s.topPadding + s.availableHeight / 2 - height / 2
        width: s.availableWidth
        height: s.lively ? 10 : 8
        Behavior on height { enabled: !app.still; NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }

        Rectangle {  // the empty track, a little sunk in
            anchors.fill: parent
            radius: height / 2
            color: Qt.alpha(s.theme.onSurface, 0.10)
            border.width: 1
            border.color: Qt.alpha(s.theme.onSurface, 0.05)
        }
        Rectangle {  // the filled part: a gentle glow from soft to full colour
            width: Math.max(parent.height, s.visualPosition * parent.width)
            height: parent.height
            radius: height / 2
            opacity: s.enabled ? 1 : 0.4
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: Qt.alpha(s.theme.primary, 0.55) }
                GradientStop { position: 1.0; color: s.theme.primary }
            }
        }
    }

    handle: Item {
        x: s.leftPadding + s.visualPosition * (s.availableWidth - width)
        y: s.topPadding + s.availableHeight / 2 - height / 2
        width: 22; height: 22

        Rectangle {  // a soft shadow under the knob
            anchors.centerIn: parent
            anchors.verticalCenterOffset: 1.5
            width: knob.width + 4; height: width; radius: width / 2
            color: Qt.alpha("black", s.theme.dark ? 0.35 : 0.14)
            scale: knob.scale
        }
        Rectangle {  // a halo while it is held or has the keyboard
            anchors.centerIn: parent
            width: 36; height: 36; radius: 18
            color: Qt.alpha(s.theme.primary, 0.16)
            opacity: s.pressed || s.visualFocus ? 1 : 0
            scale: s.pressed || s.visualFocus ? 1 : 0.6
            Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 160 } }
            Behavior on scale { enabled: !app.still; NumberAnimation { duration: 200; easing.type: Easing.OutBack } }
        }
        Rectangle {
            id: knob
            anchors.centerIn: parent
            width: 20; height: 20; radius: 10
            color: s.theme.dark ? s.theme.onSurface : "white"
            border.width: 4
            border.color: s.enabled ? s.theme.primary : s.theme.outline
            scale: s.pressed ? 1.15 : s.hovered ? 1.08 : 1
            Behavior on scale { enabled: !app.still; NumberAnimation { duration: 160; easing.type: Easing.OutBack } }
        }

        Rectangle {  // the value, shown while dragging
            id: bubble
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.top
            anchors.bottomMargin: 8
            width: bubbleText.implicitWidth + 16; height: 24; radius: 12
            color: s.theme.primary
            opacity: s.pressed ? 1 : 0
            scale: s.pressed ? 1 : 0.7
            transformOrigin: Item.Bottom
            Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 140 } }
            Behavior on scale { enabled: !app.still; NumberAnimation { duration: 180; easing.type: Easing.OutBack } }
            Text {
                id: bubbleText
                anchors.centerIn: parent
                text: s.format(s.value)
                color: s.theme.onPrimary
                font.pixelSize: 12; font.weight: Font.DemiBold
            }
            Rectangle {  // its little tail
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.verticalCenter: parent.bottom
                width: 8; height: 8; rotation: 45
                color: parent.color
                z: -1
            }
        }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
