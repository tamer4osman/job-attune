// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// Job Attune desktop shell (Electron main process).
//
// The heavy lifting stays exactly where it already is: the bundled
// standalone app (server.py + attune engine + omnidecide-c kernel +
// CPython runtime). This process spawns that server as a child on a random
// free loopback port, waits for its guarded /api/template to answer, then
// shows the UI in a BrowserWindow. Nothing is fetched remotely and nothing
// runs in the renderer:
//
//   main      lifecycle + local server supervision only
//   renderer  the vanilla web UI (contextIsolation + sandbox, no Node)
//
// Layouts resolved here:
//   packaged  <resources>/bundle/app/server.py + <resources>/bundle/runtime/python
//             - the Electron workflow unpacks job-attune-standalone-<platform>
//               into electron/standalone-bundle and electron-builder copies
//               it via extraResources (see electron-builder.yml)
//   dev       `npm start` against a repo checkout (needs system python3 and
//             a compiled kernel, or an unpacked standalone archive dropped
//             into electron/standalone-bundle - see electron/README.md)

const { app, BrowserWindow, dialog, Menu, shell } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");

const IS_MAC = process.platform === "darwin";
const IS_WIN = process.platform === "win32";
const KERNEL_LIB = IS_WIN ? "omnidecide.dll"
  : IS_MAC ? "libomnidecide.dylib"
  : "libomnidecide.so";
const APP_TITLE = "Job Attune";

let win = null;
let server = null;
let shuttingDown = false;

// ---------------------------------------------------------------- bundle

/** Locate server.py + the CPython runtime for both supported layouts. */
function resolveBundle() {
  const roots = [];
  if (app.isPackaged) roots.push(path.join(process.resourcesPath, "bundle"));
  roots.push(path.join(__dirname, "standalone-bundle"), path.join(__dirname, ".."));

  for (const root of roots) {
    // repo checkout: server.py at the top; standalone bundle: under app/
    const appDir = fs.existsSync(path.join(root, "server.py"))
      ? root
      : (fs.existsSync(path.join(root, "app", "server.py"))
        ? path.join(root, "app") : null);
    if (!appDir) continue;

    const runtimeDir = IS_WIN
      ? path.join(root, "runtime", "python")
      : path.join(root, "runtime", "python", "bin");
    const python = IS_WIN
      ? path.join(runtimeDir, "python.exe")
      : path.join(runtimeDir, "python3");

    return {
      app: appDir,
      python: fs.existsSync(python) ? python : (IS_WIN ? "python" : "python3"),
      bundledRuntime: fs.existsSync(python),
      runtimeDir,
      kernel: path.join(appDir, "vendor", "omnidecide-c", "build", KERNEL_LIB),
    };
  }
  return null;
}

/** Grab an ephemeral loopback port (tiny TOCTOU, same trick as smoke_test.py). */
function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
  });
}

// ---------------------------------------------------------------- server

async function startServer() {
  const bundle = resolveBundle();
  if (!bundle) {
    dialog.showErrorBox(APP_TITLE,
      "The bundled application files are missing (app/server.py not found).\n"
      + "The installation looks incomplete - please reinstall the app.");
    app.exit(1);
    return null;
  }
  if (!fs.existsSync(bundle.kernel)) {
    dialog.showErrorBox(APP_TITLE,
      `The compiled omnidecide-c kernel is missing:\n${bundle.kernel}\n`
      + "The installation looks incomplete - please reinstall the app.");
    app.exit(1);
    return null;
  }

  const port = await freePort();
  const env = {
    ...process.env,
    ATTUNE_ROOT: bundle.app,
    ATTUNE_HOST: "127.0.0.1",
    ATTUNE_PORT: String(port),
    OMNIDECIDE_C_LIB: bundle.kernel,
    PYTHONUNBUFFERED: "1",
  };
  // The web app spawns the engine and the PDF reporter as Python children,
  // so the bundled Python must lead the PATH (mirrors start.sh/start.bat).
  if (bundle.bundledRuntime) {
    env.PATH = IS_WIN
      ? `${bundle.runtimeDir};${env.PATH || ""}`
      : `${bundle.runtimeDir}:${env.PATH || ""}`;
  }

  server = spawn(bundle.python, ["server.py"], {
    cwd: bundle.app,
    env,
    windowsHide: true,
    stdio: ["ignore", "ignore", "pipe"],
  });
  server.stderr.on("data", (chunk) => process.stdout.write(`[server] ${chunk}`));
  server.on("exit", (code) => {
    server = null;
    if (!shuttingDown) {
      dialog.showErrorBox(APP_TITLE,
        `The local Job Attune server exited unexpectedly (code ${code}).\n`
        + "Please restart the application.");
      app.quit();
    }
  });
  return port;
}

/** Poll the guarded API until the engine stack is ready to serve. */
async function waitHealthy(port, timeoutMs = 45000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/template`, {
        headers: { "X-Attune-Client": "job-attune-desktop" },
      });
      if (res.ok) return true;
    } catch (err) { /* not up yet */ }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  return false;
}

/** Kill the server; on Windows take the whole process tree with it. */
function stopServer() {
  shuttingDown = true;
  const child = server;
  server = null;
  if (!child || child.exitCode !== null || child.signalCode) return;
  if (IS_WIN) {
    spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"],
      { windowsHide: true, stdio: "ignore" });
  } else {
    child.kill("SIGTERM");
    const killTimer = setTimeout(() => { try { child.kill("SIGKILL"); } catch {} }, 3000);
    child.once("exit", () => clearTimeout(killTimer));
  }
}

// ---------------------------------------------------------------- window

function createWindow(port) {
  win = new BrowserWindow({
    width: 1280,
    height: 880,
    minWidth: 980,
    minHeight: 640,
    title: APP_TITLE,
    backgroundColor: "#fefae7",
    show: false,
    autoHideMenuBar: !IS_MAC,
    icon: IS_MAC ? undefined : path.join(__dirname, "build", "icon.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false,
    },
  });
  win.once("ready-to-show", () => win.show());
  win.on("closed", () => { win = null; });

  // No popups; genuine external links go to the system browser instead.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url) && !url.startsWith("http://127.0.0.1")) {
      shell.openExternal(url);
    }
    return { action: "deny" };
  });
  // The app needs none of these - deny everything by default.
  win.webContents.session.setPermissionRequestHandler(
    (_wc, _permission, callback) => callback(false),
  );

  win.loadURL(`http://127.0.0.1:${port}/`);
}

// ---------------------------------------------------------------- lifecycle

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });

  app.whenReady().then(async () => {
    if (!IS_MAC) Menu.setApplicationMenu(null); // macOS keeps the default edit menu
    const port = await startServer();
    if (port === null) return;
    if (!(await waitHealthy(port))) {
      dialog.showErrorBox(APP_TITLE,
        "The local server did not become healthy in time.\n"
        + "Please restart the application.");
      app.quit();
      return;
    }
    createWindow(port);
    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0 && !shuttingDown) {
        createWindow(port);
      }
    });
  });

  // Quit on window close on every OS: this is a local utility, and keeping
  // the loopback server alive with no window would surprise users.
  app.on("window-all-closed", () => {
    stopServer();
    app.quit();
  });
  app.on("before-quit", () => stopServer());
}
