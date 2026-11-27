import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import "protondb.js" as ProtonDB

// One cover tile in the library grid.
Item {
    id: card
    required property var theme
    required property bool current
    required property string key
    required property string store
    required property var covers
    required property string title
    required property string storeName
    required property string storeColor
    required property string cover
    required property string coverFallback
    required property bool installed
    required property string job
    required property real progress
    required property int copies
    required property bool update
    required property string protondb
    required property bool favourite
    required property real achieved   // 0..1 of the game's achievements earned; -1 when unknown
    required property bool isNew      // bought or claimed this week and not played yet
    required property int dlcToBuy    // DLC you don't own on any store (0 until looked up)
    required property int dlcNew      // DLC that came out since you last looked
    required property var heroes
    required property var logos
    // "cover" (the box art), "logo" (wide art with the game's logo: the logo wall) or "box"
    // (a game case with a spine, standing on a shelf). View menu, desktop library only.
    property string style: "cover"
    readonly property real spine: style === "box" ? Math.round(width * 0.075) : 0
    property bool showProtonDb: true
    property int cornerRadius: 14
    property bool showBadge: true
    property bool showTitle: false
    property int gap: 8   // around the cover (Settings > Appearance > Density)
    property bool dim: true
    property string trailer: ""   // a trailer to play inside the cover (the main window sets it while pointed at)
    signal opened()
    signal activated()
    signal installRequested()   // the Install button on the cover
    signal menuRequested(point at)
    signal pickRequested(bool range)  // Ctrl+click (one) or Shift+click (a range): several games at once
    property bool picked: false       // one of the games picked for an action
    property bool picking: false      // some game is picked: a plain click picks too  // right-click, or a long press on a touchscreen (in the card's coordinates)

    readonly property bool hovered: hover.hovered
    readonly property point hoverAt: hover.point.scenePosition  // where the pointer is (TV: did it really move?)
    readonly property bool lit: hover.hovered || current
    property real focusScale: 1.03
    // One colour per status, the same everywhere a card shows: NEW the theme's own, an update
    // green, new DLC amber (outlined, so it never reads as NEW), downloads the theme's.
    readonly property color updateColour: "#3fb27f"
    readonly property color dlcColour: "#f0a630"
    // Tilt: the cover tips toward the pointer, like a game case held in the hand (-1..1 each way).
    // The desktop library only (TV mode sets tilt: false); Settings > Appearance turns it off.
    property bool tilt: true
    // Looks (Settings > Appearance > Look): the title and a line under the cover; games not
    // installed in grey until pointed at; a soft shadow in the cover's own colour.
    property bool shimmer: false   // Look > Loading shimmer: a soft light sweeps the cover until its art is in
    property bool playRing: false  // Look > Play ring: the Play button turns into a ring, then a tick
    property string ringState: ""  // "", "spin", "done"
    Timer { id: ringTimer; interval: 1400; onTriggered: { if (card.ringState === "spin") { card.ringState = "done"; ringTimer.restart() } else card.ringState = "" } }
    property bool caption: false
    property string captionSub: ""
    property bool greyWhenOff: false
    property bool glow: false
    // Look > Cover glow: only the cover under the pointer or the controller glows, in its own
    // colours (its colour is worked out then, not for the whole library).
    property bool glowOnFocus: false
    readonly property bool glowing: glow || (glowOnFocus && lit)
    property string glowColour: glowing ? app.gameColour(key) : ""
    Connections { target: app; enabled: card.glowing && card.glowColour === ""
                  function onGameColourReady(k, c) { if (k === card.key) card.glowColour = c } }
    property real enterY: 0   // Look > Motion: where it comes in from
    transform: Translate { y: card.enterY }
    readonly property bool tilting: tilt && hover.hovered && app.settingsMap.card_tilt !== false && !app.still
                                    && !app.light && GraphicsInfo.api !== GraphicsInfo.Software
    readonly property real tiltX: tilting ? Math.max(-1, Math.min(1, hover.point.position.x / Math.max(1, width) * 2 - 1)) : 0
    readonly property real tiltY: tilting ? Math.max(-1, Math.min(1, hover.point.position.y / Math.max(1, height) * 2 - 1)) : 0

    // The cover's own colour, glowing softly under it (brighter when pointed at).
    RectangularShadow {
        anchors.fill: frame
        visible: card.glowing && card.glowColour !== "" && !app.light
        radius: frame.radius
        scale: frame.scale
        blur: card.lit ? 36 : 24
        spread: -4
        offset.y: card.lit ? 14 : 10
        color: Qt.alpha(card.glowColour, card.lit ? 0.7 : 0.38)
        Behavior on color { ColorAnimation { duration: 160 } }
    }
    // The cover's shadow (Settings > Appearance: none, soft or deep).
    RectangularShadow {
        anchors.fill: frame
        visible: !app.light && !card.lit && (app.settingsMap.card_shadow || "none") !== "none"
        readonly property bool deep: app.settingsMap.card_shadow === "deep"
        radius: frame.radius
        scale: frame.scale
        blur: deep ? 26 : 12
        spread: 0
        offset.y: deep ? 12 : 5
        color: Qt.alpha("black", deep ? 0.6 : 0.4)
    }
    // Box view: a wooden shelf under each row; the cells sit edge to edge, so the planks join up.
    Rectangle {
        visible: card.style === "box"
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; bottomMargin: card.gap - 2 }
        height: 16
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#a87a4f" }
            GradientStop { position: 0.18; color: "#8a6038" }
            GradientStop { position: 1.0; color: "#5a3c22" }
        }
        Rectangle {  // its shadow on the wall
            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.bottom
            height: 10
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.alpha("black", 0.35) }
                GradientStop { position: 1; color: "transparent" }
            }
        }
    }
    Rectangle {
        id: frame
        anchors.fill: parent
        anchors.margins: card.gap
        anchors.bottomMargin: card.style === "box" ? card.gap + 18 : card.caption ? card.gap + 46 : card.gap
        radius: card.cornerRadius
        color: theme.surfaceContainerHigh
        // TV mode's focus reads from across the room: a bigger step than the desktop's hover.
        scale: !card.lit || app.still ? 1.0 : card.focusScale
        Behavior on scale { enabled: !app.still; NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
        transform: [
            Rotation {
                origin.x: frame.width / 2; origin.y: frame.height / 2
                axis { x: 0; y: 1; z: 0 }
                angle: card.tiltX * 7
                Behavior on angle { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            },
            Rotation {
                origin.x: frame.width / 2; origin.y: frame.height / 2
                axis { x: 1; y: 0; z: 0 }
                angle: -card.tiltY * 6
                Behavior on angle { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            }
        ]

        // Box view: the case's spine, with the title running up it.
        Rectangle {
            visible: card.style === "box"
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
            width: card.spine + 6
            radius: 3
            color: Qt.darker(card.storeColor || theme.primary, 2.6)
            Text {
                anchors.centerIn: parent
                width: parent.height - 16
                rotation: -90
                text: card.title
                color: Qt.alpha("white", 0.85)
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignHCenter
                font.family: app.titleFamily
                font.pixelSize: Math.max(8, Math.round(card.spine * 0.55)); font.weight: Font.DemiBold
            }
        }
        Item {
            id: art
            anchors.fill: parent
            anchors.leftMargin: card.spine
            layer.enabled: !app.light && GraphicsInfo.api !== GraphicsInfo.Software
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: mask
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1.0
            }

            // Placeholder shown until (or instead of) a cover.
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0; color: Qt.darker(card.storeColor, 2.2) }
                    GradientStop { position: 1; color: theme.surfaceContainerLowest || theme.surfaceContainerLow }
                }
                Text {
                    anchors.centerIn: parent
                    width: parent.width - 28
                    text: card.title
                    color: theme.onSurface
                    font.pixelSize: 17
                    font.family: app.titleFamily
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    maximumLineCount: 4
                    elide: Text.ElideRight
                    visible: img.status !== Image.Ready
                }
                // Shimmer while the cover downloads.
                Rectangle {
                    id: shimmer
                    visible: img.status === Image.Loading && !app.light
                    width: parent.width * 0.6
                    height: parent.height
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 0.5; color: Qt.alpha("white", 0.09) }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                    NumberAnimation on x {
                        running: shimmer.visible
                        loops: Animation.Infinite
                        from: -shimmer.width; to: card.width
                        duration: 1300
                        easing.type: Easing.InOutQuad
                    }
                }
            }

            // Only wide art for this game: show all of it, centred, over a blurred, enlarged
            // copy that fills the card (rather than cropping a slice out of the middle).
            readonly property bool wideArt: card.style === "cover" && img.status === Image.Ready && img.implicitWidth > img.implicitHeight * 1.1
            Image {
                id: wideBack
                anchors.fill: parent
                visible: false
                source: parent.wideArt ? img.source : ""
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize.width: 160
            }
            MultiEffect {
                anchors.fill: parent
                source: wideBack
                visible: parent.wideArt && !app.light && wideBack.status === Image.Ready
                blurEnabled: true; blur: 1.0; blurMax: 48
                brightness: -0.15
                opacity: img.opacity
            }
            ArtImage {
                id: img
                anchors.fill: parent
                sources: card.style === "logo" ? (card.heroes || []).concat(card.covers) : card.covers
                fillMode: parent.wideArt ? Image.PreserveAspectFit : Image.PreserveAspectCrop
                sourceSize.width: Math.min(app.light ? 280 : 600, Math.max(160, Math.ceil(width * Screen.devicePixelRatio / 40) * 40))
                opacity: status === Image.Ready ? (card.installed || !card.dim ? 1 : 0.78) : 0
                Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 200 } }
                // Not installed: grey, coming into colour while pointed at.
                readonly property bool grey: card.greyWhenOff && !card.installed && card.job === "" && GraphicsInfo.api !== GraphicsInfo.Software
                layer.enabled: grey
                layer.effect: MultiEffect { saturation: card.lit ? 0 : -1; Behavior on saturation { NumberAnimation { duration: 250 } } }
            }

            // Look > Loading shimmer: until the art is in, a soft band of light sweeps the empty cover.
            Rectangle {
                id: shimBox
                visible: card.shimmer && img.status !== Image.Ready
                anchors.fill: parent
                color: Qt.alpha(card.theme.onSurface, 0.05)
                clip: true
                Rectangle {
                    width: parent.width * 0.6; height: parent.height * 1.6
                    y: -parent.height * 0.3
                    rotation: 18
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 0.5; color: Qt.alpha(card.theme.onSurface, 0.09) }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                    NumberAnimation on x { running: shimBox.visible; loops: Animation.Infinite; from: -shimBox.width; to: shimBox.width * 1.4; duration: 1300; easing.type: Easing.InOutQuad }
                }
            }

            // Logo wall: the game's logo over its wide art (its title when there is no logo).
            Rectangle {
                visible: card.style === "logo"
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.35; color: "transparent" }
                    GradientStop { position: 1.0; color: Qt.alpha("black", 0.75) }
                }
            }
            Image {
                id: logoImg
                visible: card.style === "logo"
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: parent.width * 0.07 }
                height: parent.height * 0.38
                source: card.style === "logo" ? ((card.logos || [])[0] || "") : ""
                fillMode: Image.PreserveAspectFit
                horizontalAlignment: Image.AlignLeft
                verticalAlignment: Image.AlignBottom
                asynchronous: true
                sourceSize.height: 160
            }
            Text {
                visible: card.style === "logo" && logoImg.status !== Image.Ready
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: parent.width * 0.07 }
                text: card.title
                color: "white"
                wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
                font.family: app.titleFamily
                font.pixelSize: Math.round(parent.height * 0.13); font.weight: Font.Bold
            }
            // Box view: the case's plastic catches the light along its hinge.
            Rectangle {
                visible: card.style === "box"
                anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                width: parent.width * 0.12
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: Qt.alpha("white", 0.22) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }

            // The trailer, muted, inside the cover (fades in once it plays).
            Loader {
                anchors.fill: parent
                active: card.trailer !== "" && typeof canPlayVideo !== "undefined" && canPlayVideo
                source: "TvTrailer.qml"
                onLoaded: item.source = Qt.binding(() => card.trailer)
            }

            // A soft light that follows the pointer across the cover while it tilts.
            RectangularShadow {
                visible: card.tilting && img.status === Image.Ready
                width: parent.width * 0.9; height: width
                x: (card.tiltX + 1) / 2 * parent.width - width / 2
                y: (card.tiltY + 1) / 2 * parent.height - height / 2
                radius: width / 2
                blur: width * 0.45
                color: Qt.alpha("white", 0.13)
                Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                Behavior on y { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            }

            // Title strip, on hover or when there is no art to read.
            Rectangle {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                height: Math.min(110, parent.height * 0.45)
                opacity: (card.lit || card.showTitle) && img.status === Image.Ready ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: 120 } }
                gradient: Gradient {
                    GradientStop { position: 0; color: "transparent" }
                    GradientStop { position: 0.55; color: Qt.alpha("black", 0.55) }
                    GradientStop { position: 1; color: Qt.alpha("black", 0.9) }
                }
                Text {
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 12; bottomMargin: 11
                              rightMargin: quick.shown ? quick.width + 20 : 12 }
                    text: card.title
                    color: "white"
                    font.pixelSize: 14
                    font.family: app.titleFamily
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
            }

            // Install / update progress: the cover stays visible; a strip along the bottom
            // says what is happening, with the bar running along the very edge.
            Item {
                visible: card.job !== ""
                anchors.fill: parent
                Rectangle { anchors.fill: parent; color: Qt.alpha("black", 0.22) }
                Rectangle {  // Look > Rich covers: the cover fills up from the bottom as it installs
                    visible: card.caption && card.progress >= 0
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                    height: parent.height * Math.max(0, Math.min(1, card.progress / 100))
                    color: Qt.alpha(card.theme.primary, 0.28)
                    Behavior on height { enabled: !app.still; NumberAnimation { duration: 400 } }
                }
                Rectangle {
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                    height: 64
                    gradient: Gradient {
                        GradientStop { position: 0; color: "transparent" }
                        GradientStop { position: 0.45; color: Qt.alpha("black", 0.7) }
                        GradientStop { position: 1; color: Qt.alpha("black", 0.88) }
                    }
                }
                Row {
                    anchors { left: parent.left; bottom: parent.bottom; leftMargin: 12; bottomMargin: 14 }
                    spacing: 7
                    Icon {
                        anchors.verticalCenter: parent.verticalCenter
                        name: card.job === "uninstall" ? "trash-2" : card.job === "update" ? "arrow-up" : card.job === "dlc" ? "puzzle" : card.job === "move" ? "folder-open" : "download"
                        size: 14; color: "white"
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        color: "white"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        text: card.job === "uninstall" ? qsTr("Removing…") : card.job === "queued" ? qsTr("Queued")
                              : card.job === "paused" ? qsTr("Paused") + (card.progress >= 0 ? " · " + Math.floor(card.progress) + "%" : "")
                              : card.progress < 0 ? qsTr("Starting…")
                              : (card.job === "update" ? qsTr("Updating ") : card.job === "dlc" ? qsTr("DLC ") : card.job === "move" ? qsTr("Moving ") : card.job === "verify" ? qsTr("Checking ") : card.job === "fix" ? qsTr("Fixing ") : qsTr("Installing ")) + Math.floor(card.progress) + "%"
                    }
                }
                Rectangle {
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                    height: 4
                    color: Qt.alpha("white", 0.18)
                    Rectangle {
                        height: parent.height
                        color: theme.primary
                        width: card.progress < 0 ? parent.width * 0.3 : parent.width * Math.max(0.02, card.progress / 100)
                        Behavior on width { NumberAnimation { duration: 300 } }
                        // No percentage yet: a short bar slides back and forth.
                        SequentialAnimation on x {
                            running: card.job !== "" && card.job !== "paused" && card.job !== "queued" && card.progress < 0 && !app.still
                            loops: Animation.Infinite
                            NumberAnimation { from: 0; to: card.width * 0.6; duration: 900; easing.type: Easing.InOutQuad }
                            NumberAnimation { from: card.width * 0.6; to: 0; duration: 900; easing.type: Easing.InOutQuad }
                        }
                    }
                }
            }
        }

        Rectangle { id: mask; anchors.fill: parent; radius: frame.radius; layer.enabled: true; visible: false }

        // Play (or Install) right on the cover while the pointer is on it, as in Heroic and Lutris:
        // one click instead of opening the game or double-clicking.
        Rectangle {
            id: quick
            readonly property bool shown: card.quickAction && (card.hovered || card.ringState !== "") && card.job === "" && !card.picking
            visible: opacity > 0
            opacity: shown ? 1 : 0
            scale: shown ? (quickHover.hovered ? 1.08 : 1) : 0.8
            Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 140 } }
            Behavior on scale { enabled: !app.still; NumberAnimation { duration: 160; easing.type: Easing.OutBack } }
            anchors { right: parent.right; bottom: parent.bottom; margins: 10; bottomMargin: card.achieved > 0 ? 20 : 10 }
            width: Math.max(34, Math.min(44, Math.round(frame.width * 0.2))); height: width; radius: width / 2
            color: quickHover.hovered ? Qt.lighter(card.theme.primary, 1.08) : card.theme.primary
            border.width: 1; border.color: Qt.alpha("white", 0.25)
            Icon {
                anchors.centerIn: parent
                anchors.horizontalCenterOffset: card.installed && card.ringState === "" ? 1 : 0   // a play triangle looks centred a touch right
                name: card.ringState === "done" ? "check" : card.installed ? "play" : "download"
                visible: card.ringState !== "spin"
                size: Math.round(parent.width * 0.42)
                color: card.theme.onPrimary
            }
            // Starting: a ring turning around the button.
            Canvas {
                anchors.fill: parent
                visible: card.ringState === "spin"
                property color c: card.theme.onPrimary
                onVisibleChanged: requestPaint()
                onPaint: {
                    const x = getContext("2d"); x.reset(); x.lineWidth = Math.max(2.5, width * 0.08); x.lineCap = "round"
                    x.strokeStyle = c; x.beginPath(); x.arc(width / 2, height / 2, width * 0.28, 0, Math.PI * 1.4); x.stroke()
                }
                RotationAnimator on rotation { running: card.ringState === "spin"; from: 0; to: 360; duration: 800; loops: Animation.Infinite }
            }
            HoverHandler { id: quickHover; enabled: card.interactive; cursorShape: Qt.PointingHandCursor }
            TapHandler {
                enabled: card.interactive
                gesturePolicy: TapHandler.WithinBounds
                grabPermissions: PointerHandler.CanTakeOverFromAnything
                onTapped: if (card.interactive) {
                    if (card.installed && card.playRing) { card.ringState = "spin"; ringTimer.restart() }
                    card.installed ? card.activated() : card.installRequested()
                }
            }
            ToolTip.visible: quickHover.hovered
            ToolTip.delay: 600
            ToolTip.text: card.installed ? qsTr("Play") : qsTr("Install")
        }

        // Achievements earned: a thin bar along the bottom edge, in gold once all are done.
        Item {
            visible: card.achieved > 0 && card.job === "" && opacity > 0
            opacity: card.lit || card.achieved >= 1 ? 1 : 0.85
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 10 }
            height: 4
            Rectangle { anchors.fill: parent; radius: 2; color: Qt.alpha("black", 0.45) }
            Rectangle {
                height: parent.height; radius: 2
                width: Math.max(height, parent.width * Math.min(1, card.achieved))
                color: card.achieved >= 1 ? "#ffd166" : card.theme.primary
            }
        }

        // Store chip: shown while the card is pointed at or selected, so covers stay clean.
        Rectangle {
            visible: card.showBadge && opacity > 0
            opacity: card.lit ? 1 : 0
            Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 140 } }
            x: 10; y: 10
            height: 22; radius: 11
            width: chip.implicitWidth + 31
            color: Qt.alpha("black", 0.58)
            border.width: 1; border.color: Qt.alpha("white", 0.14)
            StoreIcon { x: 7; anchors.verticalCenter: parent.verticalCenter; size: 12; store: card.store; color: card.storeColor }
            Text { id: chip; x: 23; anchors.verticalCenter: parent.verticalCenter; text: card.storeName + (card.copies > 1 ? "  +" + (card.copies - 1) : ""); color: "white"; font.pixelSize: 11 }
        }

        // New: bought or claimed this week, not played yet. Gives way to the store chip when pointed at.
        Rectangle {
            visible: card.isNew && opacity > 0
            opacity: card.lit ? 0 : 1
            Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 140 } }
            x: 10; y: 10
            height: 20; radius: 10
            width: newText.implicitWidth + 18
            color: card.theme.primary
            Text { id: newText; anchors.centerIn: parent; text: qsTr("NEW"); color: card.theme.onPrimary
                   font.pixelSize: 10; font.weight: Font.Black; font.letterSpacing: 1.0 }
        }

        // New DLC out since you last opened the game's DLC list (gives way like NEW does).
        Rectangle {
            visible: card.dlcNew > 0 && !card.isNew && opacity > 0
            opacity: card.lit ? 0 : 1
            Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 140 } }
            x: 10; y: 10
            height: 20; radius: 10
            width: newDlcRow.implicitWidth + 16
            color: Qt.alpha("black", 0.62)
            border.width: 1.5; border.color: card.dlcColour
            Row {
                id: newDlcRow
                anchors.centerIn: parent
                spacing: 4
                Icon { name: "puzzle"; size: 11; color: card.dlcColour; anchors.verticalCenter: parent.verticalCenter }
                Text { text: qsTr("NEW DLC"); color: card.dlcColour; font.pixelSize: 10; font.weight: Font.Black
                       font.letterSpacing: 1.0; anchors.verticalCenter: parent.verticalCenter }
            }
        }

        // DLC to get, under the store and ProtonDB chips while pointed at.
        Rectangle {
            visible: card.dlcToBuy > 0 && opacity > 0
            opacity: card.lit ? 1 : 0
            Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 140 } }
            x: 10; y: 10 + (card.showBadge ? 28 : 0) + (card.showProtonDb && card.protondb !== "" ? 28 : 0)
            height: 22; radius: 11
            width: dlcChipText.implicitWidth + 31
            color: Qt.alpha("black", 0.58)
            border.width: 1; border.color: Qt.alpha("white", 0.14)
            Icon { x: 7; anchors.verticalCenter: parent.verticalCenter; name: "puzzle"; size: 12; color: card.dlcColour }
            Text { id: dlcChipText; x: 23; anchors.verticalCenter: parent.verticalCenter; text: qsTr("%1 DLC to get").arg(card.dlcToBuy)
                   color: "white"; font.pixelSize: 11 }
        }

        // Not-installed marker.
        Rectangle {
            visible: !card.installed && card.job === "" && opacity > 0
            opacity: card.lit ? 1 : 0   // the dimmed cover says it already; the marker on hover only
            Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 140 } }
            anchors { right: parent.right; top: parent.top; margins: 10 }
            width: 22; height: 22; radius: 11
            color: Qt.alpha("black", 0.58)
            border.width: 1; border.color: Qt.alpha("white", 0.14)
            Text { anchors.centerIn: parent; text: "↓"; color: "white"; font.pixelSize: 13; font.bold: true }
        }

        // ProtonDB rating, under the store chip (the bottom is used by the title and progress).
        Rectangle {
            visible: card.showProtonDb && card.protondb !== "" && opacity > 0
            opacity: card.lit ? 1 : 0
            Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 140 } }
            x: 10; y: card.showBadge ? 38 : 10
            height: 22; radius: 11
            width: pdbText.implicitWidth + 31
            color: Qt.alpha("black", 0.58)
            border.width: 1; border.color: Qt.alpha("white", 0.14)
            StoreIcon { x: 7; anchors.verticalCenter: parent.verticalCenter; size: 12; store: "protondb"; color: ProtonDB.color(card.protondb) }
            Text { id: pdbText; x: 23; anchors.verticalCenter: parent.verticalCenter; text: ProtonDB.label(card.protondb); color: "white"; font.pixelSize: 11 }
        }

        // Favourite marker, top right (moves left of the update marker when both show).
        Rectangle {
            visible: card.favourite && opacity > 0
            opacity: card.lit ? 1 : 0
            Behavior on opacity { enabled: !app.still; NumberAnimation { duration: 140 } }
            anchors { right: parent.right; top: parent.top; margins: 10; rightMargin: card.installed && card.update && card.job === "" ? 38 : 10 }
            width: 22; height: 22; radius: 11
            color: Qt.alpha("black", 0.58)
            border.width: 1; border.color: Qt.alpha("white", 0.14)
            Icon { anchors.centerIn: parent; name: "star-filled"; size: 12; color: "#ffd166" }
        }

        // Update-available marker.
        Rectangle {
            visible: card.installed && card.update && card.job === ""
            anchors { right: parent.right; top: parent.top; margins: 10 }
            width: 22; height: 22; radius: 11
            color: card.updateColour
            Text { anchors.centerIn: parent; text: "↑"; color: "white"; font.pixelSize: 13; font.bold: true }
        }

        Rectangle {
            anchors.fill: parent
            radius: frame.radius
            color: "transparent"
            border.width: card.lit ? 2 : 1
            border.color: card.lit ? theme.primary
                          : theme.dark === false ? Qt.alpha("black", 0.10) : Qt.alpha("white", 0.09)
        }
    }

    // Off while a pop-up is open (and just after one closes), so a click meant for the
    // pop-up never reaches the card underneath.
    property bool interactive: true
    property bool quickAction: true   // the Play / Install button on the cover while pointed at
    // Look > Rich covers: the title and how long you played, under the cover.
    Column {
        visible: card.caption
        anchors { left: frame.left; right: frame.right; top: frame.bottom; topMargin: 8 }
        spacing: 2
        Text { width: parent.width; text: card.title; elide: Text.ElideRight; color: card.theme.onSurface
               font.pixelSize: 13; font.weight: Font.DemiBold; font.family: app.titleFamily }
        Text { width: parent.width; text: card.job !== "" ? (card.progress >= 0 ? Math.floor(card.progress) + "%" : qsTr("Starting…"))
                                                           : card.installed ? (card.captionSub || qsTr("Not played yet")) : qsTr("Not installed")
               elide: Text.ElideRight; color: card.job !== "" ? card.theme.primary : card.theme.onSurfaceVariant; font.pixelSize: 11 }
    }
    HoverHandler { id: hover; enabled: card.interactive; cursorShape: Qt.PointingHandCursor }
    TapHandler {
        enabled: card.interactive
        acceptedModifiers: Qt.NoModifier
        onSingleTapped: if (card.interactive && !quickHover.hovered) { if (card.picking) card.pickRequested(false); else card.opened() }
        onDoubleTapped: if (card.interactive && !card.picking && !quickHover.hovered) card.activated()
        onLongPressed: if (card.interactive) card.menuRequested(point.position)
    }
    TapHandler { enabled: card.interactive; acceptedModifiers: Qt.ControlModifier; onTapped: card.pickRequested(false) }
    TapHandler { enabled: card.interactive; acceptedModifiers: Qt.ShiftModifier; onTapped: card.pickRequested(true) }
    // Picked: a ring in the accent colour and a tick in the corner.
    Rectangle {
        visible: card.picked
        anchors.fill: parent; anchors.margins: card.gap / 2 - 2
        radius: card.cornerRadius + 2
        color: Qt.alpha(card.theme.primary, 0.12)
        border.width: 3; border.color: card.theme.primary
        z: 50
        Rectangle {
            x: 10; y: 10; width: 26; height: 26; radius: 13
            color: card.theme.primary
            Icon { anchors.centerIn: parent; name: "check"; size: 16; color: card.theme.onPrimary }
        }
    }
    TapHandler {
        enabled: card.interactive
        acceptedButtons: Qt.RightButton
        onTapped: (eventPoint, button) => card.menuRequested(eventPoint.position)
    }
}
