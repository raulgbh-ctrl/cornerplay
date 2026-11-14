.pragma library
// Art URLs that failed this session, shared by every ArtImage, so a dead link (Steam lists
// some _2x files it does not have) is skipped at once instead of re-fetched for every card.
var dead = ({})
function mark(url) { if (url) dead[String(url)] = true }
function first(list, from) {
    for (var i = from; i < list.length; i++)
        if (!dead[String(list[i])]) return i
    return Math.max(list.length - 1, from)
}
