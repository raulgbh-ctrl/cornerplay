import QtQuick
import QtQuick.Controls.Basic

Button {
    id: b
    required property var theme
    property bool primary: false
    property bool danger: false
    property bool quiet: false     // no fill until pointed at: a quiet, secondary action
    property bool accent: false    // text and icon in the theme colour (with quiet: a link-like action)
    property color ink: "transparent"   // a status colour for text and icon instead (an update's green)
    property string iconName: ""   // a name from cornerplay/icons/ui
    implicitHeight: 38
    leftPadding: iconName && !text ? 11 : 16
    rightPadding: iconName && !text ? 11 : 18
    font.pixelSize: 13
    font.weight: Font.DemiBold
    readonly property color fg: !b.enabled ? b.theme.outline : b.primary ? b.theme.onPrimary
                                : b.danger ? b.theme.error : b.ink.a > 0 ? b.ink : b.accent ? b.theme.primary : b.theme.onSurface
    contentItem: Item {
        implicitWidth: row.implicitWidth
        implicitHeight: row.implicitHeight
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 8
            Icon { visible: b.iconName !== ""; name: b.iconName; size: 16; color: b.fg; anchors.verticalCenter: parent.verticalCenter }
            Text {
                visible: b.text !== ""
                anchors.verticalCenter: parent.verticalCenter
                text: b.text
                font: b.font
                color: b.fg
                elide: Text.ElideRight
            }
        }
    }
    background: Rectangle {
        radius: 12
        color: b.primary ? (b.enabled ? b.theme.primary : b.theme.surfaceContainerHighest)
                         : b.quiet ? (b.hovered ? Qt.alpha(b.theme.onSurface, 0.10) : "transparent")
                         : (b.hovered ? b.theme.surfaceContainerHighest : b.theme.surfaceContainerHigh)
        opacity: b.down ? 0.8 : b.hovered && b.primary ? 0.92 : 1
        border.width: b.visualFocus ? 2 : 0
        border.color: b.theme.outline
        Behavior on color { enabled: !app.still; ColorAnimation { duration: 160 } }
        scale: b.down ? 0.97 : 1
        Behavior on scale { enabled: !app.still; NumberAnimation { duration: 90 } }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
