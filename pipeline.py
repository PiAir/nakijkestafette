#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
════════════════════════════════════════════════════════════════════════════
 FORMATIVE ASSESSMENT PIPELINE — LLM-estafette met 4 lokale modellen
════════════════════════════════════════════════════════════════════════════
Simuleert het nakijken van een exit-ticket over de waterkringloop bij
20 (synthetische) leerlingen. Elke stap wordt overgedragen aan een ander
model — het "estafette"-principe:

  [0] VOORFILTER     vaste regel: leeg of geen enkele letter = ONGELDIG
  [1] TRIAGE         Tev1   — beslismodel, kiest A (ja) of B (nee)
  [2] SCORING        Clef   — beslismodel via LiteLLM System One: score, fout-tag
                              én zekerheid in één aanroep (terugval: Nimble)
  [3] FEEDBACK       Qwen3.8 — taalmodel, schrijft 1–2 zinnen feedback
  [4] DOCENT-BRIEF   Qwen3.8 — taalmodel, schrijft de briefing

Tev1 en Nimble zijn beslismodellen: ze voeren geen gesprek maar kiezen uit
vaste opties. Ze krijgen daarom een JSON met state, question en options, en
geven één letter terug. Clef wordt via LiteLLM (/v1/systemone) aangeroepen
en geeft per vraag kansen terug; scores met een zekerheid onder de 60% worden
als twijfelgeval gemarkeerd: die kijkt de docent zelf na.

