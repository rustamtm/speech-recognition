# Whisper Live Transcriber

Real-time speech recognition web app powered by [faster-whisper](https://github.com/guillaumekln/faster-whisper).

## Quick Start

1. **Run both client and server together**

   ```bash
   npm run dev
   ```

   This starts the WebSocket ASR server and serves the client concurrently using helper scripts in `app/`.

2. **Or start each component manually**

   - **Start the ASR server**
     ```bash
     cd app/server
     bash run.sh
     ```
     This creates a virtualenv, installs dependencies and launches the WebSocket server on `ws://127.0.0.1:8765`.

   - **Serve the client**
     - Option A: open `app/client/index.html` in a browser directly.
     - Option B: use the lightweight static host:
       ```bash
       cd app
       npx serve
       ```
       or run `npm run serve` if you installed dependencies.

3. Open the page in your browser, grant microphone permission, choose a language and press **Start**.

## Repository Layout

```
app/
  client/      # Browser front-end
  server/      # Python WebSocket ASR server
package.json   # Optional helper scripts
```

## Notes

- The app streams 16 kHz mono audio via WebSocket to the Python server which uses faster‑whisper to decode frames incrementally.
- Partial and final transcripts are rendered live in the full‑height textarea.
- Use the buttons or keyboard shortcuts (Ctrl+Space, Ctrl+K, Ctrl+C, Ctrl+S) to control recording and utilities.
