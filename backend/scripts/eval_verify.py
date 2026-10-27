"""Live check of the fact-check pipeline: PYTHONPATH=. .venv/bin/python scripts/eval_verify.py  (uses OPENROUTER_API_KEY from .env)."""
import asyncio
import collections
import time

from app.llm.orchestrator import run_chat

QUESTIONS = [
    "Under MCPS Policy IOD, when is the Home Language Survey followed by an English proficiency assessment?",
    "How long does the ELD team monitor students after reclassification under Policy IOD?",
    "What does IOD-RA say about documented accommodations in non-ESOL classes?",
    "How does the current MCPS high school ELD page describe English credit limits?",
    "What instructional models does MCPS describe for elementary ELD?",
]


async def main():
    tally, t0 = collections.Counter(), time.time()
    for q in QUESTIONS:
        async def emit(_e): ...
        r = await run_chat("evaluation@mcpsmd.org", [{"role": "user", "content": q}], None, [], emit)
        st = r["verification"]["status"]
        tally[st] += 1
        print(f"{st:10} cites={len(r['citations'])}  {q[:70]}")
    print(dict(tally), f"{time.time() - t0:.0f}s")


asyncio.run(main())
