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
    // Only /api and the file downloads go to the backend.
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
    // The frontend is the whole UI. The backend is an API -- with one exception,
    // below.
    //
    // `/reader` is the exception, and it is temporary.
    //
    // The React reader (`src/pages/ReaderPage.tsx`) is a port of
    // `app/reader/page.py`, and the Python original is better: it has the
    // paragraph pairing, the glossary panel and the settings that the port does
    // not have yet. Rather than hold the route hostage to an incomplete port,
    // the path is proxied back to the Python page so the reader works today, and
    // `tests/routing.test.ts` holds the exception open rather than treating it
    // as the new normal.
    //
    // A proxy rule matches the prefix, so `/reader` also covers
    // `/reader/<id>` and `/reader/<id>/asset/<path>` -- which is required, since
    // the images in that page are served by the backend under the same prefix.
    // Narrowing it to the exact paths would break the images.
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/downloads': { target: BACKEND, changeOrigin: true },
      // TEMPORARY: the Python reader, until the React one is finished. See the
      // note above, and `src/pages/ReaderPage.tsx` for what is missing.
      '/reader': { target: BACKEND, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
