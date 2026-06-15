
#prompt template
"""
    Using a combination of RAG prompt,instruction prompt,structured prompt,
    and role based prompt.
    also following a low temperature decoding   
    system prommpt is also included in  this  
"""

# log = parse_log("system.json")
# context = rag_query(event, n_chunks=3)  # Retrieve relevant context from the knowledge base


# using qwen3-8b with thinking mode off for fast structured output (use /no_think for triage)
from huggingface_hub import InferenceClient
import json
from rag_engine import rag_query, build_index
from parser import parse_log

# ── HuggingFace client (free, needs HF_TOKEN env var) ─────────────────────────
_client = None

def _get_client():
    global _client
    if _client is None:
        import os
        _client = InferenceClient(
            provider="auto",                    # picks fastest free provider
            api_key=os.environ["HF_TOKEN"]      # free token from hf.co/settings/tokens
        )
    return _client


def _build_prompt(parsed_event: dict, context: str) -> str:
    return f"""You are an OpenBMC diagnostics expert analyzing server hardware events.

Event Details:
- Sensor  : {parsed_event['sensor']}
- Category: {parsed_event['category']}
- Type    : {parsed_event['event_type']}
- Severity: {parsed_event['severity']}

Knowledge Base Context:
{context}

Based on the event and context above, provide a diagnosis in this exact JSON format:
{{
  "root_cause"              : "<one concise sentence>",
  "severity"                : "CRITICAL | HIGH | MEDIUM | LOW",
  "confidence"              : "<percentage e.g. 85%>",
  "recommendation"          : "<one actionable step>",
  "requires_immediate_action": true or false
}}

Respond with JSON only. No explanation outside the JSON block."""


def diagnose(log: dict) -> dict:
    parsed_event = parse_log(log)
    if parsed_event is None:
        return {"error": f"Unknown event type: {log.get('event')}"}

    rag_query_str = f"{parsed_event['category']} {parsed_event['event_type']}"
    context = rag_query(rag_query_str, n_chunks=2)
    prompt  = _build_prompt(parsed_event, context)

    client = _get_client()

    # Qwen3-8B with thinking mode OFF for fast JSON (use /no_think for triage)
    response = client.chat.completions.create(
        model="Qwen/Qwen3-8B",
        messages=[
            {
                "role": "system",
                "content": "You are an OpenBMC diagnostics expert. Always respond with valid JSON only."
                " /no_think"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=512,
        temperature=0.1,        # low temp = consistent structured output
    )

    raw_text = response.choices[0].message.content.strip()

    # Strip markdown fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    diagnosis = json.loads(raw_text.strip())
    diagnosis["sensor"]      = parsed_event["sensor"]
    diagnosis["event_type"]  = parsed_event["event_type"]
    diagnosis["rag_context"] = context
    return diagnosis


if __name__ == "__main__":
    build_index()

    sample_log = {
        "sensor"  : "DIMM_B2",
        "event"   : "Memory ECC Error",
        "severity": "WARNING"
    }

    result = diagnose(sample_log)
    print(json.dumps(result, indent=2))


# #testing the search function
# if __name__ == "__main__":
#     # Example usage
#     build_index(force=True)  # Build th e index from knowledge base files
#     answer = rag_query("Memory ECC error")
#     print(f"Answer: {answer}")