// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// Job Attune desktop preload - the only bridge into the sandboxed renderer.
// Exposes just enough for the web UI to detect it is running as a desktop
// app (e.g. to adjust the "100% local processing" messaging); it grants no
// Node, no IPC surface beyond these static values.

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("attuneDesktop", {
  isDesktop: true,
  platform: process.platform,
});
