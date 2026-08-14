#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { createHash, randomInt, randomUUID } from "node:crypto";
import {
  constants as fsConstants,
  createReadStream,
  createWriteStream,
  existsSync,
  readFileSync,
  realpathSync,
} from "node:fs";
import {
  access,
  chmod,
  chown,
  cp,
  lstat,
  mkdir,
  mkdtemp,
  open,
  readFile,
  readdir,
  realpath,
  rename,
  rm,
  rmdir,
  stat,
  writeFile,
} from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { basename, dirname, join, relative, resolve, sep } from "node:path";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { fileURLToPath } from "node:url";

export const PRODUCT_VERSION = "1.2.1";
export const REPOSITORY = "ParkerHwang/OpenSocrates";
export const MARKETPLACE_NAME = "opensocrates";
export const PLUGIN_NAME = "opensocrates";
export const PLUGIN_ID = `${PLUGIN_NAME}@${MARKETPLACE_NAME}`;
export const DEFAULT_HOST = "codex";
export const SUPPORTED_HOSTS = Object.freeze([
  "antigravity",
  "claude",
  "codex",
  "cursor",
  "grok",
  "opencode",
]);
export const ALL_HOST = "all";
export const HOST_CHOICES = Object.freeze([ALL_HOST, ...SUPPORTED_HOSTS]);
export function assetNameFor(host = DEFAULT_HOST) {
  if (!SUPPORTED_HOSTS.includes(host)) {
    fail(`unsupported host ${JSON.stringify(host)}`);
  }
  return `opensocrates-${PRODUCT_VERSION}-${host}-plugin.zip`;
}
export const ASSET_NAME = assetNameFor(DEFAULT_HOST);
export const CHECKSUM_NAME = `${ASSET_NAME}.sha256`;

const MARKER_NAME = ".opensocrates-managed.json";
const CODEX_MARKER = Object.freeze({
  schemaVersion: 1,
  marketplaceName: MARKETPLACE_NAME,
  pluginName: PLUGIN_NAME,
});
const CLAUDE_MARKER = Object.freeze({
  schemaVersion: 1,
  marketplaceName: MARKETPLACE_NAME,
  pluginName: PLUGIN_NAME,
  host: "claude",
});
const CURSOR_MARKER = Object.freeze({
  schemaVersion: 1,
  marketplaceName: MARKETPLACE_NAME,
  pluginName: PLUGIN_NAME,
  host: "cursor",
  registrationKind: "file-drop",
});
const ANTIGRAVITY_MARKER = Object.freeze({
  schemaVersion: 1,
  marketplaceName: MARKETPLACE_NAME,
  pluginName: PLUGIN_NAME,
  host: "antigravity",
  registrationKind: "file-drop",
});
const GROK_MARKER = Object.freeze({
  schemaVersion: 1,
  marketplaceName: MARKETPLACE_NAME,
  pluginName: PLUGIN_NAME,
  host: "grok",
  registrationKind: "file-drop",
});
const OPENCODE_MARKER = Object.freeze({
  schemaVersion: 1,
  marketplaceName: MARKETPLACE_NAME,
  pluginName: PLUGIN_NAME,
  host: "opencode",
  registrationKind: "automatic-file-discovery",
});
const OPENCODE_INSTALL_MANIFEST = ".opensocrates-installation.json";
const OPENCODE_BRIDGE_MARKER = ".opensocrates-managed.json";
// OpenCode is discovered automatically from its config directory, so it is
// deliberately not a file-drop host.
const FILE_DROP_HOSTS = Object.freeze(["antigravity", "cursor", "grok"]);
const HOST_LAYOUTS = Object.freeze({
  antigravity: {
    marketplaceRelative: null,
    pluginRelative: ".",
    manifestRelative: "plugin.json",
    requiresRuntime: false,
  },
  claude: {
    marketplaceRelative: join(".claude-plugin", "marketplace.json"),
    pluginRelative: join("plugins", PLUGIN_NAME),
    manifestRelative: join(".claude-plugin", "plugin.json"),
    requiresRuntime: true,
  },
  codex: {
    marketplaceRelative: join(".agents", "plugins", "marketplace.json"),
    pluginRelative: join("build", "generated", "plugins", "codex"),
    manifestRelative: join(".codex-plugin", "plugin.json"),
    requiresRuntime: true,
  },
  cursor: {
    marketplaceRelative: null,
    pluginRelative: ".",
    manifestRelative: "plugin.json",
    requiresRuntime: false,
  },
  grok: {
    marketplaceRelative: null,
    pluginRelative: ".",
    manifestRelative: "plugin.json",
    requiresRuntime: false,
  },
  opencode: {
    marketplaceRelative: null,
    pluginRelative: ".",
    manifestRelative: "opencode-plugin.json",
    requiresRuntime: false,
  },
});
const MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024 * 1024;
const MAX_ARCHIVE_ENTRIES = 10_000;
const DESIRED_STATE_SCHEMA = "opensocrates.desired-state/1.0.0";
const RECEIPT_SCHEMA = "opensocrates.auto-update-receipt/1.0.0";
const AUTO_UPDATE_LABEL = "com.opensocrates.auto-update";
const AUTO_UPDATE_MIN_INTERVAL_HOURS = 1;
const AUTO_UPDATE_MAX_INTERVAL_HOURS = 24 * 7;
const AUTO_UPDATE_DEFAULT_INTERVAL_HOURS = 24;
const AUTO_UPDATE_POLL_SECONDS = 60 * 60;
const LOCK_STALE_MILLISECONDS = 2 * 60 * 60 * 1000;
export const PURGE_RESULT_SCHEMA = "opensocrates.purge-result/1.0.0";
export const CODEX_TRUST_EVENTS = Object.freeze([
  "pre_tool_use",
  "post_tool_use",
  "pre_compact",
  "session_start",
  "session_end",
  "user_prompt_submit",
  "stop",
]);
const CODEX_TRUST_KEY_PREFIX = `${PLUGIN_ID}:hooks/hooks.json:`;
const MAX_CODEX_CONFIG_BYTES = 16 * 1024 * 1024;
const CODEX_APP_SERVER_ARGS = Object.freeze(["app-server", "--stdio"]);
const CODEX_APP_SERVER_TIMEOUT_MILLISECONDS = 15_000;
const CODEX_APP_SERVER_TERMINATION_MILLISECONDS = 1_000;
const MAX_CODEX_APP_SERVER_LINE_BYTES = 256 * 1024;
const MAX_CODEX_APP_SERVER_OUTPUT_BYTES = 1024 * 1024;

// Keep host security state separate from installer-owned payload cleanup so an
// explicit trust reset can fail without weakening purge path-ownership checks.
export function purgeExtensionResult(host, resetTrust = false) {
  return host === "codex"
    ? {
        component: "host-security-trust",
        status: resetTrust ? "pending" : "preserved",
        nextAction: resetTrust ? null : "rerun-purge-with-reset-trust",
      }
    : {
        component: "host-security-trust",
        status: "not-applicable",
        nextAction: null,
      };
}

export function createPurgeResult(hosts, { resetTrust = false } = {}) {
  return {
    schema: PURGE_RESULT_SCHEMA,
    status: "pending",
    hosts: [...hosts].sort().map((host) => ({
      host,
      status: "pending",
      registration: "not-checked",
      registrationDetail: null,
      components: [],
      extension: purgeExtensionResult(host, resetTrust),
      errors: [],
    })),
    finalization: {
      status: "pending",
      components: [],
      errors: [],
    },
  };
}

function trustResetFailure(message) {
  fail(`Codex OpenSocrates hook trust was not reset: ${message}`);
}

function decodeTomlBasicString(source, start) {
  let value = "";
  let index = start + 1;
  while (index < source.length) {
    const character = source[index];
    if (character === '"') {
      return { value, next: index + 1, kind: "basic", raw: source.slice(start, index + 1) };
    }
    if (character === "\\") {
      const escaped = source[index + 1];
      const simple = new Map([
        ['"', '"'],
        ["\\", "\\"],
        ["b", "\b"],
        ["t", "\t"],
        ["n", "\n"],
        ["f", "\f"],
        ["r", "\r"],
      ]);
      if (simple.has(escaped)) {
        value += simple.get(escaped);
        index += 2;
        continue;
      }
      const digits = escaped === "u" ? 4 : escaped === "U" ? 8 : 0;
      if (digits > 0) {
        const encoded = source.slice(index + 2, index + 2 + digits);
        if (!new RegExp(`^[0-9A-Fa-f]{${digits}}$`, "u").test(encoded)) return null;
        const codePoint = Number.parseInt(encoded, 16);
        if (codePoint > 0x10ffff || (codePoint >= 0xd800 && codePoint <= 0xdfff)) return null;
        value += String.fromCodePoint(codePoint);
        index += 2 + digits;
        continue;
      }
      return null;
    }
    if (character.codePointAt(0) < 0x20 || character.codePointAt(0) === 0x7f) return null;
    value += character;
    index += 1;
  }
  return null;
}

function decodeTomlLiteralString(source, start) {
  const end = source.indexOf("'", start + 1);
  if (end < 0) return null;
  const value = source.slice(start + 1, end);
  if ([...value].some((character) => character.codePointAt(0) < 0x20 || character.codePointAt(0) === 0x7f)) {
    return null;
  }
  return { value, next: end + 1, kind: "literal", raw: source.slice(start, end + 1) };
}

function parseTomlDottedKey(source) {
  const segments = [];
  let index = 0;
  const skipWhitespace = () => {
    while (source[index] === " " || source[index] === "\t") index += 1;
  };
  skipWhitespace();
  while (index < source.length) {
    let segment;
    if (source[index] === '"') {
      segment = decodeTomlBasicString(source, index);
    } else if (source[index] === "'") {
      segment = decodeTomlLiteralString(source, index);
    } else {
      const match = source.slice(index).match(/^[A-Za-z0-9_-]+/u);
      if (!match) return null;
      segment = {
        value: match[0],
        next: index + match[0].length,
        kind: "bare",
        raw: match[0],
      };
    }
    if (segment === null) return null;
    segments.push(segment);
    index = segment.next;
    skipWhitespace();
    if (index === source.length) return segments;
    if (source[index] !== ".") return null;
    index += 1;
    skipWhitespace();
    if (index === source.length) return null;
  }
  return null;
}

function scanTomlLine(line, carriedContext) {
  let state = carriedContext.stringState;
  let arrayDepth = carriedContext.arrayDepth;
  let inlineTableDepth = carriedContext.inlineTableDepth;
  let commentIndex = -1;
  for (let index = 0; index < line.length; index += 1) {
    if (state === "multiline-basic") {
      if (line[index] === "\\") {
        index += 1;
      } else if (line.startsWith('"""', index)) {
        state = null;
        index += 2;
      }
      continue;
    }
    if (state === "multiline-literal") {
      if (line.startsWith("'''", index)) {
        state = null;
        index += 2;
      }
      continue;
    }
    if (state === "basic") {
      if (line[index] === "\\") index += 1;
      else if (line[index] === '"') state = null;
      continue;
    }
    if (state === "literal") {
      if (line[index] === "'") state = null;
      continue;
    }
    if (line[index] === "#") {
      commentIndex = index;
      break;
    }
    if (line.startsWith('"""', index)) {
      state = "multiline-basic";
      index += 2;
    } else if (line.startsWith("'''", index)) {
      state = "multiline-literal";
      index += 2;
    } else if (line[index] === '"') {
      state = "basic";
    } else if (line[index] === "'") {
      state = "literal";
    } else if (line[index] === "[") {
      arrayDepth += 1;
    } else if (line[index] === "]") {
      arrayDepth -= 1;
      if (arrayDepth < 0) return { invalid: true, commentIndex, context: carriedContext };
    } else if (line[index] === "{") {
      inlineTableDepth += 1;
    } else if (line[index] === "}") {
      inlineTableDepth -= 1;
      if (inlineTableDepth < 0) return { invalid: true, commentIndex, context: carriedContext };
    }
  }
  if (state === "basic" || state === "literal") {
    return { invalid: true, commentIndex, context: carriedContext };
  }
  return {
    invalid: false,
    commentIndex,
    context: { stringState: state, arrayDepth, inlineTableDepth },
  };
}

function tomlLines(source) {
  const lines = [];
  let start = 0;
  while (start < source.length) {
    const newline = source.indexOf("\n", start);
    const end = newline < 0 ? source.length : newline + 1;
    const contentEnd = newline < 0 ? source.length : newline > start && source[newline - 1] === "\r" ? newline - 1 : newline;
    lines.push({ start, end, contentEnd, body: source.slice(start, contentEnd) });
    start = end;
  }
  return lines;
}

function parseTomlTableHeader(code) {
  const leading = code.match(/^[\t ]*/u)?.[0].length ?? 0;
  const trimmedEnd = code.trimEnd().length;
  const candidate = code.slice(leading, trimmedEnd);
  const array = candidate.startsWith("[[");
  if (!candidate.startsWith("[") || (array ? !candidate.endsWith("]]") : !candidate.endsWith("]"))) {
    return null;
  }
  const openWidth = array ? 2 : 1;
  const closeWidth = array ? 2 : 1;
  const keySource = candidate.slice(openWidth, candidate.length - closeWidth);
  const segments = parseTomlDottedKey(keySource);
  if (segments === null) return null;
  return {
    array,
    raw: candidate,
    segments,
    syntaxStart: leading,
    syntaxEnd: leading + candidate.length,
  };
}

function matchingTrustKey(segments) {
  if (
    segments.length < 3 ||
    segments[0].value !== "hooks" ||
    segments[1].value !== "state" ||
    !segments[2].value.startsWith(CODEX_TRUST_KEY_PREFIX)
  ) {
    return null;
  }
  return segments[2].value;
}

function isCanonicalTrustHeader(header, key) {
  return !header.array && header.raw === `[hooks.state.${JSON.stringify(key)}]`;
}

function assignmentKeySegments(code) {
  let state = null;
  for (let index = 0; index < code.length; index += 1) {
    if (state === "basic") {
      if (code[index] === "\\") index += 1;
      else if (code[index] === '"') state = null;
      continue;
    }
    if (state === "literal") {
      if (code[index] === "'") state = null;
      continue;
    }
    if (code[index] === '"') state = "basic";
    else if (code[index] === "'") state = "literal";
    else if (code[index] === "=") return parseTomlDottedKey(code.slice(0, index));
  }
  return null;
}

function lineContainsTrustNamespaceString(code) {
  for (let index = 0; index < code.length; index += 1) {
    let decoded = null;
    if (code[index] === '"') decoded = decodeTomlBasicString(code, index);
    else if (code[index] === "'") decoded = decodeTomlLiteralString(code, index);
    if (decoded === null) continue;
    if (decoded.value.startsWith(CODEX_TRUST_KEY_PREFIX)) return true;
    index = decoded.next - 1;
  }
  return false;
}

function pathContainsTrustNamespace(segments) {
  return matchingTrustKey(segments) !== null;
}

function trustEventFromKey(key) {
  const suffix = key.slice(CODEX_TRUST_KEY_PREFIX.length);
  const match = suffix.match(/^([a-z_]+):(\d+):(\d+)$/u);
  if (!match || !CODEX_TRUST_EVENTS.includes(match[1]) || match[2] !== "0" || match[3] !== "0") {
    trustResetFailure("the matching trust namespace has a noncanonical event or index");
  }
  return match[1];
}

function addRemovalSpan(spans, line, start, end) {
  if (start >= end) trustResetFailure("the matching trust section has an unsupported shape");
  spans.push({ start: line.start + start, end: line.start + end });
}

/**
 * Remove only the syntax bytes owned by canonical OpenSocrates hook trust
 * sections. Comments, whitespace, newline style, unrelated keys, and the
 * parent hooks.state table are retained byte-for-byte.
 */
export function stripCodexOpenSocratesTrustSections(contents) {
  const original = Buffer.isBuffer(contents) ? contents : Buffer.from(contents);
  const utf8Bom = original.subarray(0, 3).equals(Buffer.from([0xef, 0xbb, 0xbf]));
  const encodedSource = utf8Bom ? original.subarray(3) : original;
  let source;
  try {
    source = new TextDecoder("utf-8", { fatal: true }).decode(encodedSource);
  } catch {
    trustResetFailure("the configuration is not valid UTF-8");
  }
  const spans = [];
  const found = new Map();
  let currentTarget = null;
  let currentTableSegments = [];
  let context = { stringState: null, arrayDepth: 0, inlineTableDepth: 0 };
  for (const line of tomlLines(source)) {
    const startContext = { ...context };
    const scanned = scanTomlLine(line.body, context);
    if (scanned.invalid) trustResetFailure("the configuration has an unsupported string shape");
    context = scanned.context;
    const code = scanned.commentIndex < 0 ? line.body : line.body.slice(0, scanned.commentIndex);
    const firstNonWhitespace = code.search(/[^\t ]/u);
    let header = null;
    if (
      startContext.stringState === null &&
      startContext.arrayDepth === 0 &&
      startContext.inlineTableDepth === 0 &&
      firstNonWhitespace >= 0 &&
      code[firstNonWhitespace] === "["
    ) {
      header = parseTomlTableHeader(code);
      if (header === null) trustResetFailure("the configuration has an unsupported table header");
    }
    if (header !== null) {
      if (currentTarget !== null && !currentTarget.hashSeen) {
        trustResetFailure("a matching trust section is missing its canonical trusted_hash key");
      }
      currentTarget = null;
      currentTableSegments = header.segments;
      const key = matchingTrustKey(header.segments);
      if (key !== null) {
        if (!isCanonicalTrustHeader(header, key)) {
          trustResetFailure("the matching trust namespace uses a noncanonical table shape");
        }
        const event = trustEventFromKey(key);
        if (found.has(event)) trustResetFailure("a matching trust event appears more than once");
        currentTarget = { event, hashSeen: false };
        found.set(event, currentTarget);
        addRemovalSpan(spans, line, header.syntaxStart, header.syntaxEnd);
      }
      continue;
    }
    if (currentTarget === null) {
      if (code.trim().length === 0 || startContext.stringState !== null) continue;
      const assignment = assignmentKeySegments(code);
      const semanticPath = assignment === null ? [] : [...currentTableSegments, ...assignment];
      if (
        pathContainsTrustNamespace(semanticPath) ||
        ((semanticPath[0]?.value === "hooks" ||
          (currentTableSegments[0]?.value === "hooks" && currentTableSegments[1]?.value === "state")) &&
          lineContainsTrustNamespaceString(code))
      ) {
        trustResetFailure("the matching trust namespace uses a noncanonical assignment shape");
      }
      continue;
    }
    if (code.trim().length === 0) continue;
    if (
      startContext.stringState !== null ||
      context.stringState !== null ||
      startContext.arrayDepth !== 0 ||
      startContext.inlineTableDepth !== 0 ||
      context.arrayDepth !== 0 ||
      context.inlineTableDepth !== 0
    ) {
      trustResetFailure("a matching trust section contains a multiline value");
    }
    const assignment = code.match(/^(\s*)trusted_hash\s*=\s*"(?:[^"\\\r\n]|\\.)*"(\s*)$/u);
    if (assignment === null || currentTarget.hashSeen) {
      trustResetFailure("a matching trust section contains an unexpected or duplicate key");
    }
    currentTarget.hashSeen = true;
    const syntaxStart = assignment[1].length;
    const syntaxEnd = code.length - assignment[2].length;
    addRemovalSpan(spans, line, syntaxStart, syntaxEnd);
  }
  if (context.stringState !== null || context.arrayDepth !== 0 || context.inlineTableDepth !== 0) {
    trustResetFailure("the configuration has an unterminated multiline value");
  }
  if (currentTarget !== null && !currentTarget.hashSeen) {
    trustResetFailure("a matching trust section is missing its canonical trusted_hash key");
  }
  spans.sort((left, right) => left.start - right.start);
  let cursor = 0;
  let updated = "";
  for (const span of spans) {
    if (span.start < cursor) trustResetFailure("matching trust syntax overlaps unexpectedly");
    updated += source.slice(cursor, span.start);
    cursor = span.end;
  }
  updated += source.slice(cursor);
  const updatedBytes = Buffer.from(updated, "utf8");
  return {
    contents: utf8Bom ? Buffer.concat([original.subarray(0, 3), updatedBytes]) : updatedBytes,
    removedEvents: CODEX_TRUST_EVENTS.filter((event) => found.has(event)),
  };
}

function currentUid() {
  if (typeof process.getuid !== "function") {
    trustResetFailure("file ownership cannot be verified on this platform");
  }
  return process.getuid();
}

function assertOwnedDirectory(info) {
  if (!info.isDirectory() || info.isSymbolicLink() || info.uid !== currentUid() || (info.mode & 0o022) !== 0) {
    trustResetFailure("the Codex configuration directory is not a safe owner-controlled directory");
  }
}

function assertOwnedConfigFile(info) {
  if (!info.isFile() || info.isSymbolicLink() || info.uid !== currentUid() || info.nlink !== 1) {
    trustResetFailure("the Codex configuration is not a safe owner-controlled regular file");
  }
  if (info.size > MAX_CODEX_CONFIG_BYTES) {
    trustResetFailure("the Codex configuration is too large for a bounded trust reset");
  }
}

function sameSnapshot(left, right) {
  return (
    left.dev === right.dev &&
    left.ino === right.ino &&
    left.size === right.size &&
    left.mtimeNs === right.mtimeNs &&
    left.ctimeNs === right.ctimeNs &&
    left.mode === right.mode &&
    left.uid === right.uid &&
    left.gid === right.gid &&
    left.nlink === right.nlink
  );
}

async function readConfigSnapshot(target) {
  const noFollow = fsConstants.O_NOFOLLOW ?? 0;
  let handle;
  let operationFailed = false;
  try {
    handle = await open(target, fsConstants.O_RDONLY | noFollow);
    const before = await handle.stat({ bigint: true });
    if (
      !before.isFile() ||
      before.isSymbolicLink() ||
      before.uid !== BigInt(currentUid()) ||
      before.nlink !== 1n
    ) {
      trustResetFailure("the Codex configuration changed to an unsafe file");
    }
    if (before.size > BigInt(MAX_CODEX_CONFIG_BYTES)) {
      trustResetFailure("the Codex configuration is too large for a bounded trust reset");
    }
    const contents = await handle.readFile();
    const after = await handle.stat({ bigint: true });
    if (!sameSnapshot(before, after) || BigInt(contents.length) !== after.size) {
      trustResetFailure("the Codex configuration changed while it was being inspected");
    }
    return { info: after, contents };
  } catch (error) {
    operationFailed = true;
    if (error instanceof InstallerError) throw error;
    trustResetFailure("the Codex configuration could not be inspected safely");
  } finally {
    try {
      await handle?.close();
    } catch {
      if (!operationFailed) {
        trustResetFailure("the Codex configuration handle could not be closed safely");
      }
    }
  }
}

async function writeSyncedOwnerOnlyFile(target, contents) {
  let handle;
  let operationFailed = false;
  try {
    handle = await open(target, "wx", 0o600);
    await handle.writeFile(contents);
    await handle.chmod(0o600);
    await handle.sync();
  } catch (error) {
    operationFailed = true;
    if (error instanceof InstallerError) throw error;
    trustResetFailure("an owner-only Codex transaction file could not be written safely");
  } finally {
    try {
      await handle?.close();
    } catch {
      if (!operationFailed) {
        trustResetFailure("an owner-only Codex transaction file could not be closed safely");
      }
    }
  }
}

