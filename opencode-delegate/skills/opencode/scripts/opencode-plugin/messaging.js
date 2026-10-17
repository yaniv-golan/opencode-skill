// Loaded into the shared `opencode serve` by delegate.py for a delegated run.
//
// It gives the model three tools that talk back to the run's orchestrator (the
// Claude session that started it) through the private endpoint delegate.py
// exposes: a one-way progress note, a blocking question, and a message to a
// paired task. The endpoint url and bearer token arrive in a per-directory
// token file, read once on load and unlinked immediately; without it the tools
// still exist but report that messaging is unavailable.
//
// Orchestrator and peer messages reach the model as tagged text, so any tool
// output containing the same tags is escaped to stop file contents or command
// output from imitating a real message.
import { readFileSync, unlinkSync } from "node:fs";
import { createHash, createHmac } from "node:crypto";
import { homedir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const TAGGED = /<\/?(?:orchestrator-message|peer-message|task-message)/i;
const ESCAPE = /<(?=\/?(?:orchestrator-message|peer-message|task-message))/gi;
const ENVELOPE = /<\/?(?:orchestrator-message|peer-message)\b[^>]*>/gi;

export const OpencodeDelegateMessaging = async ({ directory }, options = {}) => {
  let url = null;
  let token = null;
  if (options.token_dir) {
    const file = join(options.token_dir,
      createHash("sha256").update(directory).digest("hex").slice(0, 32));
    try {
      const saved = JSON.parse(readFileSync(file, "utf8"));
      url = saved.url;
      token = saved.token;
      unlinkSync(file);
    } catch {
      url = null;
    }
  }

  const hook = async (_input, output) => {
    if (typeof output.output !== "string" || !TAGGED.test(output.output)) return;
    output.output = output.output.replace(ESCAPE, "&lt;");
  };

  // Orchestrator envelopes are signed with the run's token; one that a model
  // read elsewhere can be copied but not signed. Neutralise the brackets of any
  // opening tag (and of a closing tag that follows it) whose signature is absent
  // or wrong. Without a token there is no valid signature at all.
  const signId = (id) => createHmac("sha256", token).update(id).digest("hex").slice(0, 32);
  const sanitize = (text) => {
    const invalid = {};
    return text.replace(ENVELOPE, (tag) => {
      const name = /^<\/?([a-z-]+)/i.exec(tag)[1].toLowerCase();
      if (tag.startsWith("</")) {
        if (!invalid[name]) return tag;
        invalid[name] = false;
        return "&lt;" + tag.slice(1);
      }
      const id = /(?:^|\s)id="([^"]*)"/.exec(tag);
      const sig = /(?:^|\s)sig="([^"]*)"/.exec(tag);
      if (token && id && sig && sig[1] === signId(id[1])) {
        invalid[name] = false;
        return tag;
      }
      invalid[name] = true;
      return "&lt;" + tag.slice(1);
    });
  };
  const chatHook = async (_input, output) => {
    if (!output || !Array.isArray(output.parts)) return;
    for (const part of output.parts) {
      if (part && part.type === "text" && typeof part.text === "string") {
        part.text = sanitize(part.text);
      }
    }
  };

  let z;
  try {
    z = (await import(pathToFileURL(join(homedir(), ".config/opencode/node_modules/zod/index.js")).href)).z;
  } catch {
    return { "tool.execute.after": hook, "chat.message": chatHook };
  }

  const call = async (method, path, body) => {
    try {
      const res = await fetch(url + path, {
        method,
        headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
        body: body && JSON.stringify(body),
        signal: AbortSignal.timeout(30000),
      });
      let json = null;
      try {
        json = await res.json();
      } catch {}
      return { status: res.status, json };
    } catch {
      return { status: 0 };
    }
  };

  const OFF = "Messaging is not available in this run.";
  const LIMIT = "Not sent: the per-task message limit is reached. Continue without it.";

  return {
    tool: {
      message_orchestrator: {
        description: "Send a short note to the Claude session that orchestrates this task (progress, a blocker, something it should know). One-way; does not wait for a reply. Use sparingly: a few per task at most.",
        args: { message: z.string() },
        execute: async (args) => {
          if (!url) return OFF;
          const res = await call("POST", "/message", { body: args.message });
          if (res.status === 200) return `Sent to your orchestrator (id ${res.json?.id}).`;
          if (res.status === 429) return LIMIT;
          return `Not sent (HTTP ${res.status}).`;
        },
      },
      ask_orchestrator: {
        description: "Ask the orchestrating Claude session a question and WAIT for its answer. Use only when you cannot proceed correctly without a decision.",
        args: { question: z.string() },
        execute: async (args, ctx) => {
          if (!url) return OFF;
          const res = await call("POST", "/ask", { question: args.question });
          if (res.status === 429) return LIMIT;
          if (res.status !== 200) return `Not sent (HTTP ${res.status}).`;
          const id = res.json?.id;
          const deadline = Date.now() + 20 * 60 * 1000;
          for (;;) {
            if (ctx?.abort?.aborted) return "Aborted while waiting for an answer.";
            if (Date.now() >= deadline) return "No answer within 20 minutes. Continue with your best judgement and say so in your final message.";
            await new Promise((resolve) => setTimeout(resolve, 2000));
            const poll = await call("GET", "/answer?id=" + encodeURIComponent(id));
            if (poll.json && typeof poll.json.answer === "string") {
              return "Answer from your orchestrator: " + poll.json.answer;
            }
          }
        },
      },
      send_message: {
        description: "Send a message to another task you have been paired with (by its task name). Only works for paired tasks.",
        args: { to: z.string(), message: z.string() },
        execute: async (args) => {
          if (!url) return OFF;
          const res = await call("POST", "/send", { to: args.to, body: args.message });
          if (res.status === 200) return `Sent to ${args.to} (id ${res.json?.id}).`;
          if (res.status === 403) return `Not sent: you are not paired with ${args.to}.`;
          if (res.status === 429) return LIMIT;
          return `Not sent (HTTP ${res.status}).`;
        },
      },
    },
    "tool.execute.after": hook,
    "chat.message": chatHook,
  };
};
