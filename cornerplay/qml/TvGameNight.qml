import QtQuick
import QtQuick.Layouts

// Game night: up to six games for tonight (ones to play together on this screen first). Phones
// vote through the phone remote; A on the TV adds a vote for the game in focus; X starts the
// game with the most votes; B ends game night.
Rectangle {
    id: gn
    objectName: "tvGameNight"
    required property var theme
    required property var tint
    signal closed()
    signal play(string key)
    color: Qt.alpha(theme.background, 0.97)
    visible: false
    property int at: 0
    readonly property var night: app.gameNightInfo
    readonly property var games: night.games || []
    readonly property int topVotes: Math.max(0, ...games.map(g => g.votes))
    readonly property string winner: { const w = games.filter(g => g.votes === topVotes && topVotes > 0); return w.length ? w[0].key : "" }
    readonly property real u: height / 100
    function show() { app.startGameNight(); at = 0; visible = true; forceActiveFocus(); app.uiSound("select") }
    function close() { app.uiSound("back"); app.closeGameNight(); visible = false; closed() }
    Keys.onPressed: event => {
        event.accepted = true
        const k = event.key
        if (k === Qt.Key_Escape) close()
        else if (k === Qt.Key_Left) { at = Math.max(0, at - 1); app.uiSound("move") }
        else if (k === Qt.Key_Right) { at = Math.min(games.length - 1, at + 1); app.uiSound("move") }
        else if (k === Qt.Key_Return || k === Qt.Key_Enter) { if (games[at]) { app.voteOnTv(games[at].key); app.uiSound("select") } }
        else if (k === Qt.Key_F2) { const key = winner || (games[at] || {}).key; if (key) { visible = false; app.closeGameNight(); closed(); play(key) } }
    }

    ColumnLayout {
        anchors { fill: parent; margins: gn.u * 7 }
        spacing: gn.u * 3
        Text { text: qsTr("Game night"); color: gn.theme.onSurface; font.pixelSize: gn.u * 5.5; font.weight: Font.Bold }
        Text {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; color: gn.theme.onSurfaceVariant; font.pixelSize: gn.u * 2.3
            text: app.remoteInfo.on ? qsTr("Vote from your phones at %1 (code %2), or with A here: one press, one vote.").arg(app.remoteInfo.url).arg(app.remoteInfo.code)
                                    : qsTr("Vote with A: one press for each person who wants it. Turn on the phone remote (Guide menu) to vote from phones.")
        }
        Text { visible: gn.games.length === 0; text: qsTr("Install a few games first: game night picks from installed ones."); color: gn.theme.onSurfaceVariant; font.pixelSize: gn.u * 2.6 }
        Row {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: gn.u * 2
            Repeater {
                model: gn.games
                Item {
                    id: card
                    required property var modelData
                    required property int index
                    readonly property bool lit: index === gn.at
                    width: Math.min(gn.u * 26, (gn.width - gn.u * 14 - gn.u * 2 * 5) / 6)
                    height: parent.height
                    Column {
                        width: parent.width
                        spacing: gn.u * 1.2
                        RoundedArt {
                            width: parent.width; height: width * 1.46; radius: gn.u * 1.4
                            scale: card.lit && !app.still ? 1.05 : 1
                            Behavior on scale { NumberAnimation { duration: 140 } }
                            ArtImage { anchors.fill: parent; sources: [card.modelData.cover]; sourceSize.width: 400 }
                            Rectangle { anchors.fill: parent; color: "transparent"; radius: gn.u * 1.4
                                        border.width: card.lit ? 4 : 0; border.color: gn.tint.primary }
                            Rectangle {
                                visible: card.modelData.key === gn.winner
                                anchors { top: parent.top; right: parent.right; margins: gn.u }
                                height: gn.u * 3.4; radius: height / 2; width: crown.implicitWidth + gn.u * 2
                                color: gn.tint.primary
                                Text { id: crown; anchors.centerIn: parent; text: qsTr("Leading"); color: gn.tint.onPrimary; font.pixelSize: gn.u * 1.7; font.weight: Font.Bold }
                            }
                        }
                        Text { width: parent.width; text: card.modelData.title; elide: Text.ElideRight; color: gn.theme.onSurface
                               font.pixelSize: gn.u * 2.1; font.weight: Font.DemiBold }
                        Rectangle {
                            width: parent.width; height: gn.u * 1.2; radius: height / 2
                            color: Qt.alpha(gn.theme.onSurface, 0.1)
                            Rectangle { height: parent.height; radius: parent.radius; color: gn.tint.primary
                                        width: gn.topVotes ? parent.width * card.modelData.votes / gn.topVotes : 0
                                        Behavior on width { NumberAnimation { duration: 300 } } }
                        }
                        Text { text: card.modelData.votes === 1 ? qsTr("1 vote") : qsTr("%1 votes").arg(card.modelData.votes)
                               color: gn.theme.onSurfaceVariant; font.pixelSize: gn.u * 1.9 }
                    }
                    TapHandler { onTapped: { gn.at = card.index; app.voteOnTv(card.modelData.key) } }
                }
            }
        }
        Row {
            Layout.alignment: Qt.AlignRight
            spacing: 22
            Repeater {
                model: [{ b: "a", k: qsTr("Enter"), t: qsTr("Vote") }, { b: "x", k: "F2", t: gn.winner ? qsTr("Play the winner") : qsTr("Play this one") },
                        { b: "b", k: qsTr("Esc"), t: qsTr("End game night") }]
                Row {
                    required property var modelData
                    spacing: 8
                    PadButton { visible: pad.connected; button: modelData.b; style: pad.style; size: 26 }
                    Rectangle { visible: !pad.connected; height: 26; radius: 6; width: kt.implicitWidth + 16
                                color: Qt.alpha(gn.theme.surfaceContainerHighest, 0.9); border.width: 1; border.color: gn.theme.outlineVariant
                                Text { id: kt; anchors.centerIn: parent; text: modelData.k; color: gn.theme.onSurface; font.pixelSize: 12; font.weight: Font.DemiBold } }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: modelData.t; color: gn.theme.onSurfaceVariant; font.pixelSize: 16 }
                }
            }
        }
    }
}
