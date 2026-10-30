"""Vergelijkt de estafette met varianten die alleen Qwen3.8 gebruiken.

Zelfde 20 antwoorden, zelfde voorfilter, zelfde verwachte uitkomsten (LEERLINGEN in
pipeline.py). Meet per variant de tijd voor triage + score + feedback (de briefing
doet Qwen in alle varianten en telt niet mee) en hoeveel leerlingen de juiste score krijgen.

  A: Qwen, één aanroep per leerling voor alles
  B: Qwen, dezelfde stappen als de estafette (triage, score, fout, feedback)
  C: Qwen, de hele klas in één aanroep

Gebruik:  python vergelijk_qwen.py      (NOLAI_API_KEY uit .env)
Uitvoer:  terminal + resultaten/vergelijk_qwen.json
"""
import asyncio, json, os, re, sys, time
from pathlib import Path
HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
import pipeline as P
from live_dashboard import GatewayClient
QWEN = "CLUSTER.qwen3.8:latest"
P._lees_dotenv()
client = GatewayClient(P.BASE_URL, os.environ["NOLAI_API_KEY"], 300)
TAGS = ["Geen fout", "Vergeet verdamping", "Vergeet condensatie", "Vergeet neerslag", "Foute volgorde", "Begripsfout"]
REGELS = (f"Exit-ticketvraag: {P.VRAAG}\n"
  "poging = is dit een serieuze poging om de vraag te beantwoorden, goed of fout ('ja' of 'nee'). "
  "score: 2 = verdamping, condensatie (wolkvorming) en neerslag correct beschreven; 1 = deels correct of een fase ontbreekt; "
  "0 = geen fase correct of een verkeerd mechanisme. fout_tag: precies één van " + ", ".join(TAGS) + "; bij score 2 altijd 'Geen fout'. "
  "feedback: " + P.FEEDBACK_SYSTEM.replace("Je bent een empathische, aanmoedigende docent. ", ""))
def leerlingen(): return [l for l in P.LEERLINGEN if not P.voorfilter(l["antwoord"])]
async def qwen(system, user, max_tokens):
    r = await client.chat.completions.create(model=QWEN, messages=[{"role":"system","content":system},{"role":"user","content":user}], temperature=0, max_tokens=max_tokens)
    return r.choices[0].message.content
def json_los(t):
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t.strip())
    for a,b in (("{","}"),("[","]")):
        i,j = t.find(a), t.rfind(b)
        if i!=-1 and j>i:
            try: return json.loads(t[i:j+1])
            except Exception: pass
    return None
def norm(r):
    tag = str(r.get("fout_tag","")).strip("[] ")
    try: sc = int(r.get("score"))
    except Exception: sc = None
    return {"triage": "GELDIG" if str(r.get("poging","")).lower().startswith("j") else "ONGELDIG", "score": sc, "fout_tag": tag, "feedback": r.get("feedback")}

async def variant_A():
    sem = asyncio.Semaphore(3)
    sys_p = "Je bent een docent die exit-tickets nakijkt. " + REGELS + "\nAntwoord ALLEEN met JSON: {\"poging\": \"ja\"|\"nee\", \"score\": 0|1|2, \"fout_tag\": \"...\", \"feedback\": \"...\"}"
    async def een(l):
        async with sem:
            return l["id"], norm(json_los(await qwen(sys_p, "Antwoord van de leerling: " + l["antwoord"], 400)) or {})
    return dict(await asyncio.gather(*(een(l) for l in leerlingen())))

async def variant_B():
    for k in ("triage","scoring","feedback"): P.STAPPEN[k]["modellen"] = [QWEN]
    tri = await P.stap1_triage(P.LLMStep("triage", client), leerlingen())
    geldig = [r for r in tri if r["triage"]=="GELDIG"]
    sc = await P.stap2_scoring(P.LLMStep("scoring", client), geldig, None)
    fb = await P.stap3_feedback(P.LLMStep("feedback", client), sc)
    out = {r["id"]: {"triage": r["triage"]} for r in tri}
    for r in fb: out[r["id"]].update(score=r["score"], fout_tag=r["fout_tag"].strip("[]"), feedback=r["feedback"])
    return out

async def variant_C():
    sys_p = "Je bent een docent die een hele klas exit-tickets nakijkt. " + REGELS + "\nAntwoord ALLEEN met een JSON-lijst, één object per leerling: [{\"id\": \"L01\", \"poging\": \"ja\"|\"nee\", \"score\": 0|1|2, \"fout_tag\": \"...\", \"feedback\": \"...\"}, ...]"
    user = "\n".join(f'{l["id"]}: {l["antwoord"]}' for l in leerlingen())
    lijst = json_los(await qwen(sys_p, user, 6000)) or []
    return {r.get("id"): norm(r) for r in lijst if isinstance(r, dict)}

def evalueer(naam, res, sec):
    tri_goed = sc_goed = sc_n = 0; mis_t=[]; mis_s=[]
    for l in P.LEERLINGEN:
        v = l["verwacht"]
        if P.voorfilter(l["antwoord"]): tri_goed += 1; continue        # voorfilter: in alle varianten gelijk
        r = res.get(l["id"]) or {}
        if r.get("triage") == v["triage"]: tri_goed += 1
        else: mis_t.append(l["id"])
        if r.get("triage") == "GELDIG" and v.get("score") is not None and r.get("score") is not None:
            sc_n += 1; sc_goed += r["score"] == v["score"]
            if r["score"] != v["score"]: mis_s.append(f'{l["id"]}:{r["score"]}≠{v["score"]}')
    fb = sum(1 for r in res.values() if r.get("feedback"))
    print(f"{naam}: {sec:.0f}s | triage {tri_goed}/20 mis {mis_t} | score {sc_goed}/{sc_n} mis {mis_s} | feedback {fb}", flush=True)
    return {"variant": naam, "sec": round(sec,1), "triage": tri_goed, "score": sc_goed, "score_n": sc_n, "feedback": fb, "mis_t": mis_t, "mis_s": mis_s, "res": res}

async def main():
    uit = []
    for naam, f in (("A: Qwen, 1 aanroep per leerling", variant_A), ("B: Qwen, zelfde stappen als estafette", variant_B), ("C: Qwen, hele klas in 1 aanroep", variant_C)):
        t = time.time(); res = await f(); uit.append(evalueer(naam, res, time.time()-t))
    moet = [l for l in P.LEERLINGEN if l["verwacht"]["triage"] == "GELDIG"]
    print("\nJuiste score voor de", len(moet), "leerlingen die een score horen te krijgen (weggefilterd = fout):")
    for v in uit:
        goed = sum(1 for l in moet if (v["res"].get(l["id"]) or {}).get("triage") == "GELDIG"
                   and (v["res"].get(l["id"]) or {}).get("score") == l["verwacht"]["score"])
        print(f'  {v["variant"]:42} {v["sec"]:5.0f}s   {goed}/{len(moet)}')
    (HIER / "resultaten").mkdir(exist_ok=True)
    (HIER / "resultaten" / "vergelijk_qwen.json").write_text(json.dumps(uit, ensure_ascii=False, indent=1), encoding="utf-8")
asyncio.run(main())