async function fsyncFile(target) {
  let handle;
  let operationFailed = false;
  try {
    handle = await open(target, "r");
    await handle.sync();
  } catch (error) {
    operationFailed = true;
    if (error instanceof InstallerError) throw error;
    trustResetFailure("the Codex configuration could not be synchronized safely");
  } finally {
    try {
      await handle?.close();
    } catch {
      if (!operationFailed) {
        trustResetFailure("the Codex configuration handle could not be closed safely");
      }
    }
  }
}

async function fsyncDirectory(target) {
  let handle;
  let operationFailed = false;
  try {
    handle = await open(target, "r");
    await handle.sync();
  } catch (error) {
    operationFailed = true;
    if (error instanceof InstallerError) throw error;
    trustResetFailure("the Codex configuration directory could not be synchronized safely");
  } finally {
    try {
      await handle?.close();
    } catch {
      if (!operationFailed) {
        trustResetFailure("the Codex configuration directory handle could not be closed safely");
      }
    }
  }
}

function exactCodexInitializeResponse(message, requestId, codexHome) {
  if (message === null || typeof message !== "object" || Array.isArray(message)) return false;
  const responseKeys = Object.keys(message).sort();
  if (responseKeys.length !== 2 || responseKeys[0] !== "id" || responseKeys[1] !== "result") {
    return false;
  }
  if (message.id !== requestId) return false;
  const result = message.result;
  if (result === null || typeof result !== "object" || Array.isArray(result)) return false;
  const resultKeys = Object.keys(result).sort();
  if (
    resultKeys.length !== 4 ||
    resultKeys[0] !== "codexHome" ||
    resultKeys[1] !== "platformFamily" ||
    resultKeys[2] !== "platformOs" ||
    resultKeys[3] !== "userAgent"
  ) {
    return false;
  }
  return (
    result.codexHome === codexHome &&
    typeof result.platformFamily === "string" &&
    result.platformFamily.length > 0 &&
    typeof result.platformOs === "string" &&
    result.platformOs.length > 0 &&
    typeof result.userAgent === "string" &&
    result.userAgent.length > 0
  );
}

function codexAppServerValidationError() {
  return new InstallerError(
    "Codex OpenSocrates hook trust was not reset: the installed Codex app server did not accept the isolated configuration",
  );
}

function isolatedCodexValidationEnvironment(codexHome) {
  const environment = {
    PATH: process.env.PATH ?? "",
    HOME: codexHome,
    CODEX_HOME: codexHome,
    XDG_CACHE_HOME: join(codexHome, "xdg-cache"),
    XDG_CONFIG_HOME: join(codexHome, "xdg-config"),
    XDG_DATA_HOME: join(codexHome, "xdg-data"),
    XDG_STATE_HOME: join(codexHome, "xdg-state"),
    TMPDIR: join(codexHome, "tmp"),
    NO_COLOR: "1",
  };
  if (process.platform === "win32") {
    for (const key of ["ComSpec", "PATHEXT", "SystemRoot", "WINDIR"]) {
      if (typeof process.env[key] === "string") environment[key] = process.env[key];
    }
  }
  return environment;
}

async function runCodexAppServerConfigCheck(
  codexBin,
  codexHome,
  {
    spawnAppServer = spawn,
    timeoutMilliseconds = CODEX_APP_SERVER_TIMEOUT_MILLISECONDS,
    terminationMilliseconds = CODEX_APP_SERVER_TERMINATION_MILLISECONDS,
  } = {},
) {
  const requestId = 1;
  const request = Buffer.from(
    `${JSON.stringify({
      id: requestId,
      method: "initialize",
      params: {
        clientInfo: {
          name: "opensocrates_installer",
          title: "OpenSocrates Installer",
          version: PRODUCT_VERSION,
        },
        capabilities: { experimentalApi: false },
      },
    })}\n`,
    "utf8",
  );
  let child;
  try {
    child = spawnAppServer(codexBin, CODEX_APP_SERVER_ARGS, {
      cwd: codexHome,
      env: isolatedCodexValidationEnvironment(codexHome),
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });
  } catch {
    throw codexAppServerValidationError();
  }

  await new Promise((resolvePromise, rejectPromise) => {
    const timeoutDelay =
      Number.isFinite(timeoutMilliseconds) && timeoutMilliseconds > 0
        ? timeoutMilliseconds
        : CODEX_APP_SERVER_TIMEOUT_MILLISECONDS;
    const terminationDelay =
      Number.isFinite(terminationMilliseconds) && terminationMilliseconds > 0
        ? terminationMilliseconds
        : CODEX_APP_SERVER_TERMINATION_MILLISECONDS;
    let closed = false;
    let failed = false;
    let settled = false;
    let responseCount = 0;
    let responseAccepted = false;
    let outputBytes = 0;
    let lineBuffer = Buffer.alloc(0);
    let terminationTimer;
    let forcedFinishTimer;

    const clearTimers = () => {
      clearTimeout(deadlineTimer);
      if (terminationTimer !== undefined) clearTimeout(terminationTimer);
      if (forcedFinishTimer !== undefined) clearTimeout(forcedFinishTimer);
    };
    const finish = (accepted) => {
      if (settled) return;
      settled = true;
      clearTimers();
      if (accepted) resolvePromise();
      else rejectPromise(codexAppServerValidationError());
    };
    const terminate = () => {
      if (failed || settled) return;
      failed = true;
      try {
        child.stdin.end();
      } catch {
        // The stream may already be closed; process termination below remains bounded.
      }
      if (closed) {
        finish(false);
        return;
      }
      try {
        child.kill("SIGTERM");
      } catch {
        // A failed signal is followed by the bounded SIGKILL/final failure timers.
      }
      terminationTimer = setTimeout(() => {
        if (closed || settled) return;
        try {
          child.kill("SIGKILL");
        } catch {
          // The final timer still prevents an unbounded validator wait.
        }
        forcedFinishTimer = setTimeout(() => finish(false), terminationDelay);
      }, terminationDelay);
    };
    const consumeLine = (line) => {
      if (failed || settled) return;
      if (line.length > MAX_CODEX_APP_SERVER_LINE_BYTES || line.length === 0) {
        terminate();
        return;
      }
      const normalized = line.at(-1) === 0x0d ? line.subarray(0, -1) : line;
      let message;
      try {
        message = JSON.parse(normalized.toString("utf8"));
      } catch {
        terminate();
        return;
      }
      responseCount += 1;
      if (
        responseCount !== 1 ||
        !exactCodexInitializeResponse(message, requestId, codexHome)
      ) {
        terminate();
        return;
      }
      responseAccepted = true;
    };
    const deadlineTimer = setTimeout(terminate, timeoutDelay);

    child.stdout.on("data", (chunk) => {
      if (failed || settled) return;
      const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      outputBytes += bytes.length;
      if (outputBytes > MAX_CODEX_APP_SERVER_OUTPUT_BYTES) {
        terminate();
        return;
      }
      lineBuffer = Buffer.concat([lineBuffer, bytes]);
      for (;;) {
        const newline = lineBuffer.indexOf(0x0a);
        if (newline < 0) break;
        const line = lineBuffer.subarray(0, newline);
        lineBuffer = lineBuffer.subarray(newline + 1);
        consumeLine(line);
        if (failed || settled) return;
      }
      if (lineBuffer.length > MAX_CODEX_APP_SERVER_LINE_BYTES) terminate();
    });
    child.stderr.on("data", (chunk) => {
      if (failed || settled) return;
      const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      outputBytes += bytes.length;
      if (outputBytes > MAX_CODEX_APP_SERVER_OUTPUT_BYTES) terminate();
    });
    child.once("error", terminate);
    child.stdin.once("error", terminate);
    child.once("close", (code, signal) => {
      closed = true;
      finish(
        !failed &&
          code === 0 &&
          signal === null &&
          responseCount === 1 &&
          responseAccepted &&
          lineBuffer.length === 0,
      );
    });

    try {
      child.stdin.end(request);
    } catch {
      terminate();
    }
  });
}

async function validateCodexConfigBytes(
  codexBin,
  contents,
  {
    removeValidationHome = rm,
    spawnAppServer = spawn,
    validationTimeoutMilliseconds = CODEX_APP_SERVER_TIMEOUT_MILLISECONDS,
    validationTerminationMilliseconds = CODEX_APP_SERVER_TERMINATION_MILLISECONDS,
  } = {},
) {
  let validationHome;
  let operationFailed = false;
  try {
    validationHome = await mkdtemp(join(tmpdir(), "opensocrates-codex-config-check-"));
    await chmod(validationHome, 0o700);
    for (const directory of ["tmp", "xdg-cache", "xdg-config", "xdg-data", "xdg-state"]) {
      await mkdir(join(validationHome, directory), { mode: 0o700 });
    }
    const target = join(validationHome, "config.toml");
    await writeSyncedOwnerOnlyFile(target, contents);
    await runCodexAppServerConfigCheck(codexBin, validationHome, {
      spawnAppServer,
      timeoutMilliseconds: validationTimeoutMilliseconds,
      terminationMilliseconds: validationTerminationMilliseconds,
    });
  } catch (error) {
    operationFailed = true;
    if (error instanceof InstallerError) throw error;
    trustResetFailure("the Codex configuration could not be validated in isolation");
  } finally {
    if (validationHome !== undefined) {
      try {
        await removeValidationHome(validationHome, { recursive: true, force: true });
      } catch {
        if (!operationFailed) {
          trustResetFailure("the isolated Codex validation environment could not be removed safely");
        }
      }
    }
  }
}

async function restoreTrustConfig({
  rollback,
  target,
  parent,
  original,
  originalMode,
  originalUid,
  originalGid,
}) {
  try {
    if (!(await entryExists(rollback))) trustResetFailure("the rollback copy is unavailable");
    await rename(rollback, target);
    await chown(target, originalUid, originalGid);
    await chmod(target, originalMode);
    await fsyncFile(target);
    await fsyncDirectory(parent);
    const restored = await readConfigSnapshot(target);
    if (
      !restored.contents.equals(original) ||
      Number(restored.info.mode & 0o7777n) !== originalMode ||
      restored.info.uid !== BigInt(originalUid) ||
      restored.info.gid !== BigInt(originalGid)
    ) {
      trustResetFailure("the original configuration was not restored");
    }
  } catch (error) {
    if (error instanceof InstallerError) throw error;
    trustResetFailure("the original configuration could not be restored automatically");
  }
}

/**
 * Reset only OpenSocrates Codex hook trust. Optional hooks are dependency
 * injection seams for isolated failure/race tests; production callers pass no
 * hooks and always use the installed Codex CLI for validation.
 */
export async function resetCodexOpenSocratesHookTrust({
  codexHome = process.env.CODEX_HOME || join(homedir(), ".codex"),
  codexBin = codexBinary(),
  hooks = {},
} = {}) {
  const lexicalHome = resolve(codexHome);
  if (!(await entryExists(lexicalHome))) return { status: "absent", removedEvents: [] };
  const lexicalInfo = await lstat(lexicalHome);
  assertOwnedDirectory(lexicalInfo);
  let parent;
  try {
    parent = await realpath(lexicalHome);
  } catch {
    trustResetFailure("the Codex configuration directory could not be canonicalized");
  }
  const parentInfo = await lstat(parent);
  assertOwnedDirectory(parentInfo);
  const target = join(parent, "config.toml");
  if (!(await entryExists(target))) return { status: "absent", removedEvents: [] };
  const targetInfo = await lstat(target);
  assertOwnedConfigFile(targetInfo);
  const snapshot = await readConfigSnapshot(target);
  const originalMode = Number(snapshot.info.mode & 0o7777n);
  const originalUid = Number(snapshot.info.uid);
  const originalGid = Number(snapshot.info.gid);
  const validationOptions = {
    removeValidationHome: hooks.removeValidationHome,
    spawnAppServer: hooks.spawnAppServer,
    validationTimeoutMilliseconds: hooks.validationTimeoutMilliseconds,
    validationTerminationMilliseconds: hooks.validationTerminationMilliseconds,
  };
  await validateCodexConfigBytes(codexBin, snapshot.contents, validationOptions);
  const stripped = stripCodexOpenSocratesTrustSections(snapshot.contents);
  if (stripped.removedEvents.length === 0) {
    const current = await readConfigSnapshot(target);
    if (!sameSnapshot(snapshot.info, current.info) || !current.contents.equals(snapshot.contents)) {
      trustResetFailure("the Codex configuration changed during isolated validation");
    }
    return { status: "absent", removedEvents: [] };
  }
  await validateCodexConfigBytes(codexBin, stripped.contents, validationOptions);

  const token = randomUUID();
  const temporary = join(parent, `.config.toml.opensocrates-trust-reset-${token}.tmp`);
  const rollback = join(parent, `.config.toml.opensocrates-trust-reset-${token}.rollback`);
  let replaced = false;
  let preserveRollback = false;
  let transactionFailed = false;
  let transactionCommitted = false;
  let cleanupRequired = true;
  try {
    await hooks.beforeWrite?.({ target });
    await writeSyncedOwnerOnlyFile(temporary, stripped.contents);
    await writeSyncedOwnerOnlyFile(rollback, snapshot.contents);
    await fsyncDirectory(parent);
    await hooks.beforeRename?.({ target, temporary, rollback });
    const current = await readConfigSnapshot(target);
    if (!sameSnapshot(snapshot.info, current.info) || !current.contents.equals(snapshot.contents)) {
      trustResetFailure("the Codex configuration changed before the atomic update");
    }
    await rename(temporary, target);
    replaced = true;
    await chown(target, originalUid, originalGid);
    await chmod(target, originalMode);
    await fsyncFile(target);
    await fsyncDirectory(parent);
    await hooks.afterRename?.({ target, rollback });
    const committed = await readConfigSnapshot(target);
    if (
      !committed.contents.equals(stripped.contents) ||
      Number(committed.info.mode & 0o7777n) !== originalMode ||
      committed.info.uid !== BigInt(originalUid) ||
      committed.info.gid !== BigInt(originalGid)
    ) {
      trustResetFailure("the committed Codex configuration did not match the validated candidate");
    }
    await validateCodexConfigBytes(codexBin, committed.contents, validationOptions);
    await (hooks.removeRollback ?? rm)(rollback);
    // The candidate and parent rename are already fsynced and post-validated.
    // Keep rollback unlink as the final fallible commit step; another directory
    // fsync would only create a failure point after the recovery source is gone.
    transactionCommitted = true;
    cleanupRequired = false;
    return { status: "reset", removedEvents: stripped.removedEvents };
  } catch (error) {
    transactionFailed = true;
    if (replaced) {
      let canRollback = false;
      try {
        const current = await readConfigSnapshot(target);
        canRollback = current.contents.equals(stripped.contents);
      } catch {
        canRollback = false;
      }
      if (!canRollback) {
        preserveRollback = true;
        trustResetFailure(
          "the Codex configuration changed after replacement; automatic rollback was withheld and the owner-only recovery copy was preserved",
        );
      }
      await restoreTrustConfig({
        rollback,
        target,
        parent,
        original: snapshot.contents,
        originalMode,
        originalUid,
        originalGid,
      });
    }
    if (error instanceof InstallerError) throw error;
    trustResetFailure("the atomic configuration update failed; the original configuration was preserved");
  } finally {
    let cleanupFailed = false;
    if (cleanupRequired) {
      for (const residue of [temporary, rollback]) {
        try {
          if (residue === rollback && preserveRollback) continue;
          await hooks.beforeResidueCleanup?.({ residue });
          if (await entryExists(residue)) await rm(residue);
        } catch {
          cleanupFailed = true;
        }
      }
    }
    if (cleanupFailed && !transactionFailed && !transactionCommitted) {
      trustResetFailure("owner-only Codex transaction residue could not be removed safely");
    }
  }
}

export class InstallerError extends Error {}

function fail(message) {
  throw new InstallerError(message);
}

function shellQuote(value) {
  return `'${String(value).replaceAll("'", `'"'"'`)}'`;
}

async function exists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}

// Destructive paths must distinguish a missing entry from a dangling symlink.
// access() follows links, so it is intentionally insufficient at deletion
// boundaries where an unresolvable link must be refused rather than reported
// as already absent.
async function entryExists(target) {
  try {
    await lstat(target);
    return true;
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}

async function requireRegularFileEntry(target, label) {
  const info = await lstat(target);
  if (!info.isFile() || info.isSymbolicLink()) {
    fail(`refusing an unsafe ${label}: ${target}`);
  }
}

export function statePaths() {
  const stateDirectory = resolve(process.env.OPENSOCRATES_STATE_DIR || join(homedir(), ".opensocrates"));
  const launchAgentsDirectory = resolve(
    process.env.OPENSOCRATES_LAUNCH_AGENTS_DIR || join(homedir(), "Library", "LaunchAgents"),
  );
  return {
    directory: stateDirectory,
    desiredState: join(stateDirectory, "desired-state.json"),
    receipt: join(stateDirectory, "auto-update-receipt.json"),
    lock: join(stateDirectory, "lifecycle.lock"),
    launchAgentsDirectory,
    launchAgent: join(launchAgentsDirectory, `${AUTO_UPDATE_LABEL}.plist`),
  };
}

function defaultDesiredState() {
  return {
    schema: DESIRED_STATE_SCHEMA,
    channel: "stable",
    installedHosts: [],
    activeVersion: null,
    updatePolicy: {
      intervalHours: AUTO_UPDATE_DEFAULT_INTERVAL_HOURS,
      allowMajor: false,
    },
    autoUpdate: {
      enabled: false,
      hosts: [],
      nextCheckAt: null,
    },
    availableVersion: null,
    lastCheckAt: null,
    lastSuccessfulUpdateAt: null,
  };
}

function normalizeDesiredState(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value) || value.schema !== DESIRED_STATE_SCHEMA) {
    fail("the OpenSocrates desired-state manifest has an unsupported schema");
  }
  const installedHosts = value.installedHosts;
  if (
    !Array.isArray(installedHosts) ||
    installedHosts.some((host) => !SUPPORTED_HOSTS.includes(host)) ||
    new Set(installedHosts).size !== installedHosts.length
  ) {
    fail("the OpenSocrates desired-state manifest has an invalid host set");
  }
  const channel = value.channel;
  if (!new Set(["stable", "next"]).has(channel)) {
    fail("the OpenSocrates desired-state manifest has an invalid update channel");
  }
  const intervalHours = value.updatePolicy?.intervalHours;
  if (
    !Number.isInteger(intervalHours) ||
    intervalHours < AUTO_UPDATE_MIN_INTERVAL_HOURS ||
    intervalHours > AUTO_UPDATE_MAX_INTERVAL_HOURS ||
    typeof value.updatePolicy?.allowMajor !== "boolean" ||
    typeof value.autoUpdate?.enabled !== "boolean"
  ) {
    fail("the OpenSocrates desired-state manifest has an invalid update policy");
  }
  const autoUpdateHosts =
    value.autoUpdate.hosts === undefined ? (value.autoUpdate.enabled ? installedHosts : []) : value.autoUpdate.hosts;
  if (
    !Array.isArray(autoUpdateHosts) ||
    autoUpdateHosts.some((host) => !SUPPORTED_HOSTS.includes(host) || !installedHosts.includes(host)) ||
    new Set(autoUpdateHosts).size !== autoUpdateHosts.length ||
    (value.autoUpdate.enabled && autoUpdateHosts.length === 0) ||
    (!value.autoUpdate.enabled && autoUpdateHosts.length > 0)
  ) {
    fail("the OpenSocrates desired-state manifest has an invalid automatic-update host set");
  }
  return {
    ...defaultDesiredState(),
    ...value,
    installedHosts: [...installedHosts].sort(),
    updatePolicy: {
      intervalHours,
      allowMajor: value.updatePolicy.allowMajor,
    },
    autoUpdate: {
      enabled: value.autoUpdate.enabled,
      hosts: [...autoUpdateHosts].sort(),
      nextCheckAt: value.autoUpdate.nextCheckAt ?? null,
    },
  };
}

export async function readDesiredState() {
  const { desiredState } = statePaths();
  if (!(await entryExists(desiredState))) {
    return defaultDesiredState();
  }
  await requireRegularFileEntry(desiredState, "OpenSocrates desired-state file");
  let value;
  try {
    value = JSON.parse(await readFile(desiredState, "utf8"));
  } catch (error) {
    fail(`cannot read the OpenSocrates desired-state manifest: ${error.message}`);
  }
  return normalizeDesiredState(value);
}

async function ensurePrivateDirectory(directory) {
  if (await exists(directory)) {
    const info = await lstat(directory);
    if (!info.isDirectory() || info.isSymbolicLink()) {
      fail(`refusing to use a non-directory or symbolic-link state path: ${directory}`);
    }
    await chmod(directory, 0o700);
    return;
  }
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const info = await lstat(directory);
  if (!info.isDirectory() || info.isSymbolicLink()) {
    fail(`refusing to use an unsafe state path: ${directory}`);
  }
  await chmod(directory, 0o700);
}

async function atomicWritePrivateFile(target, contents) {
  const parent = dirname(target);
  await ensurePrivateDirectory(parent);
  const temporary = join(parent, `.${basename(target)}.${randomUUID()}.tmp`);
  try {
    await writeFile(temporary, contents, {
      encoding: "utf8",
      mode: 0o600,
      flag: "wx",
    });
    await chmod(temporary, 0o600);
    await rename(temporary, target);
  } finally {
    if (await exists(temporary)) {
      await rm(temporary, { force: true });
    }
  }
}

export async function writeDesiredState(value) {
  const normalized = normalizeDesiredState(value);
  await atomicWritePrivateFile(statePaths().desiredState, `${JSON.stringify(normalized, null, 2)}\n`);
  return normalized;
}

async function writeAutoUpdateReceipt({ version, checkedAt, hosts, result, errorCategory }) {
  const receipt = {
    schema: RECEIPT_SCHEMA,
    version,
    checkedAt,
    hosts: [...hosts]
      .sort((left, right) => left.host.localeCompare(right.host))
      .map(({ host, result: hostResult }) => ({
        host,
        result: hostResult,
      })),
    result,
    errorCategory: errorCategory ?? null,
  };
  await atomicWritePrivateFile(statePaths().receipt, `${JSON.stringify(receipt, null, 2)}\n`);
}

function nowIso() {
  return new Date().toISOString();
}

function nextCheckAt(intervalHours) {
  const intervalMilliseconds = intervalHours * 60 * 60 * 1000;
  const jitterBasisPoints = randomInt(-1500, 1501);
  return new Date(Date.now() + intervalMilliseconds * (1 + jitterBasisPoints / 10_000)).toISOString();
}

function majorVersion(value) {
  const match = String(value ?? "").match(/^(\d+)\./u);
  return match ? Number(match[1]) : null;
}

function errorCategory(error) {
  const message = error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase();
  if (/checksum|manifest|archive|symbolic link/u.test(message)) return "verification";
  if (/download|fetch|network|offline|timed? ?out/u.test(message)) return "network";
  if (/preflight|not logged|auth|version is required|could not run/u.test(message)) return "preflight";
  if (/rollback|restore/u.test(message)) return "rollback";
  if (/lock|already running/u.test(message)) return "locked";
  if (/register|plugin|marketplace/u.test(message)) return "activation";
  return "internal";
}

