import QtQuick
import QtQuick.Controls.Basic

TextField {
    id: f
    required property var theme
    property string iconName: ""   // optional icon inside the field, on the left
    property bool pill: false       // round ends, frosted, with a soft shadow (Look > Floating search)
    implicitHeight: 38
    leftPadding: iconName ? 38 : 12; rightPadding: 12
    font.pixelSize: 13
    color: theme.onSurface
    placeholderTextColor: theme.outline
    selectionColor: theme.primaryContainer
    selectedTextColor: theme.onPrimaryContainer
    selectByMouse: true
    background: Rectangle {
        radius: f.pill ? height / 2 : 10
        color: f.pill ? Qt.alpha(f.theme.surfaceContainerHigh, 0.75) : f.theme.surfaceContainerHigh
        border.width: f.activeFocus ? 2 : 1
        border.color: f.activeFocus ? f.theme.primary : f.theme.outlineVariant
        Icon {
            visible: f.iconName !== ""
            x: 13; anchors.verticalCenter: parent.verticalCenter
            name: f.iconName; size: 16
            color: f.activeFocus ? f.theme.primary : f.theme.outline
        }
    }
}
