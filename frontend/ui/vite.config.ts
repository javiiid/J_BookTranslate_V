import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { defineConfig } from 'vite'

// The Python backend is a local HTTP API on 8765. In dev we proxy to it so the
// browser sees a single origin and no CORS handling is needed anywhere.
//
// The variable was renamed with the product (JBT_API -> KALIMA_API) but the old
// name still works: an existing shell profile or .env would otherwise break with
// no error, just a proxy pointed at the wrong port.
const BACKEND =
  process.env.KALIMA_API ?? process.env.JBT_API ?? 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    host: '0.0.0.0',  // Listen on all interfaces (IPv4 + IPv6)
    port: 5173,
    // Only /api, the file downloads and the cover images go to the backend.
    //
    // The six bare-path rules this replaces -- /reader, /library, /account,
    // /workspace, /landing, /welcome -- were all paths the React router also
    // claims, and the Python backend answers four of them with a server-rendered
    // HTML page. Vite's proxy runs before its own SPA fallback, so whichever
    // matched first won: `/landing` was 65KB of Python HTML with no React on
    // it, and `/library`, `/account` and `/workspace` were proxied to a route
    // that returns HTML where the client expected a module -- which is why
    // navigating between pages kept landing somewhere that was not the app.
    //
    // The frontend is the whole UI. The backend is an API -- with one narrow
    // exception, below.
    //
    // `/reader` is proxied for chapter images only, not for the page.
    //
    // The React reader (`src/pages/ReaderPage.tsx`) finished its port
    // (settings, glossary panel, paragraph pairing, columns mode), so the
    // route belongs to the client router and `/reader/:id` renders the SPA
    // shell. But the chapter HTML the API returns carries image URLs shaped
    // `/reader/<id>/asset/<path>`, and those bytes only exist on the backend.
    // In production this needs nothing (one origin serves both); in dev the
    // rule below keeps the images working: asset URLs proxy through, every
    // other `/reader/*` URL answers the SPA shell so the client router --
    // not the proxy -- owns the page. `tests/routing.test.ts` pins both
    // halves: the assets must reach the backend, and the page must not.
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/downloads': { target: BACKEND, changeOrigin: true },
      // Library cover images. `GET /covers/<id>.<ext>` is served from
      // `data/covers` by the backend (see `app/library/covers.py`); the React
      // tiles reference it with the relative `cover_path` the API returns, so
      // in dev the prefix has to reach the backend or Vite answers with the
      // SPA's HTML and the image breaks.
      '/covers': { target: BACKEND, changeOrigin: true },
      // Chapter images only -- see the note above. `bypass` returning a path
      // serves that file instead of proxying; returning `undefined` lets the
      // request proxy through to the backend.
      '/reader': {
        target: BACKEND,
        changeOrigin: true,
        bypass: (req) => (/\/asset\//.test(req.url ?? '') ? undefined : '/index.html'),
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
