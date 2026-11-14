// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
// PWA: register the offline-shell service worker (scope /).
// Registration failure is silently ignored on purpose: contexts where it
// cannot work (file://, embedded webviews) must keep working unchanged.
// External file (not inline) so the Content-Security-Policy script-src 'self'
// stays satisfied without 'unsafe-inline'.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/sw.js').catch(function () {});
  });
}