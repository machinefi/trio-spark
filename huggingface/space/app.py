import json
import urllib.error
import urllib.request
import uuid

import gradio as gr


API_URL = "https://platform.machinefi.com/api/spark/v1/decisions"


def decide(api_key, task, state_text, choices_text):
    if not api_key or not api_key.strip():
        raise gr.Error("Enter a Trio-Spark API key. Create one in the MachineFi console.")
    try:
        state = json.loads(state_text)
        choices_value = json.loads(choices_text)
    except json.JSONDecodeError as exc:
        raise gr.Error(f"State and choices must be valid JSON: {exc.msg}") from None
    if not isinstance(state, dict):
        raise gr.Error("State must be a JSON object.")
    if isinstance(choices_value, dict):
        choices = [{"id": str(key), "description": str(value)}
                   for key, value in choices_value.items()]
    elif isinstance(choices_value, list):
        choices = choices_value
    else:
        raise gr.Error("Choices must be a JSON object or list.")
    if not 2 <= len(choices) <= 8:
        raise gr.Error("Provide 2 to 8 choices.")
    body = json.dumps({
        "model": "trio-spark-preview",
        "task": task,
        "state": state,
        "choices": choices,
    }).encode("utf-8")
    request = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
        "Idempotency-Key": str(uuid.uuid4()),
        "User-Agent": "MachineFi-HuggingFace-Space/1.0",
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            payload = json.loads(error.read().decode("utf-8"))
            detail = payload.get("error") or payload.get("message") or ""
        except Exception:
            pass
        message = f"Trio-Spark returned HTTP {error.code}"
        if detail:
            message += f": {detail}"
        raise gr.Error(message) from None
    except Exception as error:
        raise gr.Error(f"Could not reach Trio-Spark: {type(error).__name__}") from None
    return result.get("choice_id", ""), result.get("probabilities", []), result


with gr.Blocks(title="Trio-Spark v1.0", theme=gr.themes.Soft(primary_hue="green")) as demo:
    gr.Markdown("""
    # Trio-Spark v1.0
    **Fast judgment for the next move.** Give Spark a state and 2–8 possible moves; it returns one decision and the full probability distribution in one pass.

    [Create an account and API key](https://platform.machinefi.com/spark) · [Read the API docs](https://platform.machinefi.com/spark/docs) · [See real demos](https://github.com/machinefi/trio-spark)
    """)
    api_key = gr.Textbox(label="API key", type="password", placeholder="tf_…")
    task = gr.Textbox(label="Task", value="Keep the machine safe while completing the operation.")
    with gr.Row():
        state = gr.Code(label="State", language="json", value='''{
  "temperature_c": 84,
  "load_pct": 91,
  "vibration": "rising"
}''')
        choices = gr.Code(label="Allowed moves", language="json", value='''{
  "continue": "Continue at the current speed",
  "slow": "Reduce speed and keep observing",
  "stop": "Stop the machine now"
}''')
    run = gr.Button("Choose the next move", variant="primary")
    with gr.Row():
        selected = gr.Textbox(label="Selected move")
        probabilities = gr.JSON(label="Probability distribution")
    raw = gr.JSON(label="Full API response")
    run.click(decide, [api_key, task, state, choices], [selected, probabilities, raw])
    gr.Markdown("Your API key is sent only with this request to MachineFi's production endpoint and is not stored by this Space.")


if __name__ == "__main__":
    demo.launch()
