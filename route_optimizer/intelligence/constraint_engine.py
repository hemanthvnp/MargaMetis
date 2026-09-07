import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_WEIGHT_DIMS   = ("speed", "safety", "fuel_efficiency", "scenic", "comfort", "cost")
_VALID_VEHICLES = {"car", "bike", "bus", "truck", "auto"}

_SYSTEM_PROMPT = """You are a route preference extraction engine for MargaMetis, an intelligent navigation system.

Parse the user's natural-language route query into this EXACT JSON schema. Output ONLY valid JSON, nothing else.

SCHEMA:
{
  "priorities": [ordered list of active dimensions],
  "weights": {
    "speed": 0.0,
    "safety": 0.0,
    "fuel_efficiency": 0.0,
    "scenic": 0.0,
    "comfort": 0.0,
    "cost": 0.0
  },
  "avoid": [subset of: "tolls","highways","unpaved","narrow_roads","busy_roads","dark_roads"],
  "prefer": [subset of: "highways","scenic_roads","fuel_stations","lit_roads","wide_roads","coastal_roads"],
  "waypoints": [place names to route THROUGH, from "via X", "through X", "passing through X"],
  "vehicle_type": "car"|"bike"|"bus"|"truck"|"auto",
  "time_of_day": integer 0-23 or null,
  "max_routes": integer 1-5,
  "clarification_needed": false,
  "clarification_question": null,
  "contradiction_resolution": null,
  "raw_query": "<exact user query>"
}

RULES:
1. weights MUST sum to exactly 1.0
2. priorities lists dimensions from most to least important
3. Extract waypoints from "via X", "through X", "passing through X"
4. For contradictions (e.g. "fast but scenic"), split weights and explain in contradiction_resolution
5. Output ONLY valid JSON — no markdown, no explanation

EXAMPLES:

User: "fastest route avoiding tolls"
{"priorities":["speed","cost"],"weights":{"speed":0.75,"safety":0.10,"fuel_efficiency":0.02,"scenic":0.00,"comfort":0.03,"cost":0.10},"avoid":["tolls"],"prefer":["highways"],"waypoints":[],"vehicle_type":"car","time_of_day":null,"max_routes":2,"clarification_needed":false,"clarification_question":null,"contradiction_resolution":null,"raw_query":"fastest route avoiding tolls"}

User: "scenic drive to the beach, I want to relax"
{"priorities":["scenic","comfort"],"weights":{"speed":0.05,"safety":0.10,"fuel_efficiency":0.05,"scenic":0.55,"comfort":0.25,"cost":0.00},"avoid":["highways","busy_roads"],"prefer":["scenic_roads","coastal_roads"],"waypoints":[],"vehicle_type":"car","time_of_day":null,"max_routes":2,"clarification_needed":false,"clarification_question":null,"contradiction_resolution":null,"raw_query":"scenic drive to the beach, I want to relax"}

User: "via tambaram"
{"priorities":["speed","safety"],"weights":{"speed":0.40,"safety":0.20,"fuel_efficiency":0.15,"scenic":0.05,"comfort":0.15,"cost":0.05},"avoid":[],"prefer":[],"waypoints":["tambaram"],"vehicle_type":"car","time_of_day":null,"max_routes":3,"clarification_needed":false,"clarification_question":null,"contradiction_resolution":null,"raw_query":"via tambaram"}

User: "fastest route via anna nagar and nungambakkam"
{"priorities":["speed"],"weights":{"speed":0.85,"safety":0.10,"fuel_efficiency":0.02,"scenic":0.00,"comfort":0.02,"cost":0.01},"avoid":[],"prefer":["highways"],"waypoints":["anna nagar","nungambakkam"],"vehicle_type":"car","time_of_day":null,"max_routes":1,"clarification_needed":false,"clarification_question":null,"contradiction_resolution":null,"raw_query":"fastest route via anna nagar and nungambakkam"}

User: "safe night drive alone"
{"priorities":["safety"],"weights":{"speed":0.10,"safety":0.75,"fuel_efficiency":0.05,"scenic":0.00,"comfort":0.05,"cost":0.05},"avoid":["dark_roads","unpaved"],"prefer":["lit_roads","highways"],"waypoints":[],"vehicle_type":"car","time_of_day":22,"max_routes":2,"clarification_needed":false,"clarification_question":null,"contradiction_resolution":null,"raw_query":"safe night drive alone"}

User: "fuel efficient route on my bike, no tolls"
{"priorities":["fuel_efficiency","cost"],"weights":{"speed":0.05,"safety":0.15,"fuel_efficiency":0.55,"scenic":0.05,"comfort":0.05,"cost":0.15},"avoid":["tolls"],"prefer":[],"waypoints":[],"vehicle_type":"bike","time_of_day":null,"max_routes":2,"clarification_needed":false,"clarification_question":null,"contradiction_resolution":null,"raw_query":"fuel efficient route on my bike, no tolls"}

User: "fastest but also scenic"
{"priorities":["speed","scenic"],"weights":{"speed":0.55,"safety":0.10,"fuel_efficiency":0.05,"scenic":0.20,"comfort":0.10,"cost":0.00},"avoid":[],"prefer":[],"waypoints":[],"vehicle_type":"car","time_of_day":null,"max_routes":3,"clarification_needed":false,"clarification_question":null,"contradiction_resolution":"speed_over_scenic: contradictory goals — speed weighted higher (0.55 vs 0.20); 3 routes returned so user can choose","raw_query":"fastest but also scenic"}

User: "more ev stations"
{"priorities":["fuel_efficiency","speed"],"weights":{"speed":0.30,"safety":0.15,"fuel_efficiency":0.40,"scenic":0.05,"comfort":0.05,"cost":0.05},"avoid":[],"prefer":["fuel_stations"],"waypoints":[],"vehicle_type":"car","time_of_day":null,"max_routes":3,"clarification_needed":false,"clarification_question":null,"contradiction_resolution":null,"raw_query":"more ev stations"}

User: "heavy truck, need wide roads"
{"priorities":["safety","comfort"],"weights":{"speed":0.10,"safety":0.40,"fuel_efficiency":0.10,"scenic":0.00,"comfort":0.30,"cost":0.10},"avoid":["narrow_roads","unpaved"],"prefer":["highways","wide_roads"],"waypoints":[],"vehicle_type":"truck","time_of_day":null,"max_routes":2,"clarification_needed":false,"clarification_question":null,"contradiction_resolution":null,"raw_query":"heavy truck, need wide roads"}"""