async function acquireOperationLock() {
  const paths = statePaths();
  await ensurePrivateDirectory(paths.directory);
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const handle = await open(paths.lock, "wx", 0o600);
      try {
        await handle.writeFile(`${JSON.stringify({ pid: process.pid, startedAt: nowIso() })}\n`, "utf8");
      } catch (writeError) {
        await handle.close().catch(() => undefined);
        await rm(paths.lock, { force: true }).catch(() => undefined);
        throw writeError;
      }
      return async () => {
        try {
          await handle.close();
        } finally {
          await rm(paths.lock, { force: true });
        }
      };
    } catch (error) {
      if (error?.code !== "EEXIST") {
        throw error;
      }
      let stale = false;
      try {
        const lock = JSON.parse(await readFile(paths.lock, "utf8"));
        const started = Date.parse(lock.startedAt);
        let ownerAlive = null;
        if (Number.isInteger(lock.pid) && lock.pid > 0) {
          try {
            process.kill(lock.pid, 0);
            ownerAlive = true;
          } catch (processError) {
            ownerAlive = processError?.code === "ESRCH" ? false : true;
          }
        }
        stale =
          ownerAlive === false ||
          (ownerAlive === null && Number.isFinite(started) && Date.now() - started > LOCK_STALE_MILLISECONDS);
      } catch {
        const info = await lstat(paths.lock);
        stale = Date.now() - info.mtimeMs > LOCK_STALE_MILLISECONDS;
      }
      if (!stale || attempt > 0) {
        fail("another OpenSocrates lifecycle operation is already running");
      }
      await rm(paths.lock, { force: true });
    }
  }
  fail("could not acquire the OpenSocrates lifecycle lock");
}

export async function withOperationLock(action) {
  const release = await acquireOperationLock();
  try {
    return await action();
  } finally {
    await release();
  }
}

function jsonEqual(left, right) {
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  return (
    leftKeys.length === rightKeys.length &&
    leftKeys.every((key, index) => key === rightKeys[index] && left[key] === right[key])
  );
}

function jsonDeepEqual(left, right) {
  if (left === right) return true;
  if (Array.isArray(left) || Array.isArray(right)) {
    return (
      Array.isArray(left) &&
      Array.isArray(right) &&
      left.length === right.length &&
      left.every((item, index) => jsonDeepEqual(item, right[index]))
    );
  }
  if (
    left === null ||
    right === null ||
    typeof left !== "object" ||
    typeof right !== "object"
  ) {
    return false;
  }
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  return (
    leftKeys.length === rightKeys.length &&
    leftKeys.every(
      (key, index) => key === rightKeys[index] && jsonDeepEqual(left[key], right[key]),
    )
  );
}

function markerFor(host) {
  if (host === "cursor") return CURSOR_MARKER;
  if (host === "antigravity") return ANTIGRAVITY_MARKER;
  if (host === "grok") return GROK_MARKER;
  if (host === "opencode") return OPENCODE_MARKER;
  return host === "claude" ? CLAUDE_MARKER : CODEX_MARKER;
}

export function markerMatches(value, host = DEFAULT_HOST) {
  return value !== null && typeof value === "object" && !Array.isArray(value) && jsonEqual(value, markerFor(host));
}

export function isSafeArchivePath(value) {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.includes("\0") ||
    value.includes("\\") ||
    value.startsWith("/")
  ) {
    return false;
  }
  const candidate = value.endsWith("/") ? value.slice(0, -1) : value;
  if (candidate.length === 0) {
    return false;
  }
  return candidate.split("/").every((part) => part.length > 0 && part !== "." && part !== "..");
}

export function parseChecksumText(text, expectedName = ASSET_NAME) {
  const candidates = String(text)
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean);
  for (const line of candidates) {
    const match = line.match(/^([a-fA-F0-9]{64})(?:\s+[*]?(.+))?$/u);
    if (!match) {
      continue;
    }
    const namedFile = match[2]?.trim();
    if (namedFile && basename(namedFile) !== expectedName) {
      continue;
    }
    return match[1].toLowerCase();
  }
  fail(`checksum file does not contain a SHA-256 entry for ${expectedName}`);
}

export function parseCli(argv) {
  const actions = new Set(["install", "status", "update", "remove", "verify", "auto-update", "help"]);
  const args = [...argv];
  let action = "install";
  if (args[0] && !args[0].startsWith("-")) {
    action = args.shift();
  }
  if (!actions.has(action)) {
    fail(`unknown action ${JSON.stringify(action)}`);
  }
  let autoUpdateAction = null;
  if (action === "auto-update") {
    if (["--help", "-h"].includes(args[0])) {
      args.shift();
      action = "help";
    } else {
      autoUpdateAction = args.shift() ?? "status";
      if (!new Set(["enable", "status", "disable", "run"]).has(autoUpdateAction)) {
        fail(`unknown auto-update action ${JSON.stringify(autoUpdateAction)}`);
      }
    }
  }
  const options = {
    action,
    autoUpdateAction,
    host: action === "auto-update" ? ALL_HOST : DEFAULT_HOST,
    asset: null,
    checksum: null,
    hostAssets: Object.fromEntries(SUPPORTED_HOSTS.map((host) => [host, { asset: null, checksum: null }])),
    channel: "stable",
    intervalHours: AUTO_UPDATE_DEFAULT_INTERVAL_HOURS,
    allowMajor: false,
    force: false,
    purge: false,
    resetTrust: false,
  };
  const seenOptions = new Set();
  while (args.length > 0) {
    const flag = args.shift();
    if (flag === "--help" || flag === "-h") {
      options.action = "help";
      continue;
    }
    if (flag === "--host") {
      seenOptions.add("host");
      const host = args.shift();
      if (!HOST_CHOICES.includes(host)) {
        fail(`--host must be one of: ${HOST_CHOICES.join(", ")}`);
      }
      options.host = host;
      continue;
    }
    if (flag === "--allow-major") {
      seenOptions.add("allow-major");
      options.allowMajor = true;
      continue;
    }
    if (flag === "--force") {
      seenOptions.add("force");
      options.force = true;
      continue;
    }
    if (flag === "--purge") {
      seenOptions.add("purge");
      options.purge = true;
      continue;
    }
    if (flag === "--reset-trust") {
      seenOptions.add("reset-trust");
      options.resetTrust = true;
      continue;
    }
    if (flag === "--channel") {
      seenOptions.add("channel");
      const channel = args.shift();
      if (!new Set(["stable", "next"]).has(channel)) {
        fail("--channel must be one of: stable, next");
      }
      options.channel = channel;
      continue;
    }
    if (flag === "--interval-hours") {
      seenOptions.add("interval-hours");
      const raw = args.shift();
      const value = Number(raw);
      if (
        !Number.isInteger(value) ||
        value < AUTO_UPDATE_MIN_INTERVAL_HOURS ||
        value > AUTO_UPDATE_MAX_INTERVAL_HOURS
      ) {
        fail(
          `--interval-hours must be an integer from ${AUTO_UPDATE_MIN_INTERVAL_HOURS} ` +
            `through ${AUTO_UPDATE_MAX_INTERVAL_HOURS}`,
        );
      }
      options.intervalHours = value;
      continue;
    }
    const qualified = flag?.match(new RegExp(`^--(asset|checksum)-(${SUPPORTED_HOSTS.join("|")})$`, "u"));
    if (qualified) {
      seenOptions.add(qualified[1]);
      const value = args.shift();
      if (!value || value.startsWith("-")) {
        fail(`${flag} requires a file path`);
      }
      options.hostAssets[qualified[2]][qualified[1]] = resolve(value);
      continue;
    }
    if (flag !== "--asset" && flag !== "--checksum") {
      fail(`unknown option ${JSON.stringify(flag)}`);
    }
    const value = args.shift();
    if (!value || value.startsWith("-")) {
      fail(`${flag} requires a file path`);
    }
    options[flag === "--asset" ? "asset" : "checksum"] = resolve(value);
    seenOptions.add(flag.slice(2));
  }
  if ((options.asset === null) !== (options.checksum === null)) {
    fail("--asset and --checksum must be supplied together");
  }
  for (const host of SUPPORTED_HOSTS) {
    const inputs = options.hostAssets[host];
    if ((inputs.asset === null) !== (inputs.checksum === null)) {
      fail(`--asset-${host} and --checksum-${host} must be supplied together`);
    }
  }
  if (options.host === ALL_HOST && options.asset !== null) {
    fail("--host all requires host-qualified --asset-<host> and --checksum-<host> options");
  }
  if (options.host !== ALL_HOST && SUPPORTED_HOSTS.some((host) => options.hostAssets[host].asset !== null)) {
    fail("host-qualified asset options are only valid with --host all");
  }
  if (["status", "remove", "help"].includes(options.action) && options.asset !== null) {
    fail(`${options.action} does not accept --asset or --checksum`);
  }
  if (
    ["status", "remove", "help"].includes(options.action) &&
    SUPPORTED_HOSTS.some((host) => options.hostAssets[host].asset !== null)
  ) {
    fail(`${options.action} does not accept host-qualified asset options`);
  }
  if (
    options.action === "auto-update" &&
    options.autoUpdateAction !== "run" &&
    (options.asset !== null || SUPPORTED_HOSTS.some((host) => options.hostAssets[host].asset !== null))
  ) {
    fail(`auto-update ${options.autoUpdateAction} does not accept local asset options`);
  }
  const autoUpdateEnable = options.action === "auto-update" && options.autoUpdateAction === "enable";
  const autoUpdateRun = options.action === "auto-update" && options.autoUpdateAction === "run";
  for (const policyOption of ["allow-major", "channel", "interval-hours"]) {
    if (seenOptions.has(policyOption) && !autoUpdateEnable) {
      fail(`--${policyOption} is only valid with auto-update enable`);
    }
  }
  if (seenOptions.has("force") && !autoUpdateRun) {
    fail("--force is only valid with auto-update run");
  }
  if (seenOptions.has("purge") && options.action !== "remove") {
    fail("--purge is only valid with remove");
  }
  if (seenOptions.has("reset-trust") && (options.action !== "remove" || !options.purge)) {
    fail("--reset-trust requires remove --purge");
  }
  if (seenOptions.has("reset-trust") && !new Set([ALL_HOST, "codex"]).has(options.host)) {
    fail("--reset-trust is only valid with --host codex or --host all");
  }
  if (
    seenOptions.has("host") &&
    options.action === "auto-update" &&
    new Set(["status", "disable"]).has(options.autoUpdateAction)
  ) {
    fail(`auto-update ${options.autoUpdateAction} does not accept --host`);
  }
  if (autoUpdateRun && seenOptions.has("host") && options.host !== ALL_HOST) {
    fail("auto-update run always reconciles desired state and only accepts --host all");
  }
  return options;
}

function showHelp() {
  console.log(`OpenSocrates ${PRODUCT_VERSION}

Usage:
  opensocrates install [--host all|antigravity|claude|codex|cursor|grok|opencode] [--asset ZIP --checksum FILE]
  opensocrates status [--host all|antigravity|claude|codex|cursor|grok|opencode]
  opensocrates update [--host all|antigravity|claude|codex|cursor|grok|opencode] [--asset ZIP --checksum FILE]
  opensocrates remove [--host all|antigravity|claude|codex|cursor|grok|opencode] [--purge [--reset-trust]]
  opensocrates verify [--host all|antigravity|claude|codex|cursor|grok|opencode] [--asset ZIP --checksum FILE]
  opensocrates auto-update enable [--host all|antigravity|claude|codex|cursor|grok|opencode]
      [--channel stable|next] [--interval-hours ${AUTO_UPDATE_DEFAULT_INTERVAL_HOURS}]
      [--allow-major]
  opensocrates auto-update status
  opensocrates auto-update disable

Without --asset, install, update, and verify download the v${PRODUCT_VERSION}
package and checksum from GitHub Releases. The default lifecycle host is codex.
With --host all, supplied host-qualified asset/checksum pairs define the exact
transaction set and are never mixed with downloads for other hosts. Without
qualified assets, every ready host participates. Automatic updates are opt-in.

Ordinary remove unregisters the selected host and removes installer-managed
files, but may leave host-owned caches, installer state, and Codex hook trust.
Add --purge for an explicit payload/data cleanup attempt. Purge preserves Codex
hook trust unless --reset-trust is also supplied for codex or all; that explicit
option removes only the seven canonical OpenSocrates trust entries. Registration,
payload cleanup, host security trust, and user history are reported separately.
User history is always preserved. Any unverified, unsafe, or in-use component is
reported as pending.
`);
}

function managedPaths(host) {
  const configured =
    host === "antigravity"
      ? process.env.ANTIGRAVITY_CONFIG_DIR
      : host === "cursor"
        ? process.env.CURSOR_CONFIG_DIR
        : host === "grok"
          ? process.env.GROK_HOME
          : host === "opencode"
            ? process.env.OPENCODE_CONFIG_DIR
            : host === "claude"
              ? process.env.CLAUDE_CONFIG_DIR
              : process.env.CODEX_HOME;
  const defaultHome =
    host === "antigravity"
      ? join(homedir(), ".gemini", "config")
      : host === "cursor"
        ? join(homedir(), ".cursor")
        : host === "grok"
          ? join(homedir(), ".grok")
          : host === "opencode"
            ? join(homedir(), ".config", "opencode")
            : join(homedir(), host === "claude" ? ".claude" : ".codex");
  const configuredHome = resolve(configured ? configured : defaultHome);
  let hostHome = configuredHome;
  try {
    hostHome = realpathSync(configuredHome);
  } catch {
    // The installer creates a missing host home below after validating its
    // explicit, non-recursive target. Lexical resolution is the only
    // available normalization until then.
  }
  const root =
    host === "antigravity"
      ? join(hostHome, "plugins", PLUGIN_NAME)
      : host === "cursor"
        ? join(hostHome, "plugins", "local", PLUGIN_NAME)
        : host === "grok"
          ? join(hostHome, "plugins", PLUGIN_NAME)
          : host === "opencode"
            ? join(hostHome, "skills", PLUGIN_NAME)
            : join(hostHome, "managed-marketplaces", MARKETPLACE_NAME);
  const layout = HOST_LAYOUTS[host];
  return {
    hostHome,
    root,
    parent: dirname(root),
    marker: join(root, MARKER_NAME),
    marketplace: typeof layout.marketplaceRelative === "string" ? join(root, layout.marketplaceRelative) : null,
    plugin: join(root, layout.pluginRelative),
    bridge: host === "opencode" ? join(hostHome, "plugins", "opensocrates.js") : null,
    bridgeMarker: host === "opencode" ? join(hostHome, "plugins", OPENCODE_BRIDGE_MARKER) : null,
    bridgeParent: host === "opencode" ? join(hostHome, "plugins") : null,
  };
}

export function purgePathsFor(host) {
  if (!SUPPORTED_HOSTS.includes(host)) {
    fail(`unsupported host ${JSON.stringify(host)}`);
  }
  const paths = managedPaths(host);
  const cacheRoot = ["claude", "codex"].includes(host)
    ? join(paths.hostHome, "plugins", "cache", MARKETPLACE_NAME, PLUGIN_NAME)
    : null;
  return {
    ...paths,
    cacheRoot,
    cacheMarketplaceRoot: cacheRoot === null ? null : dirname(cacheRoot),
    pluginData:
      host === "claude"
        ? [
            join(paths.hostHome, "plugins", "data", "opensocrates-inline"),
            join(paths.hostHome, "plugins", "data", "opensocrates-opensocrates"),
          ]
        : [],
  };
}

// Directory that holds staging trees and rollback backups for one host.
//
// Grok scans every directory below ~/.grok/plugins, including dot-prefixed
// ones, so a staging tree or rollback backup left there would be discovered as
// a second OpenSocrates plugin. An interrupted install must not be able to
// leave a shadow copy inside Grok's plugin discovery root, so both transient
// directories live in the Grok home instead, next to the scanned directory.
function transientParent(host, paths) {
  return host === "grok" ? paths.hostHome : paths.parent;
}

export function transientPathsFor(host) {
  const paths = managedPaths(host);
  return { root: paths.root, parent: paths.parent, transient: transientParent(host, paths) };
}

function codexBinary() {
  return process.env.CODEX_BIN || "codex";
}

function claudeBinary() {
  return process.env.CLAUDE_BIN || "claude";
}

function cursorBinary() {
  return process.env.CURSOR_BIN || "cursor";
}

function cursorAppPaths() {
  return ["/Applications/Cursor.app", join(homedir(), "Applications", "Cursor.app")];
}

function antigravityBinary() {
  return process.env.AGY_BIN || "agy";
}

function grokBinary() {
  return process.env.GROK_BIN || "grok";
}

function opencodeBinary() {
  return process.env.OPENCODE_BIN || "opencode";
}

function run(command, args, { allowFailure = false } = {}) {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    env: process.env,
    maxBuffer: 16 * 1024 * 1024,
  });
  if (result.error) {
    if (allowFailure) {
      return result;
    }
    fail(`could not run ${command}: ${result.error.message}`);
  }
  if (result.status !== 0 && !allowFailure) {
    const detail = result.stderr?.trim() || result.stdout?.trim() || `exit ${result.status}`;
    fail(`${command} ${args.join(" ")} failed: ${detail}`);
  }
  return result;
}

function runJson(command, args, label) {
  const result = run(command, args);
  try {
    const payload = JSON.parse(result.stdout);
    if (payload === null || typeof payload !== "object") {
      fail(`${label} returned a non-container JSON value`);
    }
    return payload;
  } catch (error) {
    if (error instanceof InstallerError) {
      throw error;
    }
    fail(`${label} returned invalid JSON for ${args.join(" ")}: ${error.message}`);
  }
}

function runCodexJson(args) {
  const payload = runJson(codexBinary(), args, "Codex");
  if (Array.isArray(payload)) {
    fail("Codex returned an unexpected JSON array");
  }
  return payload;
}

function runClaudeJson(args) {
  return runJson(claudeBinary(), args, "Claude Code");
}

function runGrokJson(args) {
  return runJson(grokBinary(), args, "Grok Build");
}

function claudeListEntries(payload, wrapper, label) {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (
    payload !== null &&
    typeof payload === "object" &&
    !Array.isArray(payload) &&
    Object.keys(payload).length === 1 &&
    Array.isArray(payload[wrapper])
  ) {
    return payload[wrapper];
  }
  fail(`Claude Code ${label} returned an unexpected schema`);
}

function requireUniqueClaudeEntries(entries, identity, label) {
  const seen = new Set();
  for (const entry of entries) {
    if (
      entry === null ||
      typeof entry !== "object" ||
      Array.isArray(entry) ||
      typeof entry[identity] !== "string" ||
      entry[identity].trim().length === 0
    ) {
      fail(`Claude Code ${label} returned a malformed entry`);
    }
    if (seen.has(entry[identity])) {
      fail(`Claude Code ${label} returned duplicate entries for ${entry[identity]}`);
    }
    seen.add(entry[identity]);
  }
  return entries;
}

function claudeMarketplaceEntries(payload) {
  return requireUniqueClaudeEntries(
    claudeListEntries(payload, "marketplaces", "marketplace list"),
    "name",
    "marketplace list",
  );
}

function claudePluginEntries(payload) {
  return requireUniqueClaudeEntries(claudeListEntries(payload, "plugins", "plugin list"), "id", "plugin list");
}

function versionAtLeast(value, minimum) {
  const match = String(value).match(/(\d+)\.(\d+)\.(\d+)/u);
  if (!match) {
    return false;
  }
  const current = match.slice(1).map(Number);
  for (let index = 0; index < minimum.length; index += 1) {
    if (current[index] > minimum[index]) return true;
    if (current[index] < minimum[index]) return false;
  }
  return true;
}

function requireHostCli(host, { authenticated = false } = {}) {
  if (host === "grok") {
    const result = run(grokBinary(), ["--version"]);
    if (!versionAtLeast(result.stdout, [1, 0, 3])) {
      fail(`Grok Build 1.0.3 or later is required; got ${result.stdout.trim()}`);
    }
    return;
  }
  if (host === "cursor") {
    if (process.env.CURSOR_CONFIG_DIR) return;
    if (process.env.CURSOR_BIN) {
      const result = run(cursorBinary(), ["--version"]);
      if (!versionAtLeast(result.stdout, [2, 5, 0])) {
        fail(`Cursor 2.5.0 or later is required; got ${result.stdout.trim()}`);
      }
      return;
    }
    const app = cursorAppPaths().find((candidate) => existsSync(candidate));
    if (app) {
      const result = run(
        "/usr/bin/plutil",
        ["-extract", "CFBundleShortVersionString", "raw", join(app, "Contents", "Info.plist")],
        { allowFailure: true },
      );
      if (result.status !== 0 || !versionAtLeast(result.stdout, [2, 5, 0])) {
        fail("Cursor 2.5.0 or later is required for Agent Plugin support");
      }
      return;
    }
    const result = run(cursorBinary(), ["--version"]);
    if (!versionAtLeast(result.stdout, [2, 5, 0])) {
      fail(`Cursor 2.5.0 or later is required; got ${result.stdout.trim()}`);
    }
    return;
  }
  if (host === "antigravity") {
    if (process.env.ANTIGRAVITY_CONFIG_DIR) return;
    run(antigravityBinary(), ["--version"]);
    return;
  }
  if (host === "opencode") {
    // OPENCODE_CONFIG_DIR only redirects where the managed files are written;
    // it does not waive the supported-host gate. Unlike the content-only
    // file-drop hosts above, OpenCode receives an executing bridge bound to the
    // stable chat.message contract, and the shipped package declares
    // minimum_opencode_version 1.18.18 with a fail-closed <2.0.0 ceiling.
    // Installing that bridge without confirming the host version would ship
    // executable code against an unverified plugin API.
    const result = run(opencodeBinary(), ["--version"]);
    if (!versionAtLeast(result.stdout, [1, 18, 18]) || versionAtLeast(result.stdout, [2, 0, 0])) {
      fail(`OpenCode >=1.18.18 and <2.0.0 is required; got ${result.stdout.trim()}`);
    }
    return;
  }
  if (host === "claude") {
    const result = run(claudeBinary(), ["--version"]);
    if (!versionAtLeast(result.stdout, [2, 1, 205])) {
      fail(`Claude Code 2.1.205 or later is required for structured selector output; got ${result.stdout.trim()}`);
    }
    if (authenticated) {
      run(claudeBinary(), ["auth", "status"]);
    }
    return;
  }
  run(codexBinary(), ["--version"]);
  if (authenticated) {
    run(codexBinary(), ["login", "status"]);
  }
}

function marketplaceEntries(host) {
  if (FILE_DROP_HOSTS.includes(host) || host === "opencode") {
    const paths = managedPaths(host);
    const present =
      existsSync(paths.root) || (host === "opencode" && (existsSync(paths.bridge) || existsSync(paths.bridgeMarker)));
    return present ? [{ name: MARKETPLACE_NAME, root: paths.root }] : [];
  }
  const payload =
    host === "claude"
      ? runClaudeJson(["plugin", "marketplace", "list", "--json"])
      : runCodexJson(["plugin", "marketplace", "list", "--json"]).marketplaces;
  const entries = host === "claude" ? claudeMarketplaceEntries(payload) : payload;
  if (!Array.isArray(entries)) {
    fail(`${host} marketplace list returned an unexpected schema`);
  }
  return entries;
}

function marketplaceEntry(host) {
  const entries = marketplaceEntries(host);
  const matches = entries.filter((entry) => entry?.name === MARKETPLACE_NAME);
  if (matches.length > 1) {
    fail(`${host} reported duplicate marketplaces named ${MARKETPLACE_NAME}`);
  }
  return matches[0] ?? null;
}

