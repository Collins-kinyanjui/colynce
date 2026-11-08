"""Server-side Gemini integration. Set GEMINI_API_KEY via host secrets, never source code."""
import os
import httpx

async def generate_reply(message: str, history: list[dict], instructions: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Gemini key is not configured")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    contents = []
    for turn in history[-8:]:
        if isinstance(turn, dict) and turn.get("role") in ("user", "assistant") and isinstance(turn.get("content"), str):
            contents.append({"role": "model" if turn["role"] == "assistant" else "user",
                             "parts": [{"text": turn["content"][:1000]}]})
    contents.append({"role": "user", "parts": [{"text": message}]})
    # Some legacy model IDs return 404 even with a valid API key. Try a newer
    # model on 404 only, while respecting rate limits and other API failures.
    candidates = list(dict.fromkeys([model, "gemini-3.5-flash-lite", "gemini-3.8-flash"]))
    async with httpx.AsyncClient(timeout=22) as client:
        for index, candidate in enumerate(candidates):
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent",
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={"systemInstruction": {"parts": [{"text": instructions}]},
                      "contents": contents,
                      "generationConfig": {"maxOutputTokens": 350, "temperature": 0.4}},
            )
            if response.status_code == 404 and index < len(candidates) - 1:
                continue
            response.raise_for_status()
            data = response.json()
            break
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    answer = " ".join(part["text"] for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str)).strip()
    if not answer:
        raise ValueError("Gemini did not return a text response")
    return answer
