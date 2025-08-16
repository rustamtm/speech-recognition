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
     # macOS / Linux
     cd app/server
     python3 run.py
     
     # Windows (PowerShell)
     cd app\server
     python run.py
     ```

     `run.py` creates a virtualenv, installs dependencies and launches the WebSocket server on `ws://127.0.0.1:8765`.
     Set `ENABLE_HEALTH_ENDPOINT=1` to also expose `http://127.0.0.1:8766/health`.

   - **Serve the client**
     - Option A: open `app/client/index.html` in a browser directly.
     - Option B: use the lightweight static host:
       ```bash
       cd app
       npx serve
       ```
       or run `npm run serve` if you installed dependencies.

3. **Run tests**

   ```bash
   cd app
   pytest server/tests
   ```

4. Open the page in your browser, grant microphone permission, choose a language and press **Start**.

## Repository Layout

```
app/
  client/      # Browser front-end
  server/      # Python WebSocket ASR server with minimal logging
package.json   # Optional helper scripts
```

## Architecture

Audio is captured in the browser, converted to 16 kHz mono PCM and streamed over WebSocket
to the Python server. The server transcribes short audio windows using faster‑whisper and
returns partial and final transcripts. Optional health information is served on an HTTP
endpoint when enabled.

## Notes

- The app streams 16 kHz mono audio via WebSocket to the Python server which uses faster‑whisper to decode frames incrementally.
- Partial and final transcripts are rendered live in the full‑height textarea.
- Use the buttons or keyboard shortcuts (Ctrl+Space, Ctrl+K, Ctrl+C, Ctrl+S) to control recording and utilities.