// Read Grok Build's machine-readable plugin state.
//
// The managed Grok files are host-independent content, so inspecting or
// removing what the installer owns must not depend on a runnable `grok`
// command: a user who uninstalls Grok Build still has to be able to clean up.
// Transactional callers pass requireHostState so that install and update keep
// confirming activation against the host itself.
function grokInspection(requireHostState) {
  if (requireHostState) return runGrokJson(["inspect", "--json"]);
  const result = run(grokBinary(), ["inspect", "--json"], { allowFailure: true });
  if (result.error || result.status !== 0) {
    const detail = result.error?.message || result.stderr?.trim() || `exit ${result.status}`;
    console.warn(
      `warning: could not read Grok Build plugin state (${detail}); ` +
        "reporting the managed files only",
    );
    return null;
  }
  try {
    const payload = JSON.parse(result.stdout);
    if (payload === null || typeof payload !== "object") {
      fail("Grok Build returned a non-container JSON value");
    }
    return payload;
  } catch (error) {
    if (error instanceof InstallerError) throw error;
    fail(`Grok Build returned invalid JSON for inspect --json: ${error.message}`);
  }
}

function pluginState(host, { requireHostState = false } = {}) {
  if (FILE_DROP_HOSTS.includes(host)) {
    const paths = managedPaths(host);
    if (!existsSync(paths.root)) return { kind: "missing", version: null };
    let manifest;
    try {
      manifest = JSON.parse(readFileSync(join(paths.root, "plugin.json"), "utf8"));
    } catch (error) {
      fail(`${host} plugin manifest is unreadable: ${error.message}`);
    }
    if (
      manifest === null ||
      typeof manifest !== "object" ||
      Array.isArray(manifest) ||
      (host === "cursor" &&
        manifest.$schema !== "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json") ||
      (host === "grok" && manifest.skills !== "./skills") ||
      manifest.name !== PLUGIN_NAME ||
      typeof manifest.version !== "string" ||
      manifest.version.trim().length === 0
    ) {
      fail(`${host} reported an invalid OpenSocrates plugin manifest`);
    }
    if (host !== "grok") return { kind: "installed", version: manifest.version };
    const payload = grokInspection(requireHostState);
    if (payload === null) return { kind: "installed", version: manifest.version };
    if (!Array.isArray(payload.plugins)) {
      fail("Grok Build inspect returned an unexpected plugin schema");
    }
    const matches = payload.plugins.filter((entry) => entry?.name === PLUGIN_NAME);
    if (matches.length !== 1) {
      fail(
        matches.length === 0
          ? "Grok Build did not discover the managed OpenSocrates plugin"
          : "Grok Build reported duplicate OpenSocrates plugins",
      );
    }
    const entry = matches[0];
    if (
      typeof entry.enabled !== "boolean" ||
      typeof entry.path !== "string" ||
      entry.provides?.skills !== 1 ||
      entry.provides?.agents !== 0 ||
      entry.provides?.hooks !== false ||
      entry.provides?.mcpServers !== 0
    ) {
      fail("Grok Build reported an invalid OpenSocrates plugin state");
    }
    let observedPath = resolve(entry.path);
    try {
      observedPath = realpathSync(observedPath);
    } catch {
      // The managed root exists here, so a missing reported path is invalid below.
    }
    let expectedPath = resolve(paths.root);
    try {
      expectedPath = realpathSync(expectedPath);
    } catch {
      // Ownership checks report a more specific error for a missing root.
    }
    if (observedPath !== expectedPath) {
      fail(`Grok Build resolved OpenSocrates from an unmanaged location: ${observedPath}`);
    }
    return { kind: entry.enabled ? "installed" : "disabled", version: manifest.version };
  }
  if (host === "opencode") {
    const paths = managedPaths(host);
    if (!existsSync(paths.root) && !existsSync(paths.bridge) && !existsSync(paths.bridgeMarker)) {
      return { kind: "missing", version: null };
    }
    let manifest;
    try {
      manifest = JSON.parse(readFileSync(join(paths.root, ".opensocrates-package", "opencode-plugin.json"), "utf8"));
    } catch (error) {
      fail(`opencode installed manifest is unreadable: ${error.message}`);
    }
    if (
      manifest === null ||
      typeof manifest !== "object" ||
      Array.isArray(manifest) ||
      manifest.name !== PLUGIN_NAME ||
      typeof manifest.version !== "string" ||
      manifest.version.trim().length === 0
    ) {
      fail("opencode reported an invalid OpenSocrates installation manifest");
    }
    return { kind: "installed", version: manifest.version };
  }
  if (host === "claude") {
    const installed = claudePluginEntries(runClaudeJson(["plugin", "list", "--json"]));
    const matches = installed.filter((entry) => entry?.id === PLUGIN_ID);
    if (matches.length === 0) return { kind: "missing", version: null };
    const entry = matches[0];
    if (
      (entry.version !== undefined &&
        entry.version !== null &&
        (typeof entry.version !== "string" || entry.version.trim().length === 0)) ||
      typeof entry.enabled !== "boolean"
    ) {
      fail(`Claude Code reported an invalid state for ${PLUGIN_ID}`);
    }
    return {
      kind: entry.enabled ? "installed" : "disabled",
      version: entry.version ?? null,
    };
  }
  const payload = runCodexJson(["plugin", "list", "--marketplace", MARKETPLACE_NAME, "--available", "--json"]);
  const installed = Array.isArray(payload.installed) ? payload.installed : null;
  const available = Array.isArray(payload.available) ? payload.available : null;
  if (installed === null || available === null) {
    fail("Codex plugin list returned an unexpected schema");
  }
  const installedMatches = installed.filter((entry) => entry?.pluginId === PLUGIN_ID);
  const availableMatches = available.filter((entry) => entry?.pluginId === PLUGIN_ID);
  if (installedMatches.length > 1 || availableMatches.length > 1) {
    fail(`Codex reported duplicate entries for ${PLUGIN_ID}`);
  }
  if (installedMatches.length === 1) {
    return {
      kind: "installed",
      version: installedMatches[0].version ?? null,
    };
  }
  if (availableMatches.length === 1) {
    return {
      kind: "available",
      version: availableMatches[0].version ?? null,
    };
  }
  return { kind: "missing", version: null };
}

function detectLegacyClaudeInstallation() {
  const marketplaces = marketplaceEntries("claude").filter(
    (entry) =>
      typeof entry?.name === "string" &&
      entry.name !== MARKETPLACE_NAME &&
      entry.name.toLowerCase() === MARKETPLACE_NAME,
  );
  const plugins = claudePluginEntries(runClaudeJson(["plugin", "list", "--json"]));
  const legacyPlugins = plugins.filter((entry) => entry.id !== PLUGIN_ID && entry.id.toLowerCase() === PLUGIN_ID);
  const names = marketplaces.map((entry) => entry.name).join(", ") || "OpenSocrates";
  return {
    found: marketplaces.length > 0 || legacyPlugins.length > 0,
    names,
  };
}

// Install and update write into the managed root, so a case-variant pre-1.0
// registration must be resolved by the user first. Status and remove are
// diagnostic and scoped to the root this installer owns, so they only warn:
// blocking them would strand a user who needs to inspect or back out.
function requireNoLegacyClaudeInstallation() {
  const legacy = detectLegacyClaudeInstallation();
  if (legacy.found) {
    fail(
      `a legacy Claude marketplace (${legacy.names}) is installed; OpenSocrates will not remove it automatically. ` +
        "Uninstall its plugin and marketplace explicitly, then rerun this command. See the README migration section.",
    );
  }
}

function warnLegacyClaudeInstallation() {
  let legacy;
  try {
    legacy = detectLegacyClaudeInstallation();
  } catch {
    return;
  }
  if (legacy.found) {
    console.warn(
      `warning: a legacy Claude marketplace (${legacy.names}) is also registered. ` +
        "OpenSocrates never removes it automatically; this command only affects the root it owns. " +
        "See the README migration section.",
    );
  }
}

async function readJsonObject(target) {
  let payload;
  try {
    payload = JSON.parse(await readFile(target, "utf8"));
  } catch (error) {
    fail(`cannot read valid JSON from ${target}: ${error.message}`);
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    fail(`expected a JSON object in ${target}`);
  }
  return payload;
}

async function requireOwnedRoot(root, host) {
  const info = await lstat(root);
  if (!info.isDirectory() || info.isSymbolicLink()) {
    fail(`managed marketplace path is not an owned directory: ${root}`);
  }
  const markerPath = join(root, MARKER_NAME);
  await requireRegularFileEntry(markerPath, `${host} ownership marker`);
  const marker = await readJsonObject(markerPath);
  if (!markerMatches(marker, host)) {
    fail(`managed marketplace path has no valid ownership marker: ${root}`);
  }
}

async function sha256File(target) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(target)) {
    hash.update(chunk);
  }
  return hash.digest("hex");
}

function openCodeSidecar(bridgeSha256) {
  return {
    ...OPENCODE_MARKER,
    version: PRODUCT_VERSION,
    bridgeSha256,
  };
}

async function ensureSafeDirectory(target, label) {
  if (await exists(target)) {
    const info = await lstat(target);
    if (!info.isDirectory() || info.isSymbolicLink()) {
      fail(`refusing to use an unsafe ${label} directory: ${target}`);
    }
    return;
  }
  await mkdir(target, { recursive: true, mode: 0o700 });
  const info = await lstat(target);
  if (!info.isDirectory() || info.isSymbolicLink()) {
    fail(`refusing to use an unsafe ${label} directory: ${target}`);
  }
}

async function ensureOpenCodeDirectories(paths) {
  await ensureSafeDirectory(paths.hostHome, "OpenCode configuration");
  await ensureSafeDirectory(paths.parent, "OpenCode skills");
  await ensureSafeDirectory(paths.bridgeParent, "OpenCode plugins");
}

async function verifyOpenCodeInstallation(paths) {
  await requireOwnedRoot(paths.root, "opencode");
  for (const [target, label] of [
    [paths.bridge, "plugin bridge"],
    [paths.bridgeMarker, "plugin ownership sidecar"],
  ]) {
    if (!(await exists(target))) fail(`OpenCode ${label} is missing: ${target}`);
    const info = await lstat(target);
    if (!info.isFile() || info.isSymbolicLink()) {
      fail(`OpenCode ${label} is not an owned regular file: ${target}`);
    }
  }
  const sidecar = await readJsonObject(paths.bridgeMarker);
  const sidecarMarker = Object.fromEntries(Object.keys(OPENCODE_MARKER).map((key) => [key, sidecar[key]]));
  if (
    !markerMatches(sidecarMarker, "opencode") ||
    sidecar.version !== PRODUCT_VERSION ||
    typeof sidecar.bridgeSha256 !== "string" ||
    sidecar.bridgeSha256 !== (await sha256File(paths.bridge))
  ) {
    fail("OpenCode plugin bridge has an invalid ownership sidecar or checksum");
  }
  const manifest = await readJsonObject(join(paths.root, OPENCODE_INSTALL_MANIFEST));
  if (
    manifest.schema !== "opensocrates.opencode-installation/1.0.0" ||
    manifest.version !== PRODUCT_VERSION ||
    manifest.bridgeSha256 !== sidecar.bridgeSha256 ||
    manifest.files === null ||
    typeof manifest.files !== "object" ||
    Array.isArray(manifest.files)
  ) {
    fail("OpenCode installation inventory is invalid");
  }
  const actualFiles = new Set(await walkFiles(paths.root));
  actualFiles.delete(OPENCODE_INSTALL_MANIFEST);
  const declaredFiles = Object.keys(manifest.files);
  if (
    actualFiles.size !== declaredFiles.length ||
    declaredFiles.some((item) => !isSafeArchivePath(item) || !actualFiles.has(item))
  ) {
    fail("OpenCode installation inventory does not cover the complete managed skill");
  }
  for (const item of declaredFiles) {
    if (manifest.files[item] !== (await sha256File(join(paths.root, ...item.split("/"))))) {
      fail(`OpenCode installed file checksum mismatch for ${item}`);
    }
  }
  return manifest;
}

async function downloadFile(url, destination) {
  const response = await fetch(url, {
    headers: {
      accept: "application/octet-stream",
      "user-agent": `OpenSocrates-installer/${PRODUCT_VERSION}`,
    },
    redirect: "follow",
    signal: AbortSignal.timeout(15 * 60 * 1000),
  });
  if (!response.ok || response.body === null) {
    fail(`download failed (${response.status}) for ${url}`);
  }
  const contentLength = Number(response.headers.get("content-length") ?? "0");
  if (Number.isFinite(contentLength) && contentLength > MAX_DOWNLOAD_BYTES) {
    fail(`download exceeds the ${MAX_DOWNLOAD_BYTES}-byte safety limit`);
  }
  await pipeline(Readable.fromWeb(response.body), createWriteStream(destination, { mode: 0o600 }));
  const downloaded = (await stat(destination)).size;
  if (downloaded === 0 || downloaded > MAX_DOWNLOAD_BYTES) {
    fail(`downloaded file has an invalid size: ${downloaded} bytes`);
  }
}

function localAssetInputs(options, host) {
  if (options.host === ALL_HOST) {
    return options.hostAssets[host];
  }
  return { asset: options.asset, checksum: options.checksum };
}

function qualifiedAssetHosts(options) {
  if (options.host !== ALL_HOST) return [];
  return SUPPORTED_HOSTS.filter((host) => options.hostAssets[host].asset !== null);
}

async function resolveAssetInputs(options, scratch, host) {
  const local = localAssetInputs(options, host);
  if (local.asset !== null) {
    if (!(await exists(local.asset)) || !(await exists(local.checksum))) {
      fail("the supplied asset or checksum file does not exist");
    }
    return local;
  }
  const base = `https://github.com/${REPOSITORY}/releases/download/v${PRODUCT_VERSION}`;
  const assetName = assetNameFor(host);
  const checksumName = `${assetName}.sha256`;
  const asset = join(scratch, assetName);
  const checksum = join(scratch, checksumName);
  console.log(`Downloading OpenSocrates ${PRODUCT_VERSION} from GitHub Releases...`);
  await downloadFile(`${base}/${assetName}`, asset);
  await downloadFile(`${base}/${checksumName}`, checksum);
  return { asset, checksum };
}

async function verifyOuterChecksum(asset, checksum, host) {
  const expected = parseChecksumText(await readFile(checksum, "utf8"), assetNameFor(host));
  const actual = await sha256File(asset);
  if (actual !== expected) {
    fail(`release checksum mismatch: expected ${expected}, got ${actual}`);
  }
}

function archiveEntries(asset) {
  const unzip = process.platform === "darwin" ? "/usr/bin/unzip" : "unzip";
  const result = run(unzip, ["-Z1", asset]);
  const entries = result.stdout.split(/\r?\n/u).filter(Boolean);
  if (entries.length === 0 || entries.length > MAX_ARCHIVE_ENTRIES) {
    fail(`archive contains an invalid number of entries: ${entries.length}`);
  }
  const unique = new Set();
  for (const entry of entries) {
    if (!isSafeArchivePath(entry)) {
      fail(`archive contains an unsafe path: ${JSON.stringify(entry)}`);
    }
    if (unique.has(entry)) {
      fail(`archive contains a duplicate path: ${entry}`);
    }
    unique.add(entry);
  }
  return entries;
}

async function extractArchive(asset, destination) {
  archiveEntries(asset);
  await mkdir(destination, { recursive: true, mode: 0o700 });
  const unzip = process.platform === "darwin" ? "/usr/bin/unzip" : "unzip";
  run(unzip, ["-q", asset, "-d", destination]);
}

async function walkFiles(root, current = root, output = []) {
  const entries = await readdir(current, { withFileTypes: true });
  for (const entry of entries) {
    const absolute = join(current, entry.name);
    const info = await lstat(absolute);
    if (info.isSymbolicLink()) {
      fail(`package contains a symbolic link: ${relative(root, absolute)}`);
    }
    if (info.isDirectory()) {
      await walkFiles(root, absolute, output);
    } else if (info.isFile()) {
      output.push(relative(root, absolute).split(sep).join("/"));
    } else {
      fail(`package contains an unsupported filesystem entry: ${relative(root, absolute)}`);
    }
  }
  return output;
}

async function verifyPackageChecksums(pluginRoot) {
  const checksumPath = join(pluginRoot, "checksums.sha256");
  const lines = (await readFile(checksumPath, "utf8"))
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean);
  const declared = new Set();
  for (const line of lines) {
    const match = line.match(/^([a-fA-F0-9]{64})\s+[*]?(.+)$/u);
    if (!match) {
      fail(`invalid package checksum line: ${line}`);
    }
    const expected = match[1].toLowerCase();
    const item = match[2].trim();
    if (!isSafeArchivePath(item) || item === "checksums.sha256" || declared.has(item)) {
      fail(`invalid or duplicate package checksum path: ${item}`);
    }
    declared.add(item);
    const target = join(pluginRoot, ...item.split("/"));
    if (!(await exists(target))) {
      fail(`package checksum references a missing file: ${item}`);
    }
    const actual = await sha256File(target);
    if (actual !== expected) {
      fail(`package checksum mismatch for ${item}`);
    }
  }
  const actualFiles = new Set((await walkFiles(pluginRoot)).filter((item) => item !== "checksums.sha256"));
  if (actualFiles.size !== declared.size || [...actualFiles].some((item) => !declared.has(item))) {
    fail("package checksum manifest does not cover the complete archive");
  }
  return declared.size;
}

async function verifyExtractedPackage(pluginRoot, host) {
  const manifest = await readJsonObject(join(pluginRoot, HOST_LAYOUTS[host].manifestRelative));
  if (manifest.name !== PLUGIN_NAME || manifest.version !== PRODUCT_VERSION) {
    fail(
      `plugin manifest mismatch: expected ${PLUGIN_NAME} ${PRODUCT_VERSION}, ` +
        `got ${String(manifest.name)} ${String(manifest.version)}`,
    );
  }
  const release = await readJsonObject(join(pluginRoot, "release-manifest.json"));
  if (
    release.product_version !== PRODUCT_VERSION ||
    release.host !== host ||
    release.schema !== "opensocrates.plugin-release-manifest/1.0.0"
  ) {
    fail("package release manifest does not match this installer");
  }
  if (HOST_LAYOUTS[host].requiresRuntime) {
    const runtime = join(pluginRoot, "runtime", "darwin-arm64", "opensocrates-runtime", "opensocrates-runtime");
    const runtimeInfo = await stat(runtime);
    if (!runtimeInfo.isFile() || (runtimeInfo.mode & 0o111) === 0) {
      fail("package is missing the executable darwin-arm64 runtime");
    }
  } else if (
    release.launchers?.length !== 0 ||
    release.runtime_targets?.length !== 0 ||
    (await exists(join(pluginRoot, "runtime"))) ||
    (await exists(join(pluginRoot, "hooks"))) ||
    (await exists(join(pluginRoot, "bin"))) ||
    ((host === "cursor" || host === "grok") && (await exists(join(pluginRoot, "mcp.json")))) ||
    (host === "grok" &&
      ((await exists(join(pluginRoot, "commands"))) ||
        (await exists(join(pluginRoot, "agents"))) ||
        (await exists(join(pluginRoot, ".mcp.json")))))
  ) {
    fail(`${host} package contains an unexpected native runtime or launcher surface`);
  }
  if (host === "opencode") {
    if (
      manifest.minimum_opencode_version !== "1.18.18" ||
      manifest.stable_plugin_hook !== "chat.message" ||
      manifest.beta_v2_api !== false ||
      !(await exists(join(pluginRoot, "plugins", "opensocrates.js"))) ||
      !(await exists(join(pluginRoot, "skills", "opensocrates", "SKILL.md")))
    ) {
      fail("OpenCode package does not match the verified stable bridge contract");
    }
  }
  return verifyPackageChecksums(pluginRoot);
}

async function requireSafePathBelow(root, target, label, { allowRoot = false } = {}) {
  const resolvedRoot = resolve(root);
  const resolvedTarget = resolve(target);
  if (await entryExists(resolvedRoot)) {
    const rootInfo = await lstat(resolvedRoot);
    if (!rootInfo.isDirectory() || rootInfo.isSymbolicLink()) {
      fail(`refusing an unsafe ${label} root: ${root}`);
    }
  }
  const suffix = relative(resolvedRoot, resolvedTarget);
  if (
    (!allowRoot && !suffix) ||
    suffix === ".." ||
    suffix.startsWith(`..${sep}`) ||
    resolve(resolvedRoot, suffix) !== resolvedTarget
  ) {
    fail(`refusing an unsafe ${label} path: ${target}`);
  }
  let current = resolvedRoot;
  for (const component of suffix.split(sep)) {
    current = join(current, component);
    if (!(await entryExists(current))) continue;
    const info = await lstat(current);
    if (info.isSymbolicLink()) {
      fail(`refusing a symbolic-link ${label} path: ${current}`);
    }
  }
  if (await entryExists(resolvedTarget)) {
    let canonical;
    let canonicalRoot = resolvedRoot;
    try {
      canonical = realpathSync(resolvedTarget);
      if (await entryExists(resolvedRoot)) canonicalRoot = realpathSync(resolvedRoot);
    } catch (error) {
      fail(`cannot canonicalize ${label}: ${error.message}`);
    }
    if (canonical !== resolve(canonicalRoot, suffix)) {
      fail(`refusing a non-canonical ${label} path: ${target}`);
    }
  }
}

async function packageIdentityForPurge(pluginRoot, host, { allowedExtra = () => false } = {}) {
  const rootInfo = await lstat(pluginRoot);
  if (!rootInfo.isDirectory() || rootInfo.isSymbolicLink()) {
    fail(`OpenSocrates ${host} payload is not a real directory: ${pluginRoot}`);
  }
  const releasePath = join(pluginRoot, "release-manifest.json");
  const manifestPath = join(pluginRoot, HOST_LAYOUTS[host].manifestRelative);
  const checksumPath = join(pluginRoot, "checksums.sha256");
  for (const [target, label] of [
    [releasePath, `${host} release manifest`],
    [manifestPath, `${host} plugin manifest`],
    [checksumPath, `${host} checksum inventory`],
  ]) {
    await requireRegularFileEntry(target, label);
  }
  const release = await readJsonObject(releasePath);
  const version = release.product_version;
  if (
    release.schema !== "opensocrates.plugin-release-manifest/1.0.0" ||
    release.host !== host ||
    typeof version !== "string" ||
    version.trim().length === 0 ||
    !Number.isInteger(release.content_revision) ||
    release.content_revision < 1
  ) {
    fail(`OpenSocrates ${host} payload has an invalid release identity`);
  }
  const manifest = await readJsonObject(manifestPath);
  if (manifest.name !== PLUGIN_NAME || manifest.version !== version) {
    fail(`OpenSocrates ${host} payload has a mismatched plugin identity`);
  }

  const lines = (await readFile(checksumPath, "utf8"))
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length === 0) fail(`OpenSocrates ${host} payload has an empty checksum inventory`);
  const declared = new Set();
  for (const line of lines) {
    const match = line.match(/^([a-fA-F0-9]{64})\s+[*]?(.+)$/u);
    if (!match) fail(`OpenSocrates ${host} payload has an invalid checksum inventory`);
    const item = match[2].trim();
    if (!isSafeArchivePath(item) || item === "checksums.sha256" || declared.has(item)) {
      fail(`OpenSocrates ${host} payload has an unsafe checksum path`);
    }
    const target = join(pluginRoot, ...item.split("/"));
    if (!(await entryExists(target))) fail(`OpenSocrates ${host} payload is missing a declared file`);
    const info = await lstat(target);
    if (!info.isFile() || info.isSymbolicLink()) {
      fail(`OpenSocrates ${host} payload contains an unsafe declared file`);
    }
    if ((await sha256File(target)) !== match[1].toLowerCase()) {
      fail(`OpenSocrates ${host} payload checksum verification failed`);
    }
    declared.add(item);
  }
  const actual = await walkFiles(pluginRoot);
  for (const item of actual) {
    if (item === "checksums.sha256" || declared.has(item) || allowedExtra(item)) continue;
    fail(`OpenSocrates ${host} payload contains an unowned file: ${item}`);
  }
  return { version, files: actual };
}

