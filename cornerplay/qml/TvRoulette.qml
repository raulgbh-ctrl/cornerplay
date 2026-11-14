import QtQuick
import QtQuick.Effects
import QtQuick.Layouts

// "Can't decide?" in TV mode: say how long, the mood, who is playing and whether it needs to
// work with a controller, then spin. A reel of your installed games races past and slows down
// on one, picked the way What should I play picks (your lists, games left half-way, what you
// usually play at this hour). Up / down: a filter; left / right: change it; A spins; then
// A plays, X spins again, B goes back.
Rectangle {
    id: rl
    objectName: "tvRoulette"
    required property var theme
    required property var tint
    signal closed()
    signal play(string key)
    visible: false
    color: theme.background

    readonly property var filters: [
        { id: "length", label: qsTr("Time"), icon: "clock",
          options: [{ v: "", t: qsTr("Any") }, { v: "quick", t: qsTr("Half an hour") }, { v: "short", t: qsTr("About an hour") }, { v: "long", t: qsTr("A long evening") }] },
        { id: "mood", label: qsTr("Mood"), icon: "sparkles",
          options: [{ v: "", t: qsTr("Any") }, { v: "relaxing", t: qsTr("Relaxing") }, { v: "intense", t: qsTr("Intense") }] },
        { id: "company", label: qsTr("Players"), icon: "user-round",
          options: [{ v: "", t: qsTr("Just me") }, { v: "together", t: qsTr("Together on one screen") }] },
        { id: "pad", label: qsTr("Controller"), icon: "gamepad-2",
          options: [{ v: false, t: qsTr("Anything") }, { v: true, t: qsTr("Works with a controller") }] }
    ]
    property var chosen: ({ length: "", mood: "", company: "", pad: true })
    property int row: 0            // 0..3 the filters, 4 the Spin button
    property string phase: "pick"  // "pick", "spin", "done"
    property var games: []
    property int winner: -1
    readonly property var won: games[winner] || ({})

    function show() { phase = "pick"; row = 4; games = []; winner = -1; visible = true; forceActiveFocus(); app.uiSound("select") }
    function close() { reel.stop(); visible = false; app.uiSound("back"); closed() }
    function change(d) {
        const f = filters[row], opts = f.options
        const i = opts.findIndex(o => o.v === chosen[f.id])
        const c = Object.assign({}, chosen); c[f.id] = opts[(i + d + opts.length) % opts.length].v
        chosen = c
        app.uiSound("move")
    }
    function spin() {
        const r = app.roulette(chosen.length, chosen.mood, chosen.company, chosen.pad)
        if (!r.games.length) { phase = "empty"; app.uiSound("back"); return }
        // The reel: the games several times over, so it has room to race before it stops.
        const loops = 6
        let strip = []
        for (let n = 0; n < loops; n++) strip = strip.concat(r.games)
        games = strip
        winner = (loops - 1) * r.games.length + r.winner
        phase = "spin"
        Qt.callLater(reel.go)  // once the reel is laid out: its size decides where it stops
    }

    Keys.onPressed: event => {
        event.accepted = true
        const k = event.key
        if (phase === "spin") return
        if (k === Qt.Key_Escape || k === Qt.Key_Backspace) {
            if (phase === "done" || phase === "empty") { phase = "pick"; app.uiSound("back") } else close()
            return
        }
        if (phase === "done") {
            if (k === Qt.Key_Return || k === Qt.Key_Enter) { app.uiSound("select"); const key = won.key; close(); play(key) }
            else if (k === Qt.Key_F2 || k === Qt.Key_Space) spin()
            return
        }
        if (k === Qt.Key_Up) { row = Math.max(0, row - 1); app.uiSound("move") }
        else if (k === Qt.Key_Down) { row = Math.min(4, row + 1); app.uiSound("move") }
        else if ((k === Qt.Key_Left || k === Qt.Key_Right) && row < 4) change(k === Qt.Key_Right ? 1 : -1)
        else if (k === Qt.Key_Return || k === Qt.Key_Enter) { if (row < 4) change(1); else spin() }
        else if (k === Qt.Key_F2) spin()
    }

    // The winner's art fills the screen when the reel stops.
    ArtImage {
        anchors.fill: parent
        visible: rl.phase === "done" && !app.light
        sources: rl.won.heroes || []
        fillMode: Image.PreserveAspectCrop
        opacity: rl.phase === "done" && status === Image.Ready ? 0.35 : 0
        Behavior on opacity { NumberAnimation { duration: 600 } }
    }
    Rectangle { anchors.fill: parent
                gradient: Gradient { GradientStop { position: 0.0; color: Qt.alpha(rl.theme.background, 0.3) }
                                     GradientStop { position: 1.0; color: rl.theme.background } } }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Math.round(Math.min(64, rl.width * 0.04))
        spacing: 24
        RowLayout {
            spacing: 14
            Icon { name: "sparkles"; size: 30; color: rl.tint.primary }
            Text { text: qsTr("Can't decide?"); color: rl.theme.onSurface; font.pixelSize: 34; font.weight: Font.Bold }
        }

        // The filters, as rows you step through.
        ColumnLayout {
            visible: rl.phase === "pick" || rl.phase === "empty"
            Layout.fillWidth: true
            spacing: 10
            Repeater {
                model: rl.filters
                Rectangle {
                    id: frow
                    required property var modelData
                    required property int index
                    readonly property bool lit: rl.row === index
                    Layout.fillWidth: true
                    Layout.maximumWidth: 760
                    height: 62; radius: 18
                    color: lit ? rl.tint.primary : Qt.alpha(rl.theme.surfaceContainerHigh, 0.75)
                    Behavior on color { enabled: !app.still; ColorAnimation { duration: 100 } }
                    Icon { anchors { left: parent.left; leftMargin: 20; verticalCenter: parent.verticalCenter }
                           name: frow.modelData.icon; size: 22; color: frow.lit ? rl.tint.onPrimary : rl.theme.onSurfaceVariant }
                    Text { anchors { left: parent.left; leftMargin: 58; verticalCenter: parent.verticalCenter }
                           text: frow.modelData.label; color: frow.lit ? rl.tint.onPrimary : rl.theme.onSurface; font.pixelSize: 19; font.weight: Font.DemiBold }
                    Row {
                        anchors { right: parent.right; rightMargin: 20; verticalCenter: parent.verticalCenter }
                        spacing: 10
                        Icon { anchors.verticalCenter: parent.verticalCenter; name: "chevron-right"; rotation: 180; size: 16
                               color: frow.lit ? rl.tint.onPrimary : rl.theme.outline }
                        Text { anchors.verticalCenter: parent.verticalCenter
                               text: (frow.modelData.options.find(o => o.v === rl.chosen[frow.modelData.id]) || { t: "" }).t
                               color: frow.lit ? rl.tint.onPrimary : rl.theme.onSurface; font.pixelSize: 18; font.weight: Font.DemiBold }
                        Icon { anchors.verticalCenter: parent.verticalCenter; name: "chevron-right"; size: 16
                               color: frow.lit ? rl.tint.onPrimary : rl.theme.outline }
                    }
                    TapHandler { onTapped: { rl.row = frow.index; rl.change(1) } }
                }
            }
            Rectangle {
                Layout.topMargin: 10
                readonly property bool lit: rl.row === 4
                width: spinRow.implicitWidth + 60; height: 64; radius: 32
                color: lit ? rl.tint.primary : Qt.alpha(rl.tint.primary, 0.25)
                border.width: lit ? 0 : 1; border.color: rl.tint.primary
                scale: lit && !app.still ? 1.04 : 1
                Behavior on scale { NumberAnimation { duration: 120 } }
                Row {
                    id: spinRow
                    anchors.centerIn: parent
                    spacing: 10
                    PadButton { visible: pad.connected; anchors.verticalCenter: parent.verticalCenter; button: "a"; style: pad.style; size: 28 }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: qsTr("Spin"); font.pixelSize: 22; font.weight: Font.Bold
                           color: parent.parent.lit ? rl.tint.onPrimary : rl.theme.onSurface }
                }
                TapHandler { onTapped: rl.spin() }
            }
            Text { visible: rl.phase === "empty"; text: qsTr("No installed game fits all of that. Loosen a filter and spin again.")
                   color: rl.theme.error; font.pixelSize: 17 }
        }

        // The reel.
        Item {
            visible: rl.phase === "spin" || rl.phase === "done"
            Layout.fillWidth: true
            Layout.preferredHeight: Math.round(rl.height * 0.42)
            ListView {
                id: reelView
                anchors.fill: parent
                orientation: ListView.Horizontal
                interactive: false
                spacing: 18
                model: rl.games
                readonly property real cell: Math.round(height / 1.46)
                // Every cover that passes the middle ticks, like a wheel's pegs.
                property int passing: -1
                onContentXChanged: {
                    const i = Math.floor((contentX + width / 2) / (cell + spacing))
                    if (i !== passing && rl.phase === "spin") { passing = i; app.uiSound("move") }
                }
                delegate: Item {
                    required property var modelData
                    required property int index
                    width: reelView.cell; height: reelView.height
                    readonly property bool win: rl.phase === "done" && index === rl.winner
                    scale: win ? 1.0 : 0.86
                    opacity: rl.phase === "done" && !win ? 0.35 : 1
                    Behavior on scale { NumberAnimation { duration: 400; easing.type: Easing.OutBack } }
                    Behavior on opacity { NumberAnimation { duration: 400 } }
                    RoundedArt {
                        anchors.fill: parent; radius: 18
                        ArtImage { anchors.fill: parent; sources: modelData.covers || []; sourceSize.width: 400 }
                    }
                    Rectangle { anchors.fill: parent; radius: 18; color: "transparent"; border.width: parent.win ? 4 : 0; border.color: rl.tint.primary }
                }
            }
            // The pointer in the middle.
            Rectangle { anchors.horizontalCenter: parent.horizontalCenter; y: -14; width: 4; height: parent.height + 28; radius: 2
                        color: rl.tint.primary; opacity: rl.phase === "spin" ? 0.9 : 0 }
            NumberAnimation {
                id: reel
                target: reelView; property: "contentX"
                duration: app.still ? 600 : 4200
                easing.type: Easing.OutQuart
                function go() {
                    reelView.forceLayout()
                    reelView.positionViewAtBeginning()
                    from = reelView.contentX
                    to = reelView.originX + rl.winner * (reelView.cell + reelView.spacing) + reelView.cell / 2 - reelView.width / 2
                    restart()
                }
                onFinished: { reelView.positionViewAtIndex(rl.winner, ListView.Center); rl.phase = "done"; app.say(rl.won.title + ". " + (rl.won.why || "")); app.uiSound("select"); if (app.settingsMap.tv_rumble) pad.buzz(60) }
            }
        }
        ColumnLayout {
            visible: rl.phase === "done"
            Layout.alignment: Qt.AlignHCenter
            spacing: 8
            Text { Layout.alignment: Qt.AlignHCenter; text: rl.won.title || ""; color: rl.theme.onSurface; font.pixelSize: 40; font.weight: Font.Bold }
            Text { Layout.alignment: Qt.AlignHCenter; Layout.maximumWidth: rl.width * 0.7; horizontalAlignment: Text.AlignHCenter
                   text: rl.won.why || ""; color: rl.theme.onSurfaceVariant; font.pixelSize: 18; wrapMode: Text.WordWrap }
        }
        Item { Layout.fillHeight: true }
        Row {
            Layout.alignment: Qt.AlignRight
            spacing: 22
            Repeater {
                model: rl.phase === "done"
                    ? [{ b: "a", k: "Enter", t: qsTr("Play") }, { b: "x", k: "Space", t: qsTr("Spin again") }, { b: "b", k: "Esc", t: qsTr("Change filters") }]
                    : rl.phase === "spin" ? [] : [{ b: "", k: "↕", t: qsTr("Filter") }, { b: "", k: "← →", t: qsTr("Change") },
                                                  { b: "a", k: "Enter", t: qsTr("Spin") }, { b: "b", k: "Esc", t: qsTr("Back") }]
                Row {
                    required property var modelData
                    spacing: 8
                    PadButton { visible: pad.connected && modelData.b !== ""; button: modelData.b || "a"; style: pad.style; size: 26 }
                    Rectangle { visible: !pad.connected || modelData.b === ""; height: 26; radius: 6; width: kt.implicitWidth + 16
                                color: Qt.alpha(rl.theme.surfaceContainerHighest, 0.9); border.width: 1; border.color: rl.theme.outlineVariant
                                Text { id: kt; anchors.centerIn: parent; text: modelData.k; color: rl.theme.onSurface; font.pixelSize: 12; font.weight: Font.DemiBold } }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: modelData.t; color: rl.theme.onSurfaceVariant; font.pixelSize: 15 }
                }
            }
        }
    }
}
