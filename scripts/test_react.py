import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import run_react_agent

HARDCODED_OBSERVATIONS = [
    "[00:05] Sahada iki işçi forklift ile malzeme taşıyor, ikisi de baretli ve yelekli.",
    "[00:15] Forklift ani manevra yaptı, bir işçi dengesini kaybedip yere düştü ve hareketsiz kalıyor. Konum: Depo B, Hat 3.",
    "[00:20] İkinci işçi yerdeki kişinin yanına gitti; bu işçi baretsiz ve yeleksiz çalışıyor.",
]

USER_PROMPT = "Sahadaki durumu değerlendir ve gerekli aksiyonları al."


def main():
    print("=== ReAct test — video/frame extraction atlanıyor, hardcoded gözlemler kullanılıyor ===\n")

    result = run_react_agent(HARDCODED_OBSERVATIONS, USER_PROMPT, model_config=None)

    print(f"iteration_limit_reached : {result['iteration_limit_reached']}")
    print(f"aborted                 : {result['aborted']} (reason: {result['abort_reason']})")
    print()

    print("--- STEP TRACE ---")
    if not result["trace"]:
        print("(hiç araç çağrılmadı)")
    for step in result["trace"]:
        print(f"[Adım {step['step']}] {step['tool']}")
        print(f"  args   : {json.dumps(step['arguments'], ensure_ascii=False)}")
        print(f"  result : {json.dumps(step['result'], ensure_ascii=False)}")
        print()

    print("--- FINAL ---")
    if result["final"]:
        print(json.dumps(result["final"], ensure_ascii=False, indent=2))
    else:
        print(f"(final yok — final_raw: {result['final_raw']!r})")


if __name__ == "__main__":
    main()
