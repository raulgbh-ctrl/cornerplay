import QtQuick

// The Cornerplay name: lowercase, one weight, one colour, after the mark. It follows the
// theme (and so the wallpaper) like everything else.
Row {
    id: wm
    property int size: 22                    // roughly the letters' height in pixels
    property bool showIcon: true
    property color ink: app.theme.onSurface
    property color accent: app.theme.primary  // kept for callers; the name itself is one colour now
    spacing: Math.round(size * 0.45)
    BrandMark {
        visible: wm.showIcon
        anchors.verticalCenter: parent.verticalCenter
        size: Math.round(wm.size * 1.5)
    }
    Text {
        anchors.verticalCenter: parent.verticalCenter
        text: "cornerplay"
        color: wm.ink
        font.family: "Nunito"
        font.weight: Font.ExtraBold
        font.pixelSize: Math.round(wm.size * 1.25)
        font.letterSpacing: -wm.size * 0.02
    }
}
