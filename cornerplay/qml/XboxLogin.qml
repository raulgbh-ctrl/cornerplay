import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtWebEngine

// Xbox sign-in on Linux (cornerplay/xboxauth.py): the Xbox backend signs in to Microsoft itself and
// asks for each of Microsoft's pages to be shown; this window shows them. What a page hands to
// window.external.notify (as Windows' own sign-in host would get it) goes back to the backend.
// Only Microsoft's sign-in hosts load here; nothing is kept on disk.
Window {
    id: w
    property var theme: app.theme
    property int session: 0     // the page the backend has open now (0: none)
    property bool running: false
    readonly property string tag: "CORNERPLAY_XBOX_AUTH:"

    width: 560
    height: 760
    minimumWidth: 420
    minimumHeight: 560
    title: qsTr("Sign in to Xbox")
    color: theme.background
    modality: Qt.ApplicationModal

    function begin() {
        status.text = ""
        if (!running) {
            running = true
            app.xboxLoginStart(profile)
        }
        status.text = qsTr("Starting the Xbox sign-in…")
        show(); raise(); requestActivate()
    }

    Connections {
        target: app
        function onXboxAuthOpen(session, url) {
            w.session = session
            status.text = ""
            view.url = url
            w.show(); w.raise(); w.requestActivate()
        }
        function onXboxAuthContext(session, script) {
            if (session === w.session && app.xboxAuthTrusted(view.url.toString()))
                view.runJavaScript(script)
        }
        function onXboxAuthClose(session) {
            if (session !== w.session) return
            w.session = 0
            status.text = qsTr("Signing in…")
        }
        function onLoginDone(store, ok, message) {
            if (store !== "xbox") return
            w.running = false
            w.session = 0
            view.url = "about:blank"
            w.hide()
        }
    }

    onClosing: close => {
        if (w.running) app.xboxAuthCancel(w.session)  // the backend stops; loginDone hides this
    }

    WebEngineProfile {
        id: profile
        offTheRecord: true  // in memory only, gone with the window
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: hint.implicitHeight + 20
            color: w.theme.surfaceContainer
            Text {
                id: hint
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                text: qsTr("Sign in with your Microsoft account. The window closes by itself when you're signed in.")
                color: w.theme.onSurfaceVariant
                font.pixelSize: 12
                wrapMode: Text.WordWrap
            }
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 3
            color: "transparent"
            Rectangle {
                height: parent.height
                color: w.theme.primary
                width: parent.width * view.loadProgress / 100
                visible: view.loading
            }
        }
        Text {
            id: status
            Layout.fillWidth: true
            Layout.margins: text ? 10 : 0
            visible: text !== ""
            wrapMode: Text.WordWrap
            color: w.theme.onSurfaceVariant
            font.pixelSize: 12
        }
        WebEngineView {
            id: view
            Layout.fillWidth: true
            Layout.fillHeight: true
            profile: profile

            Component.onCompleted: {
                // Before the page's own scripts: external.notify, as in Windows' sign-in host.
                const s = WebEngine.script()
                s.name = "cornerplay-xbox-notify"
                s.injectionPoint = WebEngineScript.DocumentCreation
                s.worldId = WebEngineScript.MainWorld
                s.runsOnSubFrames = false
                s.sourceCode = "try { Object.defineProperty(globalThis.external, 'notify', { value: p => { "
                             + "if (typeof p === 'string' && p.length <= 65536) console.info('" + w.tag + "' + p) }, "
                             + "configurable: false, writable: false }) } catch (e) {}"
                userScripts.insert(s)
            }

            onJavaScriptConsoleMessage: (level, message, line, source) => {
                if (w.session && message.indexOf(w.tag) === 0 && app.xboxAuthTrusted(view.url.toString())
                        && app.xboxAuthTrusted(source.toString()))
                    app.xboxAuthNotify(w.session, message.slice(w.tag.length))
            }
            onNavigationRequested: request => {
                const u = request.url.toString()
                if (request.isMainFrame && u !== "about:blank" && !app.xboxAuthTrusted(u)) {
                    request.reject()
                    status.text = qsTr("That page is not part of Microsoft's sign-in, so it was not opened.")
                }
            }
            onLoadingChanged: info => {
                if (info.status !== WebEngineView.LoadSucceededStatus || !w.session) return
                const u = info.url.toString()
                // The last page of a password sign-in hands its result over as ServerData.
                if (u.indexOf("https://login.live.com/ppsecure/post.srf") === 0) {
                    const s = w.session
                    view.runJavaScript("JSON.stringify(globalThis.ServerData ?? null)", payload => {
                        if (s === w.session && typeof payload === "string" && payload !== "null" && payload.length <= 65536)
                            app.xboxAuthNotify(s, payload)
                    })
                }
            }
            onNewWindowRequested: request => app.openUrl(request.requestedUrl)
            onRenderProcessTerminated: (status, code) => { if (w.running) app.xboxAuthCancel(w.session) }
        }
    }
}
