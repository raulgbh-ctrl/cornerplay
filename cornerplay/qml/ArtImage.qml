import QtQuick
import "deadart.js" as DeadArt

// An Image that works through a list of sources, best first, until one loads.
// URLs that already failed this session (in any ArtImage) are skipped.
Image {
    id: art
    property var sources: []
    property int at: 0
    property string sig: ""
    // A model refresh hands over a new but equal list: only start over when it really changed.
    onSourcesChanged: {
        const s = JSON.stringify(sources || [])
        if (s !== sig) { sig = s; at = DeadArt.first(sources || [], 0) }
    }
    Component.onCompleted: at = DeadArt.first(sources || [], at)
    source: sources && sources.length > at ? sources[at] : ""
    asynchronous: true
    fillMode: Image.PreserveAspectCrop
    onStatusChanged: {
        if (status !== Image.Error) return
        DeadArt.mark(source)
        if (sources && at < sources.length - 1) at = DeadArt.first(sources, at + 1)
    }
}
