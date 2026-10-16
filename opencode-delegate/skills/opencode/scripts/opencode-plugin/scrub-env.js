// Loaded into the shared `opencode serve` by delegate.py, never from a repo.
//
// Every command OpenCode runs inherits the server's environment, including
// OPENCODE_SERVER_PASSWORD, which would let a script it writes drive the server
// API. shell.env can't delete inherited variables (its output.env holds only
// additions), but setting one to "" blanks it for that command (verified on
// OpenCode 1.19.3).
//
// At load it writes a heartbeat file per directory, so delegate.py can refuse
// to run when this plugin is not active (GET /config does not list plugins
// loaded this way).
import { mkdirSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { join } from "node:path";

export const OpencodeDelegateScrubEnv = async ({ directory }, options = {}) => {
  const blank = ["OPENCODE_SERVER_PASSWORD", ...(options.blank ?? [])];
  if (options.heartbeat_dir) {
    mkdirSync(options.heartbeat_dir, { recursive: true });
    const id = createHash("sha256").update(directory).digest("hex").slice(0, 32);
    writeFileSync(join(options.heartbeat_dir, id),
      JSON.stringify({ directory, pid: process.pid, loaded: Date.now() }));
  }
  return {
    "shell.env": async (_input, output) => {
      for (const name of blank) output.env[name] = "";
    },
  };
};
