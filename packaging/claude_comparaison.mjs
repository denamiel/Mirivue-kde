import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";

export const PROMPT = "Réponds exactement OK, sans outil ni lecture de fichier.";
export const MODEL = "claude-sonnet-5-5";
const MAX = 8_000_000;
const CODES = new Set([
  "invalid_request", "authentication_failed", "oauth_org_not_allowed", "account_on_hold",
  "billing_error", "rate_limit", "overloaded", "model_not_found", "server_error",
  "max_output_tokens", "cloud_credential_error", "unknown", "connection_error",
  "api_connection_error", "network_error",
]);
const REASONS = {
  connexion: /unable to connect|connection.?error|fetch failed|econnreset|econnrefused/i,
  dns: /enotfound|eai_again|getaddrinfo/i,
  certificat: /certificate verify failed|self.signed certificate|cert_has_expired|unable_to_verify/i,
  authentification: /unauthorized|invalid bearer|authentication.failed|token expired/i,
  limitation: /rate.?limit|session limit|weekly limit/i,
  facturation: /credit balance|billing.error|payment required/i,
  modele: /model.not.found|invalid model/i,
  parametres: /invalid (?:argument|parameter)|unsupported parameter|validation error|tool_choice|max_tokens/i,
  oauth_non_accepte: /oauth.{0,50}(?:not supported|not allowed)/i,
};

export function analyse(messages, errorText = "") {
  const rows = Array.isArray(messages) ? messages.filter(m => m && typeof m === "object") : [];
  const result = rows.filter(m => m.type === "result").at(-1);
  const texts = [errorText];
  const codes = new Set();
  for (const m of rows) {
    if (m.type === "assistant" && typeof m.error === "string") {
      if (CODES.has(m.error)) codes.add(m.error);
      if (Array.isArray(m.message?.content)) {
        for (const b of m.message.content) if (b?.type === "text" && typeof b.text === "string") texts.push(b.text);
      }
    }
    if (m.type === "result" && m.is_error === true) {
      for (const key of ["result", "api_error", "errors"]) {
        const value = m[key];
        if (typeof value === "string") texts.push(value);
        if (Array.isArray(value)) texts.push(...value.filter(v => typeof v === "string"));
      }
      if (CODES.has(m.api_error)) codes.add(m.api_error);
    }
  }
  for (const m of rows) if (m.type === "probe_error" && typeof m.message === "string") texts.push(m.message);
  const text = texts.join("\n");
  return {
    init: Math.min(rows.filter(m => m.type === "system" && m.subtype === "init").length, 999),
    result: !!result,
    ok: !!result && result.subtype === "success" && result.is_error === false &&
        typeof result.result === "string" && result.result.trim() === "OK",
    http: Number.isInteger(result?.api_error_status) && result.api_error_status >= 100 &&
          result.api_error_status <= 599 ? result.api_error_status : null,
    preflight: [...new Set(rows.filter(m => m.type === "probe_status" &&
      ["versions_inattendues", "consigne_action_differente", "lancement_ou_collecte_en_echec"].includes(m.code))
      .map(m => m.code))],
    codes: [...codes].sort(),
    indices: Object.entries(REASONS).filter(([, re]) => re.test(text)).map(([key]) => key),
  };
}

export function options(env, executable) {
  // Même entrée de modèle, outils, limites et sources de réglages que l'action.
  const childEnv = { ...env, CLAUDE_CODE_ENTRYPOINT: "claude-code-github-action",
    CLAUDE_CODE_ACTION: "1", DETAILED_PERMISSION_MESSAGES: "1" };
  for (const key of ["ALL_INPUTS", "ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
                     "ACTIONS_STEP_DEBUG", "DEBUG_CLAUDE_AGENT_SDK"]) delete childEnv[key];
  return {
    model: MODEL, maxTurns: 1, maxBudgetUsd: 0.10,
    tools: ["Read"], allowedTools: ["Read"], strictMcpConfig: true, mcpServers: {},
    settingSources: ["user"], systemPrompt: { type: "preset", preset: "claude_code" },
    pathToClaudeCodeExecutable: executable, env: childEnv,
    extraArgs: { "disable-slash-commands": null },
  };
}

export async function collect(query, config, write) {
  let messages = [], failure = "";
  try {
    for await (const message of query({ prompt: PROMPT, options: config })) {
      write(JSON.stringify(message) + "\n");
      messages.push(message);
      if (message.type === "result") break;
    }
  } catch (error) {
    failure = typeof error?.message === "string" ? error.message : "";
    write(JSON.stringify({ type: "probe_error", message: failure }) + "\n");
  }
  return analyse(messages, failure);
}

export function verdict(action, direct, outcome) {
  if (outcome === "success" && action.ok && direct.ok) return "deux_reussites";
  if (outcome !== "success" && !action.ok && direct.ok) return "action_seule_en_echec";
  if (outcome === "success" && action.ok && !direct.ok) return "sdk_direct_seul_en_echec";
  if (!action.ok && !direct.ok) return "deux_echecs";
  return "resultat_incoherent";
}

