import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { analyse, options, collect, verdict, PROMPT } from "../packaging/claude_comparaison.mjs";
const SECRET = "SENTINELLE_JAMAIS_PUBLIER";
const ok = [{ type: "result", subtype: "success", is_error: false, result: "OK" }];

test("seul OK explicite sans erreur valide une voie", () => {
  assert.equal(analyse(ok).ok, true);
  for (const result of ["autre", SECRET, "", null]) assert.equal(analyse([{ ...ok[0], result }]).ok, false);
  assert.equal(analyse([{ ...ok[0], is_error: true }]).ok, false);
  assert.equal(analyse([]).ok, false);
});
test("aucun texte libre, URL ou code arbitraire dans le rapport", () => {
  const report = analyse([
    { type: "assistant", error: SECRET, message: { content: [{ type: "text", text: SECRET }] } },
    { type: "result", is_error: true, result: "connection error " + SECRET, api_error: SECRET, api_error_status: "401" },
  ], SECRET);
  assert.ok(!JSON.stringify(report).includes(SECRET));
  assert.deepEqual(report.indices, ["connexion"]);
  assert.equal(report.http, null);
  assert.deepEqual(report.codes, []);
});
test("matrice des quatre resultats et incoherence", () => {
  const yes = { ok: true }, no = { ok: false };
  assert.equal(verdict(yes, yes, "success"), "deux_reussites");
  assert.equal(verdict(no, yes, "failure"), "action_seule_en_echec");
  assert.equal(verdict(yes, no, "success"), "sdk_direct_seul_en_echec");
  assert.equal(verdict(no, no, "failure"), "deux_echecs");
  assert.equal(verdict(yes, yes, "failure"), "resultat_incoherent");
});
test("options identiques declarees et jetons OIDC retires", () => {
  const config = options({ ALL_INPUTS: SECRET, ACTIONS_ID_TOKEN_REQUEST_TOKEN: SECRET }, "/fake/claude");
  assert.deepEqual(config.tools, ["Read"]);
  assert.equal(config.maxTurns, 1);
  assert.equal(config.maxBudgetUsd, 0.10);
  assert.equal(config.strictMcpConfig, true);
  assert.deepEqual(config.mcpServers, {});
  assert.equal(config.env.ALL_INPUTS, undefined);
  assert.equal(config.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN, undefined);
});
test("collecte SDK simulee sans appel reseau", async () => {
  const captured = [];
  async function* query(input) {
    assert.equal(input.prompt, PROMPT);
    yield { type: "system", subtype: "init" };
    yield ok[0];
    throw new Error("ne doit pas etre atteint");
  }
  const report = await collect(query, {}, line => captured.push(line));
  assert.equal(report.ok, true);
  assert.equal(report.init, 1);
  assert.equal(captured.length, 2);
});
test("exception uniquement en capture privee, categorie publique fixe", async () => {
  const captured = [];
  async function* query() { throw new Error("connection error " + SECRET); }
  const report = await collect(query, {}, text => captured.push(text));
  assert.equal(report.ok, false);
  assert.ok(!JSON.stringify(report).includes(SECRET));
  assert.deepEqual(report.indices, ["connexion"]);
  assert.ok(captured.join("").includes(SECRET));
});
test("rapport et nettoyage de captures synthetiques sur le runner", () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "claude-compare-test-"));
  const dir = path.join(temp, "claude-comparaison-privee");
  fs.mkdirSync(dir);
  fs.writeFileSync(path.join(temp, "claude-execution-output.json"), JSON.stringify(ok));
  fs.writeFileSync(path.join(dir, "direct.jsonl"), JSON.stringify(ok[0]) + "\n");
  for (const name of ["direct.stderr", "launcher.stdout", "launcher.stderr"]) fs.writeFileSync(path.join(dir, name), SECRET);
  const report = spawnSync(process.execPath, ["packaging/claude_comparaison.mjs", "report"], {
    cwd: process.cwd(), encoding: "utf8",
    env: { ...process.env, RUNNER_TEMP: temp, GITHUB_WORKSPACE: process.cwd(), ACTION_OUTCOME: "success" },
  });
  assert.equal(report.status, 0);
  assert.ok(report.stdout.includes("deux_reussites"));
  assert.ok(!report.stdout.includes(SECRET));
  assert.ok(!report.stderr.includes(SECRET));
  assert.equal(fs.readdirSync(dir).length, 0);
  assert.equal(fs.existsSync(path.join(temp, "claude-execution-output.json")), false);
  fs.rmdirSync(dir); fs.rmdirSync(temp);
});

test("codes de preparation fermes et rapport incomplet rouge", () => {
  assert.deepEqual(analyse([{ type: "probe_status", code: SECRET }]).preflight, []);
  assert.deepEqual(analyse([{ type: "probe_status", code: "versions_inattendues" }]).preflight, ["versions_inattendues"]);
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "claude-compare-fail-"));
  const result = spawnSync(process.execPath, ["packaging/claude_comparaison.mjs", "report"], {
    cwd: process.cwd(), encoding: "utf8",
    env: { ...process.env, RUNNER_TEMP: temp, GITHUB_WORKSPACE: process.cwd(), ACTION_OUTCOME: "failure" },
  });
  assert.equal(result.status, 1);
  assert.ok(result.stdout.includes("deux_echecs"));
  assert.ok(!result.stdout.includes(SECRET));
  fs.rmdirSync(temp);
});
