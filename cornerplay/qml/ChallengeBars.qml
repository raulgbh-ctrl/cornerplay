import QtQuick
import QtQuick.Layouts

// This month's challenges (app.challenges()): one bar per goal that is on. Used by the
// desktop's stats and TV mode's stats; `unit` scales it (1 on the desktop, larger on a TV).
ColumnLayout {
    id: cb
    required property var theme
    property var info: ({})
    property real unit: 1
    spacing: 10 * unit
    visible: !!info.any
    Text {
        text: qsTr("Challenges for %1").arg(cb.info.month || "") + "  ·  " + (cb.info.daysLeft === 1 ? qsTr("1 day left") : qsTr("%1 days left").arg(cb.info.daysLeft || 0))
        color: cb.theme.onSurface; font.pixelSize: Math.round(15 * cb.unit); font.weight: Font.DemiBold
    }
    Repeater {
        model: (cb.info.items || []).filter(i => i.goal > 0)
        ColumnLayout {
            required property var modelData
            readonly property bool met: modelData.done >= modelData.goal
            Layout.fillWidth: true
            spacing: 4 * cb.unit
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: modelData.label; color: cb.theme.onSurfaceVariant; font.pixelSize: Math.round(13 * cb.unit); elide: Text.ElideRight }
                Text { text: (parent.parent.met ? "✓  " : "") + modelData.done + modelData.unit + " / " + modelData.goal + modelData.unit
                       color: parent.parent.met ? "#7bd88f" : cb.theme.onSurface; font.pixelSize: Math.round(13 * cb.unit); font.weight: Font.DemiBold }
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: Math.round(8 * cb.unit); radius: height / 2
                color: Qt.alpha(cb.theme.onSurface, 0.1)
                Rectangle {
                    height: parent.height; radius: parent.radius
                    width: parent.width * Math.min(1, modelData.goal ? modelData.done / modelData.goal : 0)
                    color: parent.parent.met ? "#7bd88f" : cb.theme.primary
                    Behavior on width { enabled: !app.still; NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
                }
            }
        }
    }
}