def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return {k: round(1.0 / len(weights), 4) for k in weights}
    return {k: round(v / total, 4) for k, v in weights.items()}


def _validate_and_fix(data: Dict[str, Any], raw_query: str) -> Dict[str, Any]:
    data["raw_query"] = raw_query
    weights = data.get("weights", {})
    for dim in _WEIGHT_DIMS:
        weights.setdefault(dim, 0.0)
    data["weights"] = _normalize(weights)
    if not data.get("priorities"):
        data["priorities"] = sorted(_WEIGHT_DIMS, key=lambda d: -data["weights"][d])
    data.setdefault("avoid", [])
    data.setdefault("prefer", [])
    data.setdefault("waypoints", [])
    if data.get("vehicle_type") not in _VALID_VEHICLES:
        data["vehicle_type"] = "car"
    data.setdefault("time_of_day", None)
    data.setdefault("max_routes", 3)
    data.setdefault("clarification_needed", False)
    data.setdefault("clarification_question", None)
    data.setdefault("contradiction_resolution", None)
    return data


def _llm_extract(query: str, api_key: str) -> Optional[Dict[str, Any]]:
    try:
        import litellm
        response = litellm.completion(
            model="groq/llama-3.1-8b-instant",
            api_key=api_key,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": query},
            ],
            temperature=0.1,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content.strip())
    except ImportError:
        logger.warning("litellm not installed — pip install litellm")
        return None
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning(f"LLM extraction failed: {exc}")
        return None


_PEAK = frozenset({7, 8, 9, 17, 18, 19, 20})

