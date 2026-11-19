import QtQuick

// The bottom layer of every TV overlay (a page, a picker, the keyboard): it takes every click,
// tap, hover and scroll that the overlay's own buttons do not, so nothing reaches the covers on
// Home underneath (a double click on an empty part of a game's page used to start the game
// behind it). A TapHandler alone does not do this: it lets the press go on to what is below.
MouseArea {
    anchors.fill: parent
    z: -1
    hoverEnabled: true
    acceptedButtons: Qt.AllButtons
    onWheel: wheel => wheel.accepted = true
}
