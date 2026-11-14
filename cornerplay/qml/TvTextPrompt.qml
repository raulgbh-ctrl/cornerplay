import QtQuick
import QtQuick.Effects
import QtQuick.Layouts

// Typing from the sofa (a Wi-Fi password): an on-screen keyboard for the controller, with
// capitals and symbols; a real keyboard just types. A types a key, X deletes, Y switches
// capitals, LB / RB symbols, View shows the password, Done finishes, B deletes (or closes when empty).
Item {
    id: tp
    required property var theme
    required property var tint
    property string title: ""
    property string hint: ""
    property bool secret: true
    property string text: ""
    property bool reveal: false
    property bool caps: false
    property bool symbols: false
    signal accepted(string text)
    signal closed()
    visible: false
    z: 120

    function ask(t, h, isSecret) {
        title = t; hint = h || ""; secret = isSecret !== false
        text = ""; reveal = false; caps = false; symbols = false
        board.row = 1; board.col = 0
        visible = true
        board.forceActiveFocus()
        app.uiSound("select")
    }
    function close() { visible = false; closed() }
    function finish() { if (!text) return; app.uiSound("select"); visible = false; accepted(text) }

    Rectangle { anchors.fill: parent; color: Qt.alpha("black", 0.62)
                MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onClicked: tp.close(); onWheel: w => w.accepted = true } }

    Rectangle {
        id: box
        anchors.centerIn: parent
        width: Math.min(parent.width - 64, 940)
        height: col.implicitHeight + 48
        radius: 30
        color: Qt.alpha(tp.theme.surfaceContainer, 0.97)
        border.width: 1; border.color: Qt.alpha("white", 0.1)
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons }
        RectangularShadow {
            z: -1
            anchors.fill: parent
            visible: !app.light && GraphicsInfo.api !== GraphicsInfo.Software
            radius: parent.radius; blur: 60; offset.y: 20
            color: Qt.alpha("black", 0.55)
        }
        ColumnLayout {
            id: col
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 24 }
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Icon { name: tp.secret ? "lock" : "keyboard"; size: 24; color: tp.tint.primary }
                Text { Layout.fillWidth: true; text: tp.title; color: tp.theme.onSurface; font.pixelSize: 24; font.weight: Font.DemiBold; elide: Text.ElideRight }
            }
            Text { visible: tp.hint !== ""; Layout.fillWidth: true; text: tp.hint; color: tp.theme.onSurfaceVariant; font.pixelSize: 16; wrapMode: Text.WordWrap }
            Rectangle {
                Layout.fillWidth: true
                height: 58; radius: 29
                color: tp.theme.surfaceContainerHighest
                Text {
                    id: field
                    anchors { left: parent.left; leftMargin: 24; right: eye.left; rightMargin: 12; verticalCenter: parent.verticalCenter }
                    text: tp.text === "" ? (tp.secret ? qsTr("Password") : "") : tp.secret && !tp.reveal ? "•".repeat(tp.text.length) : tp.text
                    color: tp.text === "" ? tp.theme.onSurfaceVariant : tp.theme.onSurface
                    font.pixelSize: 24
                    font.letterSpacing: tp.secret && !tp.reveal && tp.text !== "" ? 3 : 0
                    elide: Text.ElideLeft
                }
                Rectangle {
                    x: field.x + Math.min(field.contentWidth, field.width) + 3
                    visible: tp.text !== "" && blink.on
                    anchors.verticalCenter: parent.verticalCenter
                    width: 2; height: 28; radius: 1
                    color: tp.tint.primary
                    Timer { id: blink; property bool on: true; interval: 530; repeat: true; running: tp.visible; onTriggered: on = !on }
                }
                Row {
                    id: eye
                    visible: tp.secret
                    anchors { right: parent.right; rightMargin: 20; verticalCenter: parent.verticalCenter }
                    spacing: 8
                    PadButton { visible: pad.connected; anchors.verticalCenter: parent.verticalCenter; button: "back"; style: pad.style; size: 24 }
                    Icon { anchors.verticalCenter: parent.verticalCenter; name: tp.reveal ? "eye-off" : "eye"; size: 22; color: tp.theme.onSurfaceVariant }
                    TapHandler { onTapped: tp.reveal = !tp.reveal }
                }
            }

            // The board: [key, width in tenths]. Up / down go to the nearest key in the next row.
            Item {
                id: board
                Layout.fillWidth: true
                Layout.preferredHeight: rows.length * rowH
                readonly property int rowH: 60
                readonly property real unit: width / 10
                readonly property var letters: [
                    "1234567890".split("").map(k => [k, 1]),
                    "qwertyuiop".split("").map(k => [k, 1]),
                    "asdfghjkl".split("").map(k => [k, 1]).concat([["@", 1]]),
                    [["shift", 1.5]].concat("zxcvbnm".split("").map(k => [k, 1])).concat([[".", 0.5], ["del", 1]]),
                    [["sym", 2], ["space", 4], ["-", 1], ["_", 1], ["done", 2]]
                ]
                readonly property var syms: [
                    "1234567890".split("").map(k => [k, 1]),
                    "!@#$%^&*()".split("").map(k => [k, 1]),
                    "-_=+[]{}\\|".split("").map(k => [k, 1]),
                    [["shift", 1.5]].concat(";:'\",.<>".split("").map(k => [k, 1])).concat([["/", 0.5], ["del", 1]]),
                    [["sym", 2], ["space", 4], ["?", 1], ["~", 1], ["done", 2]]
                ]
                readonly property var rows: tp.symbols ? syms : letters
                property int row: 1
                property int col: 0
                readonly property var current: (rows[row] || [])[col] || ["", 1]
                function startOf(r, c) { let x = 0; for (let i = 0; i < c; i++) x += rows[r][i][1]; return x }
                function centreOf(r, c) { return startOf(r, c) + rows[r][c][1] / 2 }
                function moveRow(d) {
                    const r = (row + d + rows.length) % rows.length, want = centreOf(row, col)
                    let best = 0, gap = 1e9
                    for (let c = 0; c < rows[r].length; c++) { const g = Math.abs(centreOf(r, c) - want); if (g < gap) { gap = g; best = c } }
                    row = r; col = best; app.uiSound("move")
                }
                function moveCol(d) { col = (col + d + rows[row].length) % rows[row].length; app.uiSound("move") }
                function label(k) {
                    if (k === "shift") return tp.caps ? "⇧ ABC" : "⇧ abc"
                    if (k === "sym") return tp.symbols ? "ABC" : "#+="
                    if (k === "space") return qsTr("space")
                    if (k === "del") return ""
                    if (k === "done") return qsTr("Done")
                    return tp.caps && !tp.symbols ? k.toUpperCase() : k
                }
                function press(k) {
                    app.uiSound("move")
                    if (k === "done") tp.finish()
                    else if (k === "shift") tp.caps = !tp.caps
                    else if (k === "sym") tp.symbols = !tp.symbols
                    else if (k === "del") tp.text = tp.text.slice(0, -1)
                    else if (k === "space") tp.text += " "
                    else tp.text += tp.caps && !tp.symbols ? k.toUpperCase() : k
                }
                Repeater {
                    model: board.rows.length
                    Item {
                        id: keyRow
                        required property int index
                        y: index * board.rowH
                        width: board.width; height: board.rowH
                        Repeater {
                            model: board.rows[keyRow.index]
                            Rectangle {
                                id: key
                                required property var modelData
                                required property int index
                                readonly property string k: modelData[0]
                                readonly property bool lit: board.activeFocus && board.row === keyRow.index && board.col === index
                                readonly property bool special: k.length > 1
                                readonly property bool on: (k === "shift" && tp.caps) || (k === "sym" && tp.symbols)
                                x: board.startOf(keyRow.index, index) * board.unit + 4
                                width: modelData[1] * board.unit - 8
                                height: board.rowH - 10
                                radius: 15
                                z: lit ? 1 : 0
                                scale: lit && !app.light ? 1.08 : 1
                                Behavior on scale { NumberAnimation { duration: 110; easing.type: Easing.OutCubic } }
                                color: lit ? tp.tint.primary : on ? Qt.alpha(tp.tint.primary, 0.35)
                                     : k === "done" ? Qt.alpha(tp.tint.primary, 0.22)
                                     : special ? Qt.alpha(tp.theme.surfaceContainerHighest, 0.95) : Qt.alpha(tp.theme.surfaceContainerHighest, 0.7)
                                RectangularShadow {
                                    z: -1
                                    anchors.fill: parent
                                    visible: key.lit && !app.light && GraphicsInfo.api !== GraphicsInfo.Software
                                    radius: parent.radius; blur: 22
                                    color: Qt.alpha(tp.tint.primary, 0.55)
                                }
                                Row {
                                    anchors.centerIn: parent
                                    spacing: 6
                                    Icon { visible: key.k === "del" || key.k === "done"; anchors.verticalCenter: parent.verticalCenter
                                           name: key.k === "del" ? "arrow-left" : "check"; size: 20
                                           color: key.lit ? tp.tint.onPrimary : tp.theme.onSurface }
                                    Text { anchors.verticalCenter: parent.verticalCenter; text: board.label(key.k)
                                           color: key.lit ? tp.tint.onPrimary : key.special ? tp.theme.onSurfaceVariant : tp.theme.onSurface
                                           font.pixelSize: key.special ? 16 : 21; font.weight: Font.DemiBold }
                                }
                                TapHandler { onTapped: { board.row = keyRow.index; board.col = key.index; board.press(key.k) } }
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
                Keys.onEscapePressed: { if (tp.text !== "") press("del"); else { app.uiSound("back"); tp.close() } }
                Keys.onPressed: event => {
                    const k = event.key
                    if (k === Qt.Key_F2) { press("del"); event.accepted = true }                 // X
                    else if (k === Qt.Key_F3) { tp.caps = !tp.caps; app.uiSound("move"); event.accepted = true }  // Y
                    else if (k === Qt.Key_F4) { tp.reveal = !tp.reveal; event.accepted = true }  // View: show the password
                    else if (k === Qt.Key_PageUp || k === Qt.Key_PageDown) { tp.symbols = !tp.symbols; app.uiSound("move"); event.accepted = true }
                    else if (k === Qt.Key_Backspace) { press("del"); event.accepted = true }
                    else if (event.text && event.text.length === 1 && event.text >= " " && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier))) {
                        tp.text += event.text; app.uiSound("move"); event.accepted = true  // a real keyboard
                    }
                }
            }
            Row {
                Layout.alignment: Qt.AlignHCenter
                spacing: 22
                Repeater {
                    model: pad.connected
                        ? [{ b: ["a"], t: qsTr("Type") }, { b: ["x"], t: qsTr("Delete") }, { b: ["y"], t: qsTr("Capitals") }, { b: ["lb", "rb"], t: qsTr("Symbols") },
                           { b: ["b"], t: qsTr("Back") }]
                        : [{ k: qsTr("Type"), t: qsTr("or use the keys") }, { k: qsTr("Enter"), t: qsTr("Choose") }, { k: qsTr("Esc"), t: qsTr("Back") }]
                    Row {
                        required property var modelData
                        spacing: 8
                        Repeater { model: parent.modelData.b || []; PadButton { required property string modelData; button: modelData; style: pad.style; size: 26 } }
                        Rectangle { visible: !!parent.modelData.k; height: 26; radius: 6; width: kk.implicitWidth + 16
                                    color: Qt.alpha(tp.theme.surfaceContainerHighest, 0.9); border.width: 1; border.color: tp.theme.outlineVariant
                                    Text { id: kk; anchors.centerIn: parent; text: parent.parent.modelData.k || ""; color: tp.theme.onSurface; font.pixelSize: 12; font.weight: Font.DemiBold } }
                        Text { anchors.verticalCenter: parent.verticalCenter; text: parent.modelData.t; color: tp.theme.onSurfaceVariant; font.pixelSize: 15 }
                    }
                }
            }
        }
    }
}
