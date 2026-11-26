import QtQuick
import QtQuick.Controls.Basic

// Cornerplay's own title bar (Settings > Appearance > "Cornerplay draws its own title bar"):
// the window's name and its minimise, maximise and close buttons in the app's colours, the same
// on Windows, KDE, GNOME, COSMIC, Hyprland and the rest. Drag it to move the window, double-click
// it to maximise. Moving and resizing are handed to the desktop (startSystemMove/Resize), so
// snapping and tiling keep working.
Rectangle {
    id: bar
    required property var theme
    required property var window
    readonly property bool maximized: window.visibility === Window.Maximized
    implicitHeight: 38
    color: theme.surfaceContainerLow

    function toggleMax() { if (bar.maximized) bar.window.showNormal(); else bar.window.showMaximized() }

    Rectangle {  // a hairline under it, so the bar sits softly on the page
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 1
        color: Qt.alpha(bar.theme.onSurface, 0.06)
    }

    DragHandler {
        target: null
        grabPermissions: PointerHandler.CanTakeOverFromAnything
        onActiveChanged: if (active) bar.window.startSystemMove()
    }
    TapHandler {
        acceptedButtons: Qt.LeftButton
        onDoubleTapped: bar.toggleMax()
    }

    Row {
        anchors { left: parent.left; leftMargin: 14; verticalCenter: parent.verticalCenter }
        spacing: 9
        Rectangle {  // a small warm dot in the theme colour, Cornerplay's mark
            width: 10; height: 10; radius: 5
            anchors.verticalCenter: parent.verticalCenter
            color: bar.theme.primary
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: bar.window.title
            color: bar.window.active ? bar.theme.onSurface : bar.theme.outline
            font.pixelSize: 13; font.weight: Font.DemiBold
            Behavior on color { enabled: !app.still; ColorAnimation { duration: 160 } }
        }
    }

    Row {
        anchors { right: parent.right; rightMargin: 6; verticalCenter: parent.verticalCenter }
        spacing: 2

        component Btn: AbstractButton {
            id: b
            property bool danger: false
            property Component glyph
            implicitWidth: 40; implicitHeight: 30
            hoverEnabled: true
            focusPolicy: Qt.NoFocus
            background: Rectangle {
                radius: 10
                color: b.danger && b.hovered ? bar.theme.error
                     : b.hovered ? Qt.alpha(bar.theme.onSurface, b.down ? 0.16 : 0.09) : "transparent"
                Behavior on color { enabled: !app.still; ColorAnimation { duration: 120 } }
            }
            readonly property color ink: b.danger && b.hovered ? bar.theme.onError
                                         : bar.window.active || b.hovered ? bar.theme.onSurface : bar.theme.outline
            contentItem: Item {
                Loader { anchors.centerIn: parent; sourceComponent: b.glyph; property color ink: b.ink }
            }
        }

        Btn {  // minimise
            ToolTip.visible: hovered; ToolTip.delay: 700; ToolTip.text: qsTr("Minimise")
            onClicked: bar.window.showMinimized()
            glyph: Rectangle { width: 11; height: 1.6; radius: 0.8; color: parent.ink }
        }
        Btn {  // maximise / restore
            ToolTip.visible: hovered; ToolTip.delay: 700; ToolTip.text: bar.maximized ? qsTr("Restore") : qsTr("Maximise")
            onClicked: bar.toggleMax()
            glyph: Item {
                width: 11; height: 11
                Rectangle {  // the window behind, when it can be restored
                    visible: bar.maximized
                    x: 2.5; y: 0; width: 8.5; height: 8.5; radius: 2.5
                    color: "transparent"; border.width: 1.4; border.color: parent.parent.ink
                }
                Rectangle {
                    x: 0; y: bar.maximized ? 2.5 : 0
                    width: bar.maximized ? 8.5 : 11; height: width; radius: 3
                    color: bar.color; border.width: 1.4; border.color: parent.parent.ink
                }
            }
        }
        Btn {  // close
            danger: true
            ToolTip.visible: hovered; ToolTip.delay: 700; ToolTip.text: qsTr("Close")
            onClicked: bar.window.close()
            glyph: Item {
                width: 12; height: 12
                Rectangle { anchors.centerIn: parent; width: 14; height: 1.6; radius: 0.8; rotation: 45; color: parent.parent.ink }
                Rectangle { anchors.centerIn: parent; width: 14; height: 1.6; radius: 0.8; rotation: -45; color: parent.parent.ink }
            }
        }
    }
}
