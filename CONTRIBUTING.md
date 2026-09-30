# Contributing to Trio-Spark

The model is currently served through the hosted Trio-Spark API. This public repository accepts API clients, integrations, evaluation tools, bug fixes, and demos.

## Demo contributions

Create a directory at `demos/<demo-name>/` containing:

- `README.md` with the task, environment, prerequisites, and exact run command.
- Source code or a small patch against a pinned public upstream revision.
- `evidence.json` with the measured run outcome.
- Third-party license and attribution information when applicable.

Visual demos should also include:

- An H.264 MP4 with a 16:9 frame and `faststart` enabled.
- A 16:9 PNG poster.
- Labels that distinguish model decisions from deterministic control or safety logic.
- A note when playback speed or API waiting time has been changed for presentation.

## Evidence checklist

Record enough information to understand what happened without publishing credentials or private data:

```json
{
  "demo": "example-name",
  "production_api": true,
  "duration_seconds": 12.3,
  "successful_calls": 8,
  "api_errors": 0,
  "outcome": "completed"
}
```

Add environment-specific checks such as collisions, task completion, browser assertions, forbidden contacts, or score. Do not describe a single run as a general benchmark or success rate.

## Pull request checklist

- The demo calls the Trio-Spark API for the decisions attributed to the model.
- No API key, credential, account data, private URL, or personal information is committed.
- Setup instructions work from a clean checkout.
- Third-party work is pinned and attributed.
- Claims match the included evidence.
- The video is a real recorded run. Presentation overlays and timing changes are disclosed.
- Large generated files are limited to the final shareable assets.

By contributing, you agree that your MachineFi-authored contribution can be distributed under this repository's Apache-2.0 license. Third-party components retain their original licenses.
