#!/usr/bin/env node

/**
 * Privacy-safe compatibility probe for the stable OpenCode plugin contract.
 *
 * The probe uses an isolated HOME and stores only booleans, counts, versions,
 * and fixed reason codes. It never writes prompts, model output, credentials,
 * absolute home paths, or conversation content to the evidence document.
 */

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const DEFAULT_VERSION = "1.18.18";
const EVIDENCE_SCHEMA = "opensocrates.opencode-live-probe/1.0.0";
const FIXED_PROMPT_TOKEN = "OC_SOURCE_PROMPT";
const INJECTED_TOKEN = "OC_INJECTED_CONTEXT";
const EXCEPTION_TOKEN = "OC_EXCEPTION_CONTINUED";

function parseArgs(argv) {
  const options = { version: DEFAULT_VERSION, model: null, output: null };
  const args = [...argv];
  while (args.length > 0) {
    const flag = args.shift();
    if (!["--version", "--model", "--output"].includes(flag)) {
      throw new Error(`unknown option ${JSON.stringify(flag)}`);
    }
    const value = args.shift();
    if (!value || value.startsWith("--")) throw new Error(`${flag} requires a value`);
    if (flag === "--version") options.version = value;
    if (flag === "--model") options.model = value;
    if (flag === "--output") options.output = value;
  }
  return options;
}

function runOpenCode(version, args, environment, { timeout = 90_000 } = {}) {
  return spawnSync(
    "npx",
    ["--yes", `opencode-ai@${version}`, ...args],
    {
      encoding: "utf8",
      env: environment,
      maxBuffer: 16 * 1024 * 1024,
      timeout,
    },
  );
}

function succeeded(result) {
  return !result.error && result.status === 0;
}