async function cacheHasLiveUser(versionRoot) {
  const marker = join(versionRoot, ".in_use");
  if (!(await entryExists(marker))) return false;
  const markerInfo = await lstat(marker);
  if (!markerInfo.isDirectory() || markerInfo.isSymbolicLink()) {
    fail("OpenSocrates cache has an unsafe .in_use marker");
  }
  const entries = await readdir(marker, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isSymbolicLink() || !entry.isFile() || !/^[1-9]\d*$/u.test(entry.name)) {
      fail("OpenSocrates cache has an unrecognized .in_use entry");
    }
    const pid = Number(entry.name);
    if (!Number.isSafeInteger(pid)) fail("OpenSocrates cache has an invalid .in_use process ID");
    try {
      process.kill(pid, 0);
      return true;
    } catch (error) {
      if (error?.code === "EPERM") return true;
      if (error?.code !== "ESRCH") {
        fail("OpenSocrates cache use could not be determined safely");
      }
    }
  }
  return false;
}

async function removeDirectoryIfEmpty(target) {
  if (!(await entryExists(target))) return false;
  try {
    await rmdir(target);
    return true;
  } catch (error) {
    if (error?.code === "ENOTEMPTY" || error?.code === "EEXIST") return false;
    throw error;
  }
}

async function purgeHostCache(host, paths) {
  if (paths.cacheRoot === null) {
    return { component: "plugin-cache", status: "absent", path: paths.cacheRoot };
  }
  if (!(await entryExists(paths.cacheRoot))) {
    let removedEmptyMarketplace = false;
    if (await entryExists(paths.cacheMarketplaceRoot)) {
      await requireSafePathBelow(paths.hostHome, paths.cacheMarketplaceRoot, `${host} cache marketplace`);
      const info = await lstat(paths.cacheMarketplaceRoot);
      if (!info.isDirectory() || info.isSymbolicLink()) {
        fail(`refusing an unsafe ${host} OpenSocrates cache marketplace`);
      }
      if ((await readdir(paths.cacheMarketplaceRoot)).length !== 0) {
        fail(`refusing an unrecognized entry in the ${host} OpenSocrates cache marketplace`);
      }
      await rmdir(paths.cacheMarketplaceRoot);
      removedEmptyMarketplace = true;
    }
    return {
      component: "plugin-cache",
      status: removedEmptyMarketplace ? "removed" : "absent",
      path: paths.cacheMarketplaceRoot,
    };
  }
  await requireSafePathBelow(paths.hostHome, paths.cacheRoot, `${host} plugin cache`);
  const rootInfo = await lstat(paths.cacheRoot);
  if (!rootInfo.isDirectory() || rootInfo.isSymbolicLink()) {
    fail(`refusing an unsafe ${host} OpenSocrates plugin-cache root`);
  }
  const versions = await readdir(paths.cacheRoot, { withFileTypes: true });
  let removed = 0;
  let pending = 0;
  for (const version of versions) {
    if (!version.isDirectory() || version.isSymbolicLink()) {
      fail(`refusing an unrecognized entry in the ${host} OpenSocrates plugin cache`);
    }
    const versionRoot = join(paths.cacheRoot, version.name);
    await requireSafePathBelow(paths.cacheRoot, versionRoot, `${host} cached plugin version`);
    const identity = await packageIdentityForPurge(versionRoot, host, {
      allowedExtra: (item) => item === ".orphaned_at" || item.startsWith(".in_use/"),
    });
    if (identity.version !== version.name) {
      fail(`refusing a ${host} cache directory whose version does not match its manifests`);
    }
    if (await cacheHasLiveUser(versionRoot)) {
      pending += 1;
      continue;
    }
    await rm(versionRoot, { recursive: true });
    removed += 1;
  }
  if (pending === 0) {
    const cacheRootRemoved = await removeDirectoryIfEmpty(paths.cacheRoot);
    if (!cacheRootRemoved && (await entryExists(paths.cacheRoot))) {
      return {
        component: "plugin-cache",
        status: "pending",
        path: paths.cacheRoot,
        detail: "cache-changed-during-purge",
      };
    }
    const marketplaceRemoved = await removeDirectoryIfEmpty(paths.cacheMarketplaceRoot);
    if (!marketplaceRemoved && (await entryExists(paths.cacheMarketplaceRoot))) {
      return {
        component: "plugin-cache",
        status: "pending",
        path: paths.cacheMarketplaceRoot,
        detail: "unrecognized-cache-marketplace-content",
      };
    }
  }
  return {
    component: "plugin-cache",
    status: pending > 0 ? "pending" : removed > 0 ? "removed" : "absent",
    path: paths.cacheRoot,
    detail: pending > 0 ? "host-in-use" : null,
  };
}

async function purgeClaudePluginData(paths) {
  const results = [];
  for (const target of paths.pluginData) {
    if (!(await entryExists(target))) {
      results.push({ component: "plugin-data", status: "absent", path: target });
      continue;
    }
    await requireSafePathBelow(paths.hostHome, target, "Claude OpenSocrates plugin data");
    const info = await lstat(target);
    if (!info.isDirectory() || info.isSymbolicLink()) {
      fail(`refusing an unsafe Claude OpenSocrates plugin-data path: ${target}`);
    }
    if ((await readdir(target)).length !== 0) {
      results.push({
        component: "plugin-data",
        status: "pending",
        path: target,
        detail: "nonempty-unverified-data",
      });
      continue;
    }
    await rmdir(target);
    results.push({ component: "plugin-data", status: "removed", path: target });
  }
  return results;
}

async function verifyOpenCodePurgeRoot(root) {
  await requireOwnedRoot(root, "opencode");
  const manifestPath = join(root, OPENCODE_INSTALL_MANIFEST);
  await requireRegularFileEntry(manifestPath, "OpenCode installation inventory");
  const manifest = await readJsonObject(manifestPath);
  const manifestKeys = Object.keys(manifest).sort();
  if (
    !jsonDeepEqual(manifestKeys, ["bridgeSha256", "files", "schema", "version"]) ||
    manifest.schema !== "opensocrates.opencode-installation/1.0.0" ||
    typeof manifest.version !== "string" ||
    manifest.version.trim().length === 0 ||
    !/^[a-f0-9]{64}$/u.test(manifest.bridgeSha256) ||
    manifest.files === null ||
    typeof manifest.files !== "object" ||
    Array.isArray(manifest.files)
  ) {
    fail("OpenCode installation inventory is invalid");
  }
  const declared = Object.keys(manifest.files);
  const actual = new Set(await walkFiles(root));
  actual.delete(OPENCODE_INSTALL_MANIFEST);
  if (
    actual.size !== declared.length ||
    declared.some((item) => !isSafeArchivePath(item) || !actual.has(item) || !/^[a-f0-9]{64}$/u.test(manifest.files[item]))
  ) {
    fail("OpenCode installation inventory does not cover the complete managed skill");
  }
  for (const item of declared) {
    if ((await sha256File(join(root, ...item.split("/")))) !== manifest.files[item]) {
      fail(`OpenCode installed file checksum mismatch for ${item}`);
    }
  }
  return manifest;
}

async function verifyManagedTreeForPurge(host, root) {
  if (host === "opencode") return verifyOpenCodePurgeRoot(root);
  await requireOwnedRoot(root, host);
  const layout = HOST_LAYOUTS[host];
  const pluginRoot = join(root, layout.pluginRelative);
  const identity = await packageIdentityForPurge(pluginRoot, host, {
    allowedExtra: (item) => FILE_DROP_HOSTS.includes(host) && item === MARKER_NAME,
  });
  if (FILE_DROP_HOSTS.includes(host)) return identity;

  const marketplacePath = join(root, layout.marketplaceRelative);
  await requireRegularFileEntry(marketplacePath, `${host} marketplace manifest`);
  const marketplace = await readJsonObject(marketplacePath);
  const expected = expectedMarketplace(host);
  if (host === "claude") expected.metadata.version = identity.version;
  if (!jsonDeepEqual(marketplace, expected)) {
    fail(`${host} managed marketplace does not match the exact owned plugin inventory`);
  }
  const allowed = new Set([
    MARKER_NAME,
    layout.marketplaceRelative.split(sep).join("/"),
    ...identity.files.map((item) => join(layout.pluginRelative, ...item.split("/")).split(sep).join("/")),
  ]);
  for (const item of await walkFiles(root)) {
    if (!allowed.has(item)) fail(`${host} managed marketplace contains an unowned file: ${item}`);
  }
  return identity;
}

async function removeOwnedManagedRoot(host, paths) {
  if (!(await entryExists(paths.root))) {
    return { component: "managed-root", status: "absent", path: paths.root };
  }
  await requireSafePathBelow(paths.hostHome, paths.root, `${host} managed root`);
  await verifyManagedTreeForPurge(host, paths.root);
  const backup = join(transientParent(host, paths), `.opensocrates.removed-${randomUUID()}`);
  await requireSafePathBelow(paths.hostHome, backup, `${host} removal backup`);
  await rename(paths.root, backup);
  try {
    await verifyManagedTreeForPurge(host, backup);
    await rm(backup, { recursive: true });
  } catch (error) {
    if ((await entryExists(backup)) && !(await entryExists(paths.root))) {
      const restored = await recoveryStep(`restore the ${host} managed root after purge cleanup failed`, async () => {
        await verifyManagedTreeForPurge(host, backup);
        await rename(backup, paths.root);
      });
      if (!restored) {
        console.error(`error: recoverable ${host} files remain at: ${backup}`);
        console.error(`error: retry command: opensocrates remove --host ${host} --purge`);
      }
    }
    throw error;
  }
  return { component: "managed-root", status: "removed", path: paths.root };
}

async function cleanupTransientRootResidue(host, paths) {
  const parent = transientParent(host, paths);
  if (!(await entryExists(parent))) {
    return { component: "transaction-residue", status: "absent", path: parent };
  }
  await requireSafePathBelow(paths.hostHome, parent, `${host} transient parent`, { allowRoot: true });
  const names = (await readdir(parent)).filter((name) =>
    /^\.opensocrates\.(?:staging|backup|removed)-[A-Za-z0-9-]+$/u.test(name),
  );
  let removed = 0;
  for (const name of names) {
    const target = join(parent, name);
    await requireSafePathBelow(parent, target, `${host} transaction residue`);
    const info = await lstat(target);
    if (!info.isDirectory() || info.isSymbolicLink()) {
      fail(`refusing unsafe ${host} transaction residue: ${target}`);
    }
    if ((await readdir(target)).length !== 0) {
      try {
        await verifyManagedTreeForPurge(host, target);
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        fail(`refusing unverifiable ${host} transaction residue at ${target}: ${detail}`);
      }
    }
    await rm(target, { recursive: true });
    removed += 1;
  }
  return {
    component: "transaction-residue",
    status: removed > 0 ? "removed" : "absent",
    path: parent,
  };
}

async function readOpenCodeBridgeSidecar(target) {
  const info = await lstat(target);
  if (!info.isFile() || info.isSymbolicLink()) {
    fail(`OpenCode bridge ownership sidecar is unsafe: ${target}`);
  }
  const sidecar = await readJsonObject(target);
  const expectedKeys = [...Object.keys(OPENCODE_MARKER), "version", "bridgeSha256"].sort();
  const observedKeys = Object.keys(sidecar).sort();
  const marker = Object.fromEntries(Object.keys(OPENCODE_MARKER).map((key) => [key, sidecar[key]]));
  if (
    expectedKeys.length !== observedKeys.length ||
    expectedKeys.some((key, index) => key !== observedKeys[index]) ||
    !markerMatches(marker, "opencode") ||
    typeof sidecar.version !== "string" ||
    sidecar.version.trim().length === 0 ||
    !/^[a-f0-9]{64}$/u.test(sidecar.bridgeSha256)
  ) {
    fail(`OpenCode bridge ownership sidecar is invalid: ${target}`);
  }
  return sidecar;
}

async function purgeOpenCodeBridge(paths) {
  const bridgePresent = await entryExists(paths.bridge);
  const markerPresent = await entryExists(paths.bridgeMarker);
  if (!bridgePresent && !markerPresent) {
    return { component: "opencode-bridge", status: "absent", path: paths.bridge };
  }
  await requireSafePathBelow(paths.hostHome, paths.bridge, "OpenCode bridge");
  await requireSafePathBelow(paths.hostHome, paths.bridgeMarker, "OpenCode bridge sidecar");
  if (bridgePresent && !markerPresent) {
    fail("refusing to remove an OpenCode bridge without its ownership sidecar");
  }
  const sidecar = await readOpenCodeBridgeSidecar(paths.bridgeMarker);
  if (bridgePresent) {
    const bridgeInfo = await lstat(paths.bridge);
    if (!bridgeInfo.isFile() || bridgeInfo.isSymbolicLink() || (await sha256File(paths.bridge)) !== sidecar.bridgeSha256) {
      fail("refusing to remove an OpenCode bridge whose ownership checksum does not match");
    }
    await rm(paths.bridge);
  }
  await rm(paths.bridgeMarker);
  return { component: "opencode-bridge", status: "removed", path: paths.bridge };
}

async function purgeOpenCodeBridgeResidue(paths) {
  if (!(await entryExists(paths.bridgeParent))) {
    return { component: "opencode-bridge-residue", status: "absent", path: paths.bridgeParent };
  }
  await requireSafePathBelow(paths.hostHome, paths.bridgeParent, "OpenCode bridge parent");
  const entries = await readdir(paths.bridgeParent, { withFileTypes: true });
  const bridgeNames = entries
    .filter((entry) => /^\.opensocrates\.js\.(?:staging|backup|removed)-[A-Za-z0-9-]+$/u.test(entry.name))
    .map((entry) => entry.name);
  const markerNames = entries
    .filter((entry) =>
      /^\.opensocrates-managed\.json\.(?:staging|backup|removed)-[A-Za-z0-9-]+$/u.test(entry.name),
    )
    .map((entry) => entry.name);
  const bridges = new Map();
  for (const name of bridgeNames) {
    const target = join(paths.bridgeParent, name);
    await requireSafePathBelow(paths.bridgeParent, target, "OpenCode bridge residue");
    const info = await lstat(target);
    if (!info.isFile() || info.isSymbolicLink()) fail(`unsafe OpenCode bridge residue: ${target}`);
    bridges.set(target, await sha256File(target));
  }
  let removed = 0;
  for (const name of markerNames) {
    const marker = join(paths.bridgeParent, name);
    await requireSafePathBelow(paths.bridgeParent, marker, "OpenCode bridge sidecar residue");
    const sidecar = await readOpenCodeBridgeSidecar(marker);
    const matches = [...bridges].filter(([, digest]) => digest === sidecar.bridgeSha256);
    if (matches.length > 1) fail("ambiguous OpenCode bridge transaction residue");
    if (matches.length === 1) {
      const [[bridge]] = matches;
      await rm(bridge);
      bridges.delete(bridge);
      removed += 1;
    }
    await rm(marker);
    removed += 1;
  }
  if (bridges.size > 0) fail("refusing OpenCode bridge residue without an ownership sidecar");
  return {
    component: "opencode-bridge-residue",
    status: removed > 0 ? "removed" : "absent",
    path: paths.bridgeParent,
  };
}

async function prepareVerifiedPackage(options, host = options.host) {
  if (!SUPPORTED_HOSTS.includes(host)) {
    fail(`cannot prepare a package for unsupported host ${JSON.stringify(host)}`);
  }
  const scratch = await mkdtemp(join(tmpdir(), "opensocrates-install-"));
  try {
    const { asset, checksum } = await resolveAssetInputs(options, scratch, host);
    await verifyOuterChecksum(asset, checksum, host);
    const pluginRoot = join(scratch, "plugin");
    await extractArchive(asset, pluginRoot);
    const checkedFiles = await verifyExtractedPackage(pluginRoot, host);
    return { scratch, pluginRoot, checkedFiles, host };
  } catch (error) {
    await rm(scratch, { recursive: true, force: true });
    throw error;
  }
}

async function prepareVerifiedPackages(options, hosts) {
  const settled = await Promise.allSettled(hosts.map((host) => prepareVerifiedPackage(options, host)));
  const prepared = settled.filter((result) => result.status === "fulfilled").map((result) => result.value);
  const failure = settled.find((result) => result.status === "rejected");
  if (failure) {
    await Promise.all(prepared.map((item) => rm(item.scratch, { recursive: true, force: true })));
    throw failure.reason;
  }
  return prepared;
}

function expectedMarketplace(host) {
  if (host === "claude") {
    return {
      name: MARKETPLACE_NAME,
      owner: { name: "Parker Hwang" },
      metadata: {
        description: "OpenSocrates reasoning support for Claude Code and Cowork",
        version: PRODUCT_VERSION,
      },
      plugins: [
        {
          name: PLUGIN_NAME,
          source: `./plugins/${PLUGIN_NAME}`,
          description: "Local reasoning-system selection for Claude Code and Cowork, plus one /opensocrates entry.",
          category: "workflow",
        },
      ],
    };
  }
  return {
    name: MARKETPLACE_NAME,
    interface: { displayName: "OpenSocrates" },
    plugins: [
      {
        name: PLUGIN_NAME,
        source: {
          source: "local",
          path: "./build/generated/plugins/codex",
        },
        policy: {
          installation: "AVAILABLE",
          authentication: "ON_INSTALL",
        },
        category: "Productivity",
      },
    ],
  };
}

