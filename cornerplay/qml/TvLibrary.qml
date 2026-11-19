import QtQuick
import QtQuick.Layouts

// TV mode's Library: every game, away from the home screen's shelves (Library button at the
// top of Home, or the Guide menu). Covers in a grid or a dense list; recently played along the
// top; sort, filters, lists and hidden games under Y; search with View; LT / RT jump a letter
// (or a page); pick several games for one action. Arrows move, A plays (or picks), X / Start
// opens the game's page, LB / RB store, B back (clears a search or a pick first).
FocusScope {
    id: lib
    objectName: "tvLibrary"
    required property var theme
    required property var tint
    required property var storeIds
    signal closed()
    signal play(string key)
    signal more(string key)
    signal options()      // Y: the sort and filter menu (TvView's side sheet)
    signal searchAsked()  // View: the on-screen keyboard (TvView's prompt)
    visible: false

    property bool listMode: app.settingsMap.tv_library_view === "list"
    property var picked: []           // keys picked for one action
    property bool picking: false
    readonly property Item view: listMode ? list : grid
    readonly property int count: view.count
    readonly property string currentKey: visible && view.currentIndex >= 0 ? tvAllLibrary.keyAt(view.currentIndex) : ""
    // The strip of games played last: only on the plain Library (no search, list or filter).
    readonly property var recent: app.recentGames.slice(0, 8)
    readonly property bool plain: tvAllLibrary.search === "" && tvAllLibrary.shelf === "" && !tvAllLibrary.showHidden
                                  && tvAllLibrary.tags.length === 0 && !tvAllLibrary.installedOnly
    readonly property bool stripShown: plain && recent.length > 1 && lib.height >= 700 && !picking

    readonly property var sortNames: ({ name: qsTr("Name"), recent: qsTr("Recently played"), playtime: qsTr("Most played"),
                                        added: qsTr("Recently added"), size: qsTr("Size"), rating: qsTr("Your rating") })
    readonly property var tagNames: ({ unplayed: qsTr("Not played yet"), controller: qsTr("Full controller support"),
                                       protondb: qsTr("ProtonDB Gold or better"), couch: qsTr("Play together"),
                                       linux: qsTr("Native Linux"), fav: qsTr("Favourites"), dupes: qsTr("Owned on 2+ stores") })
    function shelfName(id) {
        if (tvAllLibrary.showHidden) return qsTr("Hidden games")
        if (!id) return ""
        if (id === "fav") return qsTr("Favourites")
        if (id.startsWith("c:")) return id.slice(2)
        return ({ "s:playing": qsTr("Playing"), "s:want": qsTr("Want to play"), "s:finished": qsTr("Finished"),
                  "s:dropped": qsTr("Dropped") })[id] || id
    }

    function show() {
        tvAllLibrary.search = ""
        picking = false; picked = []
        app.uiSound("select")
        visible = true
        toTop()
        view.forceActiveFocus()
    }
    function toTop() {
        grid.currentIndex = count > 0 ? 0 : -1
        list.currentIndex = count > 0 ? 0 : -1
        grid.positionViewAtBeginning(); list.positionViewAtBeginning()
    }
    function close() {
        app.uiSound("back")
        if (picking) { picking = false; picked = []; return }
        if (tvAllLibrary.search !== "") { tvAllLibrary.search = ""; toTop(); return }
        visible = false; closed()
    }
    function setListMode(on) {
        const i = view.currentIndex
        app.setSetting("tv_library_view", on ? "list" : "grid")
        listMode = on
        const had = lib.activeFocus  // from the Y menu the keys stay in the menu
        Qt.callLater(() => { view.currentIndex = i; view.positionViewAtIndex(Math.max(0, i), GridView.Contain); if (had) view.forceActiveFocus() })
    }
    function cycleStore(step) {
        app.uiSound("move")
        const i = storeIds.indexOf(tvAllLibrary.storeFilter)
        tvAllLibrary.storeFilter = storeIds[(i + step + storeIds.length) % storeIds.length]
        toTop()
    }
    function activate() {
        if (!currentKey) return
        if (picking) { togglePick(currentKey); return }
        play(currentKey)
    }
    function togglePick(key) {
        const p = picked.slice(), i = p.indexOf(key)
        if (i >= 0) p.splice(i, 1); else p.push(key)
        picked = p
        app.uiSound("move")
    }
    function startPicking() { picking = true; picked = currentKey ? [currentKey] : []; view.forceActiveFocus() }
    // LT / RT: to the next (or previous) first letter when sorted by name, else a page.
    function initial(i) { const t = (app.game(tvAllLibrary.keyAt(i)).title || "").trim().toUpperCase(); return /^[A-Z]/.test(t) ? t[0] : "#" }
    function jumpLetter(dir) {
        const n = count, at = view.currentIndex
        if (n < 2) return
        if (tvAllLibrary.sortMode !== "name") {
            const page = listMode ? Math.max(1, Math.floor(list.height / list.rowH) - 1) : grid.across * Math.max(1, Math.floor(grid.height / grid.cellHeight))
            view.currentIndex = Math.max(0, Math.min(n - 1, at + dir * page)); return
        }
        const here = initial(at)
        let i = at
        if (dir > 0) { while (i < n - 1 && initial(i) === here) i++ }
        else {
            if (i > 0 && initial(i - 1) !== here) i--             // already at a letter's start: the one before
            const l = initial(i)
            while (i > 0 && initial(i - 1) === l) i--
        }
        view.currentIndex = i
        app.say(initial(i))
    }
    function jumpTo(letter) {
        for (let i = 0; i < count; i++) if (initial(i) === letter || (letter !== "#" && initial(i) !== "#" && initial(i) > letter)) { view.currentIndex = i; return }
        view.currentIndex = count - 1
    }
    readonly property string curLetter: currentKey && tvAllLibrary.sortMode === "name" ? initial(view.currentIndex) : ""

    // Keys both views share.
    function keys(event, v) {
        const k = event.key
        if (k === Qt.Key_F2) { if (currentKey && !picking) more(currentKey); event.accepted = true }
        else if (k === Qt.Key_F3) { options(); event.accepted = true }
        else if (k === Qt.Key_F4 || k === Qt.Key_Slash) { searchAsked(); event.accepted = true }
        else if (k === Qt.Key_PageUp || k === Qt.Key_PageDown) { if (storeIds.length > 2) cycleStore(k === Qt.Key_PageDown ? 1 : -1); event.accepted = true }
        else if ((k === Qt.Key_Left || k === Qt.Key_Right) && (event.modifiers & Qt.ShiftModifier)) { jumpLetter(k === Qt.Key_Right ? 1 : -1); event.accepted = true }
        else if (k === Qt.Key_Home) { v.currentIndex = 0; event.accepted = true }
        else if (k === Qt.Key_End) { v.currentIndex = count - 1; event.accepted = true }
        else if (k === Qt.Key_Space && pad.deck && !pad.connected) { options(); event.accepted = true }
        else if (event.text && /^[a-z0-9]$/i.test(event.text) && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier))) {
            // A letter jumps to the first game that starts with it.
            const ch = event.text.toLowerCase()
            for (let i = 0; i < count; i++)
                if ((app.game(tvAllLibrary.keyAt(i)).title || "").toLowerCase().startsWith(ch)) { v.currentIndex = i; break }
            event.accepted = true
        }
    }
    function upFromTop() {
        if (stripShown && strip.count > 0) { strip.forceActiveFocus(); app.uiSound("move"); return true }
        return false
    }

    Rectangle { anchors.fill: parent; color: lib.theme.background }
    TvShield {}  // no click, hover or scroll goes through to Home behind

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 48
        anchors.bottomMargin: 28
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            spacing: 14
            Icon { name: lib.picking ? "check" : tvAllLibrary.showHidden ? "eye-off" : "library"; size: 30; color: lib.tint.primary }
            Text {
                text: lib.picking ? qsTr("Pick games") : lib.shelfName(tvAllLibrary.shelf) || qsTr("Library")
                color: lib.theme.onSurface; font.pixelSize: 34; font.weight: Font.Bold
            }
            Text {
                Layout.leftMargin: 6
                text: lib.picking ? lib.picked.length + qsTr(" picked") : lib.count + (lib.count === 1 ? qsTr(" game") : qsTr(" games"))
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
                        TapHandler { onTapped: { tvAllLibrary.storeFilter = parent.modelData; lib.toTop(); lib.view.forceActiveFocus() } }
                    }
                }
                PadButton { visible: pad.connected && lib.storeIds.length > 2; anchors.verticalCenter: parent.verticalCenter; button: "rb"; style: pad.style; size: 26 }
            }
        }

        // What shapes the list right now: search, sort, filters. A tap on one removes it.
        Flow {
            Layout.fillWidth: true
            spacing: 8
            visible: chips.count > 0
            Repeater {
                id: chips
                model: {
                    const out = []
                    if (tvAllLibrary.search) out.push({ t: qsTr("Search: ") + tvAllLibrary.search, icon: "search", drop: "search" })
                    if (tvAllLibrary.sortMode !== "name") out.push({ t: qsTr("Sorted: ") + lib.sortNames[tvAllLibrary.sortMode], icon: "list", drop: "sort" })
                    if (tvAllLibrary.installedOnly) out.push({ t: qsTr("Installed only"), icon: "download", drop: "installed" })
                    for (const t of tvAllLibrary.tags) out.push({ t: lib.tagNames[t] || t, icon: "filter", drop: "tag:" + t })
                    return out
                }
                Rectangle {
                    required property var modelData
                    height: 34; radius: 17
                    width: chipRow.implicitWidth + 26
                    color: Qt.alpha(lib.tint.primary, 0.18)
                    border.width: 1; border.color: Qt.alpha(lib.tint.primary, 0.6)
                    Row {
                        id: chipRow
                        anchors.centerIn: parent
                        spacing: 7
                        Icon { anchors.verticalCenter: parent.verticalCenter; name: modelData.icon; size: 15; color: lib.tint.primary }
                        Text { anchors.verticalCenter: parent.verticalCenter; text: modelData.t; color: lib.theme.onSurface; font.pixelSize: 15; font.weight: Font.DemiBold }
                        Icon { anchors.verticalCenter: parent.verticalCenter; name: "x"; size: 13; color: lib.theme.onSurfaceVariant }
                    }
                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                    TapHandler {
                        onTapped: {
                            const d = modelData.drop
                            if (d === "search") tvAllLibrary.search = ""
                            else if (d === "sort") tvAllLibrary.sortMode = "name"
                            else if (d === "installed") tvAllLibrary.installedOnly = false
                            else tvAllLibrary.tags = tvAllLibrary.tags.filter(x => "tag:" + x !== d)
                            lib.toTop()
                        }
                    }
                }
            }
        }

        // Played last: up from the first row comes here.
        ColumnLayout {
            visible: lib.stripShown
            Layout.fillWidth: true
            spacing: 8
            Text { text: qsTr("Played recently"); color: strip.activeFocus ? lib.theme.onSurface : lib.theme.onSurfaceVariant; font.pixelSize: 18; font.weight: Font.DemiBold }
            ListView {
                id: strip
                objectName: "tvLibraryStrip"
                Layout.fillWidth: true
                Layout.preferredHeight: Math.round(lib.height * 0.085)
                orientation: ListView.Horizontal
                spacing: 12
                clip: true
                model: lib.stripShown ? lib.recent : []
                keyNavigationEnabled: true
                readonly property string key: (lib.recent[currentIndex] || {}).key || ""
                delegate: Rectangle {
                    id: chip
                    required property var modelData
                    required property int index
                    readonly property bool lit: ListView.isCurrentItem && strip.activeFocus
                    height: ListView.view.height
                    width: Math.round(height * 3.6)
                    radius: 14
                    color: lit ? lib.tint.primary : Qt.alpha(lib.theme.surfaceContainerHigh, 0.8)
                    RoundedArt {
                        x: 6; y: 6; height: parent.height - 12; width: Math.round(height / 1.46); radius: 9
                        ArtImage { anchors.fill: parent; sources: chip.modelData.covers || []; sourceSize.width: 120 }
                    }
                    Text {
                        anchors { left: parent.left; leftMargin: Math.round((parent.height - 12) / 1.46) + 18; right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
                        text: chip.modelData.title; elide: Text.ElideRight; maximumLineCount: 2; wrapMode: Text.WordWrap
                        color: chip.lit ? lib.tint.onPrimary : lib.theme.onSurface; font.pixelSize: 16; font.weight: Font.DemiBold
                    }
                    HoverHandler { cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: lib.play(chip.modelData.key) }
                }
                onCurrentIndexChanged: if (activeFocus) app.uiSound("move")
                onActiveFocusChanged: if (activeFocus) app.say(qsTr("Played recently"))
                Keys.onReturnPressed: if (key) lib.play(key)
                Keys.onEnterPressed: if (key) lib.play(key)
                Keys.onDownPressed: lib.view.forceActiveFocus()
                Keys.onEscapePressed: lib.close()
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_F2) { if (key) lib.more(key); event.accepted = true }
                    else if (event.key === Qt.Key_F3) { lib.options(); event.accepted = true }
                    else if (event.key === Qt.Key_Up) event.accepted = true
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            GridView {
                id: grid
                objectName: "tvLibraryGrid"
                visible: !lib.listMode
                Layout.fillWidth: true
                Layout.fillHeight: true
                focus: !lib.listMode
                clip: true
                model: lib.listMode ? null : tvAllLibrary
                // Covers about a sixth of the screen tall; as many across as fit.
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
                onCurrentIndexChanged: if (lib.visible && activeFocus) { app.uiSound("move"); speak.restart() }
                onCountChanged: if (currentIndex < 0 && count > 0) currentIndex = 0
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
                    picking: lib.picking
                    picked: lib.picked.indexOf(key) !== -1
                    onHoveredChanged: if (hovered && grid.currentIndex !== index) grid.currentIndex = index
                    onOpened: { grid.currentIndex = index; if (!lib.picking) lib.more(lib.currentKey) }
                    onActivated: { grid.currentIndex = index; lib.activate() }
                    onPickRequested: range => { grid.currentIndex = index; if (!lib.picking) lib.picking = true; lib.togglePick(key) }
                }
                Keys.onReturnPressed: lib.activate()
                Keys.onEnterPressed: lib.activate()
                Keys.onEscapePressed: lib.close()
                Keys.onUpPressed: event => { if (currentIndex < across && lib.upFromTop()) return; event.accepted = false }
                Keys.onPressed: event => lib.keys(event, grid)
            }

            ListView {
                id: list
                objectName: "tvLibraryList"
                visible: lib.listMode
                Layout.fillWidth: true
                Layout.fillHeight: true
                focus: lib.listMode
                clip: true
                model: lib.listMode ? tvAllLibrary : null
                readonly property int rowH: 84
                spacing: 6
                keyNavigationEnabled: true
                boundsBehavior: Flickable.StopAtBounds
                preferredHighlightBegin: rowH * 2
                preferredHighlightEnd: height - rowH * 2
                highlightRangeMode: ListView.ApplyRange
                highlightMoveDuration: app.still ? 0 : 160
                onCurrentIndexChanged: if (lib.visible && activeFocus) { app.uiSound("move"); speak.restart() }
                onCountChanged: if (currentIndex < 0 && count > 0) currentIndex = 0
                delegate: Rectangle {
                    id: row
                    required property int index
                    required property string key
                    required property string title
                    required property var covers
                    required property string storeName
                    required property bool installed
                    required property string job
                    required property real progress
                    readonly property bool lit: ListView.isCurrentItem && list.activeFocus
                    readonly property bool isPicked: lib.picked.indexOf(key) !== -1
                    readonly property var g: app.game(key)
                    width: list.width
                    height: list.rowH - 6
                    radius: 16
                    color: lit ? lib.tint.primary : rowHover.hovered ? Qt.alpha(lib.theme.onSurface, 0.08) : Qt.alpha(lib.theme.surfaceContainerHigh, 0.55)
                    RoundedArt {
                        id: rowArt
                        x: 8; y: 6; height: parent.height - 12; width: Math.round(height / 1.46); radius: 8
                        opacity: row.installed || !app.settingsMap.dim_uninstalled ? 1 : 0.55
                        ArtImage { anchors.fill: parent; sources: row.covers || []; sourceSize.width: 120 }
                    }
                    Rectangle {
                        visible: lib.picking
                        x: rowArt.x + rowArt.width + 16; anchors.verticalCenter: parent.verticalCenter
                        width: 26; height: 26; radius: 7
                        color: row.isPicked ? (row.lit ? lib.tint.onPrimary : lib.tint.primary) : "transparent"
                        border.width: 2; border.color: row.lit ? lib.tint.onPrimary : lib.theme.onSurfaceVariant
                        Icon { anchors.centerIn: parent; visible: row.isPicked; name: "check"; size: 18; color: row.lit ? lib.tint.primary : lib.tint.onPrimary }
                    }
                    Column {
                        anchors { left: rowArt.right; leftMargin: lib.picking ? 58 : 18; right: facts.left; rightMargin: 16; verticalCenter: parent.verticalCenter }
                        spacing: 4
                        Text { width: parent.width; text: row.title; elide: Text.ElideRight
                               color: row.lit ? lib.tint.onPrimary : lib.theme.onSurface; font.pixelSize: 20; font.weight: Font.DemiBold }
                        Text {
                            width: parent.width; elide: Text.ElideRight
                            text: [row.storeName, row.job ? qsTr("Working… ") + Math.max(0, Math.floor(row.progress)) + "%" : row.installed ? qsTr("Installed") : qsTr("Not installed")].join("  ·  ")
                            color: row.lit ? Qt.alpha(lib.tint.onPrimary, 0.8) : lib.theme.onSurfaceVariant; font.pixelSize: 15
                        }
                    }
                    Row {
                        id: facts
                        anchors { right: parent.right; rightMargin: 20; verticalCenter: parent.verticalCenter }
                        spacing: 28
                        Text { anchors.verticalCenter: parent.verticalCenter; text: row.g.playtime ? app.playedText(row.g.playtime, row.g.lastPlayed) : qsTr("Not played yet")
                               color: row.lit ? lib.tint.onPrimary : lib.theme.onSurfaceVariant; font.pixelSize: 15 }
                        Text { anchors.verticalCenter: parent.verticalCenter; text: row.g.sizeText || ""
                               width: 90; horizontalAlignment: Text.AlignRight
                               color: row.lit ? lib.tint.onPrimary : lib.theme.onSurfaceVariant; font.pixelSize: 15 }
                    }
                    HoverHandler { id: rowHover; cursorShape: Qt.PointingHandCursor; onHoveredChanged: if (hovered) list.currentIndex = row.index }
                    TapHandler { onTapped: { list.currentIndex = row.index; lib.activate() } }
                }
                Keys.onReturnPressed: lib.activate()
                Keys.onEnterPressed: lib.activate()
                Keys.onEscapePressed: lib.close()
                Keys.onUpPressed: event => { if (currentIndex === 0 && lib.upFromTop()) return; event.accepted = false }
                Keys.onPressed: event => lib.keys(event, list)
            }

            // A to Z down the side, when sorted by name: LT / RT step through it, a tap jumps.
            Column {
                id: rail
                visible: tvAllLibrary.sortMode === "name" && lib.count > 20
                Layout.alignment: Qt.AlignVCenter
                readonly property real step: Math.min(30, Math.max(14, (parent.height - 10) / 27))
                Repeater {
                    model: "#ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("")
                    Text {
                        required property string modelData
                        readonly property bool on: lib.curLetter === modelData
                        width: 24; height: rail.step
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        text: modelData
                        color: on ? lib.tint.primary : lib.theme.onSurfaceVariant
                        opacity: on ? 1 : 0.55
                        font.pixelSize: on ? Math.min(20, rail.step) : Math.min(15, rail.step * 0.75)
                        font.weight: on ? Font.Bold : Font.Normal
                        TapHandler { onTapped: { lib.jumpTo(parent.modelData); lib.view.forceActiveFocus() } }
                    }
                }
            }
        }

        Timer { id: speak; interval: 250; onTriggered: { const g = app.game(lib.currentKey); if (g.key) app.say(g.title + (g.installed ? "" : ", " + qsTr("not installed"))) } }

        Item {
            visible: lib.count === 0
            Layout.fillWidth: true
            Layout.preferredHeight: 0
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: -lib.height * 0.45
                spacing: 18
                EmptyScene { anchors.horizontalCenter: parent.horizontalCenter; width: 300; height: 200; theme: lib.theme
                             kind: app.totalCount === 0 ? "library" : tvAllLibrary.search !== "" ? "search" : "list" }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: tvAllLibrary.search !== "" ? qsTr("Nothing matches") : qsTr("No games here")
                       color: lib.theme.onSurfaceVariant; font.pixelSize: 26 }
            }
        }

        Row {
            Layout.alignment: Qt.AlignRight
            visible: lib.width >= 900
            spacing: 22
            Repeater {
                model: {
                    const g = app.game(lib.currentKey)
                    const first = lib.picking ? (lib.picked.indexOf(g.key) !== -1 ? qsTr("Unpick") : qsTr("Pick")) : g.key && !g.installed ? qsTr("Install") : qsTr("Play")
                    const opts = lib.picking ? qsTr("Actions") : qsTr("Sort and filter")
                    const back = lib.picking ? qsTr("Stop picking") : tvAllLibrary.search ? qsTr("Clear search") : qsTr("Back")
                    const out = pad.connected
                        ? [g.key ? { b: ["a"], t: first } : null, g.key && !lib.picking ? { b: ["x"], t: qsTr("More") } : null,
                           { b: ["y"], t: opts }, { b: ["back"], t: qsTr("Search") },
                           lib.count > 20 ? { b: ["lt", "rt"], t: tvAllLibrary.sortMode === "name" ? qsTr("Letter") : qsTr("Page") } : null,
                           { b: ["b"], t: back }]
                        : pad.deck
                        ? [g.key ? { b: ["a"], t: first } : null, g.key && !lib.picking ? { k: "F2", t: qsTr("More") } : null,
                           { b: ["y"], t: opts }, { b: ["b"], t: back }]
                        : [g.key ? { k: qsTr("Enter"), t: first } : null, g.key && !lib.picking ? { k: "F2", t: qsTr("More") } : null,
                           { k: "F3", t: opts }, { k: "/", t: qsTr("Search") }, { k: qsTr("Esc"), t: back }]
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