function containsToken(result, token) {
  return succeeded(result) && String(result.stdout).includes(token);
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function pluginSource() {
  return `
import { appendFile } from "node:fs/promises"

const eventFile = process.env.OPENSOCRATES_PROBE_EVENT_FILE
const injectedToken = ${JSON.stringify(INJECTED_TOKEN)}

async function record(event) {
  if (!eventFile) return
  const safe = { schema: "opensocrates.opencode-probe-event/1.0.0", ...event }
  await appendFile(eventFile, JSON.stringify(safe) + "\\n", "utf8")
}

function publicText(parts) {
  return parts
    .filter((part) => part && part.type === "text" && part.synthetic !== true)
    .map((part) => typeof part.text === "string" ? part.text : "")
    .join("\\n")
}

let chatObserved = false

export const OpenSocratesProbe = async () => ({
  "chat.message": async (input, output) => {
    const mode = process.env.OPENSOCRATES_PROBE_MODE || "inject"
    const text = publicText(Array.isArray(output?.parts) ? output.parts : [])
    chatObserved = true
    await record({
      event: "chat.message",
      input_is_object: !!input && typeof input === "object" && !Array.isArray(input),
      output_message_is_object: !!output?.message && typeof output.message === "object",
      output_parts_is_array: Array.isArray(output?.parts),
      current_text_available: text.includes("OC_"),
      part_count: Array.isArray(output?.parts) ? output.parts.length : -1,
      model_present: !!input?.model && typeof input.model === "object",
      mode,
    })

    if (mode === "exception") {
      try {
        throw new Error("fixed probe exception")
      } catch {
        await record({ event: "fail_open", mode, caught: true })
        return
      }
    }

    if (!Array.isArray(output?.parts)) return
    const duplicate = output.parts.some(
      (part) => part?.type === "text" && part?.synthetic === true && part?.metadata?.opensocrates_probe === true,
    )
    if (duplicate) {
      await record({ event: "injection", duplicate_prevented: true, injected: false })
      return
    }
    const anchor = output.parts.find((part) => part?.type === "text")
    if (!anchor || typeof anchor.sessionID !== "string" || typeof anchor.messageID !== "string") return
    output.parts.push({
      id: "prt_opensocrates_probe_" + String(input?.messageID || anchor.messageID).replace(/[^a-zA-Z0-9]/gu, ""),
      sessionID: anchor.sessionID,
      messageID: anchor.messageID,
      type: "text",
      text: "Return only " + injectedToken + ".",
      synthetic: true,
      metadata: { opensocrates_probe: true },
    })
    await record({ event: "injection", duplicate_prevented: false, injected: true, synthetic: true })
  },

  "experimental.chat.system.transform": async (_input, output) => {
    await record({
      event: "experimental.chat.system.transform",
      after_chat_message: chatObserved,
      system_is_array: Array.isArray(output?.system),
      system_count: Array.isArray(output?.system) ? output.system.length : -1,
    })
  },
})
`.trimStart();
}

function skillSource() {
  return `---
name: opensocrates-probe
description: Fixed privacy-safe OpenCode skill discovery probe
compatibility: opencode
---

This is a fixed discovery sentinel. It contains no user or conversation data.
`;
}

async function readEvents(path) {
  let value = "";
  try {
    value = await readFile(path, "utf8");
  } catch {
    return [];
  }
  return value
    .split(/\r?\n/u)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const root = await mkdtemp(join(tmpdir(), "opensocrates-opencode-probe-"));
  const home = join(root, "home");
  const config = join(home, ".config", "opencode");
  const plugin = join(config, "plugins", "opensocrates-probe.js");
  const skill = join(config, "skills", "opensocrates-probe", "SKILL.md");
  const eventFile = join(root, "events.jsonl");
  const source = pluginSource();
  const environment = {
    ...process.env,
    HOME: home,
    OPENSOCRATES_PROBE_EVENT_FILE: eventFile,
    OPENCODE_DISABLE_CLAUDE_CODE: "1",
  };

  try {
    await mkdir(join(config, "plugins"), { recursive: true });
    await mkdir(join(config, "skills", "opensocrates-probe"), { recursive: true });
    await writeFile(plugin, source, "utf8");
    await writeFile(skill, skillSource(), "utf8");

    const version = runOpenCode(options.version, ["--version"], environment);
    const paths = runOpenCode(options.version, ["debug", "paths"], environment);
    const skills = runOpenCode(options.version, ["debug", "skill"], environment);
    const base = ["run", "--format", "json"];
    if (options.model) base.push("--model", options.model);

    const providerChecks = {
      attempted: options.model !== null,
      model_fingerprint: options.model ? sha256(options.model).slice(0, 16) : null,
      same_turn_injection: null,
      exception_fail_open: null,
    };

    if (options.model) {
      environment.OPENSOCRATES_PROBE_MODE = "inject";
      const inject = runOpenCode(
        options.version,
        [...base, `Return only ${FIXED_PROMPT_TOKEN}.`],
        environment,
      );
      providerChecks.same_turn_injection = containsToken(inject, INJECTED_TOKEN);

      environment.OPENSOCRATES_PROBE_MODE = "exception";
      const exception = runOpenCode(
        options.version,
        [...base, `Return only ${EXCEPTION_TOKEN}.`],
        environment,
      );
      providerChecks.exception_fail_open = containsToken(exception, EXCEPTION_TOKEN);
    }

    const events = await readEvents(eventFile);
    const chat = events.find((event) => event.event === "chat.message");
    const system = events.find((event) => event.event === "experimental.chat.system.transform");
    const injection = events.find((event) => event.event === "injection");
    const evidence = {
      schema: EVIDENCE_SCHEMA,
      opencode_version: succeeded(version) ? version.stdout.trim() : null,
      requested_version: options.version,
      stable_plugin_api: true,
      beta_v2_api_used: false,
      discovery: {
        default_config_suffix: ".config/opencode",
        global_plugin_suffix: ".config/opencode/plugins",
        global_skill_suffix: ".config/opencode/skills/<name>/SKILL.md",
        debug_paths_confirmed: succeeded(paths) && paths.stdout.includes(".config/opencode"),
        plugin_loaded: Boolean(chat),
        skill_discovered:
          succeeded(skills) && skills.stdout.includes("opensocrates-probe"),
      },
      hook: {
        payload_shape_confirmed:
          chat?.input_is_object === true &&
          chat?.output_message_is_object === true &&
          chat?.output_parts_is_array === true,
        current_user_text_available: chat?.current_text_available ?? null,
        mutation_is_synthetic: injection?.synthetic ?? null,
        system_transform_after_chat_message: system?.after_chat_message ?? null,
        output_parts_mutation_same_turn: providerChecks.same_turn_injection,
        persisted: "source-confirmed; live transcript not retained",
        visible_in_prompt_ui: "source-confirmed-hidden-when-synthetic",
        duplicate_injection: "isolated-unit-test-required",
      },
      execution: {
        non_interactive_run: options.model ? providerChecks.same_turn_injection === true : null,
        tui: "not-run-by-noninteractive-probe",
        exception_fail_open: providerChecks.exception_fail_open,
      },
      provider: providerChecks,
      privacy: {
        prompts_retained: false,
        model_output_retained: false,
        credentials_read_or_retained: false,
        absolute_home_paths_retained: false,
      },
      plugin_source_sha256: sha256(source),
    };

    const serialized = `${JSON.stringify(evidence, null, 2)}\n`;
    if (options.output) await writeFile(options.output, serialized, "utf8");
    process.stdout.write(serialized);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

main().catch((error) => {
  process.stderr.write(`opencode probe failed: ${error.message}\n`);
  process.exitCode = 1;
});
