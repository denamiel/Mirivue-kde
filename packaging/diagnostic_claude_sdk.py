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
                         "token expired", "not logged in", "invalid oauth",
                         "invalid bearer token", "invalid authentication credentials",
                         "missing authentication", "login required"),
    "limitation": ("rate_limit", "rate limit", "usage limit", "session limit", "weekly limit"),
    "facturation": ("credit balance", "payment required", "billing_error"),
    "modele": ("model not found", "invalid model", "model_not_found"),
    "reseau": ("econnrefused", "enotfound", "etimedout", "connection error",
               "fetch failed", "tls handshake failed", "certificate verify failed",
               "unable to verify the first certificate"),
    "service": ("overloaded_error", "internal_server_error"),
    "configuration": ("invalid settings", "failed to parse", "invalid configuration"),
    "hook": ("hook failed", "hook error", "hook timed out"),
}


# Les noms ci-dessous sont des etiquettes fixes, jamais des URL imprimees.
HTTP_PATTERN = re.compile(
    r"(?i)\b(?:http(?:/\d(?:\.\d)?)?|status(?:[_ ]code)?)\s*[:=]?\s*([1-5]\d{2})\b")
URL_PATTERN = re.compile(r"https?://[^\s<>\"'\\]+", re.IGNORECASE)
ERROR_ENUMS = (
    "authentication_failed", "authentication_error", "billing_error",
    "rate_limit", "invalid_request", "server_error", "unknown",
    "api_error", "error_during_execution", "error", "stop_sequence",
)


def services(line):
    """Classer seulement les URL de domaines exacts ; ignorer queries et identifiants."""
    from urllib.parse import urlsplit
    labels = set()
    for raw in URL_PATTERN.findall(line):
        try:
            url = urlsplit(raw)
            host = url.hostname
            # Pas de confiance dans un hote cache derriere userinfo ou port atypique.
            if url.username is not None or url.password is not None:
                labels.add("url_non_reconnue")
                continue
            if url.port not in (None, 443):
                labels.add("url_non_reconnue")
                continue
            if host == "api.anthropic.com":
                if url.path.rstrip("/") == "/v1/messages":
                    labels.add("anthropic_messages")
                elif url.path.rstrip("/") in ("/v1/oauth/token", "/api/oauth/token"):
                    labels.add("anthropic_oauth_token")
                else:
                    labels.add("anthropic_api_autre")
            elif host == "claude.ai":
                if url.path.rstrip("/") in ("/v1/oauth/token", "/api/oauth/token"):
                    labels.add("claude_oauth_token")
                else:
                    labels.add("claude_web_autre")
            elif host == "api.github.com":
                labels.add("github_api")
            elif host in ("statsig.anthropic.com", "statsig.com",
                          "sentry.io", "o4507804796354560.ingest.us.sentry.io"):
                labels.add("telemetrie")
            else:
                labels.add("url_non_reconnue")
        except ValueError:
            labels.add("url_non_reconnue")
    return labels


def http_sources(text, prefix):
    """Une proximite de lignes ne prouve pas la provenance d'une reponse."""
    lines = []
    records = text.splitlines()
    occurrences = 0
    for i, record in enumerate(records):
        if "401" not in HTTP_PATTERN.findall(record):
            continue
        occurrences += 1
        if occurrences > 20:
            lines.append(prefix + " 401 : occurrences_tronquees")
            break
        window = "\n".join(records[max(0, i - 2):i + 3]).lower()
        for marker, patterns in (
            ("oauth", ("oauth",)),
            ("github", ("github",)),
            ("telemetrie", ("statsig", "telemetry", "sentry")),
            ("requete_modele", ("api:request", "api:response", "api:error", "/v1/messages")),
        ):
            if any(pattern in window for pattern in patterns):
                lines.append(prefix + " 401 marqueur_voisinage : " + marker)
        direct = services(record)
        if direct:
            labels = direct
            relation = "meme_ligne"
        else:
            labels = set()
            for neighbour in records[max(0, i - 2):i] + records[i + 1:i + 3]:
                labels.update(services(neighbour))
            relation = "voisinage_non_attribue" if labels else "source_absente"
        if len(labels) > 1:
            lines.append(prefix + " 401 : contexte_ambigu")
        if not labels:
            lines.append(prefix + " 401 : source_absente")
        for label in sorted(labels):
            lines.append(prefix + " 401 contexte " + relation + " : " + label)
    return list(dict.fromkeys(lines))


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
        for field in ("api_error", "terminal_reason", "stop_reason"):
            value = message.get(field)
            if isinstance(value, str) and value in ERROR_ENUMS:
                lines.append("SDK code ferme " + field + " : " + value)
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
    sdk_text = "\n".join(texts)
    lines.extend(http_sources(sdk_text, "SDK"))
    for label in categories(sdk_text):
        lines.append("SDK indice : " + label)

    text, state = bounded_text(debug)
    lines.append("Journal prive : " + state)
    if text is not None:
        labels = categories(text)
        for label in labels:
            lines.append("Journal indice : " + label)
        # Codes uniquement lies a un libelle de statut ; jamais de texte libre.
        codes = sorted({int(m) for m in HTTP_PATTERN.findall(text)})
        for status in codes:
            lines.append("Journal HTTP possible : " + str(status))
        lines.extend(http_sources(text, "Journal"))
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
