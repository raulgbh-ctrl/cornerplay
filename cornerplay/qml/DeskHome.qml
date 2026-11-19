import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import QtQuick.Layouts

// The desktop's Home in another shape (Settings > Appearance > Home layout), shown instead of
// the covers while nothing is searched, filtered or picked:
//   "bento"     tiles of different sizes: the last game, Continue, downloads, this week, free games
//   "console"   a row of covers along the top, the chosen game's art filling the window
//   "magazine"  a cover story in big type, three short pieces beside it, picks for tonight
//   "coverflow" the library as a turning shelf of covers, tilted in 3D
Item {
    id: home
    required property var theme
    property string mode: "bento"
    signal play(string key)
    signal open(string key)
    signal install(string key)

    readonly property var recent: app.recentGames
    readonly property var lead: recent[0] || ({})
    readonly property var leadGame: lead.key ? app.game(lead.key) : ({})
    property var st: ({})
    function refreshStats() { st = app.stats() }
    Component.onCompleted: refreshStats()
    onVisibleChanged: if (visible) refreshStats()
    Connections { target: app; function onStoresChanged() { if (home.visible) home.refreshStats() } }

    function playOrInstall(key) {
        const g = app.game(key)
        if (g.installed) home.play(key); else home.install(key)
    }
    function hours(secs) { return Math.max(1, Math.round((secs || 0) / 3600)) }

    // A tile: a frosted card that lifts a little under the pointer.
    component Tile: Rectangle {
        id: tile
        property string label: ""
        default property alias body: inner.data
        radius: 22
        color: Qt.alpha(home.theme.surfaceContainerHigh, 0.72)
        border.width: 1; border.color: Qt.alpha(home.theme.onSurface, tileHover.hovered ? 0.16 : 0.07)
        scale: tileHover.hovered && !app.still ? 1.012 : 1
        Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
        clip: true
        Text {
            visible: tile.label !== ""
            x: 18; y: 14
            text: tile.label.toUpperCase()
            color: home.theme.onSurfaceVariant; font.pixelSize: 11; font.weight: Font.Bold; font.letterSpacing: 1.2
        }
        Item { id: inner; anchors.fill: parent; anchors.topMargin: tile.label !== "" ? 36 : 0 }
        HoverHandler { id: tileHover }
    }

    // ------------------------------------------------------------------ bento
    Flickable {
        visible: home.mode === "bento"
        anchors.fill: parent
        anchors.margins: 20
        contentHeight: bento.implicitHeight + 20
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: KScrollBar { }
        GridLayout {
            id: bento
            width: parent.width
            columns: 4
            columnSpacing: 14; rowSpacing: 14
            readonly property real cell: (width - 3 * columnSpacing) / 4
            function span(n) { return cell * n + columnSpacing * (n - 1) }

            // The last game: a big tile of its art, Play on it.
            Tile {
                Layout.columnSpan: 2; Layout.rowSpan: 2
                Layout.preferredWidth: bento.span(2)
                Layout.preferredHeight: bento.cell * 1.15 * 2 + 14
                visible: !!home.lead.key
                ArtImage { anchors.fill: parent; sources: (home.lead.heroes || []).concat(home.lead.covers || []); sourceSize.width: 1400; opacity: 0.9 }
                Rectangle { anchors.fill: parent; gradient: Gradient {
                    GradientStop { position: 0.35; color: "transparent" }
                    GradientStop { position: 1.0; color: Qt.alpha(home.theme.background, 0.92) } } }
                Column {
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 24 }
                    spacing: 12
                    Text { text: qsTr("Back in your corner"); color: home.theme.primary; font.pixelSize: 13; font.weight: Font.Bold }
                    LogoTitle { logos: home.lead.logos || []; title: home.lead.title || ""; color: home.theme.onSurface
                                pixelSize: 34; logoHeight: 90; maxWidth: parent.width * 0.8 }
                    Text { text: app.playedText(home.leadGame.playtime || 0, home.leadGame.lastPlayed || 0); color: home.theme.onSurfaceVariant; font.pixelSize: 13 }
                    KButton { theme: home.theme; primary: true; text: home.leadGame.installed ? qsTr("Resume") : qsTr("Install")
                              iconName: home.leadGame.installed ? "play" : "download"; onClicked: home.playOrInstall(home.lead.key) }
                }
                TapHandler { onTapped: home.open(home.lead.key) }
            }
            // Continue playing: the next three.
            Tile {
                label: qsTr("Continue playing")
                Layout.columnSpan: 2; Layout.preferredWidth: bento.span(2); Layout.preferredHeight: bento.cell * 1.15
                Row {
                    anchors { fill: parent; margins: 16; topMargin: 0 }
                    spacing: 12
                    Repeater {
                        model: home.recent.slice(1, 4)
                        Item {
                            id: cont
                            required property var modelData
                            height: parent.height; width: Math.min((parent.width - 24) / 3, (height - 22) / 1.46)
                            RoundedArt { anchors.fill: parent; anchors.bottomMargin: 22; radius: 12
                                ArtImage { anchors.fill: parent; sources: cont.modelData.covers || []; sourceSize.width: 300 } }
                            Text { anchors.bottom: parent.bottom; width: parent.width; text: cont.modelData.title; elide: Text.ElideRight
                                   color: home.theme.onSurface; font.pixelSize: 12; font.weight: Font.DemiBold }
                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                            TapHandler { onTapped: home.open(cont.modelData.key); onDoubleTapped: home.playOrInstall(cont.modelData.key) }
                        }
                    }
                }
            }
            // Downloads, or what is installed.
            Tile {
                id: dlTile
                label: qsTr("Downloads")
                readonly property var dl: (app.downloads || []).find(d => d.state === "running") || (app.downloads || [])[0] || null
                Layout.preferredWidth: bento.span(1); Layout.preferredHeight: bento.cell * 1.15
                Column {
                    anchors { left: parent.left; right: parent.right; margins: 18; verticalCenter: parent.verticalCenter }
                    spacing: 6
                    Text { text: dlTile.dl ? (dlTile.dl.progress >= 0 ? Math.floor(dlTile.dl.progress) + "%" : "…") : home.st.installed || 0
                           color: home.theme.onSurface; font.pixelSize: 40; font.weight: Font.Bold; font.family: app.titleFamily }
                    Text { width: parent.width; text: dlTile.dl ? (app.game(dlTile.dl.key).title || "") : qsTr("games installed")
                           color: home.theme.onSurfaceVariant; font.pixelSize: 13; elide: Text.ElideRight }
                    Rectangle { visible: !!dlTile.dl; width: parent.width; height: 5; radius: 3; color: Qt.alpha(home.theme.onSurface, 0.12)
                        Rectangle { width: parent.width * Math.max(0, (dlTile.dl ? dlTile.dl.progress : 0) / 100); height: 5; radius: 3; color: home.theme.primary } }
                }
            }
            // This week: hours, and the last 14 days as bars.
            Tile {
                label: qsTr("This week")
                Layout.preferredWidth: bento.span(1); Layout.preferredHeight: bento.cell * 1.15
                Column {
                    anchors { left: parent.left; right: parent.right; margins: 18; top: parent.top }
                    spacing: 8
                    Text { text: (home.st.weekHours || 0) + " h"; color: home.theme.onSurface; font.pixelSize: 40; font.weight: Font.Bold; font.family: app.titleFamily }
                    Text { text: qsTr("the last two weeks"); color: home.theme.onSurfaceVariant; font.pixelSize: 12 }
                    Item {
                      width: parent.width; height: 44
                    Row {
                        anchors.bottom: parent.bottom
                        spacing: Math.max(2, (parent.width - 14 * 8) / 13)
                        height: 40
                        Repeater {
                            model: home.st.days || []
                            Rectangle {
                                required property var modelData
                                readonly property real peak: Math.max(1, ...(home.st.days || [1]))
                                y: 40 - height
                                width: 8; radius: 2
                                height: Math.max(3, 40 * modelData / peak)
                                color: modelData > 0 ? home.theme.primary : Qt.alpha(home.theme.onSurface, 0.15)
                            }
                        }
                    }
                    }
                }
            }
            // Free this week on Epic.
            Tile {
                label: qsTr("Free this week")
                visible: (app.epicFree || []).length > 0
                Layout.columnSpan: 2; Layout.preferredWidth: bento.span(2); Layout.preferredHeight: bento.cell * 0.9
                Row {
                    anchors { fill: parent; margins: 16; topMargin: 0 }
                    spacing: 12
                    Repeater {
                        model: (app.epicFree || []).slice(0, 2)
                        Item {
                            id: free
                            required property var modelData
                            width: (parent.width - 12) / 2; height: parent.height
                            RoundedArt { anchors.fill: parent; anchors.bottomMargin: 22; radius: 12
                                Image { anchors.fill: parent; source: free.modelData.wide || free.modelData.tall || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true } }
                            Text { anchors.bottom: parent.bottom; width: parent.width; elide: Text.ElideRight
                                   text: free.modelData.title + (free.modelData.owned ? "  ·  " + qsTr("yours") : "")
                                   color: home.theme.onSurface; font.pixelSize: 12; font.weight: Font.DemiBold }
                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                            TapHandler { onTapped: Qt.openUrlExternally(free.modelData.url) }
                        }
                    }
                }
            }
            // The library in numbers.
            Tile {
                label: qsTr("Your library")
                Layout.columnSpan: (app.epicFree || []).length > 0 ? 2 : 4; Layout.preferredWidth: bento.span((app.epicFree || []).length > 0 ? 2 : 4); Layout.preferredHeight: bento.cell * 0.9
                Row {
                    x: 18; y: Math.max(0, (parent.height - height) / 2)
                    spacing: 34
                    Repeater {
                        model: [{ n: home.st.games || 0, t: qsTr("games") }, { n: home.st.totalHours || 0, t: qsTr("hours played") },
                                { n: home.st.neverPlayed || 0, t: qsTr("never started") }]
                        Column {
                            id: num
                            required property var modelData
                            Text { text: String(num.modelData.n); color: home.theme.onSurface; font.pixelSize: 32; font.weight: Font.Bold; font.family: app.titleFamily }
                            Text { text: num.modelData.t; color: home.theme.onSurfaceVariant; font.pixelSize: 12 }
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ console
    Item {
        id: consoleView
        visible: home.mode === "console"
        anchors.fill: parent
        property int at: 0
        readonly property var cur: consoleRow.currentItem ? consoleRow.currentItem.info : ({})
        // The chosen game's art fills the page, fading from one to the next.
        Item {
            anchors.fill: parent
            ArtImage {
                id: conArt
                anchors.fill: parent
                sources: (consoleView.cur.heroes || []).concat(consoleView.cur.covers || [])
                sourceSize.width: 1920
                opacity: status === Image.Ready ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 400 } }
            }
            Rectangle { anchors.fill: parent; gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.alpha(home.theme.background, 0.55) }
                GradientStop { position: 0.45; color: Qt.alpha(home.theme.background, 0.15) }
                GradientStop { position: 1.0; color: Qt.alpha(home.theme.background, 0.95) } } }
        }
        ListView {
            id: consoleRow
            anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 18; leftMargin: 24 }
            height: 220
            orientation: ListView.Horizontal
            spacing: 14
            clip: false
            model: library
            focus: home.mode === "console" && home.visible
            keyNavigationEnabled: true
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: 0; preferredHighlightEnd: width * 0.4
            highlightMoveDuration: app.still ? 0 : 220
            delegate: Item {
                id: conItem
                required property int index
                required property string key
                required property string title
                required property var covers
                required property var heroes
                required property var logos
                required property bool installed
                required property string storeName
                readonly property var info: ({ key: key, title: title, covers: covers, heroes: heroes, logos: logos, installed: installed, storeName: storeName })
                readonly property bool on: ListView.isCurrentItem
                width: on ? 150 : 112; height: on ? 220 : 164
                y: on ? 0 : 28
                Behavior on width { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                Behavior on y { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                RoundedArt { anchors.fill: parent; radius: 14
                    ArtImage { anchors.fill: parent; sources: conItem.covers || []; sourceSize.width: 300 } }
                Rectangle { anchors.fill: parent; radius: 14; color: "transparent"; border.width: conItem.on ? 3 : 0; border.color: "white" }
                HoverHandler { cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: consoleRow.currentIndex = conItem.index; onDoubleTapped: home.playOrInstall(conItem.key) }
            }
            Keys.onReturnPressed: home.playOrInstall(consoleView.cur.key)
        }
        Column {
            anchors { left: parent.left; leftMargin: 40; bottom: parent.bottom; bottomMargin: 40 }
            width: Math.min(parent.width * 0.55, 640)
            spacing: 14
            LogoTitle { logos: consoleView.cur.logos || []; title: consoleView.cur.title || ""; color: home.theme.onSurface
                        pixelSize: 44; logoHeight: 120; maxWidth: parent.width }
            Text { text: [consoleView.cur.storeName || "", consoleView.cur.key ? app.playedText(app.game(consoleView.cur.key).playtime || 0, app.game(consoleView.cur.key).lastPlayed || 0) : ""].filter(x => x).join("  ·  ")
                   color: home.theme.onSurfaceVariant; font.pixelSize: 14 }
            Row {
                spacing: 12
                KButton { theme: home.theme; primary: true; text: consoleView.cur.installed ? qsTr("Play") : qsTr("Install")
                          iconName: consoleView.cur.installed ? "play" : "download"; onClicked: home.playOrInstall(consoleView.cur.key) }
                KButton { theme: home.theme; text: qsTr("Details"); onClicked: home.open(consoleView.cur.key) }
            }
        }
    }

    // ------------------------------------------------------------------ magazine
    Flickable {
        id: mag
        visible: home.mode === "magazine"
        anchors.fill: parent
        anchors.margins: 24
        contentHeight: magCol.implicitHeight + 30
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: KScrollBar { }
        readonly property var info: home.lead.key ? app.gameDetails(home.lead.key) : ({})
        readonly property var sale: (app.wishlistSales || [])[0] || null
        readonly property var picks: {
            const out = []
            for (let i = 0; i < Math.min(library.rowCount ? library.rowCount() : 0, 200) && out.length < 8; i++) {
                const k = library.keyAt ? library.keyAt(i) : ""
                const g = k ? app.game(k) : null
                if (g && g.installed && !(g.playtime > 0)) out.push(g)
            }
            return out
        }
        ColumnLayout {
            id: magCol
            width: parent.width
            spacing: 22
            // The masthead.
            RowLayout {
                Layout.fillWidth: true
                Text { text: "cornerplay"; color: home.theme.onSurface; font.pixelSize: 40; font.family: "Lora"; font.weight: Font.Bold; font.italic: true }
                Item { Layout.fillWidth: true }
                Text { text: Qt.formatDate(new Date(), "d MMMM yyyy").toUpperCase(); color: home.theme.onSurfaceVariant; font.pixelSize: 12; font.letterSpacing: 2; font.weight: Font.Bold }
            }
            Rectangle { Layout.fillWidth: true; height: 2; color: home.theme.onSurface }
            RowLayout {
                Layout.fillWidth: true
                spacing: 24
                // The cover story: the last game, in big type.
                Item {
                    Layout.preferredWidth: Math.max(300, magCol.width - 324)
                    Layout.preferredHeight: 460
                    RoundedArt { anchors.fill: parent; radius: 6
                        ArtImage { anchors.fill: parent; sources: (home.lead.heroes || []).concat(home.lead.covers || []); sourceSize.width: 1600 } }
                    Rectangle { anchors.fill: parent; radius: 6; gradient: Gradient {
                        GradientStop { position: 0.3; color: "transparent" }
                        GradientStop { position: 1.0; color: Qt.alpha("black", 0.85) } } }
                    Column {
                        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 28 }
                        spacing: 10
                        Text { text: qsTr("COVER STORY"); color: home.theme.primary; font.pixelSize: 12; font.weight: Font.Bold; font.letterSpacing: 2 }
                        Text { width: parent.width; text: home.lead.title || ""; color: "white"; wrapMode: Text.WordWrap
                               font.pixelSize: 54; font.family: "Lora"; font.weight: Font.Bold; lineHeight: 0.95 }
                        Text { width: parent.width * 0.85; text: mag.info.description || ""; color: Qt.alpha("white", 0.85); wrapMode: Text.WordWrap
                               maximumLineCount: 3; elide: Text.ElideRight; font.pixelSize: 15; font.family: "Lora" }
                        KButton { theme: home.theme; primary: true; text: home.leadGame.installed ? qsTr("Resume") : qsTr("Install")
                                  iconName: home.leadGame.installed ? "play" : "download"; onClicked: home.playOrInstall(home.lead.key) }
                    }
                    TapHandler { onTapped: home.open(home.lead.key) }
                }
                // Three short pieces.
                ColumnLayout {
                    Layout.preferredWidth: 300; Layout.maximumWidth: 300
                    Layout.alignment: Qt.AlignTop
                    spacing: 18
                    Repeater {
                        model: [
                            home.recent[1] ? { k: qsTr("ALSO PLAYING"), t: home.recent[1].title, s: app.playedText(0, home.recent[1].lastPlayed), key: home.recent[1].key, art: home.recent[1].covers } : null,
                            mag.sale ? { k: qsTr("ON SALE FROM YOUR WISHLIST"), t: mag.sale.title, url: mag.sale.url, art: mag.sale.tall ? [mag.sale.tall] : null,
                                                     s: ((mag.sale.discount || (mag.sale.best || {}).cut) ? "-" + (mag.sale.discount || mag.sale.best.cut) + "%  " : "") + (mag.sale.price || "") } : null,
                            { k: qsTr("THE WEEK IN NUMBERS"), t: qsTr("%1 h played").arg(home.st.weekHours || 0), s: qsTr("%1 sessions in all").arg(home.st.sessions || 0) }
                        ].filter(x => x)
                        Item {
                            id: pieceBox
                            required property var modelData
                            Layout.fillWidth: true
                            implicitHeight: piece.implicitHeight + 18
                            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Qt.alpha(home.theme.onSurface, 0.2) }
                            RowLayout {
                                id: piece
                                width: parent.width
                                spacing: 12
                                RoundedArt { visible: !!pieceBox.modelData.art; Layout.preferredWidth: 56; Layout.preferredHeight: 78; radius: 4
                                    ArtImage { anchors.fill: parent; sources: pieceBox.modelData.art || []; sourceSize.width: 120 } }
                                Column {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Text { text: pieceBox.modelData.k; color: home.theme.primary; font.pixelSize: 10; font.weight: Font.Bold; font.letterSpacing: 1.5 }
                                    Text { width: parent.width; text: pieceBox.modelData.t || ""; color: home.theme.onSurface; wrapMode: Text.WordWrap
                                           font.pixelSize: 20; font.family: "Lora"; font.weight: Font.Bold }
                                    Text { width: parent.width; text: pieceBox.modelData.s || ""; color: home.theme.onSurfaceVariant; font.pixelSize: 12; elide: Text.ElideRight }
                                }
                            }
                            HoverHandler { cursorShape: Qt.PointingHandCursor }
                            TapHandler { onTapped: { const m = pieceBox.modelData; if (m.key) home.open(m.key); else if (m.url) Qt.openUrlExternally(m.url) } }
                        }
                    }
                }
            }
            Text { text: qsTr("Picks for tonight"); color: home.theme.onSurface; font.pixelSize: 26; font.family: "Lora"; font.weight: Font.Bold; visible: mag.picks.length > 0 }
            Row {
                spacing: 16
                visible: mag.picks.length > 0
                Repeater {
                    model: mag.picks
                    Item {
                        id: pick
                        required property var modelData
                        width: 132; height: 220
                        RoundedArt { width: 132; height: 192; radius: 6
                            ArtImage { anchors.fill: parent; sources: pick.modelData.covers || []; sourceSize.width: 270 } }
                        Text { y: 198; width: parent.width; text: pick.modelData.title; elide: Text.ElideRight; color: home.theme.onSurface; font.pixelSize: 12; font.family: "Lora" }
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: home.open(pick.modelData.key); onDoubleTapped: home.play(pick.modelData.key) }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ cover flow
    Item {
        id: flow
        visible: home.mode === "coverflow"
        anchors.fill: parent
        readonly property var cur: flowView.currentItem ? flowView.currentItem.info : ({})
        PathView {
            id: flowView
            anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: parent.height * 0.08 }
            height: parent.height * 0.62
            model: library
            pathItemCount: Math.max(5, Math.min(11, Math.floor(width / 150)))
            preferredHighlightBegin: 0.5; preferredHighlightEnd: 0.5
            highlightRangeMode: PathView.StrictlyEnforceRange
            focus: home.mode === "coverflow" && home.visible
            snapMode: PathView.SnapToItem
            highlightMoveDuration: app.still ? 0 : 260
            readonly property real coverH: height * 0.8
            path: Path {
                startX: 0; startY: flowView.height / 2
                PathAttribute { name: "turn"; value: 60 }
                PathAttribute { name: "zoom"; value: 0.78 }
                PathAttribute { name: "depth"; value: 0 }
                PathLine { x: flowView.width * 0.42; y: flowView.height / 2 }
                PathAttribute { name: "turn"; value: 55 }
                PathAttribute { name: "zoom"; value: 0.85 }
                PathAttribute { name: "depth"; value: 50 }
                PathLine { x: flowView.width * 0.5; y: flowView.height / 2 }
                PathAttribute { name: "turn"; value: 0 }
                PathAttribute { name: "zoom"; value: 1.0 }
                PathAttribute { name: "depth"; value: 100 }
                PathLine { x: flowView.width * 0.58; y: flowView.height / 2 }
                PathAttribute { name: "turn"; value: -55 }
                PathAttribute { name: "zoom"; value: 0.85 }
                PathAttribute { name: "depth"; value: 50 }
                PathLine { x: flowView.width; y: flowView.height / 2 }
                PathAttribute { name: "turn"; value: -60 }
                PathAttribute { name: "zoom"; value: 0.78 }
                PathAttribute { name: "depth"; value: 0 }
            }
            delegate: Item {
                id: fItem
                required property int index
                required property string key
                required property string title
                required property var covers
                required property var heroes
                required property var logos
                required property bool installed
                required property string storeName
                readonly property var info: ({ key: key, title: title, covers: covers, heroes: heroes, logos: logos, installed: installed, storeName: storeName })
                width: flowView.coverH / 1.46; height: flowView.coverH
                z: PathView.depth || 0
                scale: PathView.zoom || 1
                transform: Rotation { origin.x: fItem.width / 2; origin.y: fItem.height / 2; axis { x: 0; y: 1; z: 0 }
                                            angle: fItem.PathView.turn || 0 }
                RoundedArt { anchors.fill: parent; radius: 10
                    ArtImage { anchors.fill: parent; sources: fItem.covers || []; sourceSize.width: 420 } }
                // Its reflection on the floor.
                Item {
                    y: parent.height + 6; width: parent.width; height: parent.height * 0.3
                    clip: true; opacity: 0.25
                    ArtImage { width: parent.width; height: fItem.height; sources: fItem.covers || []; sourceSize.width: 200
                               transform: Scale { origin.y: fItem.height / 2; yScale: -1 } }
                    Rectangle { anchors.fill: parent; gradient: Gradient {
                        GradientStop { position: 0; color: Qt.alpha(home.theme.background, 0.2) }
                        GradientStop { position: 1; color: home.theme.background } } }
                }
                TapHandler {
                    onTapped: { if (flowView.currentIndex === fItem.index) home.open(fItem.key); else flowView.currentIndex = fItem.index }
                    onDoubleTapped: home.playOrInstall(fItem.key)
                }
            }
            WheelHandler { onWheel: event => { if (event.angleDelta.y < 0 || event.angleDelta.x < 0) flowView.incrementCurrentIndex(); else flowView.decrementCurrentIndex() } }
            Keys.onLeftPressed: decrementCurrentIndex()
            Keys.onRightPressed: incrementCurrentIndex()
            Keys.onReturnPressed: home.playOrInstall(flow.cur.key)
        }
        Column {
            anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: parent.height * 0.06 }
            spacing: 10
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: flow.cur.title || ""; color: home.theme.onSurface
                   font.pixelSize: 28; font.weight: Font.Bold; font.family: app.titleFamily }
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: flow.cur.storeName || ""; color: home.theme.onSurfaceVariant; font.pixelSize: 13 }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 12
                KButton { theme: home.theme; primary: true; text: flow.cur.installed ? qsTr("Play") : qsTr("Install")
                          iconName: flow.cur.installed ? "play" : "download"; onClicked: home.playOrInstall(flow.cur.key) }
                KButton { theme: home.theme; text: qsTr("Details"); onClicked: home.open(flow.cur.key) }
            }
        }
    }
}
