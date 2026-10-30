# -*- coding: utf-8 -*-
"""
Live-dashboard en simulatie voor de Formative Assessment Pipeline.

* Live     schrijft de toestand van de run naar `live_state.js` (naast
           dashboard.html). Het dashboard laadt dat bestand elke seconde
           opnieuw in, ook als je het gewoon dubbelklikt (file://).
* GatewayClient praat met de Ollama-route van de gateway (think=false).
* SimClient speelt de laatste echte run na, met de echte wachttijden,
           zodat je de demo kunt oefenen zonder gateway.
* voorfilter  vaste regel vóór de triage: leeg of geen enkele letter = ONGELDIG.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

STATE_BESTAND = "live_state.js"
DASHBOARD_BESTAND = "dashboard.html"
VOORFILTER_NAAM = "voorfilter (vaste regel)"


def _nu_ms() -> int:
    return int(time.time() * 1000)


# ────────────────────────────────────────────────────────────────────────────
# VOORFILTER
# ────────────────────────────────────────────────────────────────────────────

def voorfilter(antwoord: str | None) -> str | None:
    """Geeft een reden als het antwoord zonder model ONGELDIG is, anders None."""
    tekst = (antwoord or "").strip()
    if not tekst:
        return "leeg antwoord"
    if not re.search(r"[^\W\d_]", tekst):          # geen enkele letter
        return "geen tekst, alleen cijfers of tekens"
    return None


# ────────────────────────────────────────────────────────────────────────────
# LIVE-TOESTAND
# ────────────────────────────────────────────────────────────────────────────

class Uit:
    """Doet niets; gebruikt zolang er geen dashboard actief is."""

    def __getattr__(self, _naam):
        return lambda *a, **k: None


class Live:
    def __init__(self, map_: Path, stappen: dict, vraag: str, leerlingen: list[dict],
                 endpoint: str, modus: str, bron: str | None = None) -> None:
        self.map = map_
        self.pad = map_ / STATE_BESTAND
        self.state: dict = {
            "versie": 1,
            "run_id": _nu_ms(),
            "modus": modus,                    # "live" | "simulatie"
            "bron": bron,                      # bij simulatie: welke opname
            "status": "bezig",                 # "bezig" | "klaar" | "fout"
            "gestart": _nu_ms(),
            "klaar_op": None,
            "fout": None,
            "vraag": vraag,
            "endpoint": endpoint,
            "stappen": {
                k: {
                    "naam": c["naam"], "rol": c["rol"],
                    "bedoeld": c["modellen"][0], "kandidaten": c["modellen"],
                    "probeert": None, "gebruikt": None, "uitgevallen": [],
                    "status": "wacht", "gestart": None, "duur": None,
                }
                for k, c in stappen.items()
            },
            "leerlingen": [
                {"id": l["id"], "antwoord": l["antwoord"], "verwacht": l.get("verwacht"),
                 "actief": None, "actief_sinds": None}
                for l in leerlingen
            ],
            "log": [],
            "briefing": None,
        }
        self._idx = {l["id"]: i for i, l in enumerate(self.state["leerlingen"])}
        self.log(None, f"Run gestart: {len(leerlingen)} exit-tickets", "info")

    # -- schrijven ----------------------------------------------------------
    def _schrijf(self) -> None:
        tekst = ("window.__clefState && window.__clefState("
                 + json.dumps(self.state, ensure_ascii=False) + ");\n")
        tmp = self.pad.with_name(self.pad.name + ".tmp")
        try:
            tmp.write_text(tekst, encoding="utf-8")
            for _ in range(40):                 # Windows: browser kan het bestand even vasthouden
                try:
                    os.replace(tmp, self.pad)
                    return
                except PermissionError:
                    time.sleep(0.05)
        except OSError:
            pass                                # dashboard is bijzaak; de run gaat door

    # -- gebeurtenissen -----------------------------------------------------
    def log(self, stap: str | None, tekst: str, soort: str = "info") -> None:
        self.state["log"].append({"t": _nu_ms(), "stap": stap, "soort": soort, "tekst": tekst})
        self.state["log"] = self.state["log"][-250:]
        self._schrijf()

    def stap_start(self, stap: str) -> None:
        s = self.state["stappen"][stap]
        s["status"], s["gestart"] = "bezig", _nu_ms()
        self.log(stap, f"{s['naam']} neemt het stokje over", "stokje")

    def stap_probeert(self, stap: str, model: str) -> None:
        s = self.state["stappen"][stap]
        if s["probeert"] != model:
            s["probeert"] = model
            self._schrijf()

    def stap_uitgevallen(self, stap: str, model: str, reden: str) -> None:
        s = self.state["stappen"][stap]
        if model not in [u["model"] for u in s["uitgevallen"]]:
            s["uitgevallen"].append({"model": model, "reden": reden})

    def stap_model(self, stap: str, model: str) -> None:
        s = self.state["stappen"][stap]
        if s["gebruikt"] != model:
            s["gebruikt"] = model
            self._schrijf()

    def stap_klaar(self, stap: str, model: str, duur: float) -> None:
        s = self.state["stappen"][stap]
        s["status"], s["duur"] = "klaar", round(duur, 1)
        if model:
            s["gebruikt"] = model
        self.log(stap, f"{s['naam']} klaar in {_mmss(duur)}", "klaar")

    def leerling(self, lid: str, **velden) -> None:
        i = self._idx.get(lid)
        if i is None:
            return
        rij = self.state["leerlingen"][i]
        if "actief" in velden:
            rij["actief_sinds"] = _nu_ms() if velden["actief"] else None
        rij.update(velden)
        self._schrijf()

    def briefing(self, markdown: str, model: str, lokaal: bool, payload: dict) -> None:
        self.state["briefing"] = {"markdown": markdown, "model": model,
                                  "lokaal": lokaal, "payload": payload}
        self._schrijf()

    def fout(self, melding: str) -> None:
        self.state["status"], self.state["fout"] = "fout", melding
        self.state["klaar_op"] = _nu_ms()
        self.log(None, melding, "fout")

    def klaar(self) -> Path | None:
        """Markeer de run als klaar en bewaar een losse HTML-momentopname."""
        self.state["status"], self.state["klaar_op"] = "klaar", _nu_ms()
        duur = (self.state["klaar_op"] - self.state["gestart"]) / 1000
        self.log(None, f"Estafette klaar in {_mmss(duur)}", "klaar")
        sjabloon = self.map / DASHBOARD_BESTAND
        if not sjabloon.is_file():
            return None
        stempel = datetime.now().strftime("%Y%m%d-%H%M")
        prefix = "resultaat_simulatie_" if self.state["modus"] == "simulatie" else "resultaat_"
        doel = self.map / "resultaten" / f"{prefix}{stempel}.html"
        doel.parent.mkdir(exist_ok=True)
        data = json.dumps(self.state, ensure_ascii=False).replace("</", "<\\/")
        html = sjabloon.read_text(encoding="utf-8").replace(
            "<!--INLINE-STATE-->", f"<script>window.__clefInline = {data};</script>", 1)
        doel.write_text(html, encoding="utf-8")
        return doel


def _mmss(sec: float) -> str:
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"


# ────────────────────────────────────────────────────────────────────────────
# GATEWAY (Ollama-route van Open WebUI, met think=false)
# ────────────────────────────────────────────────────────────────────────────

class _HttpFout(Exception):
    def __init__(self, status: int | None, melding: str) -> None:
        super().__init__(melding)
        self.status_code = status
        self.message = melding


def _zonder_sleutel(tekst: str, sleutel: str) -> str:
    """Haal de API-sleutel (of een stuk ervan) uit foutmeldingen voordat ze gelogd worden."""
    tekst = str(tekst)
    if sleutel:
        tekst = tekst.replace(sleutel, "<sleutel>")
    return re.sub(r"sk-[A-Za-z0-9_\-]{4,}", "sk-<verborgen>", tekst)


def _post_json(url: str, sleutel: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {sleutel}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read()[:300].decode("utf-8", "replace")
        raise _HttpFout(e.code, _zonder_sleutel(f"Error code: {e.code} - {detail}", sleutel)) from None
    except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
        raise _HttpFout(None, _zonder_sleutel(f"timeout of verbindingsfout: {e}", sleutel)) from None
    except Exception as e:  # noqa: BLE001 — bv. ongeldige header: nooit de sleutel doorgeven
        raise _HttpFout(None, _zonder_sleutel(f"{type(e).__name__}: {e}", sleutel)) from None


def _antwoord(tekst: str, denk: str | None = None, reden: str = "stop"):
    """Antwoord in dezelfde vorm als de OpenAI-client, zodat LLMStep ongewijzigd blijft."""
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=tekst, reasoning_content=denk or None),
        finish_reason=reden)])


class GatewayClient:
    """Praat met https://chat.nolai.nl/ollama/api/chat. Alleen standaardbibliotheek.

    think=false is hier essentieel: via de OpenAI-compatibele route laat het
    denken zich niet uitzetten en kost één keuze van Tev1 30–130 s; via deze
    route ±0,5 s.
    """

    def __init__(self, url: str, api_key: str, timeout: float) -> None:
        self.url, self.key, self.timeout = url, api_key.strip(), timeout
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, model: str, messages: list[dict], temperature: float = 0.0,
                      max_tokens: int = 256, timeout: float | None = None, **_kw):
        body = {"model": model, "messages": messages, "stream": False, "think": False,
                "options": {"temperature": temperature, "num_predict": max_tokens}}
        data = await asyncio.to_thread(self._post, body, timeout or self.timeout)
        msg = data.get("message") or {}
        return _antwoord((msg.get("content") or "").strip(), msg.get("thinking"),
                         data.get("done_reason") or "stop")

    def _post(self, body: dict, timeout: float | None = None) -> dict:
        return _post_json(self.url, self.key, body, timeout or self.timeout)


class SystemOneClient:
    """LiteLLM /v1/systemone: een state plus benoemde vragen → per vraag een
    gekalibreerd antwoord met kansen. Voor beslismodellen zoals Clef."""

    def __init__(self, url: str, api_key: str, timeout: float) -> None:
        self.url, self.key, self.timeout = url, api_key.strip(), timeout

    async def beslis(self, model: str, state: str, questions: dict) -> dict:
        body = {"model": model, "state": state, "questions": questions}
        return await asyncio.to_thread(self._post, body)

    def _post(self, body: dict, timeout: float | None = None) -> dict:
        return _post_json(self.url, self.key, body, timeout or self.timeout)


# ────────────────────────────────────────────────────────────────────────────
# OPNAME + SIMULATIE
# ────────────────────────────────────────────────────────────────────────────

_OPNAME_VELDEN = ("antwoord", "triage", "triage_letter", "triage_letter2", "triage_reden", "triage_model", "triage_s",
                  "score", "score_letter", "fout_tag", "tag_letter", "score_model", "score_s",
                  "score_zekerheid", "score_probs", "tag_zekerheid", "twijfel",
                  "feedback", "feedback_model", "feedback_s")


def bewaar_opname(pad: Path, state: dict) -> bool:
    """Sla een geslaagde echte run op als simulatie_data.json (de simulatie speelt die na).

    Een run met ontbrekende feedback of een reserve-briefing wordt niet opgeslagen,
    zodat een haperende gateway de bestaande opname niet overschrijft.
    """
    geldig = [l for l in state["leerlingen"] if l.get("triage") == "GELDIG"]
    briefing = state.get("briefing") or {}
    if briefing.get("lokaal") or not briefing.get("markdown") or any(not l.get("feedback_model") for l in geldig):
        return False
    data = {
        "bron": f"echte run van {datetime.now():%d-%m-%Y %H:%M}",
        "leerlingen": {l["id"]: {k: l.get(k) for k in _OPNAME_VELDEN} for l in state["leerlingen"]},
        "briefing": (state.get("briefing") or {}).get("markdown"),
        "briefing_s": state["stappen"]["briefing"].get("duur"),
    }
    pad.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


class SimClient:
    """Bootst de gateway na met de opgenomen antwoorden én wachttijden van een echte run.

    Gedraagt zich zoals de gateway op 29-10-2026: tev1:4b geeft 400
    'does not support chat', tev1:0.8b neemt het over.
    """

    GEEN_CHAT = {"ERASMUS.tev1:4b"}

    def __init__(self, data: dict, tempo: float) -> None:
        self.data = data
        self.tempo = max(float(tempo), 0.1)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _wacht(self, sec) -> None:
        await asyncio.sleep(max(float(sec or 1.0), 0.05) / self.tempo)

    async def beslis(self, model: str, state: str, questions: dict) -> dict:
        """Naspelen van Clef via System One, met de opgenomen kansen."""
        rij = self._zoek(state)
        await self._wacht(rij.get("score_s") or 4)
        probs = rij.get("score_probs") or {"0": 0.1, "1": 0.8, "2": 0.1}
        sleutel = (rij.get("fout_tag") or "[Begripsfout]").strip("[]").lower()
        zek = rij.get("tag_zekerheid") or 0.9
        return {"answers": {"score": {"probabilities": probs},
                            "fout": {"choice": sleutel, "confidence": zek,
                                     "probabilities": {sleutel: zek}}}}

    def _zoek(self, state: str) -> dict:
        for rij in self.data.get("leerlingen", {}).values():
            if rij.get("antwoord") and rij["antwoord"] in state:
                return rij
        return {}

    async def _create(self, model: str, messages: list[dict], **_kw):
        system, user = messages[0]["content"], messages[-1]["content"]
        await asyncio.sleep(random.uniform(0.05, 0.15))
        if model in self.GEEN_CHAT:
            raise _HttpFout(400, f'Error code: 400 - "{model.split(".", 1)[-1]}" does not support chat')

        if "didactisch" in system:
            await self._wacht(self.data.get("briefing_s") or 45)
            return _antwoord(self.data.get("briefing") or "## Samenvatting klasprestaties\n(geen opname)")
        if "empathische" in system:
            m = re.search(r"Leerling (L\d+)", user)
            rij = self.data.get("leerlingen", {}).get(m.group(1) if m else "", {})
            await self._wacht(rij.get("feedback_s") or 4)
            return _antwoord(rij.get("feedback") or "Goed dat je het probeert. Noem nu de drie fasen op volgorde.")

        vraag = json.loads(user)
        rij = self._zoek(vraag.get("state", ""))
        q = vraag.get("question", "")
        if "onzin" in q:                                   # tweede oordeel triage
            await self._wacht(0.5)
            letter = rij.get("triage_letter2") or "A"
        elif "poging" in q:
            await self._wacht(rij.get("triage_s") or 0.5)
            letter = rij.get("triage_letter") or ("B" if rij.get("triage") == "ONGELDIG" else "A")
        elif "score" in q:
            await self._wacht((rij.get("score_s") or 2) / 2)
            letter = rij.get("score_letter") or {2: "A", 1: "B", 0: "C"}.get(rij.get("score"), "B")
        else:
            await self._wacht((rij.get("score_s") or 2) / 2)
            letter = rij.get("tag_letter") or "F"
        return _antwoord(letter)


def laad_simulatiedata(pad: Path) -> dict:
    return json.loads(pad.read_text(encoding="utf-8"))
