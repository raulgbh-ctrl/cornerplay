import QtQuick
import QtMultimedia

// The focused game's trailer, muted, behind TV mode's text. Loaded through a Loader only
// where Qt Multimedia exists, so the app still starts without it.
Item {
    id: tr
    property string source: ""
    // Trailers open with ratings boards and publisher logos: a long one starts a few seconds in
    // (6 s, or a tenth of a short one), and only fades in once it is past them.
    property int skipTo: 0
    readonly property bool showing: player.playbackState === MediaPlayer.PlayingState && player.position > tr.skipTo + 400
    opacity: showing ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 700; easing.type: Easing.InOutQuad } }

    AudioOutput { id: silent; muted: true }
    MediaPlayer {
        id: player
        source: tr.source
        loops: MediaPlayer.Infinite
        videoOutput: video
        audioOutput: silent
        onSourceChanged: { tr.skipTo = 0; if (source.toString() !== "") play() }
        onSeekableChanged: tr.skipIntro()
        onDurationChanged: tr.skipIntro()
    }
    function skipIntro() {
        if (tr.skipTo > 0 || !player.seekable || player.duration < 20000) return
        tr.skipTo = Math.min(6000, Math.round(player.duration / 10))
        player.setPosition(tr.skipTo)
        seekCheck.restart()
    }
    // Steam's trailers (HLS) often ignore the jump: the player then plays from the start, hidden,
    // and the cover showed nothing for 6 s. When the jump did not happen, show it as it plays.
    Timer {
        id: seekCheck
        interval: 700
        onTriggered: if (player.position < tr.skipTo - 1500) tr.skipTo = 0
    }
    VideoOutput {
        id: video
        anchors.fill: parent
        fillMode: VideoOutput.PreserveAspectCrop
    }
}