async function buildStagingTree(parent, pluginSource, host) {
  const layout = HOST_LAYOUTS[host];
  const staging = await mkdtemp(join(parent, ".opensocrates.staging-"));
  try {
    if (FILE_DROP_HOSTS.includes(host)) {
      await cp(pluginSource, staging, { recursive: true, preserveTimestamps: true });
      await verifyExtractedPackage(staging, host);
      await writeFile(join(staging, MARKER_NAME), `${JSON.stringify(markerFor(host), null, 2)}\n`, {
        encoding: "utf8",
        mode: 0o600,
      });
      return staging;
    }
    const marketplace = join(staging, layout.marketplaceRelative);
    const plugin = join(staging, layout.pluginRelative);
    await mkdir(dirname(marketplace), { recursive: true, mode: 0o700 });
    await mkdir(dirname(plugin), { recursive: true, mode: 0o700 });
    await cp(pluginSource, plugin, {
      recursive: true,
      preserveTimestamps: true,
    });
    await writeFile(marketplace, `${JSON.stringify(expectedMarketplace(host), null, 2)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    await writeFile(join(staging, MARKER_NAME), `${JSON.stringify(markerFor(host), null, 2)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    await verifyExtractedPackage(plugin, host);
    return staging;
  } catch (error) {
    await rm(staging, { recursive: true, force: true });
    throw error;
  }
}

async function buildOpenCodeStaging(paths, pluginSource) {
  await ensureOpenCodeDirectories(paths);
  const root = await mkdtemp(join(paths.parent, ".opensocrates.staging-"));
  const bridge = join(paths.bridgeParent, `.opensocrates.js.staging-${randomUUID()}`);
  const bridgeMarker = join(paths.bridgeParent, `.opensocrates-managed.json.staging-${randomUUID()}`);
  try {
    await cp(join(pluginSource, "skills", "opensocrates"), root, {
      recursive: true,
      preserveTimestamps: true,
    });
    const metadata = join(root, ".opensocrates-package");
    await mkdir(metadata, { mode: 0o700 });
    for (const name of ["opencode-plugin.json", "release-manifest.json", "checksums.sha256"]) {
      await cp(join(pluginSource, name), join(metadata, name), {
        preserveTimestamps: true,
      });
    }
    await writeFile(join(root, MARKER_NAME), `${JSON.stringify(markerFor("opencode"), null, 2)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    await cp(join(pluginSource, "plugins", "opensocrates.js"), bridge, {
      preserveTimestamps: true,
    });
    const bridgeSha256 = await sha256File(bridge);
    const files = {};
    for (const item of (await walkFiles(root)).sort()) {
      files[item] = await sha256File(join(root, ...item.split("/")));
    }
    await writeFile(
      join(root, OPENCODE_INSTALL_MANIFEST),
      `${JSON.stringify(
        {
          schema: "opensocrates.opencode-installation/1.0.0",
          version: PRODUCT_VERSION,
          bridgeSha256,
          files,
        },
        null,
        2,
      )}\n`,
      { encoding: "utf8", mode: 0o600 },
    );
    await writeFile(bridgeMarker, `${JSON.stringify(openCodeSidecar(bridgeSha256), null, 2)}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    return { root, bridge, bridgeMarker };
  } catch (error) {
    await rm(root, { recursive: true, force: true });
    await rm(bridge, { force: true });
    await rm(bridgeMarker, { force: true });
    throw error;
  }
}

function entryRoot(entry, host) {
  if (entry === null) {
    return null;
  }
  let value;
  if (host === "claude") {
    const fields = ["path", "installLocation"].filter((field) => entry[field] !== undefined && entry[field] !== null);
    if (
      fields.length === 0 ||
      fields.some((field) => typeof entry[field] !== "string" || entry[field].trim().length === 0)
    ) {
      fail(`${host} marketplace ${MARKETPLACE_NAME} has no usable root`);
    }
    const roots = fields.map((field) => {
      const candidate = resolve(entry[field]);
      try {
        return realpathSync(candidate);
      } catch {
        return candidate;
      }
    });
    if (new Set(roots).size !== 1) {
      fail(`${host} marketplace ${MARKETPLACE_NAME} reported conflicting roots`);
    }
    [value] = roots;
  } else {
    value = entry.root;
  }
  if (typeof value !== "string" || value.trim().length === 0) {
    fail(`${host} marketplace ${MARKETPLACE_NAME} has no usable root`);
  }
  const resolved = resolve(value);
  try {
    // Host CLIs may report an equivalent canonical path even when the user
    // configured a symlinked home (for example /var versus /private/var on
    // macOS). Compare canonical existing paths without weakening ownership
    // checks for missing or unmanaged roots.
    return realpathSync(resolved);
  } catch {
    return resolved;
  }
}

function removeRegistration(host, entry, state) {
  if (FILE_DROP_HOSTS.includes(host) || host === "opencode") return;
  if (host === "claude") {
    if (["installed", "disabled"].includes(state.kind)) {
      run(claudeBinary(), ["plugin", "uninstall", PLUGIN_ID, "--scope", "user"]);
    }
    if (entry !== null) {
      run(claudeBinary(), ["plugin", "marketplace", "remove", MARKETPLACE_NAME, "--scope", "user"]);
    }
    return;
  }
  if (state.kind === "installed") {
    runCodexJson(["plugin", "remove", PLUGIN_ID, "--json"]);
  }
  if (entry !== null) {
    runCodexJson(["plugin", "marketplace", "remove", MARKETPLACE_NAME, "--json"]);
  }
}

function addRegistration(host, root, installPlugin, { enabled = true } = {}) {
  if (FILE_DROP_HOSTS.includes(host) || host === "opencode") return null;
  if (host === "claude") {
    run(claudeBinary(), ["plugin", "marketplace", "add", root, "--scope", "user"]);
    if (installPlugin) {
      run(claudeBinary(), ["plugin", "install", PLUGIN_ID, "--scope", "user"]);
      if (!enabled) {
        run(claudeBinary(), ["plugin", "disable", PLUGIN_ID, "--scope", "user"]);
      }
    }
    return null;
  }
  runCodexJson(["plugin", "marketplace", "add", root, "--json"]);
  if (installPlugin) {
    return runCodexJson(["plugin", "add", PLUGIN_ID, "--json"]);
  }
  return null;
}

function removeRegistrationBestEffort(host) {
  if (FILE_DROP_HOSTS.includes(host) || host === "opencode") return;
  const entry = (() => {
    try {
      return marketplaceEntry(host);
    } catch {
      return null;
    }
  })();
  if (entry === null) {
    return;
  }
  try {
    const state = pluginState(host);
    if (["installed", "disabled"].includes(state.kind)) {
      const binary = host === "claude" ? claudeBinary() : codexBinary();
      const args =
        host === "claude"
          ? ["plugin", "uninstall", PLUGIN_ID, "--scope", "user"]
          : ["plugin", "remove", PLUGIN_ID, "--json"];
      run(binary, args, { allowFailure: true });
    }
  } catch {
    // Rollback continues with marketplace cleanup.
  }
  const binary = host === "claude" ? claudeBinary() : codexBinary();
  const args =
    host === "claude"
      ? ["plugin", "marketplace", "remove", MARKETPLACE_NAME, "--scope", "user"]
      : ["plugin", "marketplace", "remove", MARKETPLACE_NAME, "--json"];
  run(binary, args, { allowFailure: true });
}

async function recoveryStep(label, action) {
  try {
    await action();
    return true;
  } catch (recoveryError) {
    const detail = recoveryError instanceof Error ? recoveryError.message : String(recoveryError);
    console.error(`warning: rollback step failed (${label}): ${detail}`);
    return false;
  }
}

async function preflightHost(host, action) {
  if (
    (!FILE_DROP_HOSTS.includes(host) && host !== "opencode") ||
    ["install", "update"].includes(action)
  ) {
    requireHostCli(host, { authenticated: ["install", "update"].includes(action) });
  }
  if (host === "claude") {
    if (["install", "update"].includes(action)) {
      requireNoLegacyClaudeInstallation();
    } else {
      warnLegacyClaudeInstallation();
    }
  }
  const paths = managedPaths(host);
  if (host === "opencode") {
    const presence = await Promise.all(
      [paths.root, paths.bridge, paths.bridgeMarker].map((target) => entryExists(target)),
    );
    if (presence.some(Boolean) && !presence.every(Boolean)) {
      fail("OpenCode has a partial or unowned OpenSocrates installation; refusing to replace it");
    }
    if (presence.every(Boolean)) await verifyOpenCodeInstallation(paths);
    const previousEntry = presence.every(Boolean) ? { name: MARKETPLACE_NAME, root: paths.root } : null;
    const previousState = previousEntry === null ? { kind: "missing", version: null } : pluginState(host);
    return {
      host,
      paths,
      previousEntry,
      previousState,
      rootExists: presence[0],
    };
  }
  const previousEntry = marketplaceEntry(host);
  if (previousEntry !== null && entryRoot(previousEntry, host) !== paths.root) {
    fail(
      `marketplace ${MARKETPLACE_NAME} is already registered at ${entryRoot(previousEntry, host)}; ` +
        "refusing to overwrite an unmanaged location",
    );
  }
  const rootExists = await entryExists(paths.root);
  if (rootExists) {
    await requireOwnedRoot(paths.root, host);
  }
  if (previousEntry !== null && !rootExists) {
    fail(`${host} has a managed registration whose root is missing: ${paths.root}`);
  }
  const previousState =
    previousEntry === null
      ? { kind: "missing", version: null }
      : pluginState(host, { requireHostState: ["install", "update"].includes(action) });
  return { host, paths, previousEntry, previousState, rootExists };
}

async function preflightSelectedHosts(options, action, desiredState) {
  if (options.host !== ALL_HOST) {
    return [await preflightHost(options.host, action)];
  }
  // A pre-release or offline caller may supply only the exact host archives it
  // intends to transact. Never mix those candidate packages with downloads
  // for other locally available hosts: the qualified asset set is the exact
  // transaction boundary. With no local assets, --host all retains discovery
  // of every ready host.
  const assetHosts = qualifiedAssetHosts(options);
  const candidates = assetHosts.length > 0 ? assetHosts : SUPPORTED_HOSTS;
  const desiredHosts = new Set(desiredState.installedHosts);
  const rootPresence = Object.fromEntries(
    await Promise.all(candidates.map(async (host) => [host, await entryExists(managedPaths(host).root)])),
  );
  const settled = await Promise.allSettled(candidates.map((host) => preflightHost(host, action)));
  const successes = new Map();
  const failures = new Map();
  settled.forEach((result, index) => {
    const host = candidates[index];
    if (result.status === "fulfilled") successes.set(host, result.value);
    else failures.set(host, result.reason);
  });

  const required = new Set();
  if (assetHosts.length > 0) {
    for (const host of assetHosts) required.add(host);
  } else if (action === "install") {
    for (const host of candidates) {
      if (desiredHosts.has(host) || rootPresence[host]) required.add(host);
    }
  } else if (desiredHosts.size > 0) {
    for (const host of desiredHosts) {
      if (candidates.includes(host)) required.add(host);
    }
  } else if (action === "remove") {
    for (const host of candidates) {
      if (rootPresence[host]) required.add(host);
    }
  }
  for (const host of required) {
    if (failures.has(host)) {
      const reason = failures.get(host);
      fail(`preflight failed for ${host}: ${reason instanceof Error ? reason.message : reason}`);
    }
  }

  let selected;
  if (assetHosts.length > 0) {
    selected = assetHosts.map((host) => successes.get(host)).filter(Boolean);
  } else if (action === "update" && desiredHosts.size > 0) {
    selected = [...desiredHosts].map((host) => successes.get(host)).filter(Boolean);
  } else if (action === "remove") {
    selected = [...successes.values()].filter(
      (item) => desiredHosts.has(item.host) || item.rootExists || item.previousEntry !== null,
    );
  } else {
    selected = [...successes.values()];
  }
  for (const [host, reason] of failures) {
    if (!required.has(host)) {
      console.log(
        `${host}: skipped (host is unavailable or not authenticated: ` +
          `${reason instanceof Error ? reason.message : reason})`,
      );
    }
  }
  if (selected.length === 0 && action !== "remove") {
    fail(`preflight found no ready hosts for ${action} --host all`);
  }
  return selected.sort((left, right) => left.host.localeCompare(right.host));
}

async function stageInstallation(preflight, pluginSource) {
  const { host, paths } = preflight;
  await mkdir(paths.parent, { recursive: true, mode: 0o700 });
  const transient = transientParent(host, paths);
  await mkdir(transient, { recursive: true, mode: 0o700 });
  const staging =
    host === "opencode"
      ? await buildOpenCodeStaging(paths, pluginSource)
      : await buildStagingTree(transient, pluginSource, host);
  return {
    ...preflight,
    staging,
    backup: join(transient, `.opensocrates.backup-${randomUUID()}`),
    bridgeBackup: host === "opencode" ? join(paths.bridgeParent, `.opensocrates.js.backup-${randomUUID()}`) : null,
    bridgeMarkerBackup:
      host === "opencode" ? join(paths.bridgeParent, `.opensocrates-managed.json.backup-${randomUUID()}`) : null,
    registrationRemoved: false,
    backupCreated: false,
    newRootActive: false,
    newBridgeActive: false,
    newBridgeMarkerActive: false,
    bridgeBackupCreated: false,
    bridgeMarkerBackupCreated: false,
    activationStarted: false,
  };
}

async function activateInstallation(transaction) {
  const { host, paths, previousEntry, previousState } = transaction;
  transaction.activationStarted = true;
  if (previousEntry !== null) {
    transaction.registrationRemoved = true;
    removeRegistration(host, previousEntry, previousState);
  }
  if (await entryExists(paths.root)) {
    await rename(paths.root, transaction.backup);
    transaction.backupCreated = true;
  }
  if (host === "opencode" && (await entryExists(paths.bridge))) {
    await rename(paths.bridge, transaction.bridgeBackup);
    transaction.bridgeBackupCreated = true;
  }
  if (host === "opencode" && (await entryExists(paths.bridgeMarker))) {
    await rename(paths.bridgeMarker, transaction.bridgeMarkerBackup);
    transaction.bridgeMarkerBackupCreated = true;
  }
  await rename(host === "opencode" ? transaction.staging.root : transaction.staging, paths.root);
  transaction.newRootActive = true;
  if (host === "opencode") {
    await rename(transaction.staging.bridge, paths.bridge);
    transaction.newBridgeActive = true;
    await rename(transaction.staging.bridgeMarker, paths.bridgeMarker);
    transaction.newBridgeMarkerActive = true;
    await verifyOpenCodeInstallation(paths);
  }
  const result = addRegistration(host, paths.root, true);
  const state = pluginState(host, { requireHostState: true });
  if (
    (host === "codex" && (result?.pluginId !== PLUGIN_ID || result?.version !== PRODUCT_VERSION)) ||
    state.kind !== "installed" ||
    state.version !== PRODUCT_VERSION
  ) {
    fail(`${host} did not confirm the expected installed plugin and version`);
  }
}

async function rollbackInstallation(transaction) {
  if (!transaction.activationStarted) return;
  const { host, paths, previousEntry, previousState } = transaction;
  let restored = false;
  await recoveryStep(`unregister the failed ${host} installation`, async () => {
    removeRegistrationBestEffort(host);
  });
  if (transaction.newRootActive && (await exists(paths.root))) {
    await recoveryStep(`remove the failed ${host} installation root`, async () => {
      // This root was created by this transaction, so deleting it cannot
      // cross the ownership boundary even if a failed host command damaged
      // its marker.
      await rm(paths.root, { recursive: true, force: true });
    });
  }
  if (host === "opencode") {
    if (transaction.newBridgeActive && (await exists(paths.bridge))) {
      await recoveryStep("remove the failed OpenCode bridge", async () => {
        await rm(paths.bridge, { force: true });
      });
    }
    if (transaction.newBridgeMarkerActive && (await exists(paths.bridgeMarker))) {
      await recoveryStep("remove the failed OpenCode bridge sidecar", async () => {
        await rm(paths.bridgeMarker, { force: true });
      });
    }
    if (transaction.bridgeBackupCreated && (await exists(transaction.bridgeBackup))) {
      await recoveryStep("restore the previous OpenCode bridge", async () => {
        await rename(transaction.bridgeBackup, paths.bridge);
      });
    }
    if (transaction.bridgeMarkerBackupCreated && (await exists(transaction.bridgeMarkerBackup))) {
      await recoveryStep("restore the previous OpenCode bridge sidecar", async () => {
        await rename(transaction.bridgeMarkerBackup, paths.bridgeMarker);
      });
    }
  }
  if (transaction.backupCreated && (await exists(transaction.backup))) {
    restored = await recoveryStep(`restore the previous ${host} installation`, async () => {
      await requireOwnedRoot(transaction.backup, host);
      await rename(transaction.backup, paths.root);
    });
  }
  if (transaction.registrationRemoved && previousEntry !== null && (restored || !transaction.backupCreated)) {
    await recoveryStep(`re-register the previous ${host} installation`, async () => {
      addRegistration(host, paths.root, ["installed", "disabled"].includes(previousState.kind), {
        enabled: previousState.kind !== "disabled",
      });
    });
  }
  if (transaction.backupCreated && !restored) {
    console.error(`error: the previous ${host} OpenSocrates installation could not be restored automatically.`);
    console.error(`error: your previous files are preserved at: ${transaction.backup}`);
    console.error(`error: recovery command: /bin/rm -rf -- ${shellQuote(paths.root)}`);
    console.error(`error: recovery command: /bin/mv -- ${shellQuote(transaction.backup)} ${shellQuote(paths.root)}`);
    console.error(`error: recovery command: opensocrates install --host ${host}`);
  }
}

async function cleanupInstallationTransaction(transaction) {
  if (transaction.host === "opencode") {
    await rm(transaction.staging.root, { recursive: true, force: true });
    await rm(transaction.staging.bridge, { force: true });
    await rm(transaction.staging.bridgeMarker, { force: true });
  } else if (await exists(transaction.staging)) {
    await rm(transaction.staging, { recursive: true, force: true });
  }
}

async function commitInstallation(transaction) {
  if (transaction.backupCreated && (await exists(transaction.backup))) {
    await requireOwnedRoot(transaction.backup, transaction.host);
    await rm(transaction.backup, { recursive: true });
    transaction.backupCreated = false;
  }
  if (transaction.host === "opencode") {
    for (const [created, backup] of [
      [transaction.bridgeBackupCreated, transaction.bridgeBackup],
      [transaction.bridgeMarkerBackupCreated, transaction.bridgeMarkerBackup],
    ]) {
      if (created && (await exists(backup))) await rm(backup);
    }
  }
}

function installedDesiredState(previous, hosts) {
  return {
    ...previous,
    installedHosts: [...new Set([...previous.installedHosts, ...hosts])].sort(),
    activeVersion: PRODUCT_VERSION,
    availableVersion: PRODUCT_VERSION,
  };
}

async function runInstallOrUpdate(options, action) {
  const desired = await readDesiredState();
  const preflights = await preflightSelectedHosts(options, action, desired);
  const hosts = preflights.map((item) => item.host);
  const prepared = await prepareVerifiedPackages(options, hosts);
  const packages = new Map(prepared.map((item) => [item.host, item]));
  const transactions = [];
  try {
    for (const preflight of preflights) {
      const item = packages.get(preflight.host);
      console.log(
        `${preflight.host}: verified OpenSocrates ${PRODUCT_VERSION} and ` + `${item.checkedFiles} package files`,
      );
      transactions.push(await stageInstallation(preflight, item.pluginRoot));
    }
    for (const transaction of transactions) {
      await activateInstallation(transaction);
      console.log(`${transaction.host}: activated OpenSocrates ${PRODUCT_VERSION}`);
    }
    await writeDesiredState(installedDesiredState(desired, hosts));
  } catch (error) {
    for (const transaction of [...transactions].reverse()) {
      await rollbackInstallation(transaction);
    }
    throw error;
  } finally {
    await Promise.all(transactions.map(cleanupInstallationTransaction));
    await Promise.all(prepared.map((item) => rm(item.scratch, { recursive: true, force: true })));
  }
  for (const transaction of transactions) {
    const cleaned = await recoveryStep(`remove the committed ${transaction.host} backup`, async () => {
      await commitInstallation(transaction);
    });
    if (!cleaned) {
      console.warn(`warning: ${transaction.host} is active, but its previous backup needs cleanup`);
    }
  }
  const verb = action === "update" ? "updated" : "installed";
  console.log(`OpenSocrates ${PRODUCT_VERSION} ${verb} successfully for ${hosts.join(", ")}.`);
  if (hosts.includes("codex")) {
    console.log(
      "Codex approval required: open one interactive Codex session and approve the " +
        "OpenSocrates hooks before relying on automatic selection. Non-interactive " +
        "codex exec silently skips hooks that have not been trusted.",
    );
  }
  if (hosts.includes("cursor")) {
    console.log(
      "Cursor: run Developer: Reload Window, then invoke /opensocrates from Agent chat. " +
        "This experimental package adds no automatic OpenSocrates hook selector.",
    );
  }
  if (hosts.includes("grok")) {
    console.log(
      "Grok Build: start a new task for automatic native-skill selection, or invoke /opensocrates explicitly.",
    );
  }
  if (hosts.includes("opencode")) {
    console.log(
      "OpenCode: automatic same-turn selection uses the stable chat.message bridge; " +
        "the native opensocrates skill remains available as an explicit fallback.",
    );
  }
  console.log("Start new host tasks to load the updated OpenSocrates integration.");
  return hosts;
}

async function inspectHostStatus(host) {
  if (!FILE_DROP_HOSTS.includes(host) && host !== "opencode") requireHostCli(host);
  if (host === "claude") warnLegacyClaudeInstallation();
  const paths = managedPaths(host);
  if (host === "opencode") {
    const presence = await Promise.all([paths.root, paths.bridge, paths.bridgeMarker].map((target) => exists(target)));
    if (!presence.some(Boolean)) return { host, kind: "missing", version: null, paths };
    if (!presence.every(Boolean)) return { host, kind: "files-only", version: null, paths };
    await verifyOpenCodeInstallation(paths);
    const state = pluginState(host);
    return { host, kind: state.kind, version: state.version, paths };
  }
  const entry = marketplaceEntry(host);
  if (entry === null) {
    if (await exists(paths.root)) {
      await requireOwnedRoot(paths.root, host);
      return { host, kind: "files-only", version: null, paths };
    }
    return { host, kind: "missing", version: null, paths };
  }
  if (entryRoot(entry, host) !== paths.root) {
    fail(`OpenSocrates is registered at an unmanaged location: ${entryRoot(entry, host)}`);
  }
  await requireOwnedRoot(paths.root, host);
  const state = pluginState(host);
  return { host, kind: state.kind, version: state.version, paths };
}

async function showStatus(host) {
  if (host === ALL_HOST) {
    const desired = await readDesiredState();
    console.log(`Desired version: ${desired.activeVersion ?? "none"}`);
    console.log(`Available version: ${desired.availableVersion ?? "unknown"}`);
    console.log(`Last check: ${desired.lastCheckAt ?? "never"}`);
    console.log(`Last successful update: ${desired.lastSuccessfulUpdateAt ?? "never"}`);
    console.log(`Auto-update: ${desired.autoUpdate.enabled ? "enabled" : "disabled"}`);
    let drift = false;
    for (const candidate of SUPPORTED_HOSTS) {
      try {
        const status = await inspectHostStatus(candidate);
        const expected = desired.installedHosts.includes(candidate);
        const hostDrift = expected
          ? status.kind !== "installed" || desired.activeVersion === null || status.version !== desired.activeVersion
          : status.kind !== "missing";
        drift ||= hostDrift;
        if (status.kind === "installed") {
          console.log(
            `${candidate}: installed ${status.version ?? "unknown"}` +
              (["antigravity", "cursor"].includes(candidate)
                ? " (experimental explicit-skill tier)"
                : candidate === "grok"
                  ? " (native skill; automatic and explicit invocation)"
                  : candidate === "opencode"
                    ? " (stable same-turn bridge plus native skill fallback)"
                    : "") +
              (expected
                ? hostDrift
                  ? ` (drift from ${desired.activeVersion ?? "desired state"})`
                  : " (in sync)"
                : " (not in desired state)"),
          );
        } else if (status.kind === "disabled") {
          console.log(
            `${candidate}: installed but disabled (${status.version ?? "unknown"})` +
              (expected ? " (drift: desired host is not active)" : " (not in desired state)"),
          );
        } else if (status.kind === "available") {
          console.log(
            `${candidate}: available but not installed (${status.version ?? "unknown"})` +
              (expected ? " (drift: desired host is not active)" : ""),
          );
        } else if (status.kind === "files-only") {
          console.log(`${candidate}: managed files present but not registered`);
        } else {
          console.log(`${candidate}: not installed` + (expected ? " (drift: desired host is missing)" : ""));
        }
      } catch (error) {
        if (desired.installedHosts.includes(candidate)) drift = true;
        console.log(
          `${candidate}: unavailable (${errorCategory(error)})` +
            (desired.installedHosts.includes(candidate) ? " (drift unknown)" : ""),
        );
      }
    }
    console.log(`Overall: ${drift ? "drift detected" : "no detected drift"}`);
    return;
  }
  const status = await inspectHostStatus(host);
  if (status.kind === "installed") {
    console.log(
      `OpenSocrates ${status.version ?? "unknown"} is installed.` +
        (host === "antigravity"
          ? " Antigravity support is experimental and explicit-skill only."
          : host === "cursor"
            ? " Cursor support is experimental and explicit-skill first."
            : host === "grok"
              ? " Grok Build uses automatic native-skill selection and explicit /opensocrates invocation."
              : host === "opencode"
                ? " OpenCode uses the stable same-turn bridge and native skill fallback."
                : ""),
    );
  } else if (status.kind === "disabled") {
    console.log(
      `OpenSocrates ${status.version ?? "unknown"} is installed but disabled. ` +
        (host === "grok"
          ? "Remove the OpenSocrates disabled entry from Grok Build configuration, then run status again."
          : "Run install or update to re-enable it."),
    );
  } else if (status.kind === "available") {
    console.log(`OpenSocrates ${status.version ?? "unknown"} is available but not installed.`);
  } else if (status.kind === "files-only") {
    console.log(`OpenSocrates files are present but not registered: ${status.paths.root}`);
  } else {
    console.log("OpenSocrates is not installed.");
  }
}

function removalTransaction(preflight) {
  return {
    ...preflight,
    backup: join(
      transientParent(preflight.host, preflight.paths),
      `.opensocrates.removed-${randomUUID()}`,
    ),
    bridgeBackup:
      preflight.host === "opencode"
        ? join(preflight.paths.bridgeParent, `.opensocrates.js.removed-${randomUUID()}`)
        : null,
    bridgeMarkerBackup:
      preflight.host === "opencode"
        ? join(preflight.paths.bridgeParent, `.opensocrates-managed.json.removed-${randomUUID()}`)
        : null,
    registrationRemoved: false,
    backupCreated: false,
    rootCommitted: false,
    bridgeBackupCreated: false,
    bridgeCommitted: false,
    bridgeMarkerBackupCreated: false,
    bridgeMarkerCommitted: false,
  };
}

async function activateRemoval(transaction) {
  const { host, previousEntry, previousState, paths } = transaction;
  if (previousEntry !== null) {
    transaction.registrationRemoved = true;
    removeRegistration(host, previousEntry, previousState);
  }
  if (await entryExists(paths.root)) {
    await rename(paths.root, transaction.backup);
    transaction.backupCreated = true;
  }
  if (host === "opencode" && (await entryExists(paths.bridge))) {
    await rename(paths.bridge, transaction.bridgeBackup);
    transaction.bridgeBackupCreated = true;
  }
  if (host === "opencode" && (await entryExists(paths.bridgeMarker))) {
    await rename(paths.bridgeMarker, transaction.bridgeMarkerBackup);
    transaction.bridgeMarkerBackupCreated = true;
  }
}

async function rollbackRemoval(transaction) {
  let complete = true;
  let restored = !transaction.rootExists;
  if (transaction.rootExists && transaction.backupCreated && (await entryExists(transaction.backup))) {
    restored = await recoveryStep(`restore the removed ${transaction.host} files`, async () => {
      await verifyManagedTreeForPurge(transaction.host, transaction.backup);
      await rename(transaction.backup, transaction.paths.root);
      try {
        await verifyManagedTreeForPurge(transaction.host, transaction.paths.root);
      } catch (error) {
        try {
          await rename(transaction.paths.root, transaction.backup);
        } catch (requarantineError) {
          const detail = requarantineError instanceof Error ? requarantineError.message : String(requarantineError);
          transaction.backupCreated = await entryExists(transaction.backup);
          fail(
            `the restored ${transaction.host} tree failed verification and could not be returned to ` +
              `${transaction.backup}: ${detail}`,
          );
        }
        throw error;
      }
      transaction.backupCreated = false;
    });
  } else if (transaction.rootExists && !transaction.rootCommitted && !transaction.backupCreated) {
    restored = await recoveryStep(`verify the existing ${transaction.host} files`, async () => {
      await verifyManagedTreeForPurge(transaction.host, transaction.paths.root);
    });
  }
  complete = restored && complete;
  if (
    transaction.registrationRemoved &&
    transaction.previousEntry !== null &&
    restored &&
    (await entryExists(transaction.paths.root))
  ) {
    const registrationRestored = await recoveryStep(`restore the removed ${transaction.host} registration`, async () => {
      addRegistration(
        transaction.host,
        transaction.paths.root,
        ["installed", "disabled"].includes(transaction.previousState.kind),
        { enabled: transaction.previousState.kind !== "disabled" },
      );
    });
    complete = registrationRestored && complete;
  } else if (transaction.registrationRemoved && transaction.previousEntry !== null) {
    complete = false;
  }
  if (transaction.host === "opencode") {
    let bridgeRestored = !transaction.rootExists;
    if (
      transaction.rootExists &&
      transaction.bridgeBackupCreated &&
      (await entryExists(transaction.bridgeBackup))
    ) {
      bridgeRestored = await recoveryStep("restore the removed OpenCode bridge", async () => {
        await rename(transaction.bridgeBackup, transaction.paths.bridge);
        transaction.bridgeBackupCreated = false;
      });
    } else if (transaction.rootExists && !transaction.bridgeCommitted && !transaction.bridgeBackupCreated) {
      bridgeRestored = await entryExists(transaction.paths.bridge);
    }
    complete = bridgeRestored && complete;
    let markerRestored = !transaction.rootExists;
    if (
      transaction.rootExists &&
      transaction.bridgeMarkerBackupCreated &&
      (await entryExists(transaction.bridgeMarkerBackup))
    ) {
      markerRestored = await recoveryStep("restore the removed OpenCode bridge sidecar", async () => {
        await rename(transaction.bridgeMarkerBackup, transaction.paths.bridgeMarker);
        transaction.bridgeMarkerBackupCreated = false;
      });
    } else if (
      transaction.rootExists &&
      !transaction.bridgeMarkerCommitted &&
      !transaction.bridgeMarkerBackupCreated
    ) {
      markerRestored = await entryExists(transaction.paths.bridgeMarker);
    }
    complete = markerRestored && complete;
  }
  transaction.originalStateRestored = complete;
  return complete;
}

async function commitRemoval(transaction, { beforeBackupDelete = null } = {}) {
  if (transaction.backupCreated && (await entryExists(transaction.backup))) {
    await verifyManagedTreeForPurge(transaction.host, transaction.backup);
    if (beforeBackupDelete !== null) {
      await beforeBackupDelete(Object.freeze({
        host: transaction.host,
        backup: transaction.backup,
      }));
    }
    await rm(transaction.backup, { recursive: true });
    transaction.backupCreated = false;
    transaction.rootCommitted = true;
  }
  if (transaction.host === "opencode") {
    for (const [flag, backup, label] of [
      ["bridgeBackupCreated", transaction.bridgeBackup, "bridge"],
      ["bridgeMarkerBackupCreated", transaction.bridgeMarkerBackup, "bridge sidecar"],
    ]) {
      if (!transaction[flag] || !(await entryExists(backup))) continue;
      const info = await lstat(backup);
      if (!info.isFile() || info.isSymbolicLink()) {
        fail(`refusing to remove an unsafe OpenCode ${label} backup: ${backup}`);
      }
      await rm(backup);
      transaction[flag] = false;
      if (flag === "bridgeBackupCreated") transaction.bridgeCommitted = true;
      else transaction.bridgeMarkerCommitted = true;
    }
  }
}

async function validateRemovalCommit(transaction) {
  if (transaction.backupCreated && (await entryExists(transaction.backup))) {
    await verifyManagedTreeForPurge(transaction.host, transaction.backup);
  }
  if (transaction.host !== "opencode") return;
  for (const [created, backup, label] of [
    [transaction.bridgeBackupCreated, transaction.bridgeBackup, "bridge"],
    [transaction.bridgeMarkerBackupCreated, transaction.bridgeMarkerBackup, "bridge sidecar"],
  ]) {
    if (!created || !(await entryExists(backup))) continue;
    const info = await lstat(backup);
    if (!info.isFile() || info.isSymbolicLink()) {
      fail(`refusing to remove an unsafe OpenCode ${label} backup: ${backup}`);
    }
  }
}

function xmlEscape(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

async function executablePath(name, environmentOverride) {
  const override = process.env[environmentOverride];
  if (override) {
    const candidate = resolve(override);
    await access(candidate, fsConstants.X_OK);
    return candidate;
  }
  const which = run("/usr/bin/which", [name], { allowFailure: true });
  const candidate = which.status === 0 ? which.stdout.trim() : "";
  if (!candidate || !candidate.startsWith("/")) {
    fail(`could not find an executable ${name} for the automatic updater`);
  }
  await access(candidate, fsConstants.X_OK);
  return candidate;
}

function launchctlBinary() {
  return process.env.OPENSOCRATES_LAUNCHCTL_BIN || "/bin/launchctl";
}

function launchctlDomain() {
  if (typeof process.getuid !== "function") {
    fail("automatic updates require a user launchd domain");
  }
  return `gui/${process.getuid()}`;
}

function launchAgentDocument(npx, channel, environment) {
  const packageTag = channel === "next" ? "next" : "latest";
  const arguments_ = [npx, "--yes", `opensocrates@${packageTag}`, "auto-update", "run"];
  const argumentsXml = arguments_.map((argument) => `      <string>${xmlEscape(argument)}</string>`).join("\n");
  const environmentEntries = Object.entries(environment).sort(([left], [right]) => left.localeCompare(right));
  const environmentXml =
    environmentEntries.length === 0
      ? ""
      : `\n    <key>EnvironmentVariables</key>\n    <dict>\n` +
        environmentEntries
          .map(([key, value]) => `      <key>${xmlEscape(key)}</key>\n` + `      <string>${xmlEscape(value)}</string>`)
          .join("\n") +
        "\n    </dict>";
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>${AUTO_UPDATE_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
${argumentsXml}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>${AUTO_UPDATE_POLL_SECONDS}</integer>
    <key>ProcessType</key>
    <string>Background</string>
    <key>StandardOutPath</key>
    <string>/dev/null</string>
    <key>StandardErrorPath</key>
    <string>/dev/null</string>${environmentXml}
  </dict>
</plist>
`;
}

function launchAgentTarget() {
  return `${launchctlDomain()}/${AUTO_UPDATE_LABEL}`;
}

function launchAgentLoaded() {
  return (
    run(launchctlBinary(), ["print", launchAgentTarget()], {
      allowFailure: true,
    }).status === 0
  );
}

function stopLoadedLaunchAgent() {
  if (!launchAgentLoaded()) return;
  const stopped = run(launchctlBinary(), ["bootout", launchAgentTarget()], {
    allowFailure: true,
  });
  if (stopped.status !== 0 && launchAgentLoaded()) {
    const detail = stopped.stderr?.trim() || stopped.stdout?.trim() || `exit ${stopped.status}`;
    fail(`could not stop the OpenSocrates LaunchAgent: ${detail}`);
  }
}

async function updaterEnvironment(hosts, npx) {
  const node = await executablePath("node", "OPENSOCRATES_NODE_BIN");
  const environment = {
    PATH: [...new Set([dirname(npx), dirname(node), "/usr/bin", "/bin", "/usr/sbin", "/sbin"])].join(":"),
  };
  for (const host of hosts) {
    if (host === "cursor") {
      if (process.env.CURSOR_CONFIG_DIR) {
        environment.CURSOR_CONFIG_DIR = resolve(process.env.CURSOR_CONFIG_DIR);
        continue;
      }
      const app = cursorAppPaths().find((candidate) => existsSync(candidate));
      if (app) continue;
      const executable = await executablePath("cursor", "CURSOR_BIN");
      environment.CURSOR_BIN = executable;
      environment.PATH = [...new Set([dirname(executable), ...environment.PATH.split(":")])].join(":");
      continue;
    }
    if (host === "antigravity") {
      if (process.env.ANTIGRAVITY_CONFIG_DIR) {
        environment.ANTIGRAVITY_CONFIG_DIR = resolve(process.env.ANTIGRAVITY_CONFIG_DIR);
        continue;
      }
      const executable = await executablePath("agy", "AGY_BIN");
      environment.AGY_BIN = executable;
      environment.PATH = [...new Set([dirname(executable), ...environment.PATH.split(":")])].join(":");
      continue;
    }
    if (host === "opencode") {
      // OPENCODE_CONFIG_DIR redirects configuration only. Unlike the
      // content-only hosts above, a scheduled OpenCode update re-runs the same
      // requireHostCli version gate as an interactive install, so recording
      // the config directory and stopping would leave the LaunchAgent without
      // a resolvable opencode: enable would succeed in a shell that has it on
      // PATH, then every scheduled run would fail the gate whenever opencode
      // lives outside the launchd default PATH.
      if (process.env.OPENCODE_CONFIG_DIR) {
        environment.OPENCODE_CONFIG_DIR = resolve(process.env.OPENCODE_CONFIG_DIR);
      }
      const executable = await executablePath("opencode", "OPENCODE_BIN");
      environment.OPENCODE_BIN = executable;
      environment.PATH = [...new Set([dirname(executable), ...environment.PATH.split(":")])].join(":");
      continue;
    }
    if (host === "grok") {
      const executable = await executablePath("grok", "GROK_BIN");
      environment.GROK_BIN = executable;
      environment.PATH = [...new Set([dirname(executable), ...environment.PATH.split(":")])].join(
        ":",
      );
      continue;
    }
    const key = host === "claude" ? "CLAUDE_BIN" : "CODEX_BIN";
    const executable = await executablePath(host, key);
    environment[key] = executable;
    environment.PATH = [...new Set([dirname(executable), ...environment.PATH.split(":")])].join(":");
  }
  for (const key of [
    "ANTIGRAVITY_CONFIG_DIR",
    "CLAUDE_CONFIG_DIR",
    "CODEX_HOME",
    "CURSOR_CONFIG_DIR",
    "GROK_HOME",
    "OPENCODE_CONFIG_DIR",
    "OPENSOCRATES_STATE_DIR",
  ]) {
    if (process.env[key]) environment[key] = resolve(process.env[key]);
  }
  return environment;
}

async function installLaunchAgent(channel, hosts) {
  if (process.platform !== "darwin" || process.arch !== "arm64") {
    fail(`automatic updates currently support darwin-arm64 only; detected ` + `${process.platform}-${process.arch}`);
  }
  const paths = statePaths();
  const npx = await executablePath("npx", "OPENSOCRATES_NPX_BIN");
  const environment = await updaterEnvironment(hosts, npx);
  let previousDocument = null;
  if (await exists(paths.launchAgent)) {
    const info = await lstat(paths.launchAgent);
    if (!info.isFile() || info.isSymbolicLink()) {
      fail(`refusing to replace an unsafe LaunchAgent path: ${paths.launchAgent}`);
    }
    previousDocument = await readFile(paths.launchAgent, "utf8");
  }
  const document = launchAgentDocument(npx, channel, environment);
  if (process.env.OPENSOCRATES_SKIP_LAUNCHCTL === "1") {
    await atomicWritePrivateFile(paths.launchAgent, document);
    return;
  }
  const wasLoaded = launchAgentLoaded();
  if (wasLoaded) stopLoadedLaunchAgent();
  await atomicWritePrivateFile(paths.launchAgent, document);
  const launched = run(launchctlBinary(), ["bootstrap", launchctlDomain(), paths.launchAgent], { allowFailure: true });
  if (launched.status !== 0) {
    if (previousDocument === null) {
      await rm(paths.launchAgent, { force: true });
    } else {
      await atomicWritePrivateFile(paths.launchAgent, previousDocument);
      if (wasLoaded) {
        const restored = run(launchctlBinary(), ["bootstrap", launchctlDomain(), paths.launchAgent], {
          allowFailure: true,
        });
        if (restored.status !== 0) {
          console.error("warning: the previous OpenSocrates LaunchAgent could not be reloaded");
        }
      }
    }
    const detail = launched.stderr?.trim() || launched.stdout?.trim() || `exit ${launched.status}`;
    fail(`could not enable the OpenSocrates LaunchAgent: ${detail}`);
  }
}

async function requireOwnedLaunchAgent(target) {
  const info = await lstat(target);
  if (!info.isFile() || info.isSymbolicLink()) {
    fail(`refusing to remove an unsafe LaunchAgent path: ${target}`);
  }
  const document = await readFile(target, "utf8");
  const labelPattern = new RegExp(
    `<key>\\s*Label\\s*</key>\\s*<string>\\s*${AUTO_UPDATE_LABEL.replaceAll(".", "\\.")}\\s*</string>`,
    "gu",
  );
  const argumentBlocks = [
    ...document.matchAll(/<key>\s*ProgramArguments\s*<\/key>\s*<array>([\s\S]*?)<\/array>/gu),
  ];
  const arguments_ =
    argumentBlocks.length === 1
      ? [...argumentBlocks[0][1].matchAll(/<string>([\s\S]*?)<\/string>/gu)].map((match) => match[1].trim())
      : [];
  if (
    [...document.matchAll(labelPattern)].length !== 1 ||
    arguments_.length !== 5 ||
    !arguments_[0].startsWith("/") ||
    arguments_[1] !== "--yes" ||
    !/^opensocrates@(?:latest|next)$/u.test(arguments_[2]) ||
    arguments_[3] !== "auto-update" ||
    arguments_[4] !== "run"
  ) {
    fail(`refusing to remove a LaunchAgent without the OpenSocrates ownership identity: ${target}`);
  }
}

async function disableLaunchAgent() {
  const paths = statePaths();
  const agentPresent = await entryExists(paths.launchAgent);
  if (agentPresent) {
    await requireSafePathBelow(paths.launchAgentsDirectory, paths.launchAgent, "OpenSocrates LaunchAgent");
    await requireOwnedLaunchAgent(paths.launchAgent);
  }
  if (process.env.OPENSOCRATES_SKIP_LAUNCHCTL !== "1") {
    stopLoadedLaunchAgent();
  }
  if (agentPresent) await rm(paths.launchAgent);
}

async function disableAutoUpdateState(desired) {
  await disableLaunchAgent();
  return {
    ...desired,
    autoUpdate: { enabled: false, hosts: [], nextCheckAt: null },
  };
}

async function runStandardRemove(options, { report = true, beforeBackupDelete = null } = {}) {
  const desired = await readDesiredState();
  const preflights = await preflightSelectedHosts(options, "remove", desired);
  const removedHosts = preflights.map((item) => item.host);
  const remainingHosts = desired.installedHosts.filter((host) => !removedHosts.includes(host));
  const remainingAutoUpdateHosts = desired.autoUpdate.hosts.filter((host) => !removedHosts.includes(host));
  const keepAutoUpdate = desired.autoUpdate.enabled && remainingAutoUpdateHosts.length > 0;
  const nextDesired = {
    ...desired,
    installedHosts: remainingHosts,
    activeVersion: remainingHosts.length === 0 ? null : desired.activeVersion,
    autoUpdate: keepAutoUpdate
      ? { ...desired.autoUpdate, hosts: remainingAutoUpdateHosts }
      : { enabled: false, hosts: [], nextCheckAt: null },
  };
  const launchAgentPresent = await entryExists(statePaths().launchAgent);
  const schedulerNeedsChange =
    options.host === ALL_HOST ||
    remainingHosts.length === 0 ||
    launchAgentPresent !== keepAutoUpdate ||
    desired.autoUpdate.hosts.some((host) => removedHosts.includes(host));
  const transactions = preflights.map(removalTransaction);
  // Validate every source tree before the first unregister/rename. The same
  // check runs again after activation and immediately before deletion to
  // close TOCTOU gaps without stranding pre-existing drift in a backup.
  for (const transaction of transactions) {
    if (transaction.rootExists) {
      await verifyManagedTreeForPurge(transaction.host, transaction.paths.root);
    }
  }
  let schedulerTouched = false;
  let desiredWritten = false;
  try {
    for (const transaction of transactions) await activateRemoval(transaction);
    if (schedulerNeedsChange) {
      schedulerTouched = true;
      if (keepAutoUpdate) {
        await installLaunchAgent(desired.channel, remainingAutoUpdateHosts);
      } else {
        await disableLaunchAgent();
      }
    }
    await writeDesiredState(nextDesired);
    desiredWritten = true;
    for (const transaction of transactions) await validateRemovalCommit(transaction);
    for (const transaction of transactions) {
      await commitRemoval(transaction, { beforeBackupDelete });
    }
  } catch (error) {
    let rollbackComplete = true;
    for (const transaction of [...transactions].reverse()) {
      const restored = await rollbackRemoval(transaction);
      rollbackComplete = restored && rollbackComplete;
    }
    const unrestoredHosts = new Set(
      transactions.filter((transaction) => transaction.originalStateRestored !== true).map((item) => item.host),
    );
    const recoveredHosts = desired.installedHosts.filter((host) => !unrestoredHosts.has(host));
    const recoveredAutoUpdateHosts = desired.autoUpdate.hosts.filter((host) => recoveredHosts.includes(host));
    const keepRecoveredAutoUpdate = desired.autoUpdate.enabled && recoveredAutoUpdateHosts.length > 0;
    let recoveredDesired = {
      ...desired,
      installedHosts: recoveredHosts,
      activeVersion: recoveredHosts.length === 0 ? null : desired.activeVersion,
      autoUpdate: keepRecoveredAutoUpdate
        ? { ...desired.autoUpdate, hosts: recoveredAutoUpdateHosts }
        : { enabled: false, hosts: [], nextCheckAt: null },
    };
    let schedulerRestored = true;
    if (schedulerTouched) {
      schedulerRestored = await recoveryStep("reconcile the automatic updater after removal failure", async () => {
        if (recoveredDesired.autoUpdate.enabled) {
          await installLaunchAgent(recoveredDesired.channel, recoveredDesired.autoUpdate.hosts);
        } else {
          await disableLaunchAgent();
        }
      });
      if (!schedulerRestored && recoveredDesired.autoUpdate.enabled) {
        recoveredDesired = {
          ...recoveredDesired,
          autoUpdate: {
            enabled: false,
            hosts: [],
            nextCheckAt: null,
          },
        };
      }
      rollbackComplete = schedulerRestored && rollbackComplete;
    }
    if (desiredWritten || !rollbackComplete || !schedulerRestored) {
      const stateRestored = await recoveryStep("record desired state after removal failure", async () => {
        await writeDesiredState(recoveredDesired);
      });
      rollbackComplete = stateRestored && rollbackComplete;
    }
    if (!rollbackComplete) {
      console.error("error: removal cleanup is incomplete; no success was recorded.");
      for (const transaction of transactions) {
        if (!transaction.backupCreated || !(await entryExists(transaction.backup))) continue;
        console.error(`error: preserved ${transaction.host} removal residue: ${transaction.backup}`);
        console.error(
          `error: safe cleanup retry: opensocrates remove --host ${transaction.host} --purge`,
        );
        console.error(
          "error: if purge reports an integrity failure, inspect that exact UUID residue before manual cleanup: " +
            `/bin/rm -rf -- ${shellQuote(transaction.backup)}`,
        );
      }
    }
    throw error;
  }
  if (!report) return { removedHosts, desired: nextDesired };
  for (const host of removedHosts) {
    const label =
      host === "antigravity"
        ? "Antigravity"
        : host === "claude"
          ? "Claude"
          : host === "cursor"
            ? "Cursor"
            : host === "grok"
              ? "Grok Build"
              : host === "opencode"
                ? "OpenCode"
                : "Codex";
    console.log(`OpenSocrates was removed from ${label}.`);
  }
  if (removedHosts.length === 0) console.log("OpenSocrates is not installed on any managed host.");
  console.log("Removal scope: registrations and installer-managed roots only; this is not a complete uninstall.");
  const residue = [];
  for (const host of removedHosts) {
    const paths = purgePathsFor(host);
    for (const target of [paths.cacheRoot, paths.cacheMarketplaceRoot, ...paths.pluginData]) {
      if (target !== null && (await entryExists(target))) residue.push(target);
    }
  }
  for (const target of [statePaths().desiredState, statePaths().receipt]) {
    if (await entryExists(target)) residue.push(target);
  }
  for (const target of [...new Set(residue)]) console.log(`Remaining OpenSocrates path: ${target}`);
  if (removedHosts.includes("codex")) {
    console.log("Codex OpenSocrates hook trust is preserved by this removal contract.");
  }
  console.log(`Next: close active hosts, then run opensocrates remove --host ${options.host} --purge.`);
  return { removedHosts, desired: nextDesired };
}

async function purgeRegistration(host, paths) {
  if (FILE_DROP_HOSTS.includes(host) || host === "opencode") {
    return { status: "not-applicable", detail: "file-owned-host" };
  }
  try {
    requireHostCli(host);
  } catch (error) {
    return {
      status: "unverified",
      detail: error instanceof Error ? error.message : String(error),
    };
  }
  if (host === "claude") warnLegacyClaudeInstallation();
  const entry = marketplaceEntry(host);
  if (entry !== null && entryRoot(entry, host) !== paths.root) {
    fail(`${host} OpenSocrates registration points to an unmanaged location`);
  }
  const state = pluginState(host);
  const present = entry !== null || ["installed", "disabled"].includes(state.kind);
  removeRegistration(host, entry, state);
  const remainingEntry = marketplaceEntry(host);
  const remainingState = pluginState(host);
  if (remainingEntry !== null || ["installed", "disabled"].includes(remainingState.kind)) {
    fail(`${host} did not confirm removal of the exact ${PLUGIN_ID} registration`);
  }
  return { status: present ? "removed" : "absent", detail: null };
}

async function capturePurgeComponent(hostResult, component, action) {
  try {
    const value = await action();
    const items = Array.isArray(value) ? value : [value];
    hostResult.components.push(...items);
    return items;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    hostResult.components.push({ component, status: "failed", path: null, detail: message });
    hostResult.errors.push(message);
    return [];
  }
}

function purgeComponentBlocksCompletion(component) {
  return new Set(["pending", "failed"]).has(component.status);
}

function finalizePurgeHostResult(hostResult) {
  const registrationComplete = new Set(["removed", "absent", "not-applicable"]).has(hostResult.registration);
  hostResult.status =
    registrationComplete &&
    !hostResult.components.some(purgeComponentBlocksCompletion) &&
    !purgeComponentBlocksCompletion(hostResult.extension)
      ? "complete"
      : "partial";
  return hostResult.status === "complete";
}

async function resetPurgeTrustExtension(hostResult, options) {
  if (hostResult.host !== "codex" || !options.resetTrust) return true;
  try {
    const reset = await resetCodexOpenSocratesHookTrust({ hooks: options.trustResetHooks ?? {} });
    hostResult.extension = {
      component: "host-security-trust",
      status: reset.status,
      removedCount: reset.removedEvents.length,
      nextAction: null,
    };
    return true;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    hostResult.extension = {
      component: "host-security-trust",
      status: "failed",
      removedCount: 0,
      nextAction: "retry-purge-with-reset-trust-or-review-exact-sections-manually",
      detail: message,
    };
    hostResult.errors.push(message);
    return false;
  }
}

function preservePurgeComponentsAfterTrustFailure(hostResult, paths) {
  hostResult.registration = "preserved";
  hostResult.registrationDetail = "not-attempted-after-trust-reset-failure";
  const preserved = [
    ["managed-root", paths.root],
    ["transaction-residue", null],
  ];
  if (hostResult.host === "opencode") {
    preserved.push(["opencode-bridge", paths.bridge], ["opencode-bridge-residue", null]);
  }
  if (paths.cacheRoot !== null) preserved.push(["plugin-cache", paths.cacheRoot]);
  preserved.push(...paths.pluginData.map((path) => ["plugin-data", path]));
  for (const [component, path] of preserved) {
    hostResult.components.push({
      component,
      status: "preserved",
      path,
      detail: "not-attempted-after-trust-reset-failure",
    });
  }
}

async function purgeOneHost(hostResult, options) {
  const paths = purgePathsFor(hostResult.host);
  if (!(await resetPurgeTrustExtension(hostResult, options))) {
    preservePurgeComponentsAfterTrustFailure(hostResult, paths);
    finalizePurgeHostResult(hostResult);
    return;
  }
  try {
    const registration = await purgeRegistration(hostResult.host, paths);
    hostResult.registration = registration.status;
    hostResult.registrationDetail = registration.detail;
    if (registration.status === "unverified") hostResult.errors.push(registration.detail);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    hostResult.registration = "failed";
    hostResult.registrationDetail = message;
    hostResult.errors.push(message);
  }

  await capturePurgeComponent(hostResult, "managed-root", () =>
    removeOwnedManagedRoot(hostResult.host, paths),
  );
  if (hostResult.host === "opencode") {
    await capturePurgeComponent(hostResult, "opencode-bridge", () => purgeOpenCodeBridge(paths));
  }
  await capturePurgeComponent(hostResult, "transaction-residue", () =>
    cleanupTransientRootResidue(hostResult.host, paths),
  );
  if (hostResult.host === "opencode") {
    await capturePurgeComponent(hostResult, "opencode-bridge-residue", () =>
      purgeOpenCodeBridgeResidue(paths),
    );
  }
  if (paths.cacheRoot !== null) {
    await capturePurgeComponent(hostResult, "plugin-cache", () => purgeHostCache(hostResult.host, paths));
  }
  if (paths.pluginData.length > 0) {
    await capturePurgeComponent(hostResult, "plugin-data", () => purgeClaudePluginData(paths));
  }
  finalizePurgeHostResult(hostResult);
}

function hostDeactivated(hostResult) {
  const registrationComplete = new Set(["removed", "absent", "not-applicable"]).has(hostResult.registration);
  const activationComponents = hostResult.components.filter((item) =>
    new Set(["managed-root", "opencode-bridge"]).has(item.component),
  );
  return registrationComplete && !activationComponents.some(purgeComponentBlocksCompletion);
}

async function updatePurgeDesiredState(options, desired, result) {
  const deactivated = result.hosts.filter(hostDeactivated).map((item) => item.host);
  const installedHosts = desired.installedHosts.filter((host) => !deactivated.includes(host));
  const autoUpdateHosts = desired.autoUpdate.hosts.filter((host) => !deactivated.includes(host));
  const keepAutoUpdate = desired.autoUpdate.enabled && autoUpdateHosts.length > 0;
  let nextDesired = {
    ...desired,
    installedHosts,
    activeVersion: installedHosts.length === 0 ? null : desired.activeVersion,
    autoUpdate: keepAutoUpdate
      ? { ...desired.autoUpdate, hosts: autoUpdateHosts }
      : { enabled: false, hosts: [], nextCheckAt: null },
  };
  const launchAgentPresent = await entryExists(statePaths().launchAgent);
  const schedulerNeedsChange =
    deactivated.length > 0 &&
    (options.host === ALL_HOST ||
      installedHosts.length === 0 ||
      launchAgentPresent !== keepAutoUpdate ||
      desired.autoUpdate.hosts.some((host) => deactivated.includes(host)));
  if (schedulerNeedsChange) {
    try {
      if (keepAutoUpdate) await installLaunchAgent(desired.channel, autoUpdateHosts);
      else await disableLaunchAgent();
      result.finalization.components.push({
        component: "launch-agent",
        status: launchAgentPresent ? "removed-or-reconciled" : "absent",
        path: statePaths().launchAgent,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      result.finalization.components.push({
        component: "launch-agent",
        status: "failed",
        path: statePaths().launchAgent,
        detail: message,
      });
      result.finalization.errors.push(message);
      nextDesired = desired;
    }
  } else {
    result.finalization.components.push({
      component: "launch-agent",
      status: "preserved",
      path: statePaths().launchAgent,
    });
  }
  if (!schedulerNeedsChange && jsonDeepEqual(nextDesired, desired)) {
    result.finalization.components.push({
      component: "desired-state",
      status: "preserved",
      path: statePaths().desiredState,
    });
    return desired;
  }
  try {
    nextDesired = await writeDesiredState(nextDesired);
    result.finalization.components.push({
      component: "desired-state",
      status: "updated",
      path: statePaths().desiredState,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    result.finalization.components.push({
      component: "desired-state",
      status: "failed",
      path: statePaths().desiredState,
      detail: message,
    });
    result.finalization.errors.push(message);
  }
  return nextDesired;
}

async function preparePurgeStateFinalization() {
  const paths = statePaths();
  if (!(await entryExists(paths.directory))) return { directory: paths.directory, tombstones: [] };
  const directoryInfo = await lstat(paths.directory);
  if (!directoryInfo.isDirectory() || directoryInfo.isSymbolicLink()) {
    fail(`refusing to finalize an unsafe OpenSocrates state directory: ${paths.directory}`);
  }
  const uuid = "[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}";
  const stateTemporary = new RegExp(
    `^\\.(?:desired-state|auto-update-receipt)\\.json\\.${uuid}\\.tmp$`,
    "u",
  );
  const purgeTombstone = new RegExp(
    `^\\.purge-finalize-${uuid}-(?:desired-state\\.json|auto-update-receipt\\.json|` +
      `\\.(?:desired-state|auto-update-receipt)\\.json\\.${uuid}\\.tmp)$`,
    "u",
  );
  const candidates = [paths.desiredState, paths.receipt];
  const tombstones = [];
  for (const name of await readdir(paths.directory)) {
    if (stateTemporary.test(name)) {
      candidates.push(join(paths.directory, name));
    } else if (purgeTombstone.test(name)) {
      tombstones.push({ original: null, tombstone: join(paths.directory, name) });
    }
  }
  const renamed = [];
  try {
    for (const item of tombstones) {
      await requireSafePathBelow(paths.directory, item.tombstone, "OpenSocrates prior purge tombstone");
      const info = await lstat(item.tombstone);
      if (!info.isFile() || info.isSymbolicLink()) {
        fail(`refusing to remove an unsafe prior OpenSocrates purge tombstone: ${item.tombstone}`);
      }
    }
    for (const target of candidates) {
      if (!(await entryExists(target))) continue;
      await requireSafePathBelow(paths.directory, target, "OpenSocrates state file");
      const info = await lstat(target);
      if (!info.isFile() || info.isSymbolicLink()) {
        fail(`refusing to remove an unsafe OpenSocrates state file: ${target}`);
      }
      const tombstone = join(paths.directory, `.purge-finalize-${randomUUID()}-${basename(target)}`);
      await rename(target, tombstone);
      const item = { original: target, tombstone };
      tombstones.push(item);
      renamed.push(item);
    }
    return { directory: paths.directory, tombstones };
  } catch (error) {
    for (const item of [...renamed].reverse()) {
      await recoveryStep("restore installer state after purge finalization failed", async () => {
        if (await entryExists(item.tombstone)) await rename(item.tombstone, item.original);
      });
    }
    throw error;
  }
}

async function completePurgeStateFinalization(plan, result, options) {
  try {
    for (const item of plan.tombstones) {
      if (!(await entryExists(item.tombstone))) continue;
      await requireSafePathBelow(plan.directory, item.tombstone, "OpenSocrates purge tombstone");
      const info = await lstat(item.tombstone);
      if (!info.isFile() || info.isSymbolicLink()) {
        fail(`refusing to remove an unsafe OpenSocrates purge tombstone: ${item.tombstone}`);
      }
      await rm(item.tombstone);
    }
    if (await entryExists(plan.directory)) await rmdir(plan.directory);
    result.finalization.components.push({
      component: "state-directory",
      status: "removed",
      path: plan.directory,
    });
    result.finalization.status = "complete";
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    result.finalization.components.push({
      component: "state-directory",
      status: "failed",
      path: plan.directory,
      detail: message,
    });
    result.finalization.errors.push(message);
    result.finalization.status = "partial";
    result.status = "partial";
    console.error(`error: OpenSocrates state cleanup remains at: ${plan.directory}`);
    console.error(
      `error: retry command: opensocrates remove --host ${options.host} --purge` +
        (options.resetTrust ? " --reset-trust" : ""),
    );
  }
}

async function runPurgeLocked(options) {
  const hosts = options.host === ALL_HOST ? SUPPORTED_HOSTS : [options.host];
  const result = createPurgeResult(hosts, { resetTrust: options.resetTrust });
  const desired = await readDesiredState();
  for (const hostResult of result.hosts) await purgeOneHost(hostResult, options);
  const nextDesired = await updatePurgeDesiredState(options, desired, result);
  const hostsComplete = result.hosts.every((item) => item.status === "complete");
  const finalizationComplete = result.finalization.errors.length === 0;
  result.status = hostsComplete && finalizationComplete ? "complete" : "partial";
  let stateFinalization = null;
  if (
    result.status === "complete" &&
    nextDesired.installedHosts.length === 0 &&
    !nextDesired.autoUpdate.enabled
  ) {
    try {
      stateFinalization = await preparePurgeStateFinalization();
      result.finalization.status = "ready";
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      result.finalization.components.push({
        component: "state-finalization",
        status: "failed",
        path: statePaths().directory,
        detail: message,
      });
      result.finalization.errors.push(message);
      result.finalization.status = "partial";
      result.status = "partial";
    }
  } else {
    result.finalization.status = result.status === "complete" ? "preserved" : "deferred";
  }
  return { result, stateFinalization };
}

function reportPurgeResult(result) {
  for (const host of result.hosts) {
    console.log(`${host.host}: purge ${host.status}; registration ${host.registration}.`);
    if (
      new Set(["unverified", "failed"]).has(host.registration) &&
      typeof host.registrationDetail === "string"
    ) {
      console.error(`${host.host}: registration ${host.registration} (${host.registrationDetail})`);
    }
    for (const component of host.components) {
      if (new Set(["pending", "failed"]).has(component.status)) {
        console.error(
          `${host.host}: ${component.component} ${component.status}` +
            (component.path ? ` at ${component.path}` : "") +
            (component.detail ? ` (${component.detail})` : ""),
        );
      }
    }
    if (host.extension.status === "preserved") {
      console.log(
        `${host.host}: host security trust was preserved; rerun purge with --reset-trust to reset only ` +
          "the exact OpenSocrates hook approvals.",
      );
    } else if (host.extension.status === "reset") {
      console.log(
        `${host.host}: host security trust reset completed for ${host.extension.removedCount} exact ` +
          "OpenSocrates hook entries.",
      );
    } else if (host.extension.status === "absent") {
      console.log(`${host.host}: no exact OpenSocrates host security trust entries were present.`);
    } else if (host.extension.status === "failed") {
      console.error(
        `${host.host}: host security trust reset failed; no successful trust mutation is claimed.`,
      );
      console.error(
        `${host.host}: rerun the same purge with --reset-trust after resolving Codex config validation, ` +
          "or back up the config and manually review only the seven exact OpenSocrates hook sections.",
      );
    }
  }
  for (const component of result.finalization.components) {
    if (new Set(["pending", "failed"]).has(component.status)) {
      console.error(
        `finalization: ${component.component} ${component.status}` +
          (component.path ? ` at ${component.path}` : "") +
          (component.detail ? ` (${component.detail})` : ""),
      );
    }
  }
  if (result.status === "complete") {
    console.log("OpenSocrates purge completed for registrations and provably owned payloads.");
    console.log("User task, project, chat, plan, and history data was preserved.");
  } else {
    console.error("OpenSocrates purge is incomplete; no complete-uninstall success is claimed.");
    console.error("Resolve the reported item, close active hosts if needed, and rerun the same purge command.");
  }
}

async function runPurge(options) {
  const outcome = await withOperationLock(() => runPurgeLocked(options));
  if (outcome.stateFinalization !== null) {
    await completePurgeStateFinalization(outcome.stateFinalization, outcome.result, options);
  }
  reportPurgeResult(outcome.result);
  if (outcome.result.status !== "complete") {
    fail("purge remains pending or failed for one or more components");
  }
  return outcome.result;
}

async function enableAutoUpdate(options) {
  const previous = await readDesiredState();
  const preflights = new Map();
  let installedHosts = [...previous.installedHosts];
  if (installedHosts.length === 0) {
    const discoveryOptions = { ...options, host: ALL_HOST };
    const discovered = await preflightSelectedHosts(discoveryOptions, "update", previous);
    for (const item of discovered) {
      if (item.previousState.kind === "installed") {
        preflights.set(item.host, item);
        installedHosts.push(item.host);
      }
    }
  }
  let updateHosts = options.host === ALL_HOST ? [...installedHosts] : [options.host];
  if (updateHosts.length === 0) {
    fail("install OpenSocrates on at least one host before enabling automatic updates");
  }
  for (const host of updateHosts) {
    const preflight = preflights.get(host) ?? (await preflightHost(host, "update"));
    if (preflight.previousState.kind !== "installed") {
      fail(`OpenSocrates is not installed on ${host}`);
    }
    if (typeof preflight.previousState.version !== "string") {
      fail(`cannot determine the installed OpenSocrates version on ${host}`);
    }
    preflights.set(host, preflight);
    installedHosts.push(host);
  }
  installedHosts = [...new Set(installedHosts)].sort();
  updateHosts = [...new Set(updateHosts)].sort();
  let activeVersion = previous.activeVersion;
  if (activeVersion === null) {
    const observedVersions = new Set();
    for (const host of installedHosts) {
      const preflight = preflights.get(host) ?? (await preflightHost(host, "update"));
      if (preflight.previousState.kind !== "installed" || typeof preflight.previousState.version !== "string") {
        fail(`cannot determine the installed OpenSocrates version on ${host}`);
      }
      preflights.set(host, preflight);
      observedVersions.add(preflight.previousState.version);
    }
    if (observedVersions.size !== 1) {
      fail("installed hosts do not share one known version; run update --host all before enabling automatic updates");
    }
    [activeVersion] = observedVersions;
  }
  const desired = {
    ...previous,
    channel: options.channel,
    installedHosts,
    activeVersion,
    updatePolicy: {
      intervalHours: options.intervalHours,
      allowMajor: options.allowMajor,
    },
    autoUpdate: {
      enabled: true,
      hosts: updateHosts,
      nextCheckAt: nowIso(),
    },
  };
  await writeDesiredState(desired);
  try {
    await installLaunchAgent(options.channel, desired.autoUpdate.hosts);
  } catch (error) {
    await writeDesiredState(previous);
    throw error;
  }
  console.log(
    `Automatic updates enabled for ${desired.autoUpdate.hosts.join(", ")} on the ` +
      `${desired.channel} channel every ${desired.updatePolicy.intervalHours} hours with jitter.`,
  );
  console.log(
    desired.updatePolicy.allowMajor
      ? "Automatic major-version upgrades are enabled."
      : "Automatic major-version upgrades remain disabled.",
  );
}

async function showAutoUpdateStatus() {
  const desired = await readDesiredState();
  const agentPresent = await exists(statePaths().launchAgent);
  console.log(`Automatic updates: ${desired.autoUpdate.enabled ? "enabled" : "disabled"}`);
  console.log(`LaunchAgent: ${agentPresent ? "installed" : "not installed"}`);
  console.log(`Channel: ${desired.channel}`);
  console.log(`Installed hosts: ${desired.installedHosts.join(", ") || "none"}`);
  console.log(`Automatic-update hosts: ${desired.autoUpdate.hosts.join(", ") || "none"}`);
  console.log(`Interval: ${desired.updatePolicy.intervalHours} hours with jitter`);
  console.log(`Major upgrades: ${desired.updatePolicy.allowMajor ? "allowed" : "blocked"}`);
  console.log(`Next check: ${desired.autoUpdate.nextCheckAt ?? "not scheduled"}`);
  console.log(`Last check: ${desired.lastCheckAt ?? "never"}`);
  console.log(`Last successful update: ${desired.lastSuccessfulUpdateAt ?? "never"}`);
}

async function disableAutoUpdate() {
  const desired = await readDesiredState();
  await writeDesiredState(await disableAutoUpdateState(desired));
  console.log("Automatic updates are disabled and the LaunchAgent was removed.");
}

async function runScheduledUpdate(options) {
  let desired = await readDesiredState();
  if (!desired.autoUpdate.enabled) {
    console.log("Automatic updates are disabled.");
    return;
  }
  const scheduledAt = Date.parse(desired.autoUpdate.nextCheckAt ?? "");
  if (!options.force && Number.isFinite(scheduledAt) && scheduledAt > Date.now()) {
    console.log(`The next automatic update check is scheduled for ${desired.autoUpdate.nextCheckAt}.`);
    return;
  }
  const checkedAt = nowIso();
  const hosts = desired.autoUpdate.hosts;
  if (hosts.length === 0) {
    fail("the automatic updater has no selected hosts in desired state");
  }
  const next = nextCheckAt(desired.updatePolicy.intervalHours);
  const currentMajor = majorVersion(desired.activeVersion);
  const availableMajor = majorVersion(PRODUCT_VERSION);
  if (
    !desired.updatePolicy.allowMajor &&
    currentMajor !== null &&
    availableMajor !== null &&
    availableMajor > currentMajor
  ) {
    desired = await writeDesiredState({
      ...desired,
      availableVersion: PRODUCT_VERSION,
      lastCheckAt: checkedAt,
      autoUpdate: { ...desired.autoUpdate, nextCheckAt: next },
    });
    await writeAutoUpdateReceipt({
      version: PRODUCT_VERSION,
      checkedAt,
      hosts: hosts.map((host) => ({ host, result: "blocked-major" })),
      result: "blocked",
      errorCategory: "major-policy",
    });
    console.log(`OpenSocrates ${PRODUCT_VERSION} is available but blocked by the major-version policy.`);
    return;
  }
  try {
    const ready = [];
    for (const host of hosts) ready.push(await preflightHost(host, "update"));
    const alreadyCurrent =
      desired.activeVersion === PRODUCT_VERSION &&
      ready.every((item) => item.previousState.kind === "installed" && item.previousState.version === PRODUCT_VERSION);
    if (!alreadyCurrent) {
      if (hosts.length > 1) {
        await runInstallOrUpdate({ ...options, host: ALL_HOST }, "update");
      } else {
        const [host] = hosts;
        const local = localAssetInputs(options, host);
        await runInstallOrUpdate(
          {
            ...options,
            host,
            asset: local.asset,
            checksum: local.checksum,
          },
          "update",
        );
      }
    }
    const refreshed = await readDesiredState();
    desired = await writeDesiredState({
      ...refreshed,
      availableVersion: PRODUCT_VERSION,
      lastCheckAt: checkedAt,
      lastSuccessfulUpdateAt: alreadyCurrent ? refreshed.lastSuccessfulUpdateAt : checkedAt,
      autoUpdate: { ...refreshed.autoUpdate, nextCheckAt: next },
    });
    await writeAutoUpdateReceipt({
      version: PRODUCT_VERSION,
      checkedAt,
      hosts: hosts.map((host) => ({
        host,
        result: alreadyCurrent ? "current" : "updated",
      })),
      result: alreadyCurrent ? "no-update" : "updated",
      errorCategory: null,
    });
    console.log(
      alreadyCurrent
        ? `OpenSocrates ${PRODUCT_VERSION} is already current on every managed host.`
        : `OpenSocrates ${PRODUCT_VERSION} was reconciled across ${hosts.join(", ")}.`,
    );
  } catch (error) {
    await recoveryStep("record the failed automatic update", async () => {
      desired = await writeDesiredState({
        ...(await readDesiredState()),
        availableVersion: PRODUCT_VERSION,
        lastCheckAt: checkedAt,
        autoUpdate: { ...desired.autoUpdate, nextCheckAt: next },
      });
      await writeAutoUpdateReceipt({
        version: PRODUCT_VERSION,
        checkedAt,
        hosts: hosts.map((host) => ({ host, result: "failed" })),
        result: "failed",
        errorCategory: errorCategory(error),
      });
    });
    throw error;
  }
}

function requireSupportedPlatform() {
  if (process.platform !== "darwin" || process.arch !== "arm64") {
    fail(
      `OpenSocrates ${PRODUCT_VERSION} prebuilt installation supports darwin-arm64 only; ` +
        `detected ${process.platform}-${process.arch}`,
    );
  }
}

async function verifyPackages(options) {
  const assetHosts = qualifiedAssetHosts(options);
  const hosts =
    options.host === ALL_HOST ? (assetHosts.length > 0 ? assetHosts : SUPPORTED_HOSTS) : [options.host];
  const prepared = await prepareVerifiedPackages(options, hosts);
  try {
    for (const item of prepared) {
      console.log(
        `${item.host}: verified OpenSocrates ${PRODUCT_VERSION} release and ` + `${item.checkedFiles} package files.`,
      );
      if (item.host === "opencode") {
        const paths = managedPaths("opencode");
        const presence = await Promise.all(
          [paths.root, paths.bridge, paths.bridgeMarker].map((target) => exists(target)),
        );
        if (presence.some(Boolean)) {
          if (!presence.every(Boolean)) {
            fail("OpenCode installed state is partial and failed verification");
          }
          await verifyOpenCodeInstallation(paths);
          console.log("opencode: verified installed bridge, skill inventory, and ownership.");
        }
      }
    }
  } finally {
    await Promise.all(prepared.map((item) => rm(item.scratch, { recursive: true, force: true })));
  }
}

export async function main(argv = process.argv.slice(2), internalDependencies = {}) {
  const options = parseCli(argv);
  if (options.action === "help") {
    showHelp();
    return 0;
  }
  if (options.action === "status") {
    await showStatus(options.host);
    return 0;
  }
  if (options.action === "verify") {
    await verifyPackages(options);
    return 0;
  }
  if (options.action === "auto-update" && options.autoUpdateAction === "status") {
    await showAutoUpdateStatus();
    return 0;
  }
  if (options.action === "remove" && options.purge) {
    await runPurge({
      ...options,
      trustResetHooks: internalDependencies.trustResetHooks ?? {},
    });
    return 0;
  }
  return withOperationLock(async () => {
    if (options.action === "remove") {
      await runStandardRemove(options, {
        beforeBackupDelete: internalDependencies.beforeRemovalBackupDelete ?? null,
      });
      return 0;
    }
    if (options.action === "auto-update") {
      if (options.autoUpdateAction === "enable") {
        await enableAutoUpdate(options);
      } else if (options.autoUpdateAction === "disable") {
        await disableAutoUpdate();
      } else {
        requireSupportedPlatform();
        await runScheduledUpdate(options);
      }
      return 0;
    }
    requireSupportedPlatform();
    await runInstallOrUpdate(options, options.action);
    return 0;
  });
}

let invokedDirectly = false;
if (process.argv[1] !== undefined) {
  try {
    invokedDirectly = realpathSync(process.argv[1]) === fileURLToPath(import.meta.url);
  } catch {
    invokedDirectly = false;
  }
}
if (invokedDirectly) {
  main().catch((error) => {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`error: ${message}`);
    process.exitCode = 1;
  });
}
