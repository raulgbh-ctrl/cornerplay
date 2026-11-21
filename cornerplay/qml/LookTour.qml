import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Try the looks one by one (Settings > Appearance > Look > Try them one by one): each look is
// turned on alone over the real library, and you keep it or skip it. At the end the ones you
// kept are switched on and the rest off; Stop puts everything back as it was.
Popup {
    id: tour
    property var theme: app.theme
    signal showGame()            // the look is on a game's page: open one
    signal hideGame()

    // key, name, what to do to see it, and whether it lives on a game's page
    readonly property var looks: [
        { k: "look_ambient", t: qsTr("The game's colour"), d: qsTr("A soft glow behind the library and coloured shadows under covers. Point at a few covers.") },
        { k: "look_glass", t: qsTr("Frosted glass"), d: qsTr("The sidebar and toolbar over the last game's art.") },
        { k: "look_showcase", t: qsTr("Showcase banner"), d: qsTr("A taller banner on Home that drifts and turns between your last three games.") },
        { k: "look_rich", t: qsTr("Rich covers"), d: qsTr("Title and time played under covers; games not installed stay grey until pointed at.") },
        { k: "look_titles", t: qsTr("Big titles and a greeting"), d: qsTr("Larger section titles, and Home says hello.") },
        { k: "look_motion", t: qsTr("Motion"), d: qsTr("Covers come in one after another. Change the store in the sidebar to see it.") },
        { k: "look_shelves", t: qsTr("Home as rows"), d: qsTr("Continue, Ready to play, Recently added and Not played yet as rows.") },
        { k: "look_wide", t: qsTr("Big Continue playing cards"), d: qsTr("Art, hours, achievements and your last screenshot.") },
        { k: "look_search", t: qsTr("Floating search"), d: qsTr("A search pill with quick filters under it.") },
        { k: "look_sidebar", t: qsTr("Sidebar in the game's colour"), d: qsTr("With what is running or downloading at its foot.") },
        { k: "look_expand", t: qsTr("Covers open up"), d: qsTr("Rest the pointer on a cover: it grows into a wide card with art, trailer and Play.") },
        { k: "look_skeleton", t: qsTr("Loading shimmer"), d: qsTr("Covers shimmer while their art loads (best seen on a fresh start).") },
        { k: "look_aurora", t: qsTr("Aurora"), d: qsTr("Three colours from the game's cover drift behind the library. Point at a few covers.") },
        { k: "look_fullart", t: qsTr("The window as art"), d: qsTr("The game under the pointer fills the whole window, the rest frosted over it.") },
        { k: "look_island", t: qsTr("Island"), d: qsTr("A pill at the top for the download, the game running, or the time.") },
        { k: "look_page", t: qsTr("Game page art"), d: qsTr("A game's page on tall drifting art, in the game's colour."), page: true },
        { k: "look_pagetabs", t: qsTr("Game page tabs"), d: qsTr("Section tabs, a header that stays when you scroll, achievements as a ring."), page: true },
        { k: "look_playring", t: qsTr("Play ring"), d: qsTr("Play turns into a ring while the game starts, then a tick."), page: true },
    ]
    property int idx: 0
    property var before: ({})    // every look as it was when the tour began
    property var kept: ({})
    readonly property var cur: looks[Math.min(idx, looks.length - 1)]
    readonly property bool finished: idx >= looks.length
    readonly property var keptNames: looks.filter(l => kept[l.k]).map(l => l.t)

    modal: false
    focus: false
    closePolicy: Popup.NoAutoClose   // clicks go on to the library underneath
    width: Math.min(560, parent ? parent.width - 32 : 560)
    padding: 16
    background: Rectangle {
        radius: 18
        color: tour.theme.surfaceContainerHigh
        border.width: 1; border.color: Qt.alpha(tour.theme.onSurface, 0.1)
    }

    function start(why) {  // why: unused (lets tools/shoot.py call it)
        const b = {}, k = {}
        for (const l of looks) { b[l.k] = !!app.settingsMap[l.k]; k[l.k] = b[l.k] }
        before = b; kept = k; idx = 0
        open()
        show()
    }
    // Only the look being tried is on.
    function show() {
        for (const l of looks) {
            const on = !finished && l.k === cur.k
            if (!!app.settingsMap[l.k] !== on) app.setSetting(l.k, on)
        }
        if (!finished && cur.page) { showGame(); close(); open() }  // back above the game's page
        else hideGame()
    }
    function answer(keep) {
        const k = Object.assign({}, kept); k[cur.k] = keep; kept = k
        idx += 1
        show()
    }
    function back() { if (idx > 0) { idx -= 1; show() } }
    function apply(values) {
        for (const l of looks) if (!!app.settingsMap[l.k] !== !!values[l.k]) app.setSetting(l.k, !!values[l.k])
        hideGame()
        close()
    }
    function stop() { apply(before) }
    function save() { apply(kept) }

    contentItem: ColumnLayout {
        id: col
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: tour.finished ? qsTr("Your looks") : qsTr("Look %1 of %2").arg(tour.idx + 1).arg(tour.looks.length)
                color: tour.theme.outline; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 0.4
            }
            KButton { theme: tour.theme; text: qsTr("Stop"); flat: true; onClicked: tour.stop() }
        }
        Text {
            Layout.fillWidth: true
            text: tour.finished ? (tour.keptNames.length ? tour.keptNames.join(", ") : qsTr("None: the plain look"))
                                : tour.cur.t
            color: tour.theme.onSurface; font.pixelSize: tour.finished ? 15 : 20; font.weight: Font.DemiBold
            wrapMode: Text.WordWrap
        }
        Text {
            Layout.fillWidth: true
            text: tour.finished ? qsTr("Save switches these on and the rest off. You can change each one later in Settings > Appearance > Look.")
                                : tour.cur.d
            color: tour.theme.onSurfaceVariant; font.pixelSize: 13; wrapMode: Text.WordWrap
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            KButton { theme: tour.theme; text: qsTr("Back"); flat: true; enabled: tour.idx > 0; onClicked: tour.back() }
            Item { Layout.fillWidth: true }
            KButton { theme: tour.theme; visible: !tour.finished; text: qsTr("Skip"); onClicked: tour.answer(false) }
            KButton { theme: tour.theme; visible: !tour.finished; text: qsTr("Keep it"); primary: true; onClicked: tour.answer(true) }
            KButton { theme: tour.theme; visible: tour.finished; text: qsTr("Save"); primary: true; onClicked: tour.save() }
        }
    }
}
