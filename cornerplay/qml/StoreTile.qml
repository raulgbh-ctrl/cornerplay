import QtQuick

// A store's logo in white on a soft rounded tile of the store's colour; or, with glyph and tint,
// any UI icon on a tile of that colour (the Store entry).
Rectangle {
    id: st
    property string store: ""
    property string glyph: ""          // a name from cornerplay/icons/ui, instead of a store logo
    property color tint: "transparent" // the tile's colour, instead of the store's
    property int size: 22
    property bool plain: false          // just the logo in `ink`, no coloured tile (the sidebar)
    property color ink: "white"
    width: size; height: size
    radius: Math.round(size * 0.28)
    color: st.plain ? "transparent" : st.tint.a > 0 ? st.tint : (app.storesInfo.find(s => s.id === st.store) || {}).tile || "#5f646b"
    StoreIcon { visible: st.glyph === ""; anchors.centerIn: parent; size: Math.round(st.size * (st.plain ? 0.78 : 0.62)); store: st.store; color: st.plain ? st.ink : "white" }
    Icon { visible: st.glyph !== ""; anchors.centerIn: parent; name: st.glyph; size: Math.round(st.size * (st.plain ? 0.78 : 0.64)); color: st.plain ? st.ink : "white" }
}
