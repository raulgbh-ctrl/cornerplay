import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import QtQuick.Layouts
import "protondb.js" as ProtonDB

// Full-screen, couch-distance view driven entirely by arrows / a controller.
FocusScope {
    id: tv
    required property var theme
    signal exit()
    // The Guide menus open from anywhere in TV mode (a game's page, Settings, Downloads), like
    // Steam's: keys nothing else used come up to here.
    Keys.onPressed: event => {
        if (event.key === Qt.Key_F10) { mainMenu.show(); event.accepted = true }
        else if (event.key === Qt.Key_F9) { quickMenu.show(); event.accepted = true }
    }

    property var cur: ({})

    // Skins (Settings > TV mode > Look), all Cornerplay's own: "" the usual; "phosphor" an old
    // CRT's scanlines and glow with pixel titles; "gallery" calm and flat, bigger covers, no
    // moving art; "arcade" a dark room with a neon glow around the game in focus.
    readonly property string skin: app.settingsMap.tv_skin || ""
    readonly property string skinFamily: ({ phosphor: "Silkscreen", gallery: "Lora", arcade: "Barlow Condensed" })[skin] || app.titleFamily

    // The focused game's own colour (from its cover) tints the glow and the active tab.
    property string gameAccent: ""
    property color accent: gameAccent || theme.primary
    onGameAccentChanged: if (gameAccent && tv.visible) app.lightsFor(gameAccent)  // room lights (lights.py)
    Behavior on accent { enabled: !app.still; ColorAnimation { duration: 450 } }
    readonly property var tint: {
        const c = tv.accent
        const lum = 0.299 * c.r + 0.587 * c.g + 0.114 * c.b
        return Object.assign({}, tv.theme, { primary: c.toString(), onPrimary: lum > 0.55 ? "#1b1b1f" : "#ffffff" })
    }
    // Description and genres, asked for once the focus rests (no store requests while scrolling past).
    property var info: ({})
    property string infoKey: ""
    // The trailer starts after the focus has rested a moment (and stops as soon as it moves).
    property string trailerUrl: ""
    Timer { id: trailerTimer; interval: 2500; onTriggered: tv.trailerUrl = tv.info.trailer || "" }
    onInfoChanged: { trailerUrl = ""; if (info.trailer) trailerTimer.restart(); else trailerTimer.stop() }
    property var ach: ({})
    property var anim: ({})   // animated cover / banner (SteamGridDB)
    Timer { id: infoTimer; interval: 350; onTriggered: {
        tv.info = tv.infoKey ? app.gameDetails(tv.infoKey) : ({})
        tv.ach = tv.infoKey ? app.achievements(tv.infoKey) : ({})
        tv.anim = tv.infoKey ? app.animatedArt(tv.infoKey) : ({})
    } }
    // Animated art plays only when it costs nothing that matters: plugged in (or a desktop),
    // full effects, someone is using the screen, and Cornerplay is in front.
    readonly property bool plugged: topStatus.batt.level === undefined || !!topStatus.batt.charging
    // A menu or the keyboard covers the screen: what moves behind it can rest.
    readonly property bool frosted: searching || (typeof mainMenu !== "undefined" && (mainMenu.open || quickMenu.open)) || panel.visible
                                    || (typeof tvSettings !== "undefined" && tvSettings.visible)
                                    || (typeof libraryPage !== "undefined" && libraryPage.visible)
    // Anything over Home (a page, a menu, the keyboard, a dialog)? Home's covers and buttons then
    // ignore the pointer, and keep ignoring it for a moment after it closes: the click or tap that
    // closed it (or the second half of a double click) must never land on the game underneath.
    readonly property int layers: [searching, intro.visible, gamePage.visible, gamePage.viewing, panel.visible,
        tvDownloads.visible, phonePage.visible, gameNight.visible, tvStats.visible, roulette.visible,
        libraryPage.visible, pinPrompt.visible, libPrompt.visible, prompt.visible, tvSettings.visible,
        padTest.visible, saver.visible, whoPicker.visible,
        mainMenu.open, moreMenu.open, powerMenu.open, quickMenu.open, libSheet.open, goalSheet.open, homeSheet.open,
        !!(tv.Window.window && tv.Window.window.openPopups && tv.Window.window.openPopups.length > 0)].filter(Boolean).length
    readonly property bool covered: layers > 0
    property bool settling: false
    property double quietUntil: 0
    // Whenever a layer opens or closes (Home, or one page over another), clicks rest for half a
    // second: a double click that closed a menu must not press the button that was under it.
    onLayersChanged: { quietUntil = Date.now() + 500; settling = true; settleTimer.restart() }
    Timer { id: settleTimer; interval: 500; onTriggered: tv.settling = false }
    readonly property bool homeLive: !covered && !settling
    // For a click that is about to open or start a game: checked again when it fires, because a
    // single tap is only reported once the double-click time has passed.
    function pointerOk() { return !covered && Date.now() >= quietUntil }
    // Pointing at a cover focuses it, but only when the pointer really moved: a cursor resting over
    // the grid while the d-pad scrolls it must not pull the focus back to whatever slides under it
    // (it kept the Library from going down). A scroll re-sends hover at the very same spot.
    property point lastPointer: Qt.point(-1, -1)
    function pointerMoved(p) {
        if (p.x === 0 && p.y === 0) return false  // a hover that has only just begun: no position yet
        const moved = Math.abs(p.x - lastPointer.x) + Math.abs(p.y - lastPointer.y) > 0.5
        lastPointer = p
        return moved
    }
    // Steam-style status icons (top bar, quick access): Wi-Fi or wired, Bluetooth in use, volume.
    readonly property var statusIcons: {
        const s = app.system, n = s.network || {}, b = s.bluetooth || {}, a = s.audio || {}
        const out = []
        if (n.ssid) out.push("wifi"); else if (n.wifi === false && !n.wired) out.push("wifi-off")
        if ((b.devices || []).some(d => d.connected)) out.push("bluetooth")
        if (a.volume !== undefined) out.push(controls.volumeIcon(a))
        return out
    }
    Timer { interval: 30000; repeat: true; triggeredOnStart: true; running: tv.visible && Qt.application.state === Qt.ApplicationActive
            onTriggered: app.refreshSystem() }
    readonly property bool animOk: !!app.settingsMap.tv_animated && !app.still && !tv.calm && tv.plugged && !tv.frosted
                                   && tv.visible && Qt.application.state === Qt.ApplicationActive
    onCurChanged: {
        if ((cur.key || "") === infoKey) return  // same game, just refreshed
        infoKey = cur.key || ""
        gameAccent = cur.key ? app.gameColour(cur.key) : ""
        info = ({}); ach = ({}); anim = ({})
        infoTimer.restart()
    }
    // The stores you use (games there, or signed in), like the sidebar: no empty Retro
    // games tab for someone who uses neither, and LB / RB skip them.
    readonly property var storeIds: [""].concat(app.storesInfo.filter(s => s.count > 0 || (s.inAccounts && s.loggedIn)).map(s => s.id))

    // Shelves: Continue playing, Favourites, collections, Recently added, Library. Up / down.
    property var shelfList: []
    property int shelfAt: 0
    readonly property var shelf: shelfList[shelfAt] || ({ id: "", name: qsTr("Library") })
    property bool shelvesShown: false   // the first time, start on the top shelf, like a console's home
    function loadShelves() {
        const keep = tvLibrary.shelf
        shelfList = app.shelfList()
        const i = shelfList.findIndex(s => s.id === keep)
        shelfAt = !shelvesShown ? 0 : i >= 0 ? i : shelfList.length - 1
        shelvesShown = true
        if (!searching && tvLibrary.search === "") tvLibrary.shelf = shelf.id
    }
    readonly property var nextShelf: tvLibrary.search === "" ? (shelfList[shelfAt + 1] || null) : null
    onNextShelfChanged: tvNextLibrary.shelf = nextShelf ? nextShelf.id : ""
    Connections {
        target: tvLibrary
        function onFilterChanged() {
            tvNextLibrary.storeFilter = tvLibrary.storeFilter
            tvNextLibrary.installedOnly = tvLibrary.installedOnly
        }
    }
    function stepShelf(step) {
        if (tvLibrary.search !== "") return
        const i = Math.max(0, Math.min(shelfList.length - 1, shelfAt + step))
        if (i === shelfAt) return
        app.uiSound("move")
        shelfAt = i
        tvLibrary.shelf = shelf.id
        grid.currentIndex = 0
        grid.contentX = 0
        sync()
        shelfSwap.go(0, step > 0 ? 40 : -40)
    }
    // The shelf's covers glide in from the way you moved, and fade up.
    ParallelAnimation {
        id: shelfSwap
        function go(dx, dy) { if (app.still) return; sx.from = dx; sy.from = dy; restart() }
        NumberAnimation { target: grid; property: "opacity"; from: 0.15; to: 1; duration: 240; easing.type: Easing.OutCubic }
        NumberAnimation { id: sx; target: shelfSlide; property: "x"; to: 0; duration: 280; easing.type: Easing.OutCubic }
        NumberAnimation { id: sy; target: shelfSlide; property: "y"; to: 0; duration: 280; easing.type: Easing.OutCubic }
    }
    Connections {
        target: app
        function onCollectionsChanged() { tv.loadShelves() }
        function onStoresChanged() { if (tv.visible) Qt.callLater(tv.loadShelves) }
    }

    // Search: an on-screen keyboard for the controller; a real keyboard just types.
    property bool searching: false
    function openSearch(first) {
        if (!searching) { searching = true; tvLibrary.shelf = "" }
        if (first) tvLibrary.search = tvLibrary.search + first
        keys.forceActiveFocus()
        grid.currentIndex = 0; sync()
    }
    function closeSearch(keepResults) {
        searching = false
        if (!keepResults || tvLibrary.search === "") clearSearch()
        grid.forceActiveFocus(); sync()
    }
    function clearSearch() {
        tvLibrary.search = ""
        tvLibrary.shelf = shelf.id
        grid.currentIndex = 0; sync()
    }

    // The focused game: the Library page's while it is open, else the home shelf's.
    function sync() { cur = app.game(libraryPage.visible ? libraryPage.currentKey : tvLibrary.keyAt(grid.currentIndex)); wake() }

    // Calm: after 30 s without input the moving art and the trailer stop (they redraw the
    // whole screen 60 times a second: a drained Steam Deck battery while you look at a menu).
    property bool calm: false
    function wake() { calm = false; calmTimer.restart(); lastInput = Date.now() }
    Timer { id: calmTimer; interval: 30000; running: tv.visible; onTriggered: tv.calm = true }
    function cycleStore(step) {
        app.uiSound("move")
        const i = storeIds.indexOf(tvLibrary.storeFilter)
        tvLibrary.storeFilter = storeIds[(i + step + storeIds.length) % storeIds.length]
        grid.currentIndex = 0
        sync()
        shelfSwap.go(step > 0 ? 60 : -60, 0)
    }
    function accept() {
        if (!cur.key) return
        app.uiSound("select")
        const target = app.launchTarget(cur.key)
        if (target) app.play(target)
        else panel.show()
    }
    function buildActions() {
        const out = []
        if (!cur.key) return out
        const copies = cur.copies.length ? cur.copies : [{ key: cur.key, storeName: cur.storeName }]
        const removable = []
        for (const c of copies) {
            const g = app.game(c.key)
            if (g.job) out.push({ label: qsTr("Cancel ") + ({ install: "install", update: "update" }[g.job] || "removal") + " · " + c.storeName, act: "cancel", key: c.key })
            else if (g.installed) {
                out.push({ label: qsTr("Play on ") + c.storeName, act: "play", key: c.key })
                if (g.update) out.push({ label: qsTr("Update on ") + c.storeName, act: "update", key: c.key })
                if (g.store !== "battlenet") removable.push(c)
            }
            else {
                out.push({ label: qsTr("Install from ") + c.storeName, act: "install", key: c.key })
                if (!g.external)
                    out.push({ label: app.nightQueue.indexOf(c.key) !== -1 ? qsTr("Don't install tonight") : qsTr("Install tonight from ") + c.storeName,
                               act: "tonight", key: c.key })
            }
        }
        if (app.nowPlaying.some(p => p.key === cur.key)) {
            out.unshift({ label: qsTr("Force close (if it hangs)"), act: "kill", key: cur.key })
            out.unshift({ label: qsTr("Quit game"), act: "quit", key: cur.key })
        }
        out.push({ label: cur.favourite ? qsTr("Remove from favourites") : qsTr("Add to favourites"), act: "fav", key: cur.key })
        // Backlog status: one row that steps through the choices.
        const names = { "": qsTr("None"), playing: qsTr("Playing"), want: qsTr("Want to play"), finished: qsTr("Finished"), dropped: qsTr("Dropped") }
        out.push({ label: qsTr("Status: ") + names[cur.status || ""] + "  \u25B8", act: "status", key: cur.key })
        // Controller as keyboard and mouse (padkeys.py): one row that steps through the layouts.
        {
            const keys = app.gameOptions(cur.key).pad_keys || ""
            const names = { "": qsTr("Off"), wasd: qsTr("WASD"), strategy: qsTr("Strategy"), pointclick: qsTr("Point and click"), custom: qsTr("My layout") }
            out.push({ label: qsTr("Controller as keyboard: ") + names[keys] + "  \u25B8", act: "padkeys", key: cur.key })
        }
        // Controller layout for this game (padlayout.py): one row that steps through them.
        if (cur.store !== "steam") {
            const lay = app.gameOptions(cur.key).pad_layout || ""
            const name = lay ? controls.layoutNames[lay] : qsTr("Default") + " (" + controls.layoutNames[app.settingsMap.pad_layout || ""] + ")"
            out.push({ label: qsTr("Controller: ") + name + "  \u25B8", act: "padlayout", key: cur.key })
        }
        out.push({ label: cur.hidden ? qsTr("Unhide game") : qsTr("Hide game"), act: cur.hidden ? "unhide" : "hide", key: cur.key })
        // Last, away from Play: removing a game is never one press below starting it.
        for (const c of removable) out.push({ label: qsTr("Uninstall from ") + c.storeName, act: "uninstall", key: c.key })
        return out
    }

    function grab() { loadShelves(); grid.forceActiveFocus(); sync() }
    onVisibleChanged: if (visible) { grab(); maybeIntro(); if (!intro.visible) Qt.callLater(maybeAskWho); app.refreshNews() }
    // "Who's playing?" once per start, when several people use this PC (TvWho.qml).
    property bool whoAsked: false
    function maybeAskWho() {
        if (whoAsked || !tv.visible || intro.visible || !app.settingsMap.tv_who || app.profiles.length < 2) return
        whoAsked = true
        whoPicker.show()
    }
    // Screensaver (TvScreensaver.qml): after tv_screensaver quiet minutes, while nothing runs.
    property real lastInput: Date.now()
    Connections { target: pad; function onActivity() { tv.lastInput = Date.now() } }
    Timer {
        interval: 5000; repeat: true
        running: tv.visible && (app.settingsMap.tv_screensaver || 0) > 0
        onTriggered: {
            if (saver.visible || intro.visible || whoPicker.visible || app.nowPlaying.length > 0
                    || Qt.application.state !== Qt.ApplicationActive) { tv.lastInput = Date.now(); return }
            if (Date.now() - tv.lastInput > app.settingsMap.tv_screensaver * 60000) {
                tv.focusBeforeSaver = tv.Window.activeFocusItem
                saver.start()
            }
        }
    }
    property Item focusBeforeSaver: null
    Component.onCompleted: if (visible) { Qt.callLater(grab); Qt.callLater(maybeIntro) }
    Connections {
        target: app
        function onGameChanged(key) { tv.sync(); if (panel.visible) panel.rows = tv.buildActions() }
        function onGameColourReady(key, colour) { if (key === tv.cur.key) tv.gameAccent = colour }
        function onDetailsReady(key, d) { if (key === tv.infoKey) tv.info = d }
        function onAchievementsReady(key, d) { if (key === tv.infoKey) tv.ach = d }
        function onAnimatedArtReady(key, d) { if (key === tv.infoKey) tv.anim = d }
    }

    // The screen behind a menu or the keyboard, blurred like frosted glass (art and content).
    // It blurs a snapshot taken as it appears (the screen behind is paused meanwhile, see
    // frosted), not the live screen: one blur, instead of one every frame.
    component Frost: Item {
        id: fr
        anchors.fill: parent
        readonly property bool gpu: !app.light && GraphicsInfo.api !== GraphicsInfo.Software
        readonly property bool on: gpu && visible
        onOnChanged: if (on) { snapStage.scheduleUpdate(); snapContent.scheduleUpdate() }
        // Typing a search changes the shelf behind the keyboard: take a fresh picture of it.
        Connections { target: tvLibrary; function onFilterChanged() { if (fr.on) Qt.callLater(snapContent.scheduleUpdate) } }
        Connections { target: tvAllLibrary; function onFilterChanged() { if (fr.on && fr.overLib) Qt.callLater(fr.resnap) } }
        Connections { target: fr.overLib ? libraryPage : null; function onListModeChanged() { if (fr.on) Qt.callLater(fr.resnap) } }
        function resnap() { snapStage.scheduleUpdate() }
        // Over the Library page, it is the page that is blurred (it covers the home screen).
        readonly property bool overLib: typeof libraryPage !== "undefined" && libraryPage.visible
        ShaderEffectSource { id: snapStage; sourceItem: fr.on ? (fr.overLib ? libraryPage : stage) : null; live: false; hideSource: false
                             anchors.fill: parent; visible: false }
        ShaderEffectSource { id: snapContent; sourceItem: fr.on && !fr.overLib ? tvContent : null; live: false; hideSource: false
                             x: tvContent.x; y: tvContent.y; width: tvContent.width; height: tvContent.height; visible: false }
        MultiEffect { anchors.fill: parent; visible: fr.on; source: snapStage
                      autoPaddingEnabled: false; blurEnabled: true; blur: 1.0; blurMax: 48 }
        MultiEffect { x: tvContent.x; y: tvContent.y; width: tvContent.width; height: tvContent.height
                      visible: fr.on && !fr.overLib; source: snapContent
                      blurEnabled: true; blur: 1.0; blurMax: 48 }  // its blur spills past its edges: no seam
    }

    // One of the two full-screen art images that take turns (see stage).
    component ArtLayer: ArtImage {
        property string tag: ""
        anchors.fill: parent
        // Up to 3840: a 4K TV gets Steam's double-size banners (covers.py) at their full sharpness.
        sourceSize.width: Math.min(app.light ? 1280 : 3840, Math.max(640, Math.ceil(width * Screen.devicePixelRatio / 40) * 40))
        horizontalAlignment: Image.AlignRight
        Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 450; easing.type: Easing.InOutQuad } }
        // Slow pan and zoom while the art is showing (off in Light mode).
        transformOrigin: Item.Right
        transform: Translate { id: drift }
        readonly property bool drifting: opacity > 0 && status === Image.Ready && !app.still && tv.visible && !tv.frosted
                                         && !tv.calm && Qt.application.state === Qt.ApplicationActive
        SequentialAnimation on scale {
            running: drifting
            loops: Animation.Infinite
            NumberAnimation { from: 1.0; to: 1.08; duration: 18000; easing.type: Easing.InOutSine }
            NumberAnimation { from: 1.08; to: 1.0; duration: 18000; easing.type: Easing.InOutSine }
        }
        SequentialAnimation {
            running: drifting
            loops: Animation.Infinite
            NumberAnimation { target: drift; property: "x"; from: 0; to: -40; duration: 18000; easing.type: Easing.InOutSine }
            NumberAnimation { target: drift; property: "x"; from: -40; to: 0; duration: 18000; easing.type: Easing.InOutSine }
        }
        onStatusChanged: {
            if (stage.incoming !== tag) return
            if (status === Image.Ready) {
                stage.showA = tag === "a"; stage.none = false; stage.incoming = ""
            } else if (status === Image.Error && at >= sources.length - 1) {
                stage.none = true; stage.incoming = ""
            }
        }
    }

    Rectangle { anchors.fill: parent; color: theme.background }

    // ---------------------------------------------------------------- full-screen artwork
    // The focused game's wide art fills the screen and cross-fades to the next game's.
    // Two images take turns: the incoming one loads hidden, then fades in over the other.
    Item {
        id: stage
        anchors.fill: parent
        visible: tv.visible && tv.skin !== "gallery"
        property bool showA: true
        property bool none: true      // no wide art for this game: show its blurred cover instead
        property string incoming: ""  // "a" or "b" while that image loads the next game's art
        function load(list) {
            if (!list || !list.length) { none = true; incoming = ""; return }
            const next = showA ? artB : artA
            incoming = next.tag
            next.sources = list
            if (next.status === Image.Ready && next.at === 0) { showA = next.tag === "a"; none = false; incoming = "" }
        }
        // Wait until the focus settles, so fast scrolling does not load every game on the way.
        Timer { id: settle; interval: 140; onTriggered: stage.load(tv.cur.heroes) }
        Connections {
            target: tv
            function onCurChanged() {
                if (JSON.stringify(tv.cur.heroes || []) !== stage.lastSig) {
                    stage.lastSig = JSON.stringify(tv.cur.heroes || [])
                    settle.restart()
                }
            }
        }
        property string lastSig: ""

        ArtLayer { id: artA; tag: "a"; opacity: !stage.none && stage.showA ? 1 : 0 }
        ArtLayer { id: artB; tag: "b"; opacity: !stage.none && !stage.showA ? 1 : 0 }
        AnimatedImage {
            id: animHero
            objectName: "tvAnimHero"
            anchors.fill: parent
            source: tv.animOk && tv.anim.hero ? tv.anim.hero : ""
            asynchronous: true
            // Keep Qt's default cache: an AnimatedImage from the web with cache: false crashes Qt 6.12.
            fillMode: Image.PreserveAspectCrop
            horizontalAlignment: Image.AlignRight
            playing: tv.animOk
            opacity: status === Image.Ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 450 } }
        }
        Loader {
            id: trailerLoader
            anchors.fill: parent
            active: typeof canPlayVideo !== "undefined" && canPlayVideo && app.settingsMap.tv_trailers
                    && !app.still && tv.visible && tv.trailerUrl !== "" && !tv.frosted
                    && Qt.application.state === Qt.ApplicationActive  // never behind a running game
                    && !tv.calm
            source: "TvTrailer.qml"
            onLoaded: item.source = Qt.binding(() => tv.trailerUrl)
        }

        Image {
            id: backdrop
            anchors.fill: parent
            source: stage.none && !app.light ? (tv.cur.cover || "") : ""
            asynchronous: true
            fillMode: Image.PreserveAspectCrop
            sourceSize.width: 200
            visible: false
        }
        MultiEffect {
            anchors.fill: parent
            source: backdrop
            visible: stage.none && !app.light && GraphicsInfo.api !== GraphicsInfo.Software && backdrop.status === Image.Ready
            blurEnabled: true
            blur: 1.0
            blurMax: 64
            opacity: 0.45
        }

        // No wide art: the cover itself stands large on the right, lit in the game's colour,
        // so the screen is never an empty band.
        Rectangle {
            anchors.fill: parent
            opacity: stage.none ? 1 : 0
            Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 450 } }
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.3; color: "transparent" }
                GradientStop { position: 1.0; color: Qt.alpha(tv.accent, 0.30) }
            }
        }
        ArtImage {
            id: poster
            // From below the tabs to just above the cover row.
            readonly property real h: Math.round(Math.max(180, tv.height - grid.height - tv.height * 0.12 - 150))
            anchors { right: parent.right; rightMargin: Math.round(tv.width * 0.07); top: parent.top; topMargin: Math.round(tv.height * 0.12) }
            height: h
            width: Math.round(h / 1.5)
            sources: stage.none && tv.cur.key ? (tv.cur.covers || [tv.cur.cover]).filter(u => !!u) : []
            sourceSize.width: Math.min(1200, Math.max(300, Math.ceil(width * Screen.devicePixelRatio / 40) * 40))
            fillMode: Image.PreserveAspectCrop
            opacity: stage.none && status === Image.Ready ? 1 : 0
            Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 450; easing.type: Easing.InOutQuad } }
            transform: Rotation { origin.x: poster.width; origin.y: poster.height / 2; axis { x: 0; y: 1; z: 0 } angle: -9 }
            layer.enabled: !app.light && GraphicsInfo.api !== GraphicsInfo.Software
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: tv.accent
                shadowBlur: 1.0
                shadowOpacity: 0.55
                shadowScale: 1.04
            }
        }

        // Shade: dark on the left for the title, and at the bottom for the covers.
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: Qt.alpha(theme.background, 0.94) }
                GradientStop { position: 0.3; color: Qt.alpha(theme.background, 0.72) }
                GradientStop { position: 0.55; color: Qt.alpha(theme.background, 0.25) }
                GradientStop { position: 0.75; color: Qt.alpha(theme.background, 0.0) }
            }
        }
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.alpha(theme.background, 0.55) }
                GradientStop { position: 0.16; color: Qt.alpha(theme.background, 0.0) }
                GradientStop { position: 0.5; color: Qt.alpha(theme.background, 0.0) }
                GradientStop { position: 0.82; color: Qt.alpha(theme.background, 0.85) }
                GradientStop { position: 1.0; color: theme.background }
            }
        }
    }

    // Gallery: a calm, flat wall in the game's colour instead of the moving art.
    Rectangle {
        anchors.fill: parent
        visible: tv.skin === "gallery"
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.tint(theme.background, Qt.alpha(tv.accent, 0.10)) }
            GradientStop { position: 1.0; color: theme.background }
        }
    }
    // Arcade Night: the art sinks into a dark room, with a coloured horizon at the bottom.
    Rectangle {
        anchors.fill: parent
        visible: tv.skin === "arcade"
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.alpha("#05030a", 0.72) }
            GradientStop { position: 0.7; color: Qt.alpha("#05030a", 0.55) }
            GradientStop { position: 1.0; color: Qt.alpha(tv.accent, 0.30) }
        }
    }

    ColumnLayout {
        id: tvContent
        anchors.fill: parent
        anchors.margins: 48
        anchors.bottomMargin: 28
        spacing: 18

        // Store tabs. On narrower screens (the Steam Deck) the stores you are not on show only
        // their logo, and the row never pushes the layout wider than the screen.
        RowLayout {
          Layout.fillWidth: true
          spacing: 18
          // The wordmark and the store tabs get what is left after the status on the right, and
          // are the ones cut if it is ever too little: the clock and battery always stay on screen
          // (on the Legion Go S the clock ran off the right edge).
          Item {
            id: tabsBox
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            implicitHeight: tabsRow.implicitHeight
            clip: true
          RowLayout {
            id: tabsRow
            anchors.verticalCenter: parent.verticalCenter
            // Only the active tab keeps its name when the names would not all fit (about 172 px a tab).
            readonly property bool compact: tabsBox.width < tv.storeIds.length * 172 + 240
            spacing: 12
            BrandMark { size: 34; Layout.rightMargin: 14; opacity: 0.9 }
            // Every game lives on the Library page, not on Home: up from the top shelf, then A.
            Rectangle {
                id: libBtn
                objectName: "tvLibraryButton"
                implicitWidth: libRow.implicitWidth + 36
                implicitHeight: 46
                radius: 23
                Layout.rightMargin: 8
                color: activeFocus ? tv.tint.primary : libHover.hovered ? Qt.alpha(theme.onSurface, 0.1) : "transparent"
                scale: activeFocus && !app.still ? 1.06 : 1
                Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
                Row {
                    id: libRow
                    anchors.centerIn: parent
                    spacing: 9
                    Icon { anchors.verticalCenter: parent.verticalCenter; name: "library"; size: 22; color: libBtn.activeFocus ? tv.tint.onPrimary : theme.onSurface }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: qsTr("Library"); font.pixelSize: 18; font.weight: Font.DemiBold
                           color: libBtn.activeFocus ? tv.tint.onPrimary : theme.onSurface }
                }
                onActiveFocusChanged: if (activeFocus) { app.uiSound("move"); app.say(qsTr("Library")) }
                HoverHandler { id: libHover; cursorShape: Qt.PointingHandCursor }
                TapHandler { enabled: tv.homeLive; onTapped: if (tv.pointerOk()) libraryPage.show() }
                Keys.onReturnPressed: libraryPage.show()
                Keys.onEnterPressed: libraryPage.show()
                Keys.onDownPressed: grid.forceActiveFocus()
                Keys.onEscapePressed: { app.uiSound("back"); grid.forceActiveFocus() }
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_F10) { mainMenu.show(); event.accepted = true }
                    else if (event.key === Qt.Key_F9) { quickMenu.show(); event.accepted = true }
                    else event.accepted = true  // nothing else to do up here
                }
            }
            // The store, only when one is picked (LB / RB): one quiet word instead of a row of tabs.
            Text {
                visible: tvLibrary.storeFilter !== ""
                text: (app.storesInfo.find(x => x.id === tvLibrary.storeFilter) || { name: "" }).name
                color: theme.onSurfaceVariant
                font.pixelSize: 18
            }
          }
          }
            // Console-style status: battery (Steam Deck, laptops) and the time.
            Row {
                id: topStatus
                spacing: 18
                property var batt: ({})
                property string clock: ""
                function tick() {
                    clock = Qt.formatTime(new Date(), Qt.locale(app.uiLocale).timeFormat(Locale.ShortFormat))
                    batt = app.battery()
                }
                Timer { interval: 20000; running: tv.visible; repeat: true; triggeredOnStart: true; onTriggered: topStatus.tick() }
                Row {  // the sleep timer, while it runs
                    visible: app.sleepTimerLeft > 0
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6
                    Icon { anchors.verticalCenter: parent.verticalCenter; name: "moon"; size: 20; color: tv.tint.primary }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: qsTr("%1 min").arg(app.sleepTimerLeft); color: theme.onSurfaceVariant; font.pixelSize: 18 }
                }
                Row {
                    visible: topStatus.batt.level !== undefined
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6
                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        name: topStatus.batt.charging ? "battery-charging" : "battery"
                        size: 24
                        color: (topStatus.batt.level || 100) <= 15 && !topStatus.batt.charging ? theme.error : theme.onSurfaceVariant
                    }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: (topStatus.batt.level || 0) + "%"; color: theme.onSurfaceVariant; font.pixelSize: 18 }
                }
                Rectangle {
                    visible: app.nowPlaying.length > 0
                    anchors.verticalCenter: parent.verticalCenter
                    height: 36; radius: 18
                    width: playingText.implicitWidth + 44
                    color: Qt.alpha(tv.tint.primary, 0.2)
                    border.width: 1; border.color: tv.tint.primary
                    Icon { x: 14; anchors.verticalCenter: parent.verticalCenter; name: "play"; size: 14; color: tv.tint.primary }
                    Text { id: playingText; x: 34; anchors.verticalCenter: parent.verticalCenter
                           text: app.nowPlaying.length ? app.nowPlaying[0].title : ""; color: theme.onSurface; font.pixelSize: 16 }
                }
                Row {  // who is playing, when several people use this PC
                    visible: app.profiles.length > 1
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 10
                    Rectangle {
                        width: 38; height: 38; radius: 19
                        color: tv.tint.primary
                        Text { anchors.centerIn: parent; text: (app.profile || "?").charAt(0).toUpperCase(); color: tv.tint.onPrimary
                               font.pixelSize: 18; font.weight: Font.Bold }
                    }
                    Text { visible: app.profiles.length > 1; anchors.verticalCenter: parent.verticalCenter
                           text: app.profile; color: theme.onSurfaceVariant; font.pixelSize: 18 }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: topStatus.clock
                    color: theme.onSurfaceVariant
                    font.pixelSize: 22
                }
            }
        }

        // The focused game, big, over its artwork. On short screens (the Steam Deck) the
        // description and then the genres step aside so the title never runs into the tabs.
        Item {
            id: infoArea
            Layout.fillWidth: true
            Layout.fillHeight: true
            ColumnLayout {
                anchors { left: parent.left; bottom: parent.bottom; bottomMargin: 6 }
                width: Math.min(parent.width * 0.62, 980)
                spacing: 12
                // A very short window (TV mode not full screen): shrink rather than run into the tabs.
                transformOrigin: Item.BottomLeft
                scale: implicitHeight > 0 ? Math.min(1, (infoArea.height - 6) / implicitHeight) : 1
                LogoTitle {
                    id: titleBlock
                    Layout.fillWidth: true
                    logos: tv.skin === "phosphor" ? [] : (tv.cur.logos || [])
                    title: tv.cur.title || ""
                    family: tv.skinFamily
                    color: tv.skin === "phosphor" ? tv.tint.primary : theme.onSurface
                    pixelSize: Math.round(Math.min(72, Math.max(40, tv.height * 0.06)))
                    logoHeight: Math.round(Math.min(170, Math.max(80, Math.min(tv.height * 0.15, infoArea.height * 0.3))))
                    maxWidth: Math.min(width, 640)
                }
                // One quiet line: where it is and how much you played it.
                Text {
                    id: metaRow
                    visible: text !== ""
                    color: theme.onSurfaceVariant
                    font.pixelSize: 19
                    text: {
                        if (!tv.cur.key) return ""
                        const stores = tv.cur.copies.length ? tv.cur.copies.map(c => c.storeName).join(", ") : tv.cur.storeName
                        const state = tv.cur.job ? "" : !tv.cur.installed ? qsTr("Not installed") : tv.cur.update ? qsTr("Update available") : ""
                        const played = app.playedText(tv.cur.playtime, tv.cur.lastPlayed)
                        return [stores, state, tv.cur.playtime ? played : ""].filter(t => !!t).join("   \u00B7   ")
                    }
                }
                // The two things you can do, with the button that does them.
                Row {
                    id: actionsRow
                    Layout.topMargin: 6
                    spacing: 14
                    visible: !!tv.cur.key
                    Rectangle {
                        id: playBtn
                        readonly property string label: tv.cur.job ? ({ install: qsTr("Installing"), update: qsTr("Updating"), dlc: qsTr("Installing DLC"), move: qsTr("Moving"), verify: qsTr("Checking files"), fix: qsTr("Fixing"), queued: qsTr("Queued"), paused: qsTr("Paused") }[tv.cur.job] || qsTr("Removing"))
                                                                       + (tv.cur.job !== "uninstall" ? " " + Math.max(0, Math.floor(tv.cur.progress || 0)) + "%" : "")
                                                        : tv.cur.installed ? (tv.cur.playtime ? qsTr("Resume") : qsTr("Play")) : qsTr("Install")
                        height: 56; radius: 28
                        width: playRow.implicitWidth + 44
                        color: tv.tint.primary
                        Rectangle {  // install progress fills the button
                            visible: !!tv.cur.job
                            anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                            width: parent.width * Math.max(0, Math.min(1, (tv.cur.progress || 0) / 100))
                            radius: parent.radius
                            color: Qt.alpha(tv.tint.onPrimary, 0.18)
                        }
                        Row {
                            id: playRow
                            anchors.centerIn: parent
                            spacing: 10
                            PadButton { visible: pad.connected || pad.deck; anchors.verticalCenter: parent.verticalCenter; button: "a"; style: pad.style; size: 28 }
                            Icon { visible: !pad.connected && !pad.deck; anchors.verticalCenter: parent.verticalCenter; name: tv.cur.installed ? "play" : "download"; size: 22; color: tv.tint.onPrimary }
                            Text { anchors.verticalCenter: parent.verticalCenter; text: playBtn.label; color: tv.tint.onPrimary; font.pixelSize: 21; font.weight: Font.DemiBold }
                        }
                        TapHandler { enabled: tv.homeLive; onTapped: if (tv.pointerOk()) tv.accept() }
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                    }
                    Rectangle {
                        height: 56; radius: 28
                        width: moreRow.implicitWidth + 40
                        color: Qt.alpha(theme.background, 0.55)
                        border.width: 1
                        border.color: Qt.alpha(theme.onSurface, 0.25)
                        Row {
                            id: moreRow
                            anchors.centerIn: parent
                            spacing: 10
                            PadButton { visible: pad.connected; anchors.verticalCenter: parent.verticalCenter; button: "x"; style: pad.style; size: 28 }
                            Icon { visible: !pad.connected; anchors.verticalCenter: parent.verticalCenter; name: "ellipsis"; size: 22; color: theme.onSurface }
                            Text { anchors.verticalCenter: parent.verticalCenter; text: qsTr("More"); color: theme.onSurface; font.pixelSize: 21; font.weight: Font.Medium }
                        }
                        TapHandler { enabled: tv.homeLive; onTapped: if (tv.pointerOk()) tv.openPage() }
                        HoverHandler { cursorShape: Qt.PointingHandCursor }
                    }
                    Text {  // download speed and time left, beside the progress in the button
                        visible: !!tv.cur.job && !!tv.cur.jobDetail
                        anchors.verticalCenter: parent.verticalCenter
                        text: tv.cur.jobDetail || ""
                        color: theme.onSurfaceVariant
                        font.pixelSize: 18
                    }
                }
            }
        }

        // Shelf label: just which list this is.
        Text {
            Layout.bottomMargin: -6
            text: (tvLibrary.search !== "" ? qsTr("Results for \u201c") + tvLibrary.search + "\u201d" : tv.shelf.name)
                  + (tvLibrary.installedOnly ? "  \u00B7  " + qsTr("Installed only") : "")
            color: theme.onSurfaceVariant
            font.pixelSize: 20
            font.weight: Font.DemiBold
        }

        // One row of covers along the bottom; left / right to browse.
        GridView {
            id: grid
            transform: Translate { id: shelfSlide }
            objectName: "tvGrid"
            Layout.fillWidth: true
            Layout.preferredHeight: Math.round(Math.max(200, tv.height * (tv.skin === "gallery" ? 0.42 : peek.visible ? 0.29 : 0.34)))
            focus: true
            clip: false
            model: tvLibrary
            flow: GridView.FlowTopToBottom
            cellHeight: height
            cellWidth: Math.round(height / 1.46)
            cacheBuffer: cellWidth * 4
            keyNavigationEnabled: true
            boundsBehavior: Flickable.StopAtBounds
            highlightFollowsCurrentItem: false
            // Glide just far enough to keep the focused cover (and a bit of its neighbour) in view.
            // A cover you point at is already in view, so the row never shifts under the mouse.
            function reveal() {
                if (currentIndex < 0 || width <= 0) return
                const x = currentIndex * cellWidth
                const margin = Math.min(cellWidth * 0.5, width / 4)
                let to = contentX
                if (x - contentX < margin) to = x - margin
                else if (x + cellWidth - contentX > width - margin) to = x + cellWidth - width + margin
                to = Math.max(0, Math.min(to, contentWidth - width))
                if (Math.abs(to - contentX) > 1) { glide.to = to; glide.restart() }
            }
            // While a direction is held (auto-repeat) the row keeps up instead of easing behind.
            property bool fast: false
            NumberAnimation { id: glide; target: grid; property: "contentX"; duration: app.still ? 0 : grid.fast ? 80 : 220; easing.type: Easing.OutCubic }
            onWidthChanged: Qt.callLater(reveal)
            onCurrentIndexChanged: { tv.sync(); reveal(); if (tv.visible && !fast) app.uiSound("move"); if (tv.visible && activeFocus) speakTimer.restart() }
            // Read aloud (Accessibility): the game the focus rests on, not every one scrolled past.
            Timer { id: speakTimer; interval: 250; onTriggered: if (tv.cur.key) app.say(tv.cur.title + (tv.cur.installed ? "" : ", " + qsTr("not installed"))) }
            function jump(to) { currentIndex = Math.max(0, Math.min(count - 1, to)) }
            readonly property int page: Math.max(1, Math.floor(width / cellWidth) - 1)
            onCountChanged: { if (currentIndex < 0 && count > 0) currentIndex = 0; tv.sync() }
            delegate: GameCard {
                id: tvCard
                quickAction: false   // TV mode: the controller's A button plays
                tilt: false          // and no tilt (the desktop library's)
                required property int index
                width: grid.cellWidth
                height: grid.cellHeight
                theme: tv.tint
                cornerRadius: app.settingsMap.card_radius
                showBadge: false      // the focused game's store and ProtonDB rating are shown above the row
                showProtonDb: false
                showTitle: false
                dim: app.settingsMap.dim_uninstalled
                current: GridView.isCurrentItem && !libBtn.activeFocus
                // Pointing at a cover focuses it, so its artwork fills the screen.
                interactive: tv.homeLive
                onHoverAtChanged: if (hovered && tv.homeLive && tv.pointerMoved(hoverAt) && grid.currentIndex !== index) grid.currentIndex = index
                onOpened: { if (!tv.pointerOk()) return; grid.currentIndex = index; tv.sync(); tv.openPage() }
                onActivated: { if (!tv.pointerOk()) return; grid.currentIndex = index; tv.sync(); tv.accept() }
                // A soft reflection on the shelf below (Settings > Appearance).
                Item {
                    visible: !!app.settingsMap.tv_reflection && !app.light && !peek.visible
                    x: 8; y: parent.height - 8
                    width: parent.width - 16
                    height: Math.round(parent.height * 0.1)
                    clip: true
                    opacity: tvCard.current ? 0.22 : 0.1
                    Behavior on opacity { NumberAnimation { duration: 200 } }
                    ArtImage {
                        width: parent.width
                        height: tvCard.height - 16
                        sources: tvCard.covers || []
                        sourceSize.width: 200
                        transform: Scale { origin.y: (tvCard.height - 16) / 2; yScale: -1 }
                    }
                    Rectangle {
                        anchors.fill: parent
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: Qt.alpha(theme.background, 0.2) }
                            GradientStop { position: 1.0; color: theme.background }
                        }
                    }
                }
                // Arcade Night: a neon glow in the game's colour around the cover in focus.
                RectangularShadow {
                    z: -1
                    visible: tv.skin === "arcade" && tvCard.current && GraphicsInfo.api !== GraphicsInfo.Software
                    anchors.fill: parent; anchors.margins: 8
                    radius: app.settingsMap.card_radius; blur: 40; spread: 6
                    color: Qt.alpha(tv.accent, 0.85)
                }
                // The focused game's animated cover, over its still one.
                RoundedArt {
                    anchors.fill: parent
                    anchors.margins: 8
                    radius: app.settingsMap.card_radius
                    visible: tvCard.current && tv.animOk && !!tv.anim.grid && animCover.status === Image.Ready
                    AnimatedImage {
                        id: animCover
                        anchors.fill: parent
                        source: tvCard.current && tv.animOk && tv.anim.grid ? tv.anim.grid : ""
                        asynchronous: true
                        fillMode: Image.PreserveAspectCrop
                        playing: tv.animOk
                    }
                }
            }
            Keys.onReturnPressed: tv.accept()
            Keys.onEnterPressed: tv.accept()
            Keys.onEscapePressed: {
                app.uiSound("back")
                if (tvLibrary.search !== "") tv.clearSearch()
                else if (tv.shelfAt > 0) tv.stepShelf(-tv.shelfAt)  // back to the top shelf, like Home
                else mainMenu.show()                              // home already: the menu (Exit TV mode is there)
            }
            Keys.onUpPressed: { if (tv.shelfAt === 0 || tvLibrary.search !== "") libBtn.forceActiveFocus(); else tv.stepShelf(-1) }
            Keys.onDownPressed: tv.stepShelf(1)
            Keys.onPressed: event => {
                tv.wake()
                grid.fast = event.isAutoRepeat
                if ((event.key === Qt.Key_Left || event.key === Qt.Key_Right) && (event.modifiers & Qt.ShiftModifier)) {
                    grid.jump(currentIndex + (event.key === Qt.Key_Right ? page : -page)); event.accepted = true
                }
                else if (event.key === Qt.Key_Home) { grid.jump(0); event.accepted = true }
                else if (event.key === Qt.Key_End) { grid.jump(count - 1); event.accepted = true }
                else if (event.key === Qt.Key_F2) { tv.openPage(); event.accepted = true }
                else if (event.key === Qt.Key_F10) { mainMenu.show(); event.accepted = true }
                else if (event.key === Qt.Key_F9) { quickMenu.show(); event.accepted = true }
                else if (event.key === Qt.Key_F4 || event.key === Qt.Key_Slash) { tv.openSearch(""); event.accepted = true }
                else if (event.text && /^[a-z0-9]$/i.test(event.text) && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier))) {
                    tv.openSearch(event.text.toLowerCase()); event.accepted = true  // just start typing
                }
                else if (event.key === Qt.Key_F3 || (event.key === Qt.Key_Space && pad.deck && !pad.connected)) { tvLibrary.installedOnly = !tvLibrary.installedOnly; event.accepted = true }
                else if (event.key === Qt.Key_PageUp) { tv.cycleStore(-1); event.accepted = true }
                else if (event.key === Qt.Key_PageDown) { tv.cycleStore(1); event.accepted = true }
            }

            Column {
                visible: grid.count === 0
                anchors.centerIn: parent
                spacing: 18
                EmptyScene {
                    visible: !app.refreshing
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 300; height: 200
                    theme: tv.theme
                    kind: app.totalCount === 0 ? "library" : tvLibrary.search !== "" ? "search" : "list"
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: app.refreshing ? qsTr("Loading your libraries…") : tvLibrary.search !== "" ? qsTr("Nothing matches") : qsTr("No games here")
                    color: theme.onSurfaceVariant
                    font.pixelSize: 26
                }
            }
        }

        Item { id: peek; visible: false }  // (the next shelf's preview is gone: Home stays one row)

        // Button hints: the connected controller's own glyphs, or keyboard keys; only the ones
        // that do something right now (no Jump in a short row, no Store with one store...).
        Row {
            Layout.alignment: Qt.AlignRight
            visible: tv.width >= 900
            spacing: 22
            Repeater {
                model: {
                    const play = tv.cur.key && !tv.cur.installed ? qsTr("Install") : qsTr("Play")
                    const jump = grid.count > grid.page + 1, stores = tv.storeIds.length > 2, shelves = tv.shelfList.length > 1
                    const all = pad.connected
                        ? [{ b: ["a"], t: play }, { b: ["start"], t: qsTr("More") }, { b: ["guide"], t: qsTr("Menu") }, { b: ["y"], t: tvLibrary.installedOnly ? qsTr("All games") : qsTr("Installed only") },
                           shelves ? { b: ["\u2195"], t: qsTr("Shelf"), pad: true } : null, jump ? { b: ["lt", "rt"], t: qsTr("Jump") } : null,
                           stores ? { b: ["lb", "rb"], t: qsTr("Store") } : null, { b: ["back"], t: qsTr("Search") },
                           { b: ["b"], t: tvLibrary.search ? qsTr("Clear search") : qsTr("Back") }]
                        : pad.deck  // Steam Deck in Desktop Mode: only the buttons Steam's desktop layout sends
                        ? [{ b: ["a"], t: play }, { k: "F2", t: qsTr("More") }, { b: ["y"], t: qsTr("Installed only") }, { b: ["b"], t: qsTr("Back") }]
                        : [{ k: qsTr("Enter"), t: play }, { k: "F2", t: qsTr("More") }, { k: "F10", t: qsTr("Menu") }, { k: "F3", t: tvLibrary.installedOnly ? qsTr("All games") : qsTr("Installed only") },
                           shelves ? { k: "\u2191 \u2193", t: qsTr("Shelf") } : null, jump ? { k: qsTr("Shift \u2190/\u2192"), t: qsTr("Jump") } : null,
                           stores ? { k: qsTr("PgUp / PgDn"), t: qsTr("Store") } : null, { k: qsTr("Type"), t: qsTr("Search") },
                           { k: qsTr("Esc"), t: tvLibrary.search ? qsTr("Clear search") : qsTr("Back") }]
                    // Two at most (play, menu): everything else is in the menu and on a game's page.
                    // No game in view (an empty shelf, nothing found): nothing to play or open.
                    const needGame = [qsTr("Play"), qsTr("Install"), qsTr("Options"), qsTr("More")]
                    return all.filter(h => h && !h.pad && [qsTr("Play"), qsTr("Install"), qsTr("Menu"), qsTr("Clear search")].indexOf(h.t) !== -1
                                           && (tv.cur.key || needGame.indexOf(h.t) === -1))
                }
                Hint { required property var modelData; hint: modelData }
            }
        }
    }

    // Phosphor: scanlines and a dark vignette over everything on the home screen (menus and
    // pages on top stay clean). Drawn once per size, not per frame.
    Canvas {
        id: scan
        anchors.fill: parent
        z: 30
        visible: tv.skin === "phosphor"
        enabled: false
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onVisibleChanged: if (visible) requestPaint()
        onPaint: {
            const c = getContext("2d")
            c.reset()
            c.fillStyle = "rgba(0,0,0,0.16)"
            for (let y = 0; y < height; y += 3) c.fillRect(0, y, width, 1)
            const g = c.createRadialGradient(width / 2, height / 2, Math.min(width, height) * 0.35, width / 2, height / 2, Math.max(width, height) * 0.75)
            g.addColorStop(0, "rgba(0,0,0,0)")
            g.addColorStop(1, "rgba(0,0,0,0.55)")
            c.fillStyle = g
            c.fillRect(0, 0, width, height)
        }
    }

    // One button hint: the pad's glyphs or a keycap, and what it does.
    component Hint: Row {
        property var hint: ({})
        spacing: 8
        Repeater {
            model: hint.b || []
            PadButton { required property string modelData; button: modelData; style: pad.style; size: 26 }
        }
        Rectangle {  // keycap
            visible: !!hint.k
            height: 26; radius: 6
            width: hintKey.implicitWidth + 16
            color: Qt.alpha(theme.surfaceContainerHighest, 0.9)
            border.width: 1; border.color: theme.outlineVariant
            Text { id: hintKey; anchors.centerIn: parent; text: hint.k || ""; color: theme.onSurface; font.pixelSize: 12; font.weight: Font.DemiBold }
        }
        Text { anchors.verticalCenter: parent.verticalCenter; text: hint.t || ""; color: theme.onSurfaceVariant; font.pixelSize: 15 }
    }

    // The TV intro (Settings > Appearance, off by default): the corner lights up, the name
    // appears, a soft chime; then the home screen.
    property bool introDone: false
    // The window has drawn its first frame. The intro's Animators start their clock on the first
    // frame by themselves (they run on the render thread), so the intro starts right away; only
    // the chime waits for the window to be on screen, so it never comes before the picture.
    property bool shown: true
    property bool chimeOwed: false
    onShownChanged: if (shown && chimeOwed) { chimeOwed = false; app.uiSound("intro") }
    function maybeIntro() {
        if (introDone || !app.settingsMap.tv_intro || app.still) return
        introDone = true
        intro.play()
    }
    function skipIntro() {
        app.startupAnimationDone()
        Qt.callLater(tv.maybeAskWho)
        introGone.stop()
        introAnim.stop()
        introIcon.opacity = 0; introIcon.scale = 0.8; introName.opacity = 0
        const had = intro.activeFocus
        intro.visible = false
        if (had) grid.forceActiveFocus()  // back to the shelf it took the keys from
    }
    Rectangle {
        id: intro
        objectName: "tvIntro"
        anchors.fill: parent
        z: 100
        color: theme.background
        visible: false
        function play() {
            visible = true; opacity = 1
            forceActiveFocus()  // every key and pad button comes here while it plays: any of them skips it
            if (tv.shown) app.uiSound("intro"); else tv.chimeOwed = true
            introAnim.restart(); introIcon.play()
            introGone.restart()
        }
        // The same safety as the splash: never left over TV mode if the animation cannot run.
        Timer { id: introGone; interval: 4500; onTriggered: if (intro.visible) tv.skipIntro() }
        // Animators (Qt's render thread): smooth even while the library is still loading.
        BrandMark {
            id: introIcon
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -40
            size: Math.round(tv.height * 0.22)
            opacity: 0; scale: 0.8
        }
        WordMark {
            id: introName
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: introIcon.bottom; anchors.topMargin: 28
            showIcon: false; size: Math.round(tv.height * 0.055)
            ink: "#fff3e0"; accent: "#ffb547"
            opacity: 0
        }
        SequentialAnimation {
            id: introAnim
            ParallelAnimation {
                OpacityAnimator { target: introIcon; from: 0; to: 1; duration: 600; easing.type: Easing.OutCubic }
                ScaleAnimator { target: introIcon; from: 0.8; to: 1; duration: 900; easing.type: Easing.OutBack }
            }
            OpacityAnimator { target: introName; from: 0; to: 1; duration: 450 }
            PauseAnimation { duration: 700 }
            OpacityAnimator { target: intro; from: 1; to: 0; duration: 450; easing.type: Easing.InCubic }
            ScriptAction { script: tv.skipIntro() }
        }
        TvShield { onClicked: tv.skipIntro() }
        Keys.onPressed: event => { event.accepted = true; tv.skipIntro() }
    }

    // Search keyboard: d-pad to a key, A types it, B deletes (or closes when empty),
    // View closes and keeps the results; a real keyboard types straight into it.
    // A soft dim behind the keyboard, so it reads as on top.
    Frost { visible: tv.searching; z: 4 }
    Rectangle {
        anchors.fill: parent
        visible: tv.searching
        z: 4
        color: Qt.alpha("black", 0.5)
        TvShield { onClicked: tv.closeSearch(true) }  // a click beside the keyboard closes it, keeping the results
    }
    Rectangle {
        id: searchBox
        visible: tv.searching
        anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: 120 }
        width: Math.min(parent.width - 96, 880)
        height: searchCol.implicitHeight + 44
        radius: 30
        color: Qt.alpha(theme.surfaceContainer, 0.9)
        border.width: 1; border.color: Qt.alpha("white", 0.1)
        TvShield {}
        z: 5
        RectangularShadow {
            z: -1
            anchors.fill: parent
            visible: !app.light && GraphicsInfo.api !== GraphicsInfo.Software
            radius: parent.radius; blur: 60; offset.y: 20
            color: Qt.alpha("black", 0.55)
        }
        ColumnLayout {
            id: searchCol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 20 }
            spacing: 14
            Rectangle {
                Layout.fillWidth: true
                height: 56; radius: 28
                color: theme.surfaceContainerHighest
                Icon { x: 20; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 22; color: theme.onSurfaceVariant }
                Rectangle {  // the cursor, blinking after what has been typed
                    x: 54 + (tvLibrary.search !== "" ? Math.min(searchText.contentWidth, searchText.width) + 3 : 0)
                    anchors.verticalCenter: parent.verticalCenter
                    width: 2; height: 26; radius: 1
                    color: tv.tint.primary
                    visible: keys.activeFocus && blinkOn
                    property bool blinkOn: true
                    Timer { interval: 530; repeat: true; running: keys.activeFocus; onTriggered: parent.blinkOn = !parent.blinkOn }
                }
                Text {
                    id: searchText
                    x: 54; anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 74 - 110
                    elide: Text.ElideLeft
                    text: tvLibrary.search !== "" ? tvLibrary.search : qsTr("Search your games")
                    color: tvLibrary.search !== "" ? theme.onSurface : theme.onSurfaceVariant
                    font.pixelSize: 22
                }
                Text {
                    anchors { right: parent.right; rightMargin: 22; verticalCenter: parent.verticalCenter }
                    text: grid.count + (grid.count === 1 ? qsTr(" game") : qsTr(" games"))
                    color: theme.onSurfaceVariant; font.pixelSize: 16
                }
            }
            // The on-screen keyboard, laid out like a phone's or the Steam Deck's: numbers on top,
            // then the letters in QWERTY order, a dash and an apostrophe for titles like
            // "Half-Life" or "Baldur's Gate", and a wide space bar. Left / right move along a row;
            // up / down jump to the nearest key in the next row. On a controller: A types,
            // X deletes, Y is a space, B deletes (or closes when empty), View / Select is done.
            Item {
                id: keys
                Layout.fillWidth: true
                Layout.preferredHeight: rows.length * rowH
                readonly property int rowH: 62
                readonly property real unit: width / 10
                // [key, width in tenths of the board]
                readonly property var rows: [
                    "1234567890".split("").map(k => [k, 1]),
                    "qwertyuiop".split("").map(k => [k, 1]),
                    "asdfghjkl".split("").map(k => [k, 1]).concat([["'", 1]]),
                    "zxcvbnm".split("").map(k => [k, 1]).concat([["-", 1], ["del", 2]]),
                    [["space", 6], ["clear", 2], ["done", 2]]
                ]
                property int row: 1
                property int col: 0
                readonly property var current: (rows[row] || [])[col] || ["", 1]
                function startOf(r, c) { let x = 0; for (let i = 0; i < c; i++) x += rows[r][i][1]; return x }
                function centreOf(r, c) { return startOf(r, c) + rows[r][c][1] / 2 }
                function moveRow(d) {
                    const r = (row + d + rows.length) % rows.length
                    const want = centreOf(row, col)
                    let best = 0, gap = 1e9
                    for (let c = 0; c < rows[r].length; c++) {
                        const g = Math.abs(centreOf(r, c) - want)
                        if (g < gap) { gap = g; best = c }
                    }
                    row = r; col = best
                    app.uiSound("move")
                }
                function moveCol(d) { col = (col + d + rows[row].length) % rows[row].length; app.uiSound("move") }
                function press(k) {
                    app.uiSound("move")
                    if (k === "done") { tv.closeSearch(true); return }
                    if (k === "clear") tvLibrary.search = ""
                    else if (k === "del") tvLibrary.search = tvLibrary.search.slice(0, -1)
                    else tvLibrary.search = (tvLibrary.search + (k === "space" ? " " : k)).replace(/^ +/, "")
                    grid.currentIndex = 0; tv.sync()
                }
                Repeater {
                    model: keys.rows.length
                    Item {
                        id: keyRow
                        required property int index
                        readonly property int r: index
                        y: r * keys.rowH
                        width: keys.width; height: keys.rowH
                        Repeater {
                            model: keys.rows[keyRow.r]
                            Rectangle {
                                id: key
                                required property var modelData
                                required property int index
                                readonly property string k: modelData[0]
                                readonly property bool lit: keys.activeFocus && keys.row === keyRow.r && keys.col === index
                                readonly property bool special: k.length > 1
                                x: keys.startOf(keyRow.r, index) * keys.unit + 4
                                width: modelData[1] * keys.unit - 8
                                height: keys.rowH - 10
                                radius: 16
                                z: lit ? 1 : 0
                                scale: lit && !app.still ? 1.08 : 1
                                Behavior on scale { NumberAnimation { duration: 110; easing.type: Easing.OutCubic } }
                                color: lit ? tv.tint.primary
                                     : special ? Qt.alpha(theme.surfaceContainerHighest, 0.95)
                                     : Qt.alpha(theme.surfaceContainerHighest, 0.7)
                                Row {
                                    anchors.centerIn: parent
                                    spacing: 8
                                    Icon {
                                        visible: key.k === "del" || key.k === "done" || key.k === "clear"
                                        anchors.verticalCenter: parent.verticalCenter
                                        name: ({ del: "arrow-left", done: "check", clear: "x" })[key.k] || "x"
                                        size: 20
                                        color: key.lit ? tv.tint.onPrimary : theme.onSurface
                                    }
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: ({ space: "space", del: qsTr("Delete"), done: qsTr("Done"), clear: qsTr("Clear") })[key.k] || key.k.toUpperCase()
                                        color: key.lit ? tv.tint.onPrimary : key.special ? theme.onSurfaceVariant : theme.onSurface
                                        font.pixelSize: key.special ? 17 : 21
                                        font.weight: Font.DemiBold
                                    }
                                }
                                TapHandler { onTapped: { keys.row = keyRow.r; keys.col = key.index; keys.press(key.k) } }
                            }
                        }
                    }
                }
                Keys.onLeftPressed: moveCol(-1)
                Keys.onRightPressed: moveCol(1)
                Keys.onUpPressed: moveRow(-1)
                Keys.onDownPressed: moveRow(1)
                Keys.onReturnPressed: press(current[0])
                Keys.onEnterPressed: press(current[0])
                Keys.onEscapePressed: {
                    if (tvLibrary.search !== "") press("del")
                    else { app.uiSound("back"); tv.closeSearch(false) }
                }
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_F4) { tv.closeSearch(true); event.accepted = true }       // View / Select
                    else if (event.key === Qt.Key_F2) { press("del"); event.accepted = true }           // X (and Start)
                    else if (event.key === Qt.Key_F3) { press("space"); event.accepted = true }         // Y
                    else if (event.key === Qt.Key_Backspace) { press("del"); event.accepted = true }
                    else if (event.key === Qt.Key_Space) { press("space"); event.accepted = true }
                    else if (event.text && /^[a-z0-9'\-]$/i.test(event.text)) { press(event.text.toLowerCase()); event.accepted = true }
                }
            }
            // What the controller's buttons do here.
            Row {
                Layout.alignment: Qt.AlignHCenter
                spacing: 22
                Repeater {
                    model: pad.connected
                        ? [{ b: ["a"], t: qsTr("Type") }, { b: ["x"], t: qsTr("Delete") }, { b: ["y"], t: qsTr("Space") }, { b: ["back"], t: qsTr("Done") }, { b: ["b"], t: qsTr("Back") }]
                        : [{ k: qsTr("Type"), t: qsTr("or use the keys") }, { k: qsTr("Enter"), t: qsTr("Choose") }, { k: qsTr("Esc"), t: qsTr("Back") }]
                    Hint { required property var modelData; hint: modelData }
                }
            }
        }
    }

    // The game's own page (X / More): TvPage.qml. Its Options opens the action panel below, on top of it.
    function openPage() { if (!cur.key) return; app.uiSound("select"); gamePage.show(cur, app.gameDetails(cur.key), app.achievements(cur.key)) }
    TvDownloads { id: tvDownloads; anchors.fill: parent; z: 42; theme: tv.theme; tint: tv.tint; onClosed: tv.refocus(null) }
    TvPhone { id: phonePage; anchors.fill: parent; z: 42; theme: tv.theme; tint: tv.tint; onClosed: tv.refocus(null) }
    TvGameNight {
        id: gameNight
        anchors.fill: parent; z: 42
        theme: tv.theme; tint: tv.tint
        onClosed: tv.refocus(null)
        onPlay: key => { tv.cur = app.game(key); tv.accept() }
    }
    TvStats { id: tvStats; anchors.fill: parent; z: 42; theme: tv.theme; tint: tv.tint; onClosed: tv.refocus(null) }
    TvRoulette {
        id: roulette
        anchors.fill: parent; z: 42
        theme: tv.theme; tint: tv.tint
        onClosed: tv.refocus(null)
        onPlay: key => { const t = app.launchTarget(key); if (t) app.play(t); else { tv.cur = app.game(key); panel.show() } }
    }
    TvLibrary {
        id: libraryPage
        anchors.fill: parent
        z: 38   // under the game's page and the action panel, which open from it
        theme: tv.theme
        tint: tv.tint
        storeIds: tv.storeIds
        onCurrentKeyChanged: if (visible) tv.sync()
        onVisibleChanged: tv.sync()
        onClosed: tv.refocus(null)
        onPlay: key => { tv.cur = app.game(key); tv.accept() }
        onMore: key => { tv.cur = app.game(key); tv.openPage() }
        onOptions: libSheet.show()
        onSearchAsked: { libPrompt.back = tv.Window.activeFocusItem; libPrompt.ask(qsTr("Search the library"), qsTr("Type part of a name, a developer or a genre."), false) }
    }
    // Family limits: the PIN, with the on-screen keyboard.
    TvTextPrompt {
        id: pinPrompt
        anchors.fill: parent
        theme: tv.theme
        tint: tv.tint
        property Item back: null
        property string what: ""
        property string arg: ""
        Connections { target: app; enabled: tv.visible
                      function onPinNeeded(what, arg) { pinPrompt.what = what; pinPrompt.arg = arg; pinPrompt.back = tv.Window.activeFocusItem
                                                        pinPrompt.ask(qsTr("Family PIN"), what === "switch" ? qsTr("Type the PIN to switch to %1.").arg(arg) : qsTr("Type the PIN."), true) } }
        onAccepted: text => { app.enterPin(text, what, arg); tv.refocus(back) }
        onClosed: tv.refocus(back)
    }
    TvTextPrompt {
        id: libPrompt
        anchors.fill: parent
        theme: tv.theme
        tint: tv.tint
        property Item back: null
        onAccepted: text => { tvAllLibrary.search = text; libraryPage.toTop(); tv.refocus(back) }
        onClosed: tv.refocus(back)
        onTextChanged: if (visible) { tvAllLibrary.search = text; libraryPage.toTop() }  // the results follow the typing
    }
    TvPage {
        id: gamePage
        anchors.fill: parent
        z: 40
        theme: tv.theme
        tint: tv.tint
        onOptions: panel.show()
        onClosed: tv.refocus(null)
    }

    // Action panel: every choice for the focused game, one press each.
    Rectangle {
        anchors.fill: parent
        z: 45
        visible: panel.visible
        color: "#b0000000"
        // A MouseArea, not a TapHandler: it takes the click (and the hover), so the cover
        // underneath never gets it. A tap outside the panel closes it.
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.AllButtons
            onClicked: panel.hide()
            onWheel: wheel => wheel.accepted = true
        }
    }
    Rectangle {
        id: panel
        z: 46
        property var rows: []
        property int armed: -1
        function show() { if (!tv.cur.key) return; app.uiSound("select"); rows = tv.buildActions(); armed = -1; list.currentIndex = 0; visible = true; list.forceActiveFocus() }
        function hide() { app.uiSound("back"); visible = false; tv.refocus(null) }
        // Swallow clicks and hover on the panel's empty parts too (its rows sit on top of this).
        MouseArea {
            anchors.fill: parent
            z: -1
            hoverEnabled: true
            acceptedButtons: Qt.AllButtons
            onWheel: wheel => wheel.accepted = true
        }
        function run(i) {
            const a = rows[i]
            if (!a) return
            if (a.act === "uninstall" && armed !== i) { armed = i; return }
            armed = -1
            if (a.act === "play") { app.preferCopy(a.key); app.play(a.key) }
            else if (a.act === "install") { app.preferCopy(a.key); app.install(a.key) }
            else if (a.act === "tonight") { app.installTonight(a.key, app.nightQueue.indexOf(a.key) === -1); rows = tv.buildActions(); return }
            else if (a.act === "update") app.update(a.key)
            else if (a.act === "cancel") app.cancel(a.key)
            else if (a.act === "uninstall") app.uninstall(a.key)
            else if (a.act === "hide" || a.act === "unhide") app.setHidden(a.key, a.act === "hide")
            else if (a.act === "fav") app.toggleFavourite(a.key)
            else if (a.act === "quit" || a.act === "kill") app.quitGame(a.key, a.act === "kill")
            else if (a.act === "padkeys") {
                const order = ["", "wasd", "strategy", "pointclick", "custom"]
                const now = app.gameOptions(a.key).pad_keys || ""
                app.setGameOption(a.key, "pad_keys", order[(order.indexOf(now) + 1) % order.length])
                rows = tv.buildActions()
                return
            }
            else if (a.act === "padlayout") {
                const order = ["", "none", "swap_ab", "nintendo", "southpaw", "shoulders"]
                const now = app.gameOptions(a.key).pad_layout || ""
                app.setGameOption(a.key, "pad_layout", order[(order.indexOf(now) + 1) % order.length])
                rows = tv.buildActions()
                return
            }
            else if (a.act === "status") {
                const order = ["", "playing", "want", "finished", "dropped"]
                app.setStatus(a.key, order[(order.indexOf(tv.cur.status || "") + 1) % order.length])
                rows = tv.buildActions()
                return  // stay open: press again for the next status
            }
            hide()
        }
        visible: false
        // The game's page: everything about it on the left, what to do on the right.
        anchors.fill: parent
        color: theme.background
        // The game's art behind the page, dimmed, so it feels like the game's own room.
        ArtImage {
            anchors.fill: parent
            visible: panel.visible && !app.light
            sources: tv.cur.heroes || []
            sourceSize.width: Math.min(2560, Math.max(640, Math.ceil(width * Screen.devicePixelRatio / 40) * 40))
            opacity: status === Image.Ready ? 0.38 : 0
            Behavior on opacity { NumberAnimation { duration: 300 } }
        }
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: Qt.alpha(theme.background, 0.55) }
                GradientStop { position: 0.6; color: Qt.alpha(theme.background, 0.75) }
                GradientStop { position: 1.0; color: Qt.alpha(theme.background, 0.95) }
            }
        }
        RowLayout {
            anchors.fill: parent
            anchors.margins: Math.round(Math.min(64, tv.width * 0.04))
            spacing: Math.round(Math.min(56, tv.width * 0.035))
        Item { Layout.fillWidth: true }  // the game's own page shows behind: no second copy of it here
        ColumnLayout {
            visible: false
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14
            LogoTitle {
                Layout.fillWidth: true
                logos: tv.cur.logos || []
                title: tv.cur.title || ""
                color: theme.onSurface
                pixelSize: Math.round(Math.min(56, Math.max(34, tv.height * 0.05)))
                logoHeight: Math.round(Math.min(150, Math.max(70, tv.height * 0.13)))
                maxWidth: Math.min(width, 620)
            }
            Text {
                Layout.fillWidth: true
                text: [tv.cur.storeName || "", tv.cur.installed ? qsTr("Installed") : qsTr("Not installed"),
                       tv.cur.key ? app.playedText(tv.cur.playtime, tv.cur.lastPlayed) : "",
                       tv.info.developer || "", tv.info.year || ""].filter(x => x).join("   \u00B7   ")
                color: theme.onSurfaceVariant; font.pixelSize: 18; wrapMode: Text.WordWrap
            }
            Flow {
                Layout.fillWidth: true
                spacing: 8
                Repeater {
                    model: tv.info.genres || []
                    Rectangle { required property string modelData; height: 30; radius: 15; width: pgT.implicitWidth + 26
                                color: "transparent"; border.width: 1; border.color: tv.tint.primary
                                Text { id: pgT; anchors.centerIn: parent; text: parent.modelData; color: theme.onSurface; font.pixelSize: 14 } }
                }
            }
            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 80
                clip: true
                contentHeight: pgAbout.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                Text { id: pgAbout; width: parent.width; text: tv.info.description || ""; textFormat: Text.PlainText; color: theme.onSurface; opacity: 0.85
                       font.pixelSize: 18; lineHeight: 1.3; wrapMode: Text.WordWrap }
            }
            ListView {
                visible: (tv.info.screenshots || []).length > 0 && tv.height >= 640
                Layout.fillWidth: true
                Layout.preferredHeight: Math.round(Math.floor((width - 24) / 3) * 9 / 16)
                orientation: ListView.Horizontal
                spacing: 12
                interactive: false
                clip: true
                model: tv.info.screenshots || []
                delegate: RoundedArt {
                    required property var modelData
                    // three across, sized to the column (none cut off at the edge)
                    width: Math.floor((ListView.view.width - 24) / 3); height: Math.round(width * 9 / 16); radius: 16
                    Image { anchors.fill: parent; source: modelData.thumb || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true }
                }
            }
        }
        ColumnLayout {
            Layout.preferredWidth: Math.min(520, tv.width * 0.38)
            Layout.maximumWidth: Math.min(520, tv.width * 0.38)
            Layout.fillWidth: false  // (it would take its list's fill and cover the whole page)
            Layout.fillHeight: true
            spacing: 18
            Text {  // which game, small: the actions are the point
                Layout.fillWidth: true
                Layout.topMargin: 8
                text: tv.cur.title || ""
                color: theme.onSurface
                font.pixelSize: 24
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            Text {
                Layout.fillWidth: true
                visible: (tv.cur.copies || []).length > 1
                text: qsTr("You own this on ") + (tv.cur.copies || []).length + qsTr(" stores. Choose the launcher:")
                color: theme.onSurfaceVariant
                font.pixelSize: 16
                wrapMode: Text.WordWrap
            }
            ListView {
                id: list
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 10
                model: panel.rows
                keyNavigationWraps: true
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: list.width
                    height: 62
                    radius: 18
                    readonly property bool lit: ListView.isCurrentItem
                    color: lit ? tv.tint.primary : Qt.alpha(theme.surfaceContainerHigh, 0.72)
                    border.width: lit ? 0 : 1
                    border.color: Qt.alpha("white", 0.07)
                    Behavior on color { enabled: !app.still; ColorAnimation { duration: 120 } }
                    Icon {
                        anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 22 }
                        size: 22
                        name: ({ play: "play", install: "download", update: "arrow-up", cancel: "x", uninstall: "trash-2",
                                 fav: "star", status: "bookmark", hide: "eye-off", unhide: "eye", close: "x",
                                 quit: "x", kill: "x", padlayout: "gamepad-2", tonight: "moon", padkeys: "keyboard" })[parent.modelData.act] || "ellipsis"
                        color: parent.ListView.isCurrentItem ? tv.tint.onPrimary
                               : parent.modelData.act === "uninstall" ? theme.error : theme.onSurfaceVariant
                    }
                    Text {
                        anchors { verticalCenter: parent.verticalCenter; left: parent.left; right: parent.right; leftMargin: 62; rightMargin: 22 }
                        text: panel.armed === parent.index ? qsTr("Press again to uninstall") : parent.modelData.label
                        color: parent.ListView.isCurrentItem ? tv.tint.onPrimary
                               : parent.modelData.act === "uninstall" ? theme.error : theme.onSurface
                        font.pixelSize: 19
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                    TapHandler { onTapped: { list.currentIndex = parent.index; panel.run(parent.index) } }
                }
                onCurrentIndexChanged: { panel.armed = -1; if (panel.visible) { app.uiSound("move"); app.say((panel.rows[currentIndex] || {}).label || "") } }
                Keys.onReturnPressed: panel.run(currentIndex)
                Keys.onEnterPressed: panel.run(currentIndex)
                Keys.onEscapePressed: panel.hide()
                Keys.onLeftPressed: panel.hide()
            }
        }
        }
        // The page's own hints: only what works here.
        Row {
            anchors { right: parent.right; bottom: parent.bottom; margins: 28 }
            spacing: 22
            Repeater {
                model: pad.connected || pad.deck ? [{ b: ["a"], t: qsTr("Choose") }, { b: ["b"], t: qsTr("Back") }]
                                                 : [{ k: qsTr("Enter"), t: qsTr("Choose") }, { k: qsTr("Esc"), t: qsTr("Back") }]
                Hint { required property var modelData; hint: modelData }
            }
        }
    }

    // ------------------------------------------------------------ side menus (SteamOS style)
    // Guide: the main menu slides in from the left. Guide + A (or Share): quick access from the
    // right, in tabs like Steam's: quick settings, performance, now playing, TV mode.
    // The Guide menu: a short list; the rest is one step away in More and Power.
    function mainRows() {
        return [
            { label: qsTr("Home"), icon: "house", act: "home" },
            { label: qsTr("Library"), icon: "library", act: "library", value: String(app.totalCount || "") },
            ...(app.downloads.length ? [{ label: qsTr("Downloads"), icon: "download", act: "downloads", value: String(app.downloads.length) }] : []),
            { label: qsTr("More"), icon: "ellipsis", act: "more", value: "\u203A" },
            { label: qsTr("Settings"), icon: "settings-2", act: "settings" },
            { label: qsTr("Power"), icon: "power", act: "powermenu", value: "\u203A" }
        ]
    }
    function moreRows() {
        return [
            { label: qsTr("Can't decide?"), icon: "sparkles", act: "roulette" },
            { label: qsTr("Game night"), icon: "user-round", act: "night" },
            ...(app.settingsMap.stream_pc ? [{ label: qsTr("Play on ") + app.settingsMap.stream_pc, icon: "tv", act: "stream" }] : []),
            { label: qsTr("Your stats"), icon: "trophy", act: "stats" },
            { label: qsTr("Challenges"), icon: "zap", act: "challenges" },
            { label: qsTr("Edit Home"), icon: "layout-grid", act: "edithome" },
            { label: qsTr("Phone remote"), icon: "link", act: "phone", value: app.settingsMap.phone_remote ? qsTr("On") : "" },
            ...app.pluginActions.map(a => ({ label: a.label, icon: "puzzle", act: "plugin", id: a.id }))
        ]
    }
    function powerMenuRows() { return [...controls.powerRows(""), ...controls.leaveRows("")] }
    // What a row in any of those menus does.
    // The Guide's places replace whatever page is open (like Steam's): otherwise a page opened from
    // the Guide could sit under the one already up (Downloads under Settings) while taking the keys,
    // and Home could leave a game's page over a shelf that had the focus (A then started the game
    // behind it). keepLibrary: the Library stays (a page opened from it goes over it).
    function closePages(keepLibrary) {
        if (padTest.visible) padTest.close()
        if (roulette.visible) roulette.close()
        if (gameNight.visible) app.closeGameNight()
        for (const p of [gamePage, panel, tvDownloads, phonePage, gameNight, tvStats, roulette, tvSettings, pinPrompt, libPrompt, prompt])
            p.visible = false
        gamePage.viewing = false
        if (!keepLibrary) libraryPage.visible = false
        if (searching) closeSearch(true)
    }
    function menuPick(sheet, row) {
        const places = ["home", "library", "settings", "downloads", "stats", "night", "phone", "roulette"]
        if (places.indexOf(row.act) !== -1) { sheet.open = false; closePages(row.act === "library") }
        if (row.act === "home") { sheet.hide(); libraryPage.visible = false; if (tvLibrary.search !== "") tv.clearSearch(); if (tv.shelfAt > 0) tv.stepShelf(-tv.shelfAt); grid.forceActiveFocus() }
        else if (row.act === "library") { sheet.hide(); if (!libraryPage.visible) libraryPage.show(); else libraryPage.forceActiveFocus() }
        else if (row.act === "more") { sheet.open = false; moreMenu.show(); moreMenu.back = sheet.back }
        else if (row.act === "powermenu") { sheet.open = false; powerMenu.show(); powerMenu.back = sheet.back }
        else if (row.act === "edithome") { sheet.hide(); homeSheet.show() }
        else if (row.act === "settings") { sheet.hide(); tvSettings.show("") }
        else if (row.act === "downloads") { sheet.hide(); tvDownloads.show() }
        else if (row.act === "stats") { sheet.hide(); tvStats.show() }
        else if (row.act === "challenges") { sheet.hide(); goalSheet.show() }
        else if (row.act === "night") { sheet.hide(); gameNight.show() }
        else if (row.act === "phone") { sheet.hide(); phonePage.show() }
        else if (row.act === "plugin") { sheet.hide(); app.runPluginAction(row.id) }
        else if (row.act === "roulette") { sheet.hide(); roulette.show() }
        else if (row.act === "stream") { sheet.hide(); app.streamFromPc() }
        else controls.run(row)
    }
    readonly property var quickTabs: [
        { id: "quick", label: qsTr("Quick settings"), icon: "sliders-horizontal" },
        { id: "perf", label: qsTr("Performance"), icon: "gauge" },
        { id: "playing", label: qsTr("Now playing"), icon: "gamepad-2" },
        { id: "tv", label: qsTr("TV mode"), icon: "tv" }
    ]
    function quickRows(tab) {
        if (tab === "perf") return controls.performance()
        if (tab === "tv") return controls.tvQuick()
        if (tab !== "playing") return controls.quick(topStatus.batt)
        const out = []
        for (const p of app.nowPlaying) {
            out.push({ group: qsTr("Now playing"), label: p.title, icon: "play", sub: qsTr("Running") })
            if (app.settingsMap.clips)
                out.push({ group: qsTr("Now playing"), label: qsTr("Save a clip"), icon: "images", sub: qsTr("The last 30 seconds"), act: "clip" })
            out.push({ group: qsTr("Now playing"), label: controls.armed === "kill:" + p.key ? qsTr("Press again to force close") : qsTr("Quit game"),
                       icon: "x", act: "quitgame", key: p.key, alt: qsTr("Force close"), danger: controls.armed === "kill:" + p.key })
        }
        for (const j of app.jobList())
            out.push({ group: qsTr("Downloads"), label: j.title, icon: j.job === "update" ? "arrow-up" : "download", act: "downloads",
                       value: j.job === "queued" ? qsTr("Queued") : j.progress < 0 ? qsTr("Starting") : Math.floor(j.progress) + "%", sub: j.detail })
        if (!out.length) out.push({ group: qsTr("Now playing"), label: qsTr("Nothing running"), icon: "gamepad-2", sub: qsTr("Games you start show here, with Quit") })
        return out
    }
    SideSheet {
        id: mainMenu
        objectName: "tvMainMenu"
        side: "left"
        title: qsTr("Cornerplay")
        rowsFn: tab => tv.mainRows()
        onPicked: row => tv.menuPick(mainMenu, row)
    }
    SideSheet {
        id: moreMenu
        objectName: "tvMoreMenu"
        side: "left"
        title: qsTr("More")
        rowsFn: tab => tv.moreRows()
        onPicked: row => tv.menuPick(moreMenu, row)
    }
    SideSheet {
        id: powerMenu
        objectName: "tvPowerMenu"
        side: "left"
        title: qsTr("Power")
        rowsFn: tab => tv.powerMenuRows()
        onPicked: row => tv.menuPick(powerMenu, row)
    }
    SideSheet {
        id: quickMenu
        objectName: "tvQuickMenu"
        side: "right"
        tabs: tv.quickTabs
        title: topStatus.clock + (topStatus.batt.level !== undefined ? "   ·   " + topStatus.batt.level + "%" + (topStatus.batt.charging ? " ⚡" : "") : "")
        rowsFn: tab => tv.quickRows(tab)
        // Download progress and what is running change by themselves.
        Timer { interval: 1000; repeat: true; running: quickMenu.open && quickMenu.tabId === "playing"; onTriggered: quickMenu.refresh() }
        onPicked: (row) => {
            if (row.act === "quitgame") { app.quitGame(row.key, false); hide() }
            else if (row.act === "clip") { hide(); app.saveClip() }
            else if (row.act === "downloads") { open = false; tv.closePages(false); tvDownloads.show() }
            else controls.run(row)
        }
        onAlt: (row) => {
            if (row.act === "quitgame") { if (controls.arm("kill:" + row.key)) { app.quitGame(row.key, true); hide() } }
            else controls.runAlt(row)
        }
    }

    // The Library's Y menu: sort, view, which games, filters; while picking, what to do with them.
    function libRows() {
        const L = libraryPage, P = tvAllLibrary, out = []
        const again = () => Qt.callLater(libSheet.refresh)
        if (L.picking) {
            const keys = L.picked, n = keys.length, g = qsTr("%1 picked").arg(n)
            const bulk = (what, arg) => { app.bulk(keys, what, arg || ""); L.picking = false; L.picked = []; libSheet.hide() }
            if (n) {
                out.push({ group: g, label: qsTr("Install"), icon: "download", act: "do", run: () => bulk("install") })
                out.push({ group: g, label: qsTr("Update"), icon: "arrow-up", act: "do", run: () => bulk("update") })
                out.push({ group: g, label: qsTr("Add to favourites"), icon: "star", act: "do", run: () => bulk("fav") })
                out.push({ group: g, label: qsTr("Remove from favourites"), icon: "star", act: "do", run: () => bulk("unfav") })
                for (const c of app.collections)
                    out.push({ group: g, label: qsTr("Add to ") + c, icon: "bookmark", act: "do", run: () => bulk("collection", c) })
                for (const st of [["playing", qsTr("Playing")], ["want", qsTr("Want to play")], ["finished", qsTr("Finished")], ["dropped", qsTr("Dropped")]])
                    out.push({ group: g, label: qsTr("Mark as ") + st[1], icon: "tag", act: "do", run: () => bulk("status", st[0]) })
                out.push(P.showHidden ? { group: g, label: qsTr("Unhide"), icon: "eye", act: "do", run: () => bulk("unhide") }
                                      : { group: g, label: qsTr("Hide"), icon: "eye-off", act: "do", run: () => bulk("hide") })
            }
            out.push({ group: g, label: qsTr("Pick all %1 shown").arg(L.count), icon: "check", act: "do",
                       run: () => { const all = []; for (let i = 0; i < L.count; i++) all.push(P.keyAt(i)); L.picked = all; again() } })
            out.push({ group: g, label: qsTr("Stop picking"), icon: "x", act: "do", run: () => { L.picking = false; L.picked = []; libSheet.hide() } })
            return out
        }
        const sorts = ["name", "recent", "playtime", "added", "size", "rating"]
        out.push({ group: qsTr("Order"), label: qsTr("Sort by"), icon: "list", kind: "choice", cur: P.sortMode,
                   options: sorts.map(v => ({ v: v, t: L.sortNames[v] })), set: v => { P.sortMode = v; L.toTop(); again() } })
        out.push({ group: qsTr("Order"), label: qsTr("Show as"), icon: "layout-grid", kind: "choice", cur: L.listMode ? "list" : "grid",
                   options: [{ v: "grid", t: qsTr("Covers") }, { v: "list", t: qsTr("List") }], set: v => { L.setListMode(v === "list"); again() } })
        // Which games: everything, a list of yours, a backlog status, or the hidden ones.
        const which = [{ v: "", t: qsTr("All games") }, { v: "fav", t: qsTr("Favourites") }]
        for (const c of app.collections) which.push({ v: "c:" + c, t: c })
        for (const st of [["s:playing", qsTr("Playing")], ["s:want", qsTr("Want to play")], ["s:finished", qsTr("Finished")], ["s:dropped", qsTr("Dropped")]])
            which.push({ v: st[0], t: st[1] })
        which.push({ v: "hidden", t: qsTr("Hidden games") })
        out.push({ group: qsTr("Games"), label: qsTr("Show"), icon: "library", kind: "choice", cur: P.showHidden ? "hidden" : P.shelf, options: which,
                   set: v => { P.showHidden = v === "hidden"; P.shelf = v === "hidden" ? "" : v; L.toTop(); again() } })
        out.push({ group: qsTr("Filters"), label: qsTr("Installed only"), icon: "download", on: P.installedOnly,
                   set: v => { P.installedOnly = v; L.toTop(); again() } })
        for (const t of ["unplayed", "controller", "protondb", "couch", "linux", "dupes"]) {
            const has = P.tags.indexOf(t) !== -1
            out.push({ group: qsTr("Filters"), label: L.tagNames[t], icon: "filter", on: has,
                       set: v => { P.tags = v ? P.tags.concat([t]) : P.tags.filter(x => x !== t); L.toTop(); again() } })
        }
        if (!L.plain || P.sortMode !== "name")
            out.push({ group: qsTr("Filters"), label: qsTr("Clear all"), icon: "x", act: "do",
                       run: () => { P.search = ""; P.shelf = ""; P.showHidden = false; P.installedOnly = false; P.tags = []; P.sortMode = "name"; L.toTop(); again() } })
        out.push({ group: qsTr("Several at once"), label: qsTr("Pick games"), sub: qsTr("A picks or unpicks; Y again for what to do with them"), icon: "check", act: "do",
                   run: () => { libSheet.hide(); L.startPicking() } })
        return out
    }
    SideSheet {
        id: libSheet
        objectName: "tvLibrarySheet"
        side: "right"
        title: libraryPage.picking ? qsTr("Picked games") : qsTr("Sort and filter")
        rowsFn: tab => tv.libRows()
        onPicked: row => { if (row.run) row.run() }
    }

    // Challenges: this month's goals, left / right to set each; the progress is in the row.
    function goalRows() {
        const c = app.challenges(), out = []
        for (const i of c.items) {
            const steps = i.id === "hours" ? [0, 5, 10, 20, 30, 40, 60, 80, 100] : [0, 1, 2, 3, 4, 5, 6, 8, 10, 15, 20]
            out.push({ group: qsTr("Challenges for %1").arg(c.month) + "  ·  " + qsTr("%1 days left").arg(c.daysLeft),
                       label: i.label, icon: i.goal && i.done >= i.goal ? "check" : "zap",
                       sub: i.goal ? qsTr("%1 of %2 so far").arg(i.done + i.unit).arg(i.goal + i.unit) : qsTr("Off"),
                       kind: "choice", cur: i.goal,
                       options: steps.map(v => ({ v: v, t: v ? (i.id === "hours" ? qsTr("%1 hours").arg(v) : qsTr("%1 games").arg(v)) : qsTr("Off") })),
                       set: v => { app.setGoal(i.id, v); Qt.callLater(goalSheet.refresh) } })
        }
        return out
    }
    SideSheet {
        id: goalSheet
        objectName: "tvGoalSheet"
        side: "right"
        title: qsTr("Challenges")
        rowsFn: tab => tv.goalRows()
    }

    // Edit Home: which rows Home shows, and in what order (each person their own, synced).
    function homeRows() {
        const all = app.homeShelves(), out = []
        const save = list => { app.setHomeShelves(list.map(s => s.id), list.filter(s => !s.on).map(s => s.id)); Qt.callLater(homeSheet.refresh) }
        all.forEach((s, i) => {
            out.push({ group: qsTr("Rows on Home (X moves one up)"), label: s.name, icon: s.id === "news" ? "bell" : s.id.startsWith("c:") ? "bookmark" : "list",
                       sub: s.count ? (s.count === 1 ? qsTr("1 game") : qsTr("%1 games").arg(s.count)) : qsTr("Empty right now: hidden until it has games"),
                       on: s.on, alt: i > 0 ? qsTr("Move up") : "",
                       set: v => { const l = all.slice(); l[i] = Object.assign({}, s, { on: v }); save(l) },
                       move: () => { if (i === 0) return; const l = all.slice(); l.splice(i - 1, 0, l.splice(i, 1)[0]); save(l) } })
        })
        out.push({ group: qsTr("Rows on Home (X moves one up)"), label: qsTr("Back to the usual order"), icon: "refresh-cw", act: "do",
                   run: () => { app.setHomeShelves([], []); Qt.callLater(homeSheet.refresh) } })
        return out
    }
    SideSheet {
        id: homeSheet
        objectName: "tvHomeSheet"
        side: "right"
        title: qsTr("Edit Home")
        rowsFn: tab => tv.homeRows()
        onPicked: row => { if (row.run) row.run() }
        onAlt: row => { if (row.move && row.alt) { row.move(); Qt.callLater(() => homeSheet.nudge(-1)) } }  // the cursor goes up with the row
    }

    // What the menus control (TvControls.qml), the Settings screen, and a keyboard for passwords.
    TvControls {
        id: controls
        onAskPassword: ssid => { tv.joining = ssid; prompt.back = tv.Window.activeFocusItem; prompt.ask(qsTr("Join ") + ssid, qsTr("Type the Wi-Fi password."), true) }
        onOpenSettings: section => { mainMenu.open = false; quickMenu.open = false; tv.closePages(false); tvSettings.show(section) }
        onPadTest: padTest.show()
        onPower: what => { mainMenu.hide(); quickMenu.hide(); app.power(what) }
        onLeave: how => {
            mainMenu.hide(); quickMenu.hide(); tv.closePages(false)
            if (how === "exit") tv.exit()
            else Qt.quit()
        }
    }
    property string joining: ""
    TvSettings {
        id: tvSettings
        anchors.fill: parent
        z: 60
        theme: tv.theme
        tint: tv.tint
        controls: controls
        batt: topStatus.batt
        onClosed: tv.refocus(null)
    }
    TvPadTest {
        id: padTest
        anchors.fill: parent
        theme: tv.theme
        tint: tv.tint
        onClosed: tv.refocus(null)
    }
    TvTextPrompt {
        id: prompt
        anchors.fill: parent
        theme: tv.theme
        tint: tv.tint
        property Item back: null
        onAccepted: text => { app.wifiConnect(tv.joining, text, false); tv.refocus(back) }
        onClosed: tv.refocus(back)
    }
    // Back to where the keys were before an overlay took them (Settings under a menu, say).
    function refocus(item) {
        if (item && item.visible) item.forceActiveFocus()
        else if (tvSettings.visible) tvSettings.forceActiveFocus()
        else if (gamePage.visible) gamePage.forceActiveFocus()
        else if (libraryPage.visible) libraryPage.forceActiveFocus()
        else grid.forceActiveFocus()
    }
    // The menus, Settings and the keyboard show the PC as it is: read again when one opens.
    Connections {
        target: app
        enabled: quickMenu.open || mainMenu.open
        function onSystemChanged() { if (quickMenu.open) quickMenu.refresh() }
        function onSettingsChanged() { if (quickMenu.open) Qt.callLater(quickMenu.refresh) }
        function onSleepTimerChanged() { if (quickMenu.open) Qt.callLater(quickMenu.refresh) }
    }
    Connections {
        target: controls
        function onArmedChanged() { if (quickMenu.open) quickMenu.refresh(); if (mainMenu.open) mainMenu.refresh(); if (powerMenu.open) powerMenu.refresh() }
    }

    // A menu that slides in from one side over a dimmed screen. A chooses, B (or the way it came
    // from) closes it; with tabs, LB / RB switch them. Rows: see TvRowList.qml.
    component SideSheet: Item {
        id: sheet
        property string side: "left"
        property string title: ""
        property var tabs: []
        property int tab: 0
        readonly property string tabId: (tabs[tab] || {}).id || ""
        property var rowsFn: function(tab) { return [] }
        property var rows: []
        property bool open: false
        property Item back: null
        signal picked(var row)
        signal alt(var row)
        anchors.fill: parent
        z: 90
        visible: open || slide.running || fadeIn.running
        function show() {
            if (open) { hide(); return }
            const f = tv.Window.activeFocusItem
            back = f && f !== sheetList ? f : null
            app.uiSound("select"); app.refreshSystem(); refresh(); sheetList.first(); open = true; sheetList.forceActiveFocus()
        }
        function hide() { if (!open) return; app.uiSound("back"); open = false; tv.refocus(back) }
        function nudge(d) { sheetList.currentIndex = Math.max(0, Math.min(rows.length - 1, sheetList.currentIndex + d)) }
        function refresh() { const i = sheetList.currentIndex; rows = rowsFn(tabId); sheetList.currentIndex = Math.min(Math.max(0, i), rows.length - 1)
                             if (!sheetList.pickable(rows[sheetList.currentIndex])) sheetList.first() }
        function setTab(i) {
            if (!tabs.length) return
            tab = (i + tabs.length) % tabs.length
            app.uiSound("move")
            rows = rowsFn(tabId); sheetList.first(); sheetList.positionViewAtBeginning()
            tabSwap.restart()
        }
        readonly property real w: Math.round(Math.min(520, Math.max(360, tv.width * 0.33)))
        // The state is read again now and then while it is open (a controller that connects).
        Timer { interval: 5000; repeat: true; running: sheet.open && sheet.tabs.length > 0; onTriggered: app.refreshSystem() }

        Frost { opacity: sheet.open ? 1 : 0; visible: opacity > 0; Behavior on opacity { NumberAnimation { duration: 200 } } }
        Rectangle {  // the dimmed screen behind; a click on it closes the menu
            anchors.fill: parent
            color: "black"
            opacity: sheet.open ? 0.5 : 0
            Behavior on opacity { enabled: !app.still; NumberAnimation { id: fadeIn; duration: 200 } }
            MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onClicked: sheet.hide(); onWheel: w => w.accepted = true }
        }
        Rectangle {
            id: pane
            width: sheet.w
            height: parent.height
            x: sheet.side === "left" ? (sheet.open ? 0 : -width) : (sheet.open ? parent.width - width : parent.width)
            Behavior on x { enabled: !app.still; NumberAnimation { id: slide; duration: 220; easing.type: Easing.OutCubic } }
            color: Qt.alpha(theme.surfaceContainerLow, 0.9)
            MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: w => w.accepted = true }
            RectangularShadow {
                z: -1
                anchors.fill: parent
                visible: !app.light && GraphicsInfo.api !== GraphicsInfo.Software
                blur: 50
                color: Qt.alpha("black", 0.6)
            }
            Rectangle {  // a thin light edge on the side facing the screen
                width: 1; height: parent.height
                x: sheet.side === "left" ? parent.width - 1 : 0
                color: Qt.alpha("white", 0.08)
            }
            // The way it came from closes it: Guide for the main menu, Guide + A for quick access;
            // the other one swaps to it. LB / RB: the tabs.
            Keys.onPressed: event => {
                const k = event.key
                if ((k === Qt.Key_F10 && sheet.side === "left") || (k === Qt.Key_F9 && sheet.side === "right")) { sheet.hide(); event.accepted = true }
                else if (k === Qt.Key_F10 || k === Qt.Key_F9) {
                    const other = k === Qt.Key_F10 ? mainMenu : quickMenu
                    sheet.open = false
                    other.show(); other.back = sheet.back
                    event.accepted = true
                }
                else if ((k === Qt.Key_PageUp || k === Qt.Key_PageDown) && sheet.tabs.length) { sheet.setTab(sheet.tab + (k === Qt.Key_PageDown ? 1 : -1)); event.accepted = true }
            }
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 28
                anchors.topMargin: 32
                spacing: 16
                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    WordMark { visible: sheet === mainMenu; anchors.verticalCenter: parent.verticalCenter; size: 28 }
                    Text { visible: sheet !== mainMenu; anchors.verticalCenter: parent.verticalCenter
                           text: sheet.title; color: theme.onSurface; font.pixelSize: 24; font.weight: Font.Medium }
                    // Steam-style status at a glance: Wi-Fi, Bluetooth, volume.
                    Row {
                        visible: sheet.side !== "left"
                        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                        spacing: 12
                        Repeater {
                            model: tv.statusIcons
                            Icon { required property var modelData; name: modelData; size: 20; color: theme.onSurfaceVariant }
                        }
                    }
                }
                // The tabs: LB / RB (or a tap). The open one shows its name.
                Row {
                    visible: sheet.tabs.length > 0
                    Layout.fillWidth: true
                    spacing: 8
                    PadButton { visible: pad.connected; anchors.verticalCenter: parent.verticalCenter; button: "lb"; style: pad.style; size: 24 }
                    Repeater {
                        model: sheet.tabs
                        Rectangle {
                            id: tabPill
                            required property var modelData
                            required property int index
                            readonly property bool on: index === sheet.tab
                            height: 44; radius: 22
                            width: on ? tabName.implicitWidth + 70 : 50
                            Behavior on width { enabled: !app.still; NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                            color: on ? Qt.alpha(tv.tint.primary, 0.22) : tabHov.hovered ? Qt.alpha(theme.onSurface, 0.08) : Qt.alpha(theme.onSurface, 0.04)
                            border.width: on ? 1 : 0; border.color: tv.tint.primary
                            clip: true
                            Icon { x: 14; anchors.verticalCenter: parent.verticalCenter; name: tabPill.modelData.icon; size: 22
                                   color: tabPill.on ? tv.tint.primary : theme.onSurfaceVariant }
                            Text { id: tabName; x: 46; anchors.verticalCenter: parent.verticalCenter; visible: tabPill.on
                                   text: tabPill.modelData.label; color: theme.onSurface; font.pixelSize: 16; font.weight: Font.DemiBold }
                            HoverHandler { id: tabHov; cursorShape: Qt.PointingHandCursor }
                            TapHandler { onTapped: { sheet.setTab(tabPill.index); sheetList.forceActiveFocus() } }
                        }
                    }
                    PadButton { visible: pad.connected; anchors.verticalCenter: parent.verticalCenter; button: "rb"; style: pad.style; size: 24 }
                }
                TvRowList {
                    id: sheetList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    theme: tv.theme
                    tint: tv.tint
                    rows: sheet.rows
                    catchBack: true
                    catchLeft: sheet.side === "left"
                    catchRight: sheet.side === "right"
                    onBack: sheet.hide()
                    onEdge: sheet.hide()
                    onPicked: row => sheet.picked(row)
                    onAlt: row => sheet.alt(row)
                    transform: Translate { id: tabShift }
                    NumberAnimation { id: tabSwap; target: tabShift; property: "x"; from: 18; to: 0; duration: 200; easing.type: Easing.OutCubic }
                }
                Row {
                    spacing: 20
                    Repeater {
                        model: {
                            const r = sheetList.current
                            const adj = r.kind === "slider" || r.kind === "choice"
                            const out = pad.connected || pad.deck
                                ? [{ b: ["a"], t: r.kind === "slider" && r.press ? qsTr("Mute") : qsTr("Choose") },
                                   adj ? { k: "← →", t: qsTr("Change") } : null,
                                   r.alt ? { b: ["x"], t: r.alt } : null, { b: ["b"], t: qsTr("Back") }]
                                : [{ k: qsTr("Enter"), t: qsTr("Choose") }, adj ? { k: "← →", t: qsTr("Change") } : null,
                                   r.alt ? { k: "F2", t: r.alt } : null, { k: qsTr("Esc"), t: qsTr("Back") }]
                            return out.filter(h => h)
                        }
                        Hint { required property var modelData; hint: modelData }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------ music, screensaver, who's playing
    Loader {
        active: typeof canPlayVideo !== "undefined" && canPlayVideo && !!app.settingsMap.tv_music
        source: "TvMusic.qml"
        onLoaded: item.playing = Qt.binding(() => tv.visible && Qt.application.state === Qt.ApplicationActive
                                                   && app.nowPlaying.length === 0 && !trailerLoader.active)
    }
    TvScreensaver {
        id: saver
        anchors.fill: parent
        z: 200
        theme: tv.theme
        onWoke: {
            tv.lastInput = Date.now()
            if (tv.focusBeforeSaver && tv.focusBeforeSaver.visible) tv.focusBeforeSaver.forceActiveFocus()
            else grid.forceActiveFocus()
        }
    }
    TvWho {
        id: whoPicker
        anchors.fill: parent
        z: 150
        theme: tv.theme
        onDone: tv.refocus(null)
    }
    // The half second after a layer opens or closes: one invisible sheet over everything takes
    // the stray clicks (see tv.layers). The keys and the controller are never held back.
    MouseArea {
        anchors.fill: parent
        z: 1000
        visible: tv.settling
        acceptedButtons: Qt.AllButtons
        onWheel: wheel => wheel.accepted = true
    }
}