_KW: Dict[str, Dict[str, float]] = {
    "fast":        {"speed": 0.80, "safety": 0.10, "comfort": 0.05, "fuel_efficiency": 0.03, "scenic": 0.00, "cost": 0.02},
    "fastest":     {"speed": 0.85, "safety": 0.10, "fuel_efficiency": 0.02, "scenic": 0.00, "comfort": 0.02, "cost": 0.01},
    "quick":       {"speed": 0.75, "safety": 0.10, "fuel_efficiency": 0.05, "scenic": 0.00, "comfort": 0.07, "cost": 0.03},
    "scenic":      {"scenic": 0.55, "comfort": 0.20, "safety": 0.10, "fuel_efficiency": 0.10, "speed": 0.03, "cost": 0.02},
    "beautiful":   {"scenic": 0.55, "comfort": 0.20, "safety": 0.10, "fuel_efficiency": 0.10, "speed": 0.03, "cost": 0.02},
    "safe":        {"safety": 0.75, "comfort": 0.10, "speed": 0.10, "fuel_efficiency": 0.03, "scenic": 0.00, "cost": 0.02},
    "safest":      {"safety": 0.80, "comfort": 0.10, "speed": 0.05, "fuel_efficiency": 0.03, "scenic": 0.00, "cost": 0.02},
    "fuel":        {"fuel_efficiency": 0.60, "cost": 0.15, "safety": 0.10, "comfort": 0.10, "speed": 0.03, "scenic": 0.02},
    "efficient":   {"fuel_efficiency": 0.55, "cost": 0.15, "safety": 0.15, "comfort": 0.10, "speed": 0.03, "scenic": 0.02},
    "cheap":       {"cost": 0.60, "fuel_efficiency": 0.20, "safety": 0.10, "comfort": 0.05, "speed": 0.03, "scenic": 0.02},
    "comfortable": {"comfort": 0.50, "safety": 0.20, "speed": 0.15, "fuel_efficiency": 0.10, "scenic": 0.03, "cost": 0.02},
    "relax":       {"scenic": 0.40, "comfort": 0.35, "safety": 0.15, "fuel_efficiency": 0.05, "speed": 0.03, "cost": 0.02},
}


