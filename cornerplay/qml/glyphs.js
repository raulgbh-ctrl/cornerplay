.pragma library
// Button prompts for every kind of controller: what each button is called and how it looks,
// by its position (SDL's names: a = bottom, b = right, x = left, y = top). pad.style picks one;
// gamepad.py tells them apart (SDL's controller type, and Valve's vendor id for the Deck).

const XBOX_COLOURS = { a: "#6dc04b", b: "#e5574d", x: "#3d8fea", y: "#f2c230" }
const MONO = "#ececf0"

// face: letters (with colours, or one ink) or PlayStation's symbols;
// names: the other buttons as printed on the pad.
const STYLES = {
    xbox: { name: "Xbox", face: { a: "A", b: "B", x: "X", y: "Y" }, colours: XBOX_COLOURS,
            names: { lb: "LB", rb: "RB", lt: "LT", rt: "RT", back: "⧉", start: "☰", guide: "XBOX", share: "SHARE", ls: "LS", rs: "RS" } },
    xbox360: { name: "Xbox 360", face: { a: "A", b: "B", x: "X", y: "Y" }, colours: XBOX_COLOURS,
               names: { lb: "LB", rb: "RB", lt: "LT", rt: "RT", back: "BACK", start: "START", guide: "GUIDE", share: "", ls: "LS", rs: "RS" } },
    ps5: { name: "PlayStation 5", ps: true, colours: { a: MONO, b: MONO, x: MONO, y: MONO },
           names: { lb: "L1", rb: "R1", lt: "L2", rt: "R2", back: "CREATE", start: "OPTIONS", guide: "PS", share: "MIC", ls: "L3", rs: "R3" } },
    ps4: { name: "PlayStation 4", ps: true, colours: { a: "#7fa9ec", b: "#ec6f6f", x: "#d58ad8", y: "#41c7a0" },
           names: { lb: "L1", rb: "R1", lt: "L2", rt: "R2", back: "SHARE", start: "OPTIONS", guide: "PS", share: "", ls: "L3", rs: "R3" } },
    ps3: { name: "PlayStation 3", ps: true, colours: { a: "#7fa9ec", b: "#ec6f6f", x: "#d58ad8", y: "#41c7a0" },
           names: { lb: "L1", rb: "R1", lt: "L2", rt: "R2", back: "SELECT", start: "START", guide: "PS", share: "", ls: "L3", rs: "R3" } },
    // Nintendo prints A on the right and B at the bottom: by position, bottom is B.
    switch: { name: "Nintendo Switch", face: { a: "B", b: "A", x: "Y", y: "X" }, ink: MONO,
              names: { lb: "L", rb: "R", lt: "ZL", rt: "ZR", back: "−", start: "+", guide: "HOME", share: "◉", ls: "LS", rs: "RS" } },
    deck: { name: "Steam Deck", face: { a: "A", b: "B", x: "X", y: "Y" }, ink: "#d8dbe2",
            names: { lb: "L1", rb: "R1", lt: "L2", rt: "R2", back: "⧉", start: "☰", guide: "STEAM", share: "···", ls: "L3", rs: "R3" } },
    steam: { name: "Steam Controller", face: { a: "A", b: "B", x: "X", y: "Y" }, colours: XBOX_COLOURS,
             names: { lb: "LB", rb: "RB", lt: "LT", rt: "RT", back: "◀", start: "▶", guide: "STEAM", share: "", ls: "LS", rs: "RS" } },
    stadia: { name: "Stadia", face: { a: "A", b: "B", x: "X", y: "Y" }, ink: MONO,
              names: { lb: "L1", rb: "R1", lt: "L2", rt: "R2", back: "⋯", start: "☰", guide: "STADIA", share: "◉", ls: "L3", rs: "R3" } },
    luna: { name: "Amazon Luna", face: { a: "A", b: "B", x: "X", y: "Y" }, ink: MONO,
            names: { lb: "LB", rb: "RB", lt: "LT", rt: "RT", back: "⧉", start: "☰", guide: "LUNA", share: "MIC", ls: "LS", rs: "RS" } },
    shield: { name: "NVIDIA Shield", face: { a: "A", b: "B", x: "X", y: "Y" }, ink: MONO,
              names: { lb: "LB", rb: "RB", lt: "LT", rt: "RT", back: "◁", start: "▷", guide: "NVIDIA", share: "", ls: "LS", rs: "RS" } },
    generic: { name: "Generic", face: { a: "1", b: "2", x: "3", y: "4" }, ink: MONO,
               names: { lb: "L1", rb: "R1", lt: "L2", rt: "R2", back: "SELECT", start: "START", guide: "HOME", share: "", ls: "L3", rs: "R3" } }
}
// Older settings and the three families the rest of Cornerplay asks about.
const ALIASES = { playstation: "ps5", nintendo: "switch", joycon: "switch" }

function of(style) { return STYLES[ALIASES[style] || style] || STYLES.xbox }
function isPlayStation(style) { return !!of(style).ps }
function isNintendo(style) { return of(style) === STYLES.switch }

// What a button says (shoulders, Start...) or, for a face button, its letter.
function label(style, button) {
    const g = of(style)
    if (g.face && g.face[button] !== undefined) return g.face[button]
    return g.names[button] !== undefined ? g.names[button] : button.toUpperCase()
}
function colour(style, button) {
    const g = of(style)
    return (g.colours && g.colours[button]) || g.ink || MONO
}

// The choices for Settings > Controllers > Button prompts.
function choices() {
    return ["xbox", "xbox360", "ps5", "ps4", "ps3", "switch", "deck", "steam", "stadia", "luna", "shield", "generic"]
        .map(k => ({ v: k, t: STYLES[k].name }))
}
