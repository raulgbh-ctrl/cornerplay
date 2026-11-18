import QtQuick
import QtQuick.Layouts

// TV mode's Library: every game in a grid of covers, away from the home screen's shelves
// (Library button at the top of Home, or the Guide menu). Arrows move, A plays, X / Start
// opens the game's page, Y installed only, LB / RB store, B back.
FocusScope {
    id: lib
    objectName: "tvLibrary"
    required property var theme
    required property var tint
    required property var storeIds
    signal closed()
    signal play(string key)
    signal more(string key)
    visible: false
    readonly property string currentKey: visible && grid.currentIndex >= 0 ? tvAllLibrary.keyAt(grid.currentIndex) : ""

    function show() {
        tvAllLibrary.search = ""
        tvAllLibrary.shelf = ""
        app.uiSound("select")
        visible = true
        grid.currentIndex = grid.count > 0 ? 0 : -1
        grid.positionViewAtBeginning()
        grid.forceActiveFocus()
    }
    function close() { app.uiSound("back"); visible = false; closed() }
    function cycleStore(step) {
        app.uiSound("move")
        const i = storeIds.indexOf(tvAllLibrary.storeFilter)
        tvAllLibrary.storeFilter = storeIds[(i + step + storeIds.length) % storeIds.length]
        grid.currentIndex = grid.count > 0 ? 0 : -1
        grid.positionViewAtBeginning()
    }

    Rectangle { anchors.fill: parent; color: lib.theme.background }
    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: w => w.accepted = false }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 48
        anchors.bottomMargin: 28
        spacing: 22

        RowLayout {
            Layout.fillWidth: true
            spacing: 14
            Icon { name: "library"; size: 30; color: lib.tint.primary }
            Text { text: qsTr("Library"); color: lib.theme.onSurface; font.pixelSize: 34; font.weight: Font.Bold }
            Text {
                Layout.leftMargin: 6
                text: grid.count + (grid.count === 1 ? qsTr(" game") : qsTr(" games"))
                color: lib.theme.onSurfaceVariant; font.pixelSize: 20
            }
            Item { Layout.fillWidth: true }
            // The stores, like Home's tabs: LB / RB (or a tap).
            Row {
                spacing: 10
                PadButton { visible: pad.connected && lib.storeIds.length > 2; anchors.verticalCenter: parent.verticalCenter; button: "lb"; style: pad.style; size: 26 }
                Repeater {
                    model: lib.storeIds.length > 2 ? lib.storeIds : []
                    Rectangle {
                        required property string modelData
                        readonly property bool active: tvAllLibrary.storeFilter === modelData
                        readonly property var info: app.storesInfo.find(s => s.id === modelData) || ({ name: qsTr("All games") })
                        anchors.verticalCenter: parent.verticalCenter
                        width: storeRow.implicitWidth + 30; height: 42; radius: 21
                        color: active ? lib.tint.primary : storeHover.hovered ? Qt.alpha(lib.theme.onSurface, 0.1) : Qt.alpha(lib.theme.onSurface, 0.05)
                        Row {
                            id: storeRow
                            anchors.centerIn: parent
                            spacing: 8
                            StoreTile { visible: parent.parent.modelData !== ""; anchors.verticalCenter: parent.verticalCenter; size: 22; store: parent.parent.modelData }
                            Text {
                                visible: parent.parent.active || parent.parent.modelData === ""
                                anchors.verticalCenter: parent.verticalCenter
                                text: parent.parent.info.name
                                color: parent.parent.active ? lib.tint.onPrimary : lib.theme.onSurfaceVariant
                                font.pixelSize: 16; font.weight: parent.parent.active ? Font.DemiBold : Font.Normal
                            }
                        }
                        HoverHandler { id: storeHover; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: { tvAllLibrary.storeFilter = parent.modelData; grid.currentIndex = grid.count > 0 ? 0 : -1; grid.forceActiveFocus() } }
                    }
                }
                PadButton { visible: pad.connected && lib.storeIds.length > 2; anchors.verticalCenter: parent.verticalCenter; button: "rb"; style: pad.style; size: 26 }
            }
            Rectangle {
                Layout.leftMargin: 6
                height: 42; radius: 21
                width: instRow.implicitWidth + 30
                color: tvAllLibrary.installedOnly ? Qt.alpha(lib.tint.primary, 0.22) : Qt.alpha(lib.theme.onSurface, 0.05)
                border.width: tvAllLibrary.installedOnly ? 1 : 0; border.color: lib.tint.primary
                Row {
                    id: instRow
                    anchors.centerIn: parent
                    spacing: 8
                    PadButton { visible: pad.connected || pad.deck; anchors.verticalCenter: parent.verticalCenter; button: "y"; style: pad.style; size: 24 }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: qsTr("Installed only"); color: lib.theme.onSurface; font.pixelSize: 16; font.weight: Font.DemiBold }
                }
                HoverHandler { cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: { tvAllLibrary.installedOnly = !tvAllLibrary.installedOnly; grid.forceActiveFocus() } }
            }
        }

        GridView {
            id: grid
            objectName: "tvLibraryGrid"
            Layout.fillWidth: true
            Layout.fillHeight: true
            focus: true
            clip: true
            model: tvAllLibrary
            // Covers about a fifth of the screen tall; as many across as fit.
            readonly property int across: Math.max(3, Math.floor(width / Math.max(150, lib.height * 0.155)))
            cellWidth: Math.floor(width / across)
            cellHeight: Math.round(cellWidth * 1.46) + 44
            keyNavigationEnabled: true
            keyNavigationWraps: false
            boundsBehavior: Flickable.StopAtBounds
            highlightFollowsCurrentItem: false
            preferredHighlightBegin: cellHeight * 0.3
            preferredHighlightEnd: height - cellHeight * 0.7
            highlightRangeMode: GridView.ApplyRange
            highlightMoveDuration: app.still ? 0 : 200
            cacheBuffer: cellHeight * 2
            onCurrentIndexChanged: if (lib.visible) { app.uiSound("move"); speak.restart() }
            onCountChanged: if (currentIndex < 0 && count > 0) currentIndex = 0
            Timer { id: speak; interval: 250; onTriggered: { const g = app.game(lib.currentKey); if (g.key) app.say(g.title + (g.installed ? "" : ", " + qsTr("not installed"))) } }
            delegate: GameCard {
                id: card
                required property int index
                width: grid.cellWidth
                height: grid.cellHeight
                theme: lib.tint
                quickAction: false
                cornerRadius: app.settingsMap.card_radius
                showBadge: true
                showProtonDb: false
                showTitle: true
                dim: app.settingsMap.dim_uninstalled
                current: GridView.isCurrentItem && grid.activeFocus
                onHoveredChanged: if (hovered && grid.currentIndex !== index) grid.currentIndex = index
                onOpened: { grid.currentIndex = index; lib.more(lib.currentKey) }
                onActivated: { grid.currentIndex = index; lib.play(lib.currentKey) }
            }
            Keys.onReturnPressed: if (lib.currentKey) lib.play(lib.currentKey)
            Keys.onEnterPressed: if (lib.currentKey) lib.play(lib.currentKey)
            Keys.onEscapePressed: lib.close()
            Keys.onPressed: event => {
                const k = event.key
                if (k === Qt.Key_F2) { if (lib.currentKey) lib.more(lib.currentKey); event.accepted = true }
                else if (k === Qt.Key_F3 || (k === Qt.Key_Space && pad.deck && !pad.connected)) { tvAllLibrary.installedOnly = !tvAllLibrary.installedOnly; event.accepted = true }
                else if (k === Qt.Key_PageUp || k === Qt.Key_PageDown) { if (lib.storeIds.length > 2) lib.cycleStore(k === Qt.Key_PageDown ? 1 : -1); event.accepted = true }
                else if (k === Qt.Key_Home) { currentIndex = 0; event.accepted = true }
                else if (k === Qt.Key_End) { currentIndex = count - 1; event.accepted = true }
                else if (event.text && /^[a-z0-9]$/i.test(event.text) && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier))) {
                    // A letter jumps to the first game that starts with it (sorted by name).
                    const ch = event.text.toLowerCase()
                    for (let i = 0; i < count; i++) {
                        const g = app.game(tvAllLibrary.keyAt(i))
                        if ((g.title || "").toLowerCase().startsWith(ch)) { currentIndex = i; break }
                    }
                    event.accepted = true
                }
            }

            Column {
                visible: grid.count === 0
                anchors.centerIn: parent
                spacing: 18
                EmptyScene { anchors.horizontalCenter: parent.horizontalCenter; width: 300; height: 200; theme: lib.theme; kind: app.totalCount === 0 ? "library" : "list" }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: qsTr("No games here"); color: lib.theme.onSurfaceVariant; font.pixelSize: 26 }
            }
        }

        Row {
            Layout.alignment: Qt.AlignRight
            spacing: 22
            Repeater {
                model: {
                    const g = app.game(lib.currentKey)
                    const play = g.key && !g.installed ? qsTr("Install") : qsTr("Play")
                    const out = pad.connected || pad.deck
                        ? [g.key ? { b: ["a"], t: play } : null, g.key ? (pad.connected ? { b: ["start"], t: qsTr("More") } : { k: "F2", t: qsTr("More") }) : null,
                           { b: ["y"], t: tvAllLibrary.installedOnly ? qsTr("All games") : qsTr("Installed only") }, { b: ["b"], t: qsTr("Back") }]
                        : [g.key ? { k: qsTr("Enter"), t: play } : null, g.key ? { k: "F2", t: qsTr("More") } : null,
                           { k: "F3", t: tvAllLibrary.installedOnly ? qsTr("All games") : qsTr("Installed only") }, { k: qsTr("Esc"), t: qsTr("Back") }]
                    return out.filter(h => h)
                }
                Row {
                    required property var modelData
                    spacing: 8
                    Repeater { model: modelData.b || []; PadButton { required property string modelData; button: modelData; style: pad.style; size: 26 } }
                    Rectangle {
                        visible: !!modelData.k
                        height: 26; radius: 6; width: hk.implicitWidth + 16
                        color: Qt.alpha(lib.theme.surfaceContainerHighest, 0.9)
                        border.width: 1; border.color: lib.theme.outlineVariant
                        Text { id: hk; anchors.centerIn: parent; text: modelData.k || ""; color: lib.theme.onSurface; font.pixelSize: 12; font.weight: Font.DemiBold }
                    }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: modelData.t; color: lib.theme.onSurfaceVariant; font.pixelSize: 15 }
                }
            }
        }
    }
}
