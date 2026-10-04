# ASL 10-word local camera prototype

This private localhost prototype observes one isolated sign at a time and returns one label from an exact ten-word vocabulary. It is not continuous ASL translation, sentence recognition, or an accessibility service.

The vocabulary and recognition protocol are experimental and have no ten-word accuracy or signer-disjoint validation result. `NO_SIGN` and `UNCLEAR` are explicit outcomes rather than forced word labels.

## Start locally

```bash
export TRIO_SPARK_API_KEY=tf_...
python3 demos/asl-words/server.py --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. Camera permission is requested only after **Start camera** is clicked. The default recognizer calls the public Trio-Spark API. An operator may inject a private adapter with `--recognizer-module /absolute/private/path.py`; that untracked module must export `create_recognizer()` and return an object with `recognize(frames)`. Private endpoints and credentials must remain outside this repository.

For a private HTTPS reverse proxy, keep the Python process bound to loopback and add its exact browser-facing origin, for example `--public-origin https://exact-device-name.example.ts.net`. The server admits only that exact configured `Origin` and `Host`; the proxy URL is runtime configuration and does not belong in Git.

The browser never receives an API key. The Python server owns recognition and exposes only:

- `GET /api/config` → `{"vocabulary":[{"id":"...","display":"..."}, ...]}` with exactly ten entries.
- `POST /api/recognize` with four chronological 512-pixel JPEG frames and strictly increasing nonnegative integer `timestamp_ms` values.
- A response containing `status` (`recognized`, `no_sign`, or `unclear`), `label`, `score`, `score_scope: "conditional_within_bank"`, `route`, `leaf`, `calls`, and `latency_ms`.

The recognizer uses a fixed two-stage bank protocol: route between two five-word banks, `NO_SIGN`, and `UNCLEAR`, then classify within the selected bank. The browser does not compare scores across banks. It displays a recognized word score only as conditional within the routed bank. Each window makes one or two model calls, so this prototype does not promise subsecond latency.

## Runtime boundaries

- Bind only to loopback. Reject unknown `Host` and non-local `Origin` values.
- Keep `TRIO_SPARK_API_KEY` in the server process. Never inject it into HTML or JavaScript.
- Accept a bounded JSON body and exactly four canonical JPEG frames.
- Allow one recognition request at a time. Return a bounded busy response instead of queueing.
- Do not follow redirects with an authorization header.
- Stop every camera track on Stop, page hide, or mode exit. Late responses are discarded by an epoch guard.

The committed frontend has no synthetic recognizer. Browser fixtures used by tests must label themselves as UI tests and must never be presented as model output.
