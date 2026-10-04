# ASL 10-word local camera prototype

This private localhost prototype observes one isolated sign at a time and returns one label from an exact ten-word vocabulary. It is not continuous ASL translation, sentence recognition, or an accessibility service.

The browser never receives an API key. The Python server owns recognition and exposes only:

- `GET /api/config` → `{"vocabulary":[{"id":"...","display":"..."}, ...]}` with exactly ten entries.
- `POST /api/recognize` with four chronological 512-pixel JPEG frames and strictly increasing nonnegative integer `timestamp_ms` values.
- A response containing `status` (`recognized`, `no_sign`, or `unclear`), `label`, `score`, `score_scope: "conditional_within_bank"`, `route`, `leaf`, `calls`, and `latency_ms`.

The recognizer uses a fixed two-stage bank protocol. The browser does not compare scores across banks. It displays a score only as conditional within the routed bank.

## Runtime boundaries

- Bind only to loopback. Reject unknown `Host` and non-local `Origin` values.
- Keep `TRIO_SPARK_API_KEY` in the server process. Never inject it into HTML or JavaScript.
- Accept a bounded JSON body and exactly four canonical JPEG frames.
- Allow one recognition request at a time. Return a bounded busy response instead of queueing.
- Do not follow redirects with an authorization header.
- Stop every camera track on Stop, page hide, or mode exit. Late responses are discarded by an epoch guard.

The committed frontend has no synthetic recognizer. Browser fixtures used by tests must label themselves as UI tests and must never be presented as model output.
