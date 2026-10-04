# Visual decisions with Trio-Spark v1.1

Give Spark a picture or a short sequence of frames, tell it what matters, and
receive a structured decision with probabilities. Use the same account, API key
and wallet as text decisions.

- [Playground](https://platform.machinefi.com/spark)
- [Hand gesture demo](https://platform.machinefi.com/spark?demo=gestures)
- [Full console documentation](https://platform.machinefi.com/spark/docs)

## One model, two kinds of input

Use `model: "trio-spark-v1.1"` with `POST /v1/systemone`.
Without media, Spark evaluates text. With media, Spark evaluates the visual input
alongside your instructions. Invalid media returns an error; it is not silently
ignored. Existing `trio-spark-v1.0` text requests remain supported.

## A complete image request

This example uses only Python's standard library. Keep the API key server-side.
Set `TRIO_SPARK_API_KEY` in your environment, save a JPEG as `scene.jpg`, and run:

```python
import base64
import json
import os
import urllib.request
import uuid
from pathlib import Path

payload = {
    "model": "trio-spark-v1.1",
    "state": "A view of an entrance. Decide only from visible evidence.",
    "images": [{
        "content_type": "image/jpeg",
        "base64": base64.b64encode(Path("scene.jpg").read_bytes()).decode(),
    }],
    "questions": {
        "person_present": {
            "type": "choice",
            "instructions": "Is a person visible in this image?",
            "criteria": {
                "yes": "A person is clearly visible",
                "no": "No person is visible",
                "unclear": "The view is too obscured or unclear to decide",
            },
        }
    },
}
request = urllib.request.Request(
    "https://platform.machinefi.com/v1/systemone",
    data=json.dumps(payload).encode(),
    headers={
        "Authorization": "Bearer " + os.environ["TRIO_SPARK_API_KEY"],
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4()),
    },
    method="POST",
)
# Keep credentials on the intended endpoint even if a proxy redirects.
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

with urllib.request.build_opener(NoRedirect()).open(request, timeout=45) as response:
    result = json.load(response)
print(result["answers"]["person_present"])
print(result["usage"])
```

An answer includes `choice` and a `probabilities` mapping keyed by your supplied
criteria. `usage.input_tokens` reports billed input tokens. Outputs are decisions,
not generated captions, bounding boxes or object tracks.

## Video and camera input

Extract **2–4 JPEG or PNG frames**, in chronological order, from a window spanning
at most **30 seconds**. Replace `images` with this `media` field:

```python
payload.pop("images")
payload["media"] = {
    "type": "video",
    "frames": [
        {
            "mime_type": "image/jpeg",
            "data_base64": base64.b64encode(Path(path).read_bytes()).decode(),
            "timestamp_ms": timestamp,
        }
        for path, timestamp in [("frame0.jpg", 0), ("frame1.jpg", 1000)]
    ],
}
```

Build the request after updating the payload. For example, ask whether a person
has entered the view during this window, rather than asking about the entire
unseen video. For single-frame camera decisions, use the image form above.

The Playground accepts image uploads, local video files and camera capture. It
samples frames before making API requests. The API does **not** accept an MP4,
RTSP address or livestream URL directly; your application decodes its source and
submits the frames. Sampled windows cannot establish what happened between frames.

## Input contract

| Input | Supported form |
| --- | --- |
| Text | `state` plus typed `questions` |
| Single image | One embedded JPEG/PNG in `images` |
| Single image, native form | `media: {"type":"image", "frames":[{"mime_type":"image/jpeg", "data_base64":"..."}]}` |
| Video/camera window | `media.type: "video"`, 2–4 frames with increasing integer `timestamp_ms` |
| Choices | 2–8 alternatives per choice question |
| Questions | At most 16 per System One request |
| Context | At most 1,024 model input tokens, including visual input |

Do not combine `images` and `media`. Empty or multi-image `images` arrays, remote
image URLs, unsupported formats and visual requests using v1.0 are rejected.
This is a supported subset of the System One image request shape, not a claim
that every other provider's media extension is interchangeable.

## Price and application behavior

Text and visual inputs both cost **$0.042 per million billed input tokens**.
Visual billing includes the model's media tokens. There is no generated
output-token charge. Free decisions and paid balance are shared across inputs;
the console shows current allowance and usage.

Keep the same idempotency key when retrying the same request. A new input needs a
new key. Handle errors and uncertain decisions explicitly; probabilities describe
the model's preference among supplied answers and do not guarantee correctness.
A gesture or scene demo is an example application, not a safety certification.

See the [API reference](api.md) for authentication, errors and legacy text clients.
