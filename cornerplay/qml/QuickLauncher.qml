import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import QtQuick.Layouts

// A small floating search-and-play window, like Spotlight: `cornerplay --launcher` (bind it to a
// key) opens it over whatever is on screen; type, Enter starts the first game, Esc closes it.
Window {
    id: ql
    required property var theme
    signal openGame(string key)
    width: 620
    height: Math.min(470, 76 + Math.max(1, results.length) * 58 + (results.length ? 16 : 0))
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    title: "Cornerplay launcher"
    property var results: []
    property int at: 0
    function toggle(arg) { if (visible) hide(); else showUp() }  // (arg: tools/shoot.py passes one)
    function showUp() {
        field.text = ""; results = app.recentGames.slice(0, 6); at = 0
        x = Screen.virtualX + (Screen.width - width) / 2
        y = Screen.virtualY + Screen.height * 0.22
        show(); raise(); requestActivate()
        field.forceActiveFocus()
    }
    function run(i) {
        const r = results[i]
        if (!r) return
        hide()
        const g = app.game(r.key)
        if (g.installed) { const t = app.launchTarget(r.key); if (t) app.play(t); else openGame(r.key) }
        else openGame(r.key)
    }
    onActiveChanged: if (!active && visible) hide()   // a click elsewhere puts it away

    Rectangle {
        anchors.fill: parent
        radius: 22
        color: Qt.alpha(ql.theme.surfaceContainer, 0.97)
        border.width: 1; border.color: Qt.alpha(ql.theme.onSurface, 0.12)
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 8
                spacing: 10
                BrandMark { size: 28 }
                TextField {
                    id: field
                    Layout.fillWidth: true
                    placeholderText: qsTr("Play something…")
                    placeholderTextColor: ql.theme.outline
                    color: ql.theme.onSurface
                    font.pixelSize: 22
                    background: Item { }
                    onTextChanged: { ql.results = text.trim() ? app.quickFind(text, 6) : app.recentGames.slice(0, 6); ql.at = 0 }
                    Keys.onDownPressed: ql.at = Math.min(ql.results.length - 1, ql.at + 1)
                    Keys.onUpPressed: ql.at = Math.max(0, ql.at - 1)
                    Keys.onReturnPressed: ql.run(ql.at)
                    Keys.onEnterPressed: ql.run(ql.at)
                    Keys.onEscapePressed: ql.hide()
                }
            }
            Repeater {
                model: ql.results
                Rectangle {
                    id: row
                    required property var modelData
                    required property int index
                    readonly property bool on: index === ql.at
                    Layout.fillWidth: true
                    Layout.preferredHeight: 52
                    radius: 14
                    color: on ? Qt.alpha(ql.theme.primary, 0.2) : rowHover.hovered ? Qt.alpha(ql.theme.onSurface, 0.06) : "transparent"
                    RowLayout {
                        anchors { fill: parent; leftMargin: 8; rightMargin: 14 }
                        spacing: 12
                        RoundedArt {
                            Layout.preferredWidth: 30; Layout.preferredHeight: 42; radius: 6
                            ArtImage { anchors.fill: parent; sources: row.modelData.covers || []; sourceSize.width: 80 }
                        }
                        Text { Layout.fillWidth: true; text: row.modelData.title; elide: Text.ElideRight; color: ql.theme.onSurface
                               font.pixelSize: 15; font.weight: Font.DemiBold; font.family: app.titleFamily }
                        Text { text: (app.game(row.modelData.key).installed ? qsTr("Play") : qsTr("Install")) + (row.on ? "  ⏎" : "")
                               color: row.on ? ql.theme.primary : ql.theme.onSurfaceVariant; font.pixelSize: 13; font.weight: Font.DemiBold }
                    }
                    HoverHandler { id: rowHover; cursorShape: Qt.PointingHandCursor; onHoveredChanged: if (hovered) ql.at = row.index }
                    TapHandler { onTapped: ql.run(row.index) }
                }
            }
            Item { Layout.fillHeight: true }
        }
    }
}