def _rule_extract(query: str) -> Dict[str, Any]:
    q = query.lower()

    weights: Dict[str, float] = {d: 0.0 for d in _WEIGHT_DIMS}
    for kw, delta in _KW.items():
        if kw in q:
            for dim, val in delta.items():
                weights[dim] = max(weights[dim], val)

    if max(weights.values()) < 0.10:
        weights = {"speed": 0.40, "safety": 0.20, "fuel_efficiency": 0.15,
                   "scenic": 0.05, "comfort": 0.15, "cost": 0.05}

    avoid:  List[str] = []
    prefer: List[str] = []

    if re.search(r'\b(no|avoid|without).{0,8}toll', q):     avoid.append("tolls")
    if re.search(r'\btoll.{0,5}free\b', q):                  avoid.append("tolls")
    if re.search(r'\b(avoid|no).{0,8}highway', q):           avoid.append("highways")
    if re.search(r'\b(avoid|no).{0,8}traffic|traffic.{0,5}free\b', q): avoid.append("busy_roads")
    if re.search(r'\bdark|unlit', q):
        avoid.append("dark_roads"); prefer.append("lit_roads")
    if re.search(r'\bunpaved|dirt road|kachcha', q):          avoid.append("unpaved")
    if re.search(r'\bnarrow', q):                             avoid.append("narrow_roads")
    if re.search(r'\bhighway|expressway|NH\b', q) and "highways" not in avoid:
        prefer.append("highways")
    if re.search(r'\bfuel.{0,10}station|petrol.{0,5}pump|ev.{0,10}station|charging|more.{0,5}ev\b', q, re.IGNORECASE):
        prefer.append("fuel_stations")
        weights["fuel_efficiency"] = max(weights.get("fuel_efficiency", 0), 0.30)
        weights = _normalize(weights)
    if re.search(r'\bECR|coastal|beach', q):
        prefer.append("coastal_roads")

    # "via X and Y" — capture the whole block then split on "and" / ","
    waypoints: List[str] = []
    via_block = re.search(
        r'\b(?:via|through|passing\s+through|pass\s+through)\s+'
        r'([A-Za-z][A-Za-z\s,]{2,80}?)(?:\s+(?:at|on|by|for|with|to|from)\b|\s*$)',
        query, re.IGNORECASE
    )
    if via_block:
        for part in re.split(r'\s+and\s+|,\s*', via_block.group(1)):
            wp = part.strip()
            if wp and len(wp) > 2 and wp.lower() not in ('the', 'a', 'an'):
                waypoints.append(wp)

    vehicle = "car"
    for pat, v in [
        (r'\btruck|lorry|HGV\b', "truck"),
        (r'\bbus\b', "bus"),
        (r'\bauto.?rickshaw|autorickshaw\b', "auto"),
        (r'\bbike|bicycle|scooter|motorcycle\b', "bike"),
    ]:
        if re.search(pat, q, re.IGNORECASE):
            vehicle = v
            break

    tod = None
    m = re.search(r'\b(\d{1,2})\s*(am|pm)\b', q, re.IGNORECASE)
    if m:
        h = int(m.group(1))
        if m.group(2).lower() == "pm" and h != 12: h += 12
        elif m.group(2).lower() == "am" and h == 12: h = 0
        tod = h % 24
    else:
        for word, hour in [("midnight", 0), ("night", 22), ("evening", 18),
                            ("afternoon", 14), ("noon", 12), ("morning", 8)]:
            if re.search(rf'\b{word}\b', q):
                tod = hour
                break

    if tod is not None and (tod >= 20 or tod <= 5):
        weights["safety"] = max(weights["safety"], 0.55)
        if "lit_roads" not in prefer:  prefer.append("lit_roads")
        if "dark_roads" not in avoid:  avoid.append("dark_roads")
        weights = _normalize(weights)

    if vehicle == "truck":
        weights["safety"]  = max(weights["safety"], 0.35)
        weights["comfort"] = max(weights["comfort"], 0.25)
        weights = _normalize(weights)
        if "wide_roads" not in prefer:   prefer.append("wide_roads")
        if "narrow_roads" not in avoid:  avoid.append("narrow_roads")

    if "tolls" in avoid:
        weights["cost"] = max(weights["cost"], 0.30)
        weights = _normalize(weights)

    priorities = sorted(_WEIGHT_DIMS, key=lambda d: -weights[d])
    clarification = len([w for w in re.split(r"\W+", query.strip()) if len(w) > 2]) < 1

    return {
        "priorities": priorities,
        "weights":    weights,
        "avoid":      list(dict.fromkeys(avoid)),
        "prefer":     list(dict.fromkeys(prefer)),
        "waypoints":  waypoints,
        "vehicle_type": vehicle,
        "time_of_day":  tod,
        "max_routes":   3,
        "clarification_needed":   clarification,
        "clarification_question": (
            "What kind of route do you prefer? (e.g. fastest, scenic, avoid tolls)"
            if clarification else None
        ),
        "contradiction_resolution": None,
        "raw_query": query,
    }


def extract_constraints(query: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    if not query.strip():
        return _validate_and_fix(
            {"clarification_needed": True,
             "clarification_question": "Please describe your route preference."},
            query
        )

    key = api_key or os.environ.get("GROQ_API_KEY")
    if key:
        result = _llm_extract(query, key)
        if result is not None:
            return _validate_and_fix(result, query)

    return _validate_and_fix(_rule_extract(query), query)


class ConstraintEngine:
    """Wraps extract_constraints with JSONL query logging for dataset building."""

    def __init__(self, api_key: Optional[str] = None, log_dir: str = "logs") -> None:
        self.api_key   = api_key or os.environ.get("GROQ_API_KEY")
        self.log_path  = Path(log_dir) / "constraint_queries.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def extract_constraints(self, query: str) -> Dict[str, Any]:
        result = extract_constraints(query, self.api_key)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp":   datetime.now(timezone.utc).isoformat(),
                    "query":       query,
                    "constraints": result,
                }) + "\n")
        except OSError:
            pass
        return result
