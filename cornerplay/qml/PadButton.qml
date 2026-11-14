import QtQuick
import "glyphs.js" as Glyphs

// One controller button, drawn the way the connected pad labels it (glyphs.js has every kind:
// Xbox and Xbox 360, PlayStation 3 / 4 / 5, Switch, Steam Deck, Steam Controller, Stadia, Luna,
// Shield, generic).
// button: the position SDL reports ("a" bottom, "b" right, "x" left, "y" top, "lb", "rb", "lt",
// "rt", "back", "start", "guide", "share", "ls", "rs"); style: pad.style.
Item {
    id: pb
    property string button: "a"
    property string style: "xbox"
    property int size: 26
    readonly property bool face: ["a", "b", "x", "y"].indexOf(button) !== -1
    readonly property bool shoulder: !face
    readonly property bool ps: face && Glyphs.isPlayStation(style)
    readonly property string text: Glyphs.label(style, button)
    readonly property color ink: face ? Glyphs.colour(style, button) : "#ececf0"
    // Words (OPTIONS, STEAM) get smaller type than symbols and short names.
    readonly property bool wordy: !face && text.length > 3
    readonly property bool symbol: !face && text.length === 1 && !/[A-Za-z0-9+]/.test(text)
    implicitWidth: shoulder ? Math.max(size, label.implicitWidth + size * 0.7) : size
    implicitHeight: size
    width: implicitWidth
    height: implicitHeight

    // PlayStation face symbols as SVG (cross, circle, square, triangle).
    function psSvg(b, c) {
        const s = 'fill="none" stroke="' + c + '" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"'
        const shape = b === "a" ? '<path d="M8 8 L16 16 M16 8 L8 16" ' + s + '/>'
                    : b === "b" ? '<circle cx="12" cy="12" r="5" ' + s + '/>'
                    : b === "x" ? '<rect x="7.5" y="7.5" width="9" height="9" ' + s + '/>'
                    : '<path d="M12 6.8 L17.2 15.8 L6.8 15.8 Z" ' + s + '/>'
        return "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">' + shape + '</svg>')
    }

    Rectangle {
        anchors.fill: parent
        radius: pb.shoulder ? height * 0.32 : width / 2
        color: "#26262b"
        border.width: 1
        border.color: Qt.alpha("white", 0.18)
    }
    Text {
        id: label
        visible: !pb.ps
        anchors.centerIn: parent
        font.pixelSize: Math.round(pb.size * (pb.face ? 0.56 : pb.wordy ? 0.34 : pb.symbol ? 0.62 : 0.46))
        font.weight: Font.Bold
        font.letterSpacing: pb.wordy ? 0.4 : 0
        color: pb.ink
        text: pb.text
    }
    Image {
        visible: pb.ps
        anchors.fill: parent
        source: visible ? pb.psSvg(pb.button, pb.ink) : ""
        sourceSize: Qt.size(Math.ceil(pb.size * Math.max(2, Screen.devicePixelRatio)), Math.ceil(pb.size * Math.max(2, Screen.devicePixelRatio)))
    }
}