Transport: de Ollama-route van de NOLAI-gateway
(https://chat.nolai.nl/ollama/api/chat) met think=false. Via de
OpenAI-compatibele route laat het denken zich niet uitzetten, en dan duurt
één keuze 30–130 s in plaats van ±0,5–1 s. Geen extra Python-packages nodig.

Live-dashboard en simulatie:
  * dashboard.html beweegt mee tijdens de run (dubbelklik hem gewoon; hij leest
    live_state.js elke seconde opnieuw in)
  * per leerling een verwachte uitkomst (`verwacht`): het dashboard toont
    meteen waar de modellen afwijken
  * de ids van ongeldige tickets gaan expliciet mee naar Qwen (geen raden)
  * elke echte run wordt opgenomen in simulatie_data.json; --simulatie speelt
    die laatste echte run na (oefenen, of als de gateway hapert)

Gebruik:
  python pipeline.py                  # volledige run (20 leerlingen)
  python pipeline.py --limiet 4       # snelle smoke-test
  python pipeline.py --simulatie      # laatste echte run naspelen

Output:
  * gekleurde terminal-log (ANSI) per stap en per leerling
  * live_state.js (voor dashboard.html) en aan het eind resultaten/resultaat_<datum-tijd>.html,
    een losse momentopname van het dashboard die je kunt bewaren of doorsturen
  * Markdown-resultaat (alleen bij een echte run): resultaten/resultaat_formative_assessment.md

API-keys (environment of .env in deze map of erboven):
  * NOLAI_API_KEY    voor chat.nolai.nl (Tev1, Nimble, Qwen3.8)
  * LITELLM_API_KEY  voor litellm.nolai.nl (Clef via System One); zonder deze
                     sleutel valt de scoring terug op Nimble
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import webbrowser

from live_dashboard import (VOORFILTER_NAAM, GatewayClient, Live, SimClient,
                            SystemOneClient, Uit, bewaar_opname, laad_simulatiedata,
                            voorfilter)

LIVE = Uit()   # wordt in main() vervangen door een Live-object

# ────────────────────────────────────────────────────────────────────────────
# CONFIGURATIE
# ────────────────────────────────────────────────────────────────────────────

# Elke stap: lijst met kandidaat-modellen. Kandidaat 0 is de eerste keus; bij
# een model-level fout (bv. tev1:4b: "does not support chat") of een
# onbruikbaar antwoord schakelt de pipeline automatisch naar de volgende.
STAPPEN = {
    "triage": {
        "naam": "Tev1",
        "rol": "Triage: is dit een serieuze poging?",
        "modellen": ["ERASMUS.tev1:4b", "ERASMUS.tev1:0.8b"],   # Nimble scoort hier slecht (5–12/18)
        "temperature": 0.0,
        "max_tokens": 3,             # één letter
        "concurrentie": 4,
    },
    "scoring": {
        "naam": "Clef",
        "rol": "Score 0–2 + fout-tag met zekerheid (System One)",
        # clef:27b gaat via LiteLLM System One (zie stap2_scoring); valt die uit,
        # dan neemt Nimble het over via de gateway (letterkeuze, zonder zekerheid).
        "modellen": ["clef:27b", "CLUSTER.nimble:9b"],
        "temperature": 0.0,
        "max_tokens": 3,
        "concurrentie": 3,
    },
    "feedback": {
        "naam": "Qwen3.8",
        "rol": "Formatieve feedback (taalmodel)",
        "modellen": ["CLUSTER.qwen3.8:latest", "CLUSTER.ornith-1.5:35b"],
        "temperature": 0.4,
        "max_tokens": 220,
        "concurrentie": 3,
    },
    "briefing": {
        "naam": "Qwen3.8",
        "rol": "Docent-briefing + actieplan",
        "modellen": ["CLUSTER.qwen3.8:latest"],
        "temperature": 0.4,
        "max_tokens": 2500,
        "concurrentie": 1,
    },
}

BASE_URL = os.environ.get("NOLAI_BASE_URL", "https://chat.nolai.nl/ollama/api/chat")
TIMEOUT_SEC = 180          # per API-call (ruim: eerste call laadt het model)
RETRIES = 2                # transiënte fouten (timeout/429/5xx) per model

VRAAG = ("Leg in maximaal 3 zinnen uit hoe de waterkringloop werkt. "
         "Noem minimaal drie fasen.")

# 20 synthetische leerlingantwoorden: perfect → deels goed → onzin → leeg.
# `verwacht` is een inschatting van de juiste uitkomst (pas aan naar je eigen
# oordeel). Het dashboard toont waar de modellen hiervan afwijken; de modellen
# zelf krijgen deze waarde nooit te zien.
LEERLINGEN = [
    {"id": "L01", "verwacht": {"triage": "GELDIG", "score": 2}, "antwoord": "Water verdampt door de warmte van de zon, kondenseert in de hoge lucht tot wolken en valt als neerslag, regen of sneeuw, terug op aarde."},
    {"id": "L02", "verwacht": {"triage": "GELDIG", "score": 2}, "antwoord": "De waterkringloop bestaat uit verdamping, condensatie en neerslag. Water stoomt op uit zeeën, wordt wolken en regent of sneuvelt weer naar beneden."},
    {"id": "L03", "verwacht": {"triage": "GELDIG", "score": 2}, "antwoord": "Het water gaat omhoog als damp, maakt wolken en dan regent het weer."},
    {"id": "L04", "verwacht": {"triage": "GELDIG", "score": 1}, "antwoord": "Water verdamp en dan regent het weer op de grond."},
    {"id": "L05", "verwacht": {"triage": "GELDIG", "score": 1}, "antwoord": "Eerst valt er neerslag uit de lucht en daarna verdampt het water weer in de oceaan."},
    {"id": "L06", "verwacht": {"triage": "GELDIG", "score": 1}, "antwoord": "De zon verwarmt het water in de zee en dat komt omhoog als wolken in de lucht."},
    {"id": "L07", "verwacht": {"triage": "GELDIG", "score": 1}, "antwoord": "Wolken vallen uit de lucht en dan stroomt het water in de zee."},
    {"id": "L08", "verwacht": {"triage": "GELDIG", "score": 1}, "antwoord": "Het water stroomt via rivieren naar de zee en komt dan weer terug in de lucht."},
    {"id": "L09", "verwacht": {"triage": "GELDIG", "score": 1}, "antwoord": "Als het warm is dan verdampt het water en dat wordt dan wind die de wolken door de lucht duwt."},
    {"id": "L10", "verwacht": {"triage": "GELDIG", "score": 0}, "antwoord": "De waterkringloop is een soort kring van water die altijd door blijft gaan."},
    {"id": "L11", "verwacht": {"triage": "GELDIG", "score": 0}, "antwoord": "Ik denk dat het te maken heeft met de maan, want het water gaat omhoog en omlaag."},
    {"id": "L12", "verwacht": {"triage": "GELDIG", "score": 0}, "antwoord": "Omdat vissen het water in de lucht duwen met hun staarten."},
    {"id": "L13", "verwacht": {"triage": "GELDIG", "score": 0}, "antwoord": "De waterkringloop bestaat omdat het water honger heeft naar de aarde."},
    {"id": "L14", "verwacht": {"triage": "ONGELDIG"}, "antwoord": "Waternoom is een dier dat in de zee woont en dat spuilt dan het water de lucht in."},
    {"id": "L15", "verwacht": {"triage": "GELDIG", "score": 0}, "antwoord": "Omdat de zon 's nachts het water drinkt en 's ochtends weer brukt op de aarde."},
    {"id": "L16", "verwacht": {"triage": "ONGELDIG"}, "antwoord": "1234567890"},
    {"id": "L17", "verwacht": {"triage": "ONGELDIG"}, "antwoord": ""},
    {"id": "L18", "verwacht": {"triage": "GELDIG", "score": 1}, "antwoord": "In de zee wordt water verdampt en dan regent het weer op de bergen."},
    {"id": "L19", "verwacht": {"triage": "GELDIG", "score": 1}, "antwoord": "Het water loopt langzaam de berg op en dan valt het er weer van af als regen."},
    {"id": "L20", "verwacht": {"triage": "GELDIG", "score": 0}, "antwoord": "Iets met wolken en regen, maar ik weet de fases niet echt te benoemen."},
]

# ── Beslisvragen voor Tev1 en Nimble: state + question + options → één letter ──
BESLIS_SYSTEM = "Kies de best passende optie. Antwoord met alleen de letter."

# Getest op de 18 antwoorden die door de voorfilter komen (30-10-2026):
#   "Gaat dit antwoord over de waterkringloop?"           Tev1 16/18, Nimble 9/18
#   "Is dit een serieuze poging … goed of fout?"         Tev1 17/18, Nimble 5/18
# Fout antwoorden (misconcepties) moeten dóór: die leerlingen hebben juist feedback nodig.
TRIAGE_VRAAG = "Is dit een serieuze poging om de vraag te beantwoorden, goed of fout?"
TRIAGE_OPTIES = {"A": ("ja", "GELDIG"), "B": ("nee", "ONGELDIG")}   # korte opties: Tev1 0.8b raakt van lange teksten in de war
# Tweede oordeel, alleen als de eerste vraag "nee" geeft. Pas als ook deze
# vraag zegt dat het onzin is, gaat het ticket apart. Bij twijfel: doorlaten.
TWEEDE_VRAAG = "Is dit antwoord onzin?"
TWEEDE_OPTIES = {"A": ("nee", "GELDIG"), "B": ("ja", "ONGELDIG")}

SCORE_VRAAG = "Welke score krijgt dit antwoord?"
SCORE_OPTIES = {
    "A": ("2 punten, verdamping, condensatie (wolkvorming) en neerslag correct beschreven", 2),
    "B": ("1 punt, deels correct of een fase ontbreekt", 1),
    "C": ("0 punten, geen fase correct of een verkeerd mechanisme", 0),
}
TAG_VRAAG = "Wat is de belangrijkste fout in dit antwoord?"
TAG_OPTIES = {
    "A": ("geen fout, alle drie fasen correct", "[Geen fout]"),
    "B": ("verdamping ontbreekt", "[Vergeet verdamping]"),
    "C": ("condensatie of wolkvorming ontbreekt", "[Vergeet condensatie]"),
    "D": ("neerslag ontbreekt", "[Vergeet neerslag]"),
    "E": ("de fasen staan in de verkeerde volgorde", "[Foute volgorde]"),
    "F": ("verkeerd mechanisme of misvatting", "[Begripsfout]"),
}


# ── Clef via LiteLLM System One: score en fout in één aanroep, met kansen ──
LITELLM_URL = os.environ.get("LITELLM_URL", "https://litellm.nolai.nl/v1/systemone")
SYSTEMONE_MODEL = "clef:27b"
TWIJFEL_GRENS = 0.60          # zekerheid over de score lager dan dit = docent kijkt zelf
SO_VRAGEN = {
    "score": {
        "type": "score",
        "instructions": "Welke score krijgt dit antwoord?",
        "criteria": [
            "0 punten: geen fase correct of een verkeerd mechanisme",
            "1 punt: deels correct of een fase ontbreekt",
            "2 punten: verdamping, condensatie (wolkvorming) en neerslag correct beschreven",
        ],
    },
    "fout": {
        "type": "choice",
        "instructions": "Wat is de belangrijkste fout in dit antwoord?",
        "criteria": {
            "geen fout": "alle drie fasen correct",
            "vergeet verdamping": "verdamping ontbreekt",
            "vergeet condensatie": "condensatie of wolkvorming ontbreekt",
            "vergeet neerslag": "neerslag ontbreekt",
            "foute volgorde": "de fasen staan in de verkeerde volgorde",
            "begripsfout": "verkeerd mechanisme of misvatting",
        },
    },
}
SO_FOUT_TAG = {k: "[" + k[0].upper() + k[1:] + "]" for k in SO_VRAGEN["fout"]["criteria"]}


def beslis_bericht(state: str, vraag: str, opties: dict) -> str:
    return json.dumps({"state": state, "question": vraag,
                       "options": [f"{k}: {v[0]}" for k, v in opties.items()]},
                      ensure_ascii=False)


def state_triage(antwoord: str) -> str:
    return "Antwoord van een leerling op de vraag hoe de waterkringloop werkt: " + antwoord


def state_scoring(antwoord: str) -> str:
    return f"Antwoord van een leerling op: '{VRAAG}'\nAntwoord: {antwoord}"


FEEDBACK_SYSTEM = (
    "Je bent een empathische, aanmoedigende docent. Op basis van de score en de fout-tag "
    "schrijf je 1 à 2 zinnen formatieve feedback in het Nederlands voor de leerling. "
    "Herhaal niet de volledige stof, maar wijs de leerling aan waar het klopt en wat de "
    "belangrijkste volgende stap is. Bevestig NOOIT een onjuiste uitspraak of misvatting "
    "(bv. dat vissen water in de lucht duwen); corrigeer die dan vriendelijk in dezelfde zin. "
    "Leid altijd terug naar de waterkringloop (verdamping, condensatie, neerslag) en ga niet "
    "in op zijpaden zoals getijden of hoe vissen zwemmen. "
    "Geen aanhalingstekens of voorvoegsels — alleen de feedback."
)
BRIEFING_SYSTEM = (
    "Je bent een didactisch adviseur. Op basis van de JSON met de resultaten van een "
    "exit-ticket schrijf je een beknopte, praktische docent-briefing in het Nederlands, "
    "geformatteerd in Markdown, met exact deze secties:\n"
    "## Samenvatting klasprestaties\n"
    "## Veelvoorkomende misvattingen\n"
    "## Voorstel opening volgende les\n"
    "Gebruik uitsluitend de gegevens uit de JSON. Noem bij ongeldige tickets alleen "
    "de leerling-ids uit klas.ongeldige_ids; verzin geen ids, aantallen of oorzaken. "
    "Staan er leerlingen in twijfelgevallen, noem die dan expliciet in de samenvatting: "
    "daar is het nakijkmodel onzeker over de score en kijkt de docent zelf na."
)
BRIEFING_INSTRUCTIE = (
    "\n\nSchrijf de briefing. De opening van de volgende les moet concreet zijn "
    "(5-10 minuten, een directe activiteit die aansluit op de gesignaleerde misvattingen)."
)

# ────────────────────────────────────────────────────────────────────────────
# TERMIKLEURTEN (ANSI, geen extra afhankelijkheid)
# ────────────────────────────────────────────────────────────────────────────

_KLEUR_TOEGESTAAN = (os.environ.get("FORCE_COLOR") or
                     (sys.stdout.isatty() and not os.environ.get("NOCOLOR")))


def _c(code: str) -> str:
    return f"\033[{code}m" if _KLEUR_TOEGESTAAN else ""


class K:
    VET = _c("1")
    DONS = _c("2")
    RESET = _c("0") if _KLEUR_TOEGESTAAN else ""
    CYAN = _c("96")
    GREEN = _c("92")
    MAGENTA = _c("95")
    YELLOW = _c("93")
    RED = _c("91")
    BLUE = _c("94")

STAP_KLEUR = {
    "triage": K.CYAN,
    "scoring": K.GREEN,
    "feedback": K.MAGENTA,
    "briefing": K.YELLOW,
}

# ────────────────────────────────────────────────────────────────────────────
# OUTPUTMAP: de map van dit script; momentopnames en rapporten in resultaten/
# ────────────────────────────────────────────────────────────────────────────

def _output_dir() -> Path:
    base = Path(__file__).resolve().parent
    (base / "resultaten").mkdir(exist_ok=True)
    print(f"  {K.DONS}outputmap: {base / 'resultaten'}{K.RESET}")
    return base


def _lees_dotenv() -> None:
    """Lees NOLAI_API_KEY (en dergelijke) uit .env als de env-variabele ontbreekt."""
    hier = Path(__file__).resolve().parent
    for cand in (hier / ".env", hier.parent / ".env", Path.cwd() / ".env"):
        if cand.is_file():
            for line in cand.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
            return


# ────────────────────────────────────────────────────────────────────────────
# LLM-STEP met model-fallback, retries en "denk-model"-ondersteuning
# ────────────────────────────────────────────────────────────────────────────

class PipelineError(RuntimeError):
    pass


class LLMStep:
    """Eén stap van de estafette: praat met het eerst-beschikbare model.

    Gedrag:
      * probeert de kandidaat-modellen in volgorde;
      * 400/404/405 (bv. 'does not support chat') → direct volgende kandidaat;
      * 429/5xx/timeouts → RETRIES pogingen, dan volgende kandidaat;
      * onthoudt het model dat wél werkt (lock-in) voor de rest van de stap;
      * 'denk-modellen' (Qwen3-stijl) die hun antwoord in reasoning_content
        stoppen, worden afgevangen: content wordt leeggelaten → laatste regel
        van de redenering wordt gebruikt (gemarkeerd).
    """

    def __init__(self, stap_key: str, client: GatewayClient) -> None:
        cfg = STAPPEN[stap_key]
        self.key = stap_key
        self.naam = cfg["naam"]
        self.modellen: list[str] = cfg["modellen"]
        self.temperature = cfg["temperature"]
        self.max_tokens = cfg["max_tokens"]
        self.escalatie_cap = cfg.get("escalatie_cap", 6000)
        self.validate = VALIDATORS.get(stap_key)
        self.client = client
        self.idx = 0
        self.gebruikt = self.modellen[0]      # feitelijk gebruikte model (voor rapportage)
        self._gemeld: set[str] = set()

    def _log(self, msg: str) -> None:
        kleur = STAP_KLEUR[self.key]
        print(f"  {kleur}▸{K.RESET} {msg}")
        LIVE.log(self.key, msg, "info")

    def _meld_eekeermaal(self, model: str, fout: str) -> None:
        if model in self._gemeld:
            return
        self._gemeld.add(model)
        volgende = self.modellen[(self.idx + 1) % len(self.modellen)]
        if len(self.modellen) > 1 and volgende != model:
            extra = f" → substitute: {volgende}"
        else:
            extra = " (geen substitute beschikbaar)"
        print(f"  {K.RED}⚠ {model} onbeschikbaar ({fout[:60]}){extra}{K.RESET}")
        LIVE.stap_uitgevallen(self.key, model, fout[:120])
        LIVE.log(self.key, f"{model} valt uit ({fout[:80]}){extra}", "wissel")

    async def complete(self, system: str, user: str) -> str:
        laatste_fout: Exception | None = None
        start = self.idx          # vastzetten: andere gelijktijdige calls kunnen self.idx wijzigen
        for stap in range(len(self.modellen)):
            model = self.modellen[(start + stap) % len(self.modellen)]
            budget = self.max_tokens
            LIVE.stap_probeert(self.key, model)
            for poging in range(1, RETRIES + 1):
                try:
                    tekst = ""
                    for _escal in range(3):        # denk-fase onaf → grotere budget
                        resp = await self.client.chat.completions.create(
                            model=model,
                            messages=[
                                {"role": "system", "content": system},
                                {"role": "user", "content": user},
                            ],
                            temperature=self.temperature,
                            max_tokens=budget,
                            timeout=TIMEOUT_SEC,
                        )
                        keuze = resp.choices[0]
                        msg = keuze.message
                        tekst = (msg.content or "").strip()
                        redenering = getattr(msg, "reasoning_content", None) or ""
                        if not tekst and redenering:
                            if keuze.finish_reason == "length" and budget < self.escalatie_cap:
                                budget = min(budget * 2, self.escalatie_cap)
                                self._log(f"{model}: 'denk-fase' liep vast → opnieuw "
                                          f"met grotere budget ({budget} tokens)")
                                continue
                            regels = [r.strip() for r in redenering.splitlines() if r.strip()]
                            tekst = regels[-1] if regels else ""
                            self._log(f"{model}: 'denk-fase' onafgemaakt → gebruikte "
                                      f"laatste regel van redenering")
                        break
                    if not tekst:
                        raise PipelineError("géén content én géén redenering")
                    if self.validate is not None and not self.validate(tekst):
                        self._log(f"{model}: antwoord onbruikbaar voor deze taak → "
                                  f"volgende kandidaat")
                        LIVE.stap_uitgevallen(self.key, model, "onbruikbaar antwoord")
                        break
                    self.idx = self.modellen.index(model)   # was: (self.idx + stap), sprong terug bij gelijktijdige calls
                    self.gebruikt = model
                    LIVE.stap_model(self.key, model)
                    return tekst
                except Exception as e:  # noqa: BLE001 — bewust breed, zie classdoc
                    laatste_fout = e
                    status = getattr(e, "status_code", None)
                    msg_err = str(getattr(e, "message", None) or e)
                    if status in (400, 404, 405):          # model-level → volgende kandidaat
                        self._meld_eekeermaal(model, f"HTTP {status} {msg_err}")
                        break
                    if status in (429, 500, 502, 503) or "timeout" in msg_err.lower():
                        if poging < RETRIES:
                            await asyncio.sleep(2 * poging)
                            continue
                        self._meld_eekeermaal(model, f"transiënte fout: {msg_err[:50]}")
                        break
                    # onbekende fout → probeer de volgende kandidaat
                    self._meld_eekeermaal(model, msg_err[:60])
                    break
        raise PipelineError(
            f"Stap '{self.key}' ({self.naam}): géén model gaf een antwoord. "
            f"Laatste fout: {laatste_fout}"
        )


# ────────────────────────────────────────────────────────────────────────────
# PARSEERS (robuust voor kleine/losse modellen)
# ────────────────────────────────────────────────────────────────────────────

def parse_letter(tekst: str, geldig: str) -> str | None:
    """Haal de gekozen optieletter uit het antwoord ('B', 'B.', '(b)', 'B: nee' …)."""
    m = re.match(r"\W*([A-Za-z])(?![A-Za-z])", (tekst or "").strip())
    if m and m.group(1).upper() in geldig:
        return m.group(1).upper()
    return None


# Per-stap validatie: is het model-antwoord bruikbaar voor DEZE taak?
# Onbruikbaar = de kandidaat heeft de taak niet gehaald → volgende kandidaat.
VALIDATORS: dict[str, callable] = {
    "triage": lambda tekst: parse_letter(tekst, "AB") is not None,
    "scoring": lambda tekst: parse_letter(tekst, "ABCDEF") is not None,
}


# ────────────────────────────────────────────────────────────────────────────
# DE VIER STAPPEN
# ────────────────────────────────────────────────────────────────────────────

async def stap1_triage(stap: LLMStep, leerlingen: list[dict]) -> list[dict]:
    """Voorfilter + Tev1: gaat het antwoord over de waterkringloop? (A=ja, B=nee)"""
    sem = asyncio.Semaphore(STAPPEN["triage"]["concurrentie"])

    async def eentje(ler: dict) -> dict:
        reden = voorfilter(ler["antwoord"])
        if reden:                                  # vaste regel: geen model nodig
            print(f"  {ler['id']}  {K.RED}[ONGELDIG]{K.RESET}   "
                  f"{K.DONS}(voorfilter: {reden}){K.RESET}")
            LIVE.leerling(ler["id"], triage="ONGELDIG", triage_model=VOORFILTER_NAAM,
                          triage_reden=reden, triage_s=0.0, actief=None)
            return {**ler, "triage": "ONGELDIG", "triage_door": "voorfilter"}
        async with sem:
            LIVE.leerling(ler["id"], actief="triage")
            t0 = time.monotonic()
            try:
                tekst = await stap.complete(
                    BESLIS_SYSTEM,
                    beslis_bericht(state_triage(ler["antwoord"]), TRIAGE_VRAAG, TRIAGE_OPTIES),
                )
                model = stap.gebruikt
            except PipelineError:
                tekst, model = "", None
            letter = parse_letter(tekst, "AB")
            letter2, reden = None, None
            if letter is None:
                label = "GELDIG"   # onleesbaar → liever doorlaten dan stil wegfilteren
                reden = "antwoord van het model onleesbaar, doorgelaten"
                print(f"  {K.YELLOW}⚠ {ler['id']}: onleesbaar antwoord van het model → doorgeleid als GELDIG{K.RESET}")
            else:
                label = TRIAGE_OPTIES[letter][1]
            if label == "ONGELDIG":                # tweede oordeel voordat iemand apart gaat
                try:
                    tekst2 = await stap.complete(
                        BESLIS_SYSTEM,
                        beslis_bericht(state_triage(ler["antwoord"]), TWEEDE_VRAAG, TWEEDE_OPTIES),
                    )
                except PipelineError:
                    tekst2 = ""
                letter2 = parse_letter(tekst2, "AB")
                if letter2 is None or TWEEDE_OPTIES[letter2][1] == "GELDIG":
                    label = "GELDIG"
                    reden = "eerst 'geen poging', maar volgens de tweede vraag geen onzin: doorgelaten"
                    LIVE.log("triage", f"{ler['id']}: tweede oordeel, toch doorgelaten", "wissel")
                else:
                    reden = "beide vragen: geen poging, onzin"
            icoon = K.GREEN if label == "GELDIG" else K.RED
            print(f"  {ler['id']}  {icoon}[{label}]{K.RESET}   "
                  f"{K.DONS}({time.monotonic() - t0:.1f}s){K.RESET}")
            LIVE.leerling(ler["id"], triage=label, triage_model=model, triage_letter=letter,
                          triage_letter2=letter2, triage_reden=reden,
                          triage_s=round(time.monotonic() - t0, 1), actief=None)
            return {**ler, "triage": label}

    resultaten = await asyncio.gather(*(eentje(l) for l in leerlingen))
    return sorted(resultaten, key=lambda r: r["id"])


async def stap2_scoring(stap: LLMStep, geldig: list[dict],
                        so_client: SystemOneClient | None = None) -> list[dict]:
    """Clef via System One (score + fout + zekerheid in één aanroep).

    Terugval als System One niet bereikbaar is: Nimble via de gateway, met twee
    keuzevragen (score A/B/C en fout-tag A–E), zonder zekerheid.
    """
    sem = asyncio.Semaphore(STAPPEN["scoring"]["concurrentie"])
    so_aan = [so_client is not None]

    async def via_clef(state: str):
        d = await so_client.beslis(SYSTEMONE_MODEL, state, SO_VRAGEN)
        a = d["answers"]
        probs = {int(k): float(v) for k, v in a["score"]["probabilities"].items()}
        score = max(probs, key=probs.get)
        fprobs = a["fout"].get("probabilities") or {a["fout"]["choice"]: a["fout"].get("confidence", 1.0)}
        if score == 2:                           # vaste regel: volle score = geen fout
            sleutel = "geen fout"
        else:                                    # anders de waarschijnlijkste echte fout
            sleutel = max((k for k in fprobs if k != "geen fout"), key=fprobs.get, default="begripsfout")
        return (score, SO_FOUT_TAG.get(sleutel, "[Onleesbaar]"), probs[score],
                fprobs.get(sleutel), {str(k): round(v, 3) for k, v in sorted(probs.items())})

    async def kies(state: str, vraag: str, opties: dict):
        try:
            tekst = await stap.complete(BESLIS_SYSTEM, beslis_bericht(state, vraag, opties))
            return parse_letter(tekst, "".join(opties)), stap.gebruikt
        except PipelineError:
            return None, None

    async def eentje(ler: dict) -> dict:
        async with sem:
            LIVE.leerling(ler["id"], actief="scoring")
            t0 = time.monotonic()
            state = state_scoring(ler["antwoord"])
            extra: dict = {}
            l_score = l_tag = None
            if so_aan[0]:
                LIVE.stap_probeert("scoring", SYSTEMONE_MODEL)
                try:
                    score, tag, zek, tag_zek, probs = await via_clef(state)
                    model = SYSTEMONE_MODEL
                    LIVE.stap_model("scoring", model)
                    extra = {"score_zekerheid": round(zek, 3), "score_probs": probs,
                             "tag_zekerheid": round(tag_zek, 3) if tag_zek is not None else None,
                             "twijfel": zek < TWIJFEL_GRENS}
                except Exception as e:  # noqa: BLE001 — System One weg → terugval
                    if so_aan[0]:
                        so_aan[0] = False
                        fout = str(getattr(e, "message", None) or e)[:100]
                        print(f"  {K.RED}⚠ {SYSTEMONE_MODEL} via System One onbeschikbaar "
                              f"({fout}) → terugval: Nimble{K.RESET}")
                        LIVE.stap_uitgevallen("scoring", SYSTEMONE_MODEL, fout)
                        LIVE.log("scoring", f"{SYSTEMONE_MODEL} via System One valt uit ({fout}) → Nimble", "wissel")
            if not extra:                        # terugval: Nimble, letterkeuze
                l_score, model = await kies(state, SCORE_VRAAG, SCORE_OPTIES)
                score = SCORE_OPTIES[l_score][1] if l_score else None
                if score == 2:                   # vaste regel: volle score = geen fout
                    tag = TAG_OPTIES["A"][1]
                else:                            # anders alleen kiezen uit echte fouten
                    fouten = dict(zip("ABCDE", [v for k, v in TAG_OPTIES.items() if k != "A"]))
                    l_tag, _ = await kies(state, TAG_VRAAG, fouten)
                    tag = fouten[l_tag][1] if l_tag else "[Onleesbaar]"
            if score is None:
                print(f"  {K.YELLOW}⚠ {ler['id']}: score onleesbaar → score None{K.RESET}")
            else:
                kleur = K.GREEN if score == 2 else (K.YELLOW if score == 1 else K.RED)
                zek_txt = f" ({extra['score_zekerheid']:.0%})" if extra else ""
                twijfel_txt = f"  {K.YELLOW}twijfel → docent{K.RESET}" if extra.get("twijfel") else ""
                print(f"  {ler['id']}  {kleur}{score}/2{K.RESET}{zek_txt}  {tag}{twijfel_txt}   "
                      f"{K.DONS}({time.monotonic() - t0:.1f}s){K.RESET}")
            LIVE.leerling(ler["id"], score=score, fout_tag=tag, score_model=model,
                          score_letter=l_score, tag_letter=l_tag,
                          score_s=round(time.monotonic() - t0, 1), actief=None, **extra)
            return {**ler, "score": score, "fout_tag": tag,
                    "zekerheid": extra.get("score_zekerheid"), "twijfel": extra.get("twijfel", False)}

    resultaten = await asyncio.gather(*(eentje(l) for l in geldig))
    return sorted(resultaten, key=lambda r: r["id"])


async def stap3_feedback(stap: LLMStep, gescoord: list[dict]) -> list[dict]:
    """Qwen3.8: 1-2 zinnen empathische, formatieve feedback per leerling."""
    sem = asyncio.Semaphore(STAPPEN["feedback"]["concurrentie"])

    async def eentje(ler: dict) -> dict:
        async with sem:
            LIVE.leerling(ler["id"], actief="feedback")
            t0 = time.monotonic()
            try:
                tekst = await stap.complete(
                    FEEDBACK_SYSTEM,
                    f"Leerling {ler['id']}. Score: {ler['score']}/2. "
                    f"Fout-tag: {ler['fout_tag']}. "
                    f"Antwoord was: \"{ler['antwoord']}\"",
                )
                model = stap.gebruikt
            except PipelineError:
                tekst, model = "", None
            feedback = tekst or "(geen feedback ontvangen — model gaf geen leesbaar antwoord)"
            if not tekst:
                print(f"  {K.YELLOW}⚠ {ler['id']}: feedback ontbreekt{K.RESET}")
            else:
                preview = " ".join(feedback.split())[:90]
                print(f"  {ler['id']}  \"{preview}\"   {K.DONS}({time.monotonic() - t0:.1f}s){K.RESET}")
            LIVE.leerling(ler["id"], feedback=feedback, feedback_model=model,
                          feedback_s=round(time.monotonic() - t0, 1), actief=None)
            return {**ler, "feedback": feedback}

    resultaten = await asyncio.gather(*(eentje(l) for l in gescoord))
    return sorted(resultaten, key=lambda r: r["id"])


async def stap4_briefing(stap: LLMStep, resultaten: list[dict],
                         klassetotaal: int, n_geldig: int,
                         ongeldige_ids: list[str] = ()) -> tuple[str, dict, bool]:
    """Qwen3.8: aggegreerde JSON → docent-briefing. (fallback: lokale briefing)"""
    scores = [r["score"] for r in resultaten if r["score"] is not None]
    gemiddeld = round(sum(scores) / len(scores), 2) if scores else None
    verdeling = {str(s): scores.count(s) for s in (0, 1, 2)}
    tag_teller: dict[str, int] = {}
    for r in resultaten:
        tag_teller[r["fout_tag"]] = tag_teller.get(r["fout_tag"], 0) + 1

    payload = {
        "exit_ticket_vraag": VRAAG,
        "klas": {
            "aantal_leerlingen": klassetotaal,
            "geldig": n_geldig,
            "ongeldig": klassetotaal - n_geldig,
            "ongeldige_ids": list(ongeldige_ids),
        },
        "scores": {
            "gemiddeld": gemiddeld,
            "verdeling": verdeling,
        },
        "fout_tags": dict(sorted(tag_teller.items(), key=lambda kv: -kv[1])),
        "twijfelgevallen": [
            {"id": r["id"], "score": r["score"], "zekerheid": r.get("zekerheid")}
            for r in resultaten if r.get("twijfel")
        ],
        "leerlingen": [
            {"id": r["id"], "score": r["score"], "fout_tag": r["fout_tag"],
             "zekerheid_score": r.get("zekerheid"),
             "antwoord": r["antwoord"], "feedback": r["feedback"]}
            for r in resultaten
        ],
    }

    try:
        tekst = await stap.complete(
            BRIEFING_SYSTEM,
            json.dumps(payload, ensure_ascii=False, indent=2) + BRIEFING_INSTRUCTIE,
        )
        if not tekst.strip():
            raise PipelineError("leeg antwoord")
        return tekst, payload, False
    except PipelineError as e:
        print(f"  {K.RED}⚠ Qwen-briefing mislukt ({e}) → lokale fallback-briefing gegenereerd{K.RESET}")
        return lokale_briefing(payload), payload, True


def lokale_briefing(payload: dict) -> str:
    """Deterministische fallback als géén model beschikbaar is voor stap 4."""
    tags = payload["fout_tags"]
    top = ", ".join(f"{t} ({n})" for t, n in list(tags.items())[:3])
    gem = payload["scores"]["gemiddeld"]
    return (
        "## Samenvatting klasprestaties\n"
        f"Gemiddelde score {gem}/2 over {payload['klas']['geldig']} geldige antwoorden "
        f"({payload['klas']['ongeldig']} leerlingen niet beoordeeld door triage).\n\n"
        "## Veelvoorkomende misvattingen\n"
        f"- {top}\n\n"
        "## Voorstel opening volgende les\n"
        "- Open met een 5-minuten 'concept cart': laat leerlingen in tweetallen de drie fases "
        "van de waterkringloop op een rijtje zetten en vergelijk direct met de klassenoplossing."
    )


# ────────────────────────────────────────────────────────────────────────────
# MARKDOWN-RAPPORT
# ────────────────────────────────────────────────────────────────────────────

def _mdcel(tekst: str | None) -> str:
    return (tekst or "").replace("|", "\\|").replace("\n", "<br>").strip()


def bouw_markdown(t0: float, klassetotaal: int, triage_res: list[dict],
                  feedback_res: list[dict], briefing: str, briefing_lokaal: bool,
                  payload: dict, staps_modellen: list[tuple[str, str, str, float]]) -> str:
    nu = datetime.now().strftime("%Y-%m-%d %H:%M")
    L: list[str] = []
    L.append("# Formative Assessment Pipeline — Resultaat")
    L.append("")
    L.append(f"_Genereerd op {nu} · endpoint `{BASE_URL}` · "
             f"estafette: " + " → ".join(c["naam"] for c in STAPPEN.values()) + "_")
    L.append("")
    L.append("## De opgave")
    L.append("")
    L.append(f"> {VRAAG}")
    L.append("")
    L.append(f"{klassetotaal} synthetische leerlingantwoorden (exit-ticket) zijn door de "
             "pijplijn gelopen: triage, foutenscoring, gepersonaliseerde feedback en een "
             "docent-briefing.")
    L.append("")
    L.append("## De estafette (welk model deed wat)")
    L.append("")
    L.append("| Stap | Rol | Model | Substituent gebruikt? | Duur |")
    L.append("|------|-----|-------|-----------------------|------|")
    for rol, model, naam, duur in staps_modellen:
        subs = "ja" if model != STAPPEN[rol]["modellen"][0] else "nee"
        L.append(f"| {rol.capitalize()} | {STAPPEN[rol]['rol']} | `{model}` | {subs} | {duur:.0f}s |")
    L.append("")
    L.append(f"## Stap 1 — Triage ({STAPPEN['triage']['naam']})")
    L.append("")
    L.append("| Leerling | Antwoord (uitsnede) | Classificatie |")
    L.append("|----------|---------------------|---------------|")
    for r in triage_res:
        ant = (r["antwoord"] or "(leeg)")[:70]
        L.append(f"| {r['id']} | {_mdcel(ant)} | {r['triage']} |")
    L.append("")
    L.append(f"## Stap 2 — Scoring & Stap 3 — Feedback ({STAPPEN['scoring']['naam']} + {STAPPEN['feedback']['naam']})")
    L.append("")
    L.append("| Leerling | Score | Fout-tag | Feedback |")
    L.append("|----------|-------|----------|----------|")
    for r in feedback_res:
        score = f"{r['score']}/2" if r["score"] is not None else "—"
        L.append(f"| {r['id']} | {score} | {_mdcel(r['fout_tag'])} | {_mdcel(r['feedback'])} |")
    L.append("")
    L.append("## Stap 4 — Docent-briefing")
    L.append("")
    if briefing_lokaal:
        L.append("_Qwen was niet beschikbaar; dit is de deterministische fallback-briefing._")
        L.append("")
    L.append(briefing.strip())
    L.append("")
    L.append("## Aggegreerde data (JSON die naar Qwen werd gestuurd)")
    L.append("")
    L.append("```json")
    L.append(json.dumps(payload, ensure_ascii=False, indent=2))
    L.append("```")
    L.append("")
    L.append("---")
    L.append(f"_Gegenereerd door `pipeline.py` in {time.monotonic() - t0:.0f}s "
             f"totaal. Regenereer met: `python pipeline.py`_")
    return "\n".join(L)


# ────────────────────────────────────────────────────────────────────────────
# HOOFD
# ────────────────────────────────────────────────────────────────────────────

def _banner(n_leerlingen: int) -> None:
    line = "═" * 72
    print(f"\n{K.VET}{line}")
    print("   FORMATIVE ASSESSMENT PIPELINE — LLM-estafette (4 modellen)")
    print(line + K.RESET)
    print(f"  {K.DONS}vraag:{K.RESET}   {VRAAG}")
    print(f"  {K.DONS}klas:{K.RESET}    {n_leerlingen} leerlingen (synthetische exit-tickets)")
    print(f"  {K.DONS}endpoint:{K.RESET} {BASE_URL}")
    print(f"\n  {K.VET}ESTAFETTE:{K.RESET}")
    volgorde = ("triage", "scoring", "feedback", "briefing")
    for nr, key in enumerate(volgorde, start=1):
        cfg = STAPPEN[key]
        kleur = STAP_KLEUR[key]
        print(f"   [{nr}] {kleur}{cfg['naam']:<7}{K.RESET} {cfg['modellen'][0]:<28} "
              f"{K.DONS}{cfg['rol']}{K.RESET}")
    print()


def _stap_header(nr: int, titel: str, kleur: str, model: str) -> None:
    bar = "─" * 72
    print(f"\n{kleur}{K.VET}{bar}")
    print(f"  STAP {nr}/4 · {titel}   [model: {model}]")
    print(bar + K.RESET)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Formative Assessment Pipeline (LLM-estafette)")
    parser.add_argument("--limiet", type=int, default=0,
                        help="slechts de eerste N leerlingen verwerken (snelle test)")
    parser.add_argument("--simulatie", action="store_true",
                        help="geen gateway: speel opgenomen modelantwoorden na")
    parser.add_argument("--tempo", type=float, default=1.0,
                        help="simulatie: hoeveel keer sneller dan echt (standaard 1 = echte snelheid)")
    parser.add_argument("--geen-browser", action="store_true",
                        help="dashboard.html niet automatisch openen")
    args = parser.parse_args()
    global LIVE

    sim_bron = Path(__file__).resolve().parent / "simulatie_data.json"
    if args.simulatie:
        if not sim_bron.is_file():
            print(f"\n{K.RED}FOUT: {sim_bron.name} ontbreekt; zonder opname geen simulatie.{K.RESET}")
            return 1
        sim_data = laad_simulatiedata(sim_bron)
        client = SimClient(sim_data, args.tempo)
        heeft_so = any(r.get("score_probs") for r in sim_data.get("leerlingen", {}).values())
        so_client = client if heeft_so else None
    else:
        _lees_dotenv()
        api_key = os.environ.get("NOLAI_API_KEY", "").strip()
        if not api_key:
            print(f"\n{K.RED}FOUT: NOLAI_API_KEY is niet gevonden (env of .env).{K.RESET}")
            return 1
        client = GatewayClient(BASE_URL, api_key, TIMEOUT_SEC)
        so_key = os.environ.get("LITELLM_API_KEY", "").strip()
        so_client = SystemOneClient(LITELLM_URL, so_key, TIMEOUT_SEC) if so_key else None
        if not so_key:
            print(f"\n{K.YELLOW}⚠ LITELLM_API_KEY niet gevonden: scoring valt terug op Nimble "
                  f"(zonder zekerheid).{K.RESET}")
    leerlingen = LEERLINGEN if args.limiet <= 0 else LEERLINGEN[:args.limiet]
    klassetotaal = len(leerlingen)

    t0 = time.monotonic()
    _banner(klassetotaal)
    output_dir = _output_dir()
    LIVE = Live(output_dir, STAPPEN, VRAAG, leerlingen, BASE_URL,
                "simulatie" if args.simulatie else "live",
                sim_data.get("bron") if args.simulatie else None)
    dashboard = output_dir / "dashboard.html"
    print(f"  {K.DONS}dashboard:{K.RESET} {dashboard}")
    if dashboard.is_file() and not args.geen_browser:
        try:
            webbrowser.open(dashboard.resolve().as_uri())
        except Exception:  # noqa: BLE001 — geen browser (sandbox/ssh): gewoon doorgaan
            pass
    staps_modellen: list[tuple[str, str, str, float]] = []

    # ── STAP 1: TRIAGE ─────────────────────────────────────────────────────
    stap1 = LLMStep("triage", client)
    LIVE.stap_start("triage")
    t1 = time.monotonic()
    _stap_header(1, "TRIAGE", K.CYAN, stap1.modellen[0])
    try:
        triage_res = await stap1_triage(stap1, leerlingen)
    except PipelineError as e:
        print(f"\n{K.RED}{e}{K.RESET}")
        LIVE.fout(str(e))
        return 1
    geldig = [r for r in triage_res if r["triage"] == "GELDIG"]
    staps_modellen.append(("triage", stap1.gebruikt, stap1.naam, time.monotonic() - t1))
    LIVE.stap_klaar("triage", stap1.gebruikt, time.monotonic() - t1)
    print(f"\n  → {K.GREEN}{len(geldig)}{K.RESET}/{klassetotaal} geldig doorgezet naar stap 2 "
          f"({K.RED}{klassetotaal - len(geldig)}{K.RESET} gefilterd)")
    if not geldig:
        print(f"\n{K.RED}Geen enkel geldig antwoord — pipeline gestopt.{K.RESET}")
        LIVE.fout("Geen enkel geldig antwoord, pipeline gestopt")
        return 1

    # ── STAP 2: SCORING ────────────────────────────────────────────────────
    stap2 = LLMStep("scoring", client)
    LIVE.stap_start("scoring")
    t2 = time.monotonic()
    _stap_header(2, "SCORING + FOUTEN-TAGS", K.GREEN, stap2.modellen[0])
    try:
        gescoord = await stap2_scoring(stap2, geldig, so_client)
    except PipelineError as e:
        print(f"\n{K.RED}{e}{K.RESET}")
        LIVE.fout(str(e))
        return 1
    staps_modellen.append(("scoring", stap2.gebruikt, stap2.naam, time.monotonic() - t2))
    LIVE.stap_klaar("scoring", stap2.gebruikt, time.monotonic() - t2)

    # ── STAP 3: FEEDBACK ───────────────────────────────────────────────────
    stap3 = LLMStep("feedback", client)
    LIVE.stap_start("feedback")
    t3 = time.monotonic()
    _stap_header(3, "GEPERSONALISEERDE FEEDBACK", K.MAGENTA, stap3.modellen[0])
    try:
        met_feedback = await stap3_feedback(stap3, gescoord)
    except PipelineError as e:
        print(f"\n{K.RED}{e}{K.RESET}")
        LIVE.fout(str(e))
        return 1
    staps_modellen.append(("feedback", stap3.gebruikt, stap3.naam, time.monotonic() - t3))
    LIVE.stap_klaar("feedback", stap3.gebruikt, time.monotonic() - t3)

    # ── STAP 4: DOCENT-BRIEFING ────────────────────────────────────────────
    stap4 = LLMStep("briefing", client)
    LIVE.stap_start("briefing")
    t4 = time.monotonic()
    _stap_header(4, "DOCENT-BRIEFING + ACTIEPLAN", K.YELLOW, stap4.modellen[0])
    ongeldige_ids = [r["id"] for r in triage_res if r["triage"] == "ONGELDIG"]
    briefing, payload, lokale = await stap4_briefing(stap4, met_feedback, klassetotaal,
                                                     len(geldig), ongeldige_ids)
    LIVE.briefing(briefing, stap4.gebruikt if not lokale else "lokale fallback", lokale, payload)
    staps_modellen.append(("briefing", stap4.gebruikt, stap4.naam, time.monotonic() - t4))
    LIVE.stap_klaar("briefing", stap4.gebruikt, time.monotonic() - t4)
    preview = " ".join(briefing.split())[:220]
    print(f"\n  {K.YELLOW}▸ briefing ({len(briefing)} tekens){K.RESET}")
    print(f"    {preview}…")

    # ── RAPPORT ────────────────────────────────────────────────────────────
    markdown = bouw_markdown(t0, klassetotaal, triage_res, met_feedback,
                             briefing, lokale, payload, staps_modellen)
    pad = output_dir / "resultaten" / "resultaat_formative_assessment.md"
    if not args.simulatie:                 # simulatie overschrijft het echte rapport niet
        pad.write_text(markdown, encoding="utf-8")
        if args.limiet <= 0:               # alleen volledige, geslaagde runs worden de nieuwe simulatie
            if bewaar_opname(sim_bron, LIVE.state):
                print(f"  {K.GREEN}✓ opgeslagen als simulatie: {sim_bron.name}{K.RESET}")
            else:
                print(f"  {K.YELLOW}⚠ run niet volledig geslaagd: {sim_bron.name} niet overschreven{K.RESET}")
    snapshot = LIVE.klaar()

    scores = [r["score"] for r in met_feedback if r["score"] is not None]
    gem = round(sum(scores) / len(scores), 2) if scores else None
    bar = "═" * 72
    print(f"\n{K.VET}{bar}")
    print("   RESULTAAT")
    print(bar + K.RESET)
    print(f"  leerlingen:   {klassetotaal} (geldig {len(geldig)} / ongeldig {klassetotaal - len(geldig)})")
    print(f"  gem. score:   {gem}/2 (n={len(scores)})")
    print(f"  totaal:       {time.monotonic() - t0:.0f}s")
    if not args.simulatie:
        print(f"  {K.GREEN}✓ rapport: {pad}{K.RESET}")
    if snapshot:
        print(f"  {K.GREEN}✓ dashboard-momentopname: {snapshot}{K.RESET}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print(f"\n{K.YELLOW}Afgebroken door gebruiker.{K.RESET}")
        sys.exit(130)
