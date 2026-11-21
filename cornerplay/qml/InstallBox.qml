import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs

// The Install window (as Heroic has it): how big the game is, where it goes and whether that
// drive has room, the language and version (GOG), the DLCs, and Install now or tonight.
KDialog {
    id: box
    objectName: "installBox"
    heading: qsTr("Install %1").arg(g.title || "")
    headingIcon: "download"
    width: Math.min((parent ? parent.width : 800) - 60, 600)

    property string key: ""
    property var g: ({})
    property var info: ({})
    property string folder: ""
    property bool dlcs: true
    property bool askAgain: true
    property string language: ""
    property string platform: "windows"
    property var space: ({})

    function ask(k) {
        key = k; g = app.game(k); info = ({}); dlcs = true; askAgain = true; language = ""; platform = "windows"
        folder = ""; space = ({})
        app.installInfo(k)
        open()
    }
    function refreshSpace() { space = folder ? app.folderSpace(folder) : ({}) }
    onFolderChanged: refreshSpace()
    Connections {
        target: app
        function onInstallInfoReady(k, d) {
            if (k !== box.key) return
            box.info = d
            if (!box.folder) box.folder = d.folder || ""
            box.language = d.language || ""
            box.platform = d.platform || "windows"
        }
    }

    // GOG gives sizes per language ("*" is shared by all): add the shared part to the chosen one.
    readonly property var sizes: {
        const s = info.sizes || {}
        if (!Object.keys(s).length) return [info.download || 0, info.disk || 0]
        const base = s["*"] || [0, 0], own = s[language] || [0, 0]
        return [base[0] + own[0], base[1] + own[1]]
    }
    readonly property real need: sizes[1] || sizes[0] || 0
    readonly property real left: (space.free || 0) - need
    readonly property bool full: !!space.ok && need > 0 && left <= 0
    readonly property bool tight: !!space.ok && need > 0 && !full && left < 0.10 * (space.total || 0)

    function langName(code) {
        const n = Qt.locale(String(code).replace("-", "_")).nativeLanguageName
        return n ? n.charAt(0).toUpperCase() + n.slice(1) : code
    }

    FolderDialog {
        id: pickFolder
        title: qsTr("Install in which folder?")
        onAccepted: {
            const u = selectedFolder.toString()
            box.folder = decodeURIComponent(u.replace(/^file:\/\//, ""))
        }
    }

    contentItem: ColumnLayout {
        spacing: 16

        // The game, and how much it takes.
        RowLayout {
            Layout.fillWidth: true
            spacing: 16
            RoundedArt {
                Layout.preferredWidth: 78; Layout.preferredHeight: 114
                radius: 10
                Rectangle { anchors.fill: parent; color: theme.surfaceContainerHigh }
                ArtImage { anchors.fill: parent; sources: box.g.covers || []; sourceSize.width: 160 }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
                Row {
                    spacing: 7
                    StoreIcon { anchors.verticalCenter: parent.verticalCenter; size: 16; store: box.g.store || ""; color: box.g.storeColor || theme.primary }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: box.g.storeName || ""; color: theme.onSurfaceVariant; font.pixelSize: 13 }
                }
                GridLayout {
                    columns: 2; columnSpacing: 18; rowSpacing: 4
                    visible: box.info.ready === true && box.sizes[0] > 0
                    Text { text: qsTr("Download"); color: theme.outline; font.pixelSize: 12 }
                    Text { text: app.niceSize(box.sizes[0]); color: theme.onSurface; font.pixelSize: 15; font.weight: Font.DemiBold }
                    Text { text: qsTr("On disk"); color: theme.outline; font.pixelSize: 12; visible: box.sizes[1] > 0 }
                    Text { text: app.niceSize(box.sizes[1]); color: theme.onSurface; font.pixelSize: 15; font.weight: Font.DemiBold; visible: box.sizes[1] > 0 }
                }
                Row {
                    visible: box.info.ready !== true
                    spacing: 8
                    Icon { anchors.verticalCenter: parent.verticalCenter; name: "loader"; size: 14; color: theme.outline
                           RotationAnimation on rotation { running: box.visible && box.info.ready !== true && !app.still; from: 0; to: 360; duration: 1000; loops: Animation.Infinite } }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: qsTr("Asking %1 how big it is…").arg(box.g.storeName || ""); color: theme.outline; font.pixelSize: 13 }
                }
                Text { visible: box.info.ready === true && !(box.sizes[0] > 0); text: qsTr("The store did not say how big it is.")
                       color: theme.outline; font.pixelSize: 13 }
            }
        }

        // Where it goes, and whether that drive has room.
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6
            Text { text: qsTr("Install in"); color: theme.onSurfaceVariant; font.pixelSize: 12; font.weight: Font.DemiBold }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                KField {
                    id: folderField
                    theme: box.theme
                    Layout.fillWidth: true
                    iconName: "folder-open"
                    text: box.folder
                    onEditingFinished: box.folder = text.trim()
                }
                KButton { theme: box.theme; text: qsTr("Change…"); onClicked: pickFolder.open() }
            }
            Text {
                Layout.fillWidth: true
                visible: !!box.space.ok
                wrapMode: Text.WordWrap
                font.pixelSize: 12
                color: box.full ? theme.error : box.tight ? "#e0a030" : theme.outline
                text: box.need > 0
                      ? (box.full ? qsTr("Not enough room: %1 free on %2, it needs %3.").arg(app.niceSize(box.space.free)).arg(box.space.label).arg(app.niceSize(box.need))
                                  : qsTr("%1 free on %2, %3 left after installing.").arg(app.niceSize(box.space.free)).arg(box.space.label).arg(app.niceSize(box.left))
                                    + (box.tight ? "  " + qsTr("That is nearly full.") : ""))
                      : qsTr("%1 free on %2.").arg(app.niceSize(box.space.free)).arg(box.space.label)
            }
            // Not enough room: games on that drive you have not played for a while, biggest
            // first, enough of them to make room. Uninstall asks twice.
            ColumnLayout {
                id: room
                Layout.fillWidth: true
                visible: box.full && suggest.length > 0
                spacing: 6
                property string armed: ""
                readonly property var suggest: box.full ? app.spaceToFree(box.folder, box.need) : []
                Text { Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 12; color: theme.onSurfaceVariant
                       text: qsTr("To make room, you could uninstall:") }
                Repeater {
                    model: room.suggest
                    RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 10
                        Text { Layout.fillWidth: true; elide: Text.ElideRight; font.pixelSize: 13; color: theme.onSurface
                               text: modelData.title + "  ·  " + modelData.sizeText + "  ·  " + qsTr("last played %1").arg(modelData.last) }
                        KButton {
                            theme: box.theme; danger: true
                            text: room.armed === modelData.key ? qsTr("Sure? Uninstall") : qsTr("Uninstall")
                            onClicked: {
                                if (room.armed !== modelData.key) { room.armed = modelData.key; return }
                                room.armed = ""
                                app.uninstall(modelData.key)
                                spaceAgain.restart()
                            }
                        }
                    }
                }
                // The drive's free space once the uninstall has had a moment.
                Timer { id: spaceAgain; interval: 4000; repeat: false; onTriggered: box.refreshSpace() }
            }
        }

        // GOG: which version and which language.
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            visible: (box.info.linux === true) || (box.info.languages || []).length > 1
            ColumnLayout {
                visible: box.info.linux === true
                spacing: 6
                Text { text: qsTr("Version"); color: theme.onSurfaceVariant; font.pixelSize: 12; font.weight: Font.DemiBold }
                KCombo {
                    theme: box.theme
                    Layout.preferredWidth: 200
                    model: [{ label: qsTr("Windows (through Proton)"), value: "windows" }, { label: qsTr("Linux"), value: "linux" }]
                    currentIndex: box.platform === "linux" ? 1 : 0
                    onActivated: box.platform = currentValue
                }
            }
            ColumnLayout {
                visible: (box.info.languages || []).length > 1
                Layout.fillWidth: true
                spacing: 6
                Text { text: qsTr("Language"); color: theme.onSurfaceVariant; font.pixelSize: 12; font.weight: Font.DemiBold }
                KCombo {
                    theme: box.theme
                    Layout.fillWidth: true
                    model: (box.info.languages || []).map(c => ({ label: box.langName(c), value: c }))
                    currentIndex: Math.max(0, (box.info.languages || []).indexOf(box.language))
                    onActivated: box.language = currentValue
                }
            }
        }

        // The DLCs you own.
        Rectangle {
            Layout.fillWidth: true
            visible: (box.info.dlcs || []).length > 0
            implicitHeight: dlcCol.implicitHeight + 20
            radius: 12
            color: theme.surfaceContainerHigh
            ColumnLayout {
                id: dlcCol
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                spacing: 4
                Tick {
                    text: qsTr("Also install the DLCs you own (%1)").arg((box.info.dlcs || []).length)
                    on: box.dlcs
                    onFlipped: box.dlcs = !box.dlcs
                }
                Text {
                    Layout.fillWidth: true
                    leftPadding: 30
                    text: (box.info.dlcs || []).join(", ")
                    color: theme.outline; font.pixelSize: 11
                    elide: Text.ElideRight; maximumLineCount: 2; wrapMode: Text.WordWrap
                }
            }
        }

        Tick {
            text: qsTr("Ask every time (Settings > Library)")
            on: box.askAgain
            onFlipped: box.askAgain = !box.askAgain
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Item { Layout.fillWidth: true }
            KButton { theme: box.theme; text: qsTr("Cancel"); onClicked: box.close() }
            KButton {
                theme: box.theme; iconName: "moon"; text: qsTr("Tonight")
                onClicked: { box.go(true); box.close() }
            }
            KButton {
                theme: box.theme; primary: true; iconName: "download"
                text: box.full ? qsTr("Install anyway") : qsTr("Install")
                onClicked: { box.go(false); box.close() }
            }
        }
    }

    function go(tonight) {
        app.installWith(key, { folder: folder, dlcs: dlcs, language: language, platform: platform,
                               tonight: tonight, ask_again: askAgain })
    }

    // A tick box: a small square that fills in, and its words.
    component Tick: RowLayout {
        id: tk
        property string text
        property bool on
        signal flipped()
        Layout.fillWidth: true
        spacing: 10
        Rectangle {
            implicitWidth: 20; implicitHeight: 20; radius: 6
            color: tk.on ? app.theme.primary : "transparent"
            border.width: tk.on ? 0 : 2; border.color: app.theme.outline
            Icon { anchors.centerIn: parent; visible: tk.on; name: "check"; size: 14; color: app.theme.onPrimary }
        }
        Text { Layout.fillWidth: true; text: tk.text; color: app.theme.onSurface; font.pixelSize: 13; wrapMode: Text.WordWrap }
        HoverHandler { cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: tk.flipped() }
    }
}
