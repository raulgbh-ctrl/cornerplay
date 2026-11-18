import QtQuick
import QtQuick.Layouts

// The phone remote (remote.py): a QR code with the address and the code, so a phone on the
// same network becomes a remote, a keyboard for search, and a ballot for game night.
Rectangle {
    id: ph
    objectName: "tvPhone"
    required property var theme
    required property var tint
    signal closed()
    color: Qt.alpha(theme.background, 0.97)
    visible: false
    readonly property var info: app.remoteInfo
    function show() { visible = true; forceActiveFocus(); app.uiSound("select") }
    function close() { app.uiSound("back"); visible = false; closed() }
    Keys.onPressed: event => {
        event.accepted = true
        if (event.key === Qt.Key_Escape || event.key === Qt.Key_Backspace) close()
        else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) app.setSetting("phone_remote", !app.settingsMap.phone_remote)
    }
    readonly property real u: height / 100

    RowLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width * 0.8, ph.u * 150)
        spacing: ph.u * 6
        Rectangle {
            Layout.preferredWidth: ph.u * 42; Layout.preferredHeight: ph.u * 42
            radius: ph.u * 2
            color: "white"
            visible: ph.info.on
            Image { anchors.fill: parent; anchors.margins: ph.u * 1.5; source: ph.info.qr || ""; fillMode: Image.PreserveAspectFit
                    sourceSize: Qt.size(width * 2, height * 2); smooth: false; visible: !!ph.info.qr }
            Text { anchors.centerIn: parent; visible: !ph.info.qr; width: parent.width - 30; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter
                   text: qsTr("Install qrencode for a QR code, or type the address below."); color: "#333"; font.pixelSize: ph.u * 2 }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: ph.u * 2
            Text { text: qsTr("Phone remote"); color: ph.theme.onSurface; font.pixelSize: ph.u * 5; font.weight: Font.Bold }
            Text {
                Layout.fillWidth: true; wrapMode: Text.WordWrap; color: ph.theme.onSurfaceVariant; font.pixelSize: ph.u * 2.3
                text: ph.info.on ? qsTr("On a phone on the same Wi-Fi, scan the code or open the address and type the code. It becomes a remote with a keyboard for search, and the ballot for game night.")
                                 : qsTr("Turn it on to use a phone as a remote, type searches from it, and vote on game night. Only phones that know the code can use it.")
            }
            Text { visible: ph.info.on; text: ph.info.url || ""; color: ph.tint.primary; font.pixelSize: ph.u * 3.4; font.weight: Font.DemiBold }
            Text { visible: ph.info.on; text: qsTr("Code: %1").arg(ph.info.code || ""); color: ph.theme.onSurface; font.pixelSize: ph.u * 4.2; font.weight: Font.Bold; font.letterSpacing: ph.u * 0.6 }
            Text { visible: !!ph.info.error; text: ph.info.error || ""; color: ph.theme.error; font.pixelSize: ph.u * 2 }
            Row {
                spacing: 22
                Repeater {
                    model: [{ b: "a", k: qsTr("Enter"), t: app.settingsMap.phone_remote ? qsTr("Turn off") : qsTr("Turn on") }, { b: "b", k: qsTr("Esc"), t: qsTr("Back") }]
                    Row {
                        required property var modelData
                        spacing: 8
                        PadButton { visible: pad.connected || pad.deck; button: modelData.b; style: pad.style; size: 26 }
                        Rectangle { visible: !pad.connected && !pad.deck; height: 26; radius: 6; width: kt.implicitWidth + 16
                                    color: Qt.alpha(ph.theme.surfaceContainerHighest, 0.9); border.width: 1; border.color: ph.theme.outlineVariant
                                    Text { id: kt; anchors.centerIn: parent; text: modelData.k; color: ph.theme.onSurface; font.pixelSize: 12; font.weight: Font.DemiBold } }
                        Text { anchors.verticalCenter: parent.verticalCenter; text: modelData.t; color: ph.theme.onSurfaceVariant; font.pixelSize: 16 }
                    }
                }
            }
        }
    }
}
