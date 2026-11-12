"""Diagnostic SDK a sorties publiques fermees ; execution sur runner GitHub."""
import json
import os
import re
from pathlib import Path

MAX_BYTES = 8_000_000
EVENTS = ("system", "assistant", "user", "result", "rate_limit_event")
FIELDS = ("result", "errors", "api_error_status", "api_error",
          "terminal_reason", "stop_reason", "permission_denials")
RULES = {
    "authentification": ("unauthorized", "authentication_error", "invalid api key",
                         "token expired", "not logged in", "invalid oauth"),
    "limitation": ("rate_limit", "rate limit", "usage limit", "session limit", "weekly limit"),
    "facturation": ("credit balance", "payment required", "billing_error"),
    "modele": ("model not found", "invalid model", "model_not_found"),
    "reseau": ("econnrefused", "enotfound", "etimedout", "connection error",
               "fetch failed", "tls", "certificate"),
    "service": ("overloaded_error", "internal_server_error"),
    "configuration": ("invalid settings", "failed to parse", "invalid configuration"),
    "hook": ("hook failed", "hook error", "hook timed out"),
}


def bounded_text(path):
    if path.is_symlink():
        return None, "lien_refuse"
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return None, "trop_volumineux"
        return raw.decode("utf-8"), "lisible"
    except (OSError, UnicodeError):
        return None, "absent_ou_illisible"


def shape(value, present):
    if not present:
        return "absent"
    if value is None:
        return "null"
    if isinstance(value, str):
        return "texte_non_vide" if value else "texte_vide"
    if isinstance(value, list):
        return "liste_non_vide" if value else "liste_vide"
    if type(value) is int:
        return "entier"
    if type(value) is bool:
        return "booleen"
    return "autre"


def categories(text):
    lowered = text.lower()
    return [label for label, patterns in RULES.items()
            if any(pattern in lowered for pattern in patterns)]


def report(execution, debug):
    # Toutes les valeurs emises sont des constantes ou des entiers bornes.
    lines = []
    text, state = bounded_text(execution)
    lines.append("SDK fichier : " + state)
    messages = []
    if text is not None:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                messages = [m for m in parsed if isinstance(m, dict)]
                lines.append("SDK format : liste")
            else:
                lines.append("SDK format : inattendu")
        except (ValueError, RecursionError):
            lines.append("SDK format : json_invalide")
    for kind in EVENTS:
        lines.append("SDK evenements " + kind + " : " +
                     str(min(sum(m.get("type") == kind for m in messages), 9999)))
    unknown = sum(m.get("type") not in EVENTS for m in messages)
    lines.append("SDK evenements autres : " + str(min(unknown, 9999)))
    texts = []
    for index, message in enumerate(m for m in messages if m.get("type") == "result"):
        if index >= 8:
            lines.append("SDK resultats : tronques")
            break
        for field in FIELDS:
            lines.append("SDK resultat " + field + " : " +
                         shape(message.get(field), field in message))
        status = message.get("api_error_status")
        if type(status) is int and 100 <= status <= 599:
            lines.append("SDK HTTP : " + str(status))
        for field in ("result", "errors", "api_error", "terminal_reason"):
            value = message.get(field)
            if isinstance(value, str):
                texts.append(value)
            elif isinstance(value, list):
                texts.extend(v for v in value if isinstance(v, str))
    for message in messages:
        value = message.get("error")
        if isinstance(value, str):
            texts.append(value)
    for label in categories("\n".join(texts)):
        lines.append("SDK indice : " + label)

    text, state = bounded_text(debug)
    lines.append("Journal prive : " + state)
    if text is not None:
        labels = categories(text)
        for label in labels:
            lines.append("Journal indice : " + label)
        # Codes uniquement lies a un libelle de statut ; jamais de texte libre.
        codes = sorted({int(m) for m in re.findall(
            r"(?i)\b(?:http(?:/\d(?:\.\d)?)?|status(?:[_ ]code)?)\s*[:=]?\s*([1-5]\d{2})\b",
            text)})
        for status in codes:
            lines.append("Journal HTTP possible : " + str(status))
        if not labels and not codes:
            lines.append("Journal indice : aucun_reconnu")
    lines.append("Diagnostic : indices seulement ; aucune cause deduite de leur absence")
    return lines


def main():
    temp = Path(os.environ["RUNNER_TEMP"])
    paths = (temp / "claude-execution-output.json", temp / "claude-sdk-startup.log")
    try:
        try:
            lines = report(*paths)
        except Exception:
            # Ne jamais publier un message d'exception contenant des donnees brutes.
            lines = ["Diagnostic : analyse_impossible"]
        for line in lines:
            print(line)
    finally:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                print("Diagnostic : nettoyage_impossible")


if __name__ == "__main__":
    main()