function privateRead(file) {
  if (fs.lstatSync(file).isSymbolicLink()) throw new Error("private_file");
  const fd = fs.openSync(file, "r");
  try {
    const buffer = Buffer.alloc(MAX + 1);
    const size = fs.readSync(fd, buffer, 0, buffer.length, 0);
    if (size > MAX) throw new Error("private_file");
    return buffer.subarray(0, size).toString("utf8");
  } finally { fs.closeSync(fd); }
}

function emit(label, summary) {
  // Ne publier que les valeurs de analyse(), jamais un objet reçu d'un fichier brut.
  console.log(label + " " + JSON.stringify(summary));
}

async function main() {
  const temp = process.env.RUNNER_TEMP;
  const root = process.env.GITHUB_WORKSPACE;
  if (!temp || !root) { console.log("Comparaison : environnement_absent"); return 1; }
  const privateDir = path.join(temp, "claude-comparaison-privee");
  const output = path.join(temp, "claude-execution-output.json");
  const files = ["direct.jsonl", "direct.stderr", "launcher.stdout", "launcher.stderr"];
  if (process.argv[2] === "direct") {
    fs.mkdirSync(privateDir, { recursive: true, mode: 0o700 });
    let written = 0;
    const write = (file, text) => {
      const bytes = Buffer.from(String(text));
      if (written + bytes.length > MAX) throw new Error("capture_limit");
      fs.appendFileSync(path.join(privateDir, file), bytes, { mode: 0o600 });
      written += bytes.length;
    };
    try {
      const effectivePrompt = privateRead(path.join(temp, "claude-prompts/claude-prompt.txt")).trim();
      if (effectivePrompt !== PROMPT) {
        write("direct.jsonl", JSON.stringify({ type: "probe_status", code: "consigne_action_differente" }) + "\n");
        return 1;
      }
      const actionDir = path.join(root, ".compare-action");
      const requireFromAction = createRequire(path.join(actionDir, "package.json"));
      const pkg = JSON.parse(privateRead(path.join(actionDir, "node_modules/@anthropic-ai/claude-agent-sdk/package.json")));
      const executable = path.join(os.homedir(), ".local/bin/claude");
      const version = execFileSync(executable, ["--version"], { encoding: "utf8", timeout: 10000 });
      if (pkg.version !== "0.3.322" || !/^2\.1\.322\b/.test(version)) {
        write("direct.jsonl", JSON.stringify({ type: "probe_status", code: "versions_inattendues" }) + "\n");
        return 1;
      }
      // Réutiliser exactement l'installation de l'action ; aucun npm install ici.
      const { query } = await import(pathToFileURL(requireFromAction.resolve("@anthropic-ai/claude-agent-sdk")).href);
      const config = options(process.env, executable);
      config.stderr = text => write("direct.stderr", text);
      await collect(query, config, text => write("direct.jsonl", text));
      return 0;
    } catch (error) {
      // Collection privée ; aucun message d'exception libre dans stdout.
      try { write("direct.stderr", typeof error?.message === "string" ? error.message : ""); } catch {}
      try { write("direct.jsonl", JSON.stringify({ type: "probe_status", code: "lancement_ou_collecte_en_echec" }) + "\n"); } catch {}
      console.log("SDK direct : lancement_ou_collecte_en_echec");
      return 1;
    }
  }
  if (process.argv[2] !== "report") { console.log("Comparaison : mode_invalide"); return 1; }
  try {
    let actionRows = [], directRows = [], directError = "";
    try { actionRows = JSON.parse(privateRead(output)); } catch {}
    try {
      directRows = privateRead(path.join(privateDir, "direct.jsonl")).split("\n")
        .flatMap(line => { try { return [JSON.parse(line)]; } catch { return []; } });
      directError = privateRead(path.join(privateDir, "direct.stderr"));
    } catch {}
    const action = analyse(actionRows);
    const direct = analyse(directRows, directError);
    emit("Action", action); emit("SDK direct", direct);
    const result = verdict(action, direct, process.env.ACTION_OUTCOME);
    console.log("Comparaison : " + result);
    return result === "deux_reussites" ? 0 : 1;
  } catch {
    console.log("Comparaison : analyse_impossible"); return 1;
  } finally {
    let cleanupFailed = false;
    // Fichiers explicitement nommés ; aucune suppression récursive.
    for (const file of [output, ...files.map(f => path.join(privateDir, f))]) {
      try { fs.rmSync(file, { force: true }); } catch { cleanupFailed = true; }
    }
    if (cleanupFailed) { console.log("Comparaison : nettoyage_en_echec"); process.exitCode = 1; }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().then(code => { process.exitCode = Math.max(process.exitCode || 0, code); })
    .catch(() => { console.log("Comparaison : erreur_interne"); process.exitCode = 1; });
}
