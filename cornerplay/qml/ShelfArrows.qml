import QtQuick

// Left / right buttons over a horizontal shelf (a ListView of tiles), shown while there is more
// to see that way, as Heroic's store rows have. Put it inside the ListView: ShelfArrows { view: lv }
Item {
    id: arrows
    required property Flickable view
    property var theme: app.theme
    parent: view
    anchors.fill: parent
    z: 10
    readonly property bool more: view.contentWidth > view.width + 2
    readonly property bool pointed: shelfHover.hovered

    HoverHandler { id: shelfHover }

    function page(dir) {
        const max = Math.max(0, view.contentWidth - view.width) + view.originX
        slide.to = Math.max(view.originX, Math.min(max, view.contentX + dir * view.width * 0.8))
        slide.restart()
    }
    NumberAnimation { id: slide; target: arrows.view; property: "contentX"; duration: app.still ? 0 : 360; easing.type: Easing.OutCubic }

    // A soft edge where tiles run on past the side, so the cut reads as "more this way".
    Repeater {
        model: [-1, 1]
        Rectangle {
            required property int modelData
            readonly property bool can: arrows.more && (modelData < 0 ? !arrows.view.atXBeginning : !arrows.view.atXEnd)
            opacity: can ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 150 } }
            x: modelData < 0 ? 0 : parent.width - width
            width: 56; height: parent.height
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: modelData < 0 ? arrows.theme.background : "transparent" }
                GradientStop { position: 1; color: modelData < 0 ? "transparent" : arrows.theme.background }
            }
        }
    }
    Repeater {
        model: [-1, 1]
        Rectangle {
            required property int modelData
            readonly property bool can: arrows.more && (modelData < 0 ? !arrows.view.atXBeginning : !arrows.view.atXEnd)
            visible: opacity > 0
            opacity: can ? (arrows.pointed ? 1 : 0.0) : 0
            Behavior on opacity { NumberAnimation { duration: 150 } }
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -20
            x: modelData < 0 ? 8 : parent.width - width - 8
            width: 40; height: 40; radius: 20
            color: btnHover.hovered ? arrows.theme.surfaceContainerHighest : Qt.alpha(arrows.theme.surfaceContainerHigh, 0.92)
            border.width: 1; border.color: Qt.alpha("white", 0.12)
            Icon { anchors.centerIn: parent; name: "chevron-right"; size: 20; color: arrows.theme.onSurface
                   rotation: parent.modelData < 0 ? 180 : 0 }
            HoverHandler { id: btnHover; cursorShape: Qt.PointingHandCursor }
            TapHandler { gesturePolicy: TapHandler.WithinBounds; onTapped: arrows.page(parent.modelData) }
        }
    }
}
