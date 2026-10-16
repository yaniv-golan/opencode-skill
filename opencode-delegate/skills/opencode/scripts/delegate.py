#!/usr/bin/env python3
"""opencode delegate: run a coding task in OpenCode, isolated in a git worktree.

Claude orchestrates; OpenCode edits. Every task gets its own worktree and branch
(opencode/<task>), all runs go through ONE shared `opencode serve` (parallel
`opencode run` processes corrupt-lock OpenCode's SQLite state), and the run is
refused unless the worktree's opencode.json denies unlisted shell commands.

Subcommands (all print plain text; exit codes below):
  server start|stop|status        manage the shared OpenCode server
  models                          list models the server offers (free ones marked)
  init REPO [--allow CMD ...]     write a default-deny opencode.json into REPO
  run --repo R --task SLUG (--prompt TEXT | --prompt-file F) [options]
  diff --repo R --task SLUG       full diff of the task worktree vs its base
  list [--repo R]                 task worktrees and their change counts
  remove --repo R --task SLUG [--delete-branch] [--force]
  report [--since DAYS] [--project NAME] [--fails]

Exit codes for `run`:
  0 changes made, syntax OK      2 ran but changed nothing (WROTE_NOTHING)
  3 timed out (session aborted)  4 OpenCode/model error
  5 changes made but syntax check failed
  1 usage / setup error (nothing was delegated)

Environment:
  OPENCODE_DELEGATE_MODEL   default model (else opencode/deepseek-v4.1-flash-free)
  OPENCODE_DELEGATE_PORT    server port (default 4096)
  OPENCODE_DELEGATE_HOME    state dir (default ~/.local/state/opencode-delegate)
  OPENCODE_DELEGATE_PASS_ENV  comma-separated extra variables to pass to the server. By default
                            it gets only PATH/HOME/locale/proxy/toolchain basics, because every
                            command OpenCode runs inherits the server's environment.
  OPENCODE_DELEGATE_PATH_PREPEND  dir(s) put first on PATH for the server (so for every
                            shell command OpenCode runs) and for --setup, e.g. a pinned
                            Node: ~/.nvm/versions/node/v24.18.0/bin. Read at server start.
"""
import argparse, base64, hashlib, json, os, re, secrets, shutil, signal, socket, subprocess, sys, threading, time, queue
import urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

DEFAULT_MODEL = "opencode/deepseek-v4.1-flash-free"
HOME = Path(os.environ.get("OPENCODE_DELEGATE_HOME", Path.home() / ".local/state/opencode-delegate"))
PORT = int(os.environ.get("OPENCODE_DELEGATE_PORT", "4096"))
URL = f"http://127.0.0.1:{PORT}"
SERVER_FILE = HOME / "server.json"
RUN_LOG = HOME / "runs.jsonl"
WORKTREES = HOME / "worktrees"
POLICY_FILE = "opencode.json"
SCRUB_PLUGIN = Path(__file__).resolve().parent / "opencode-plugin" / "scrub-env.js"
HEARTBEATS = HOME / "alive"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,48}$")
DENIED_MARK = "prevents you from using this specific tool call"

EXIT_OK, EXIT_USAGE, EXIT_NOTHING, EXIT_TIMEOUT, EXIT_ERROR, EXIT_SYNTAX = 0, 1, 2, 3, 4, 5


def toolchain_env(base=None):
    env = dict(os.environ if base is None else base)
    pre = os.environ.get("OPENCODE_DELEGATE_PATH_PREPEND", "")
    if pre:
        env["PATH"] = os.path.expanduser(pre) + os.pathsep + env.get("PATH", "")
    return env


# The server's environment is inherited by every command OpenCode runs, so it
# gets only what it needs. Anything else (e.g. a paid provider's API key) must
# be named in OPENCODE_DELEGATE_PASS_ENV (comma-separated).
SERVER_ENV_KEEP = {"PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "TERM", "LANG",
                   "TZ", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME",
                   "NVM_DIR", "PNPM_HOME", "COREPACK_HOME", "SSL_CERT_FILE", "NODE_EXTRA_CA_CERTS",
                   "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy"}


def server_env():
    """Minimal environment for `opencode serve` (and so for OpenCode's shells)."""
    passthrough = {v.strip() for v in os.environ.get("OPENCODE_DELEGATE_PASS_ENV", "").split(",") if v.strip()}
    env = {k: v for k, v in os.environ.items()
           if k in SERVER_ENV_KEEP or k in passthrough or k.startswith("LC_")
           or (k.startswith("OPENCODE_") and not k.startswith("OPENCODE_DELEGATE_")
               and k != "OPENCODE_SERVER_PASSWORD")}
    return toolchain_env(env)


def server_plugin_config(env):
    """OPENCODE_CONFIG_CONTENT that adds our scrub plugin, merged with any the user set."""
    try:
        cfg = json.loads(env.get("OPENCODE_CONFIG_CONTENT") or "{}")
    except ValueError:
        die("OPENCODE_CONFIG_CONTENT is set but is not JSON; can't add the safety plugin to it")
    plugins = [p for p in cfg.get("plugin", []) if "opencode-delegate" not in json.dumps(p)]
    plugins.append([SCRUB_PLUGIN.as_uri(), {"heartbeat_dir": str(HEARTBEATS)}])
    cfg["plugin"] = plugins
    return json.dumps(cfg)


def heartbeat_file(directory):
    return HEARTBEATS / hashlib.sha256(str(directory).encode()).hexdigest()[:32]


def node_version(env):
    exe = shutil.which("node", path=env.get("PATH"))
    if not exe:
        return None
    r = subprocess.run([exe, "--version"], capture_output=True, text=True, env=env)
    return r.stdout.strip() or None


def die(msg, code=EXIT_USAGE):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        die(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


# ── server ──────────────────────────────────────────────────────────────────

def _state():
    try:
        return json.loads(SERVER_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _auth_header(state):
    pw = state.get("password")
    if not pw:
        return {}
    return {"Authorization": "Basic " + base64.b64encode(f"opencode:{pw}".encode()).decode()}


def api(method, path, state=None, timeout=10):
    state = _state() if state is None else state
    req = urllib.request.Request(URL + path, method=method, headers=_auth_header(state))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    return json.loads(body) if body else None


def server_healthy(state=None):
    """True only for the server this script started: it answers with our
    password and rejects requests without one."""
    state = _state() if state is None else state
    if not state.get("password"):
        return False
    try:
        if not api("GET", "/global/health", state, timeout=3).get("healthy"):
            return False
    except (urllib.error.URLError, OSError, ValueError, AttributeError):
        return False
    try:
        urllib.request.urlopen(URL + "/global/health", timeout=3)
        return False  # answers without a password: not ours
    except urllib.error.HTTPError as e:
        return e.code == 401
    except (urllib.error.URLError, OSError):
        return False


def server_start(quiet=False):
    if not shutil.which("opencode"):
        die("opencode CLI not found on PATH (install: brew install opencode)")
    state = _state()
    if server_healthy(state):
        if not quiet:
            print(f"server already running at {URL} (pid {state.get('pid', '?')})")
        return state
    if _pid_alive(state.get("pid")):
        # Ours, alive, but not answering: never start a second one beside it.
        die(f"the server this script started (pid {state['pid']}) is running but not answering "
            f"health checks; retry shortly, or `server stop` to restart it")
    # Anything else listening on the port is not ours. A plain TCP connect, so a
    # slow or busy foreign server is not mistaken for a free port.
    try:
        socket.create_connection(("127.0.0.1", PORT), timeout=2).close()
        die(f"port {PORT} is held by a process this script did not start "
            f"(see `lsof -nP -iTCP:{PORT} -sTCP:LISTEN`); stop it or set OPENCODE_DELEGATE_PORT")
    except OSError:
        pass
    HOME.mkdir(parents=True, exist_ok=True)
    password = secrets.token_urlsafe(24)
    log = open(HOME / "server.log", "ab")
    if not SCRUB_PLUGIN.is_file():
        die(f"safety plugin missing: {SCRUB_PLUGIN}")
    env = server_env()
    env["OPENCODE_CONFIG_CONTENT"] = server_plugin_config(env)
    env["OPENCODE_SERVER_PASSWORD"] = password
    proc = subprocess.Popen(["opencode", "serve", "--hostname", "127.0.0.1", "--port", str(PORT)],
                            stdout=log, stderr=log, stdin=subprocess.DEVNULL, env=env,
                            start_new_session=True)
    state = {"pid": proc.pid, "port": PORT, "password": password, "node": node_version(env),
             "scrub_plugin": hashlib.sha256(SCRUB_PLUGIN.read_bytes()).hexdigest(),
             "path_prepend": os.environ.get("OPENCODE_DELEGATE_PATH_PREPEND", ""),
             "started": datetime.now(timezone.utc).isoformat()}
    for _ in range(60):
        if proc.poll() is not None:
            die(f"opencode serve exited with {proc.returncode}; see {HOME / 'server.log'}")
        if server_healthy(state):
            # Record only a server that is up, so a failed start never orphans a live one.
            tmp = SERVER_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(state))
            os.chmod(tmp, 0o600)
            os.replace(tmp, SERVER_FILE)
            if not quiet:
                print(f"server started at {URL} (pid {proc.pid}); log: {HOME / 'server.log'}")
            return state
        time.sleep(0.5)
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    die(f"opencode serve did not become healthy in 30s (stopped it); see {HOME / 'server.log'}")


def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    r = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True)
    return "opencode" in r.stdout and "serve" in r.stdout


def server_stop():
    state = _state()
    pid = state.get("pid")
    if not pid:
        print("no server recorded")
        return
    try:
        busy = {k: v for k, v in (api("GET", "/session/status", state) or {}).items()
                if (v or {}).get("type") != "idle"}
    except Exception:
        busy = {}
    if busy:
        print(f"WARNING: stopping with {len(busy)} active session(s): {', '.join(busy)}")
    try:
        os.killpg(pid, signal.SIGTERM)
        print(f"stopped server pid {pid}")
    except ProcessLookupError:
        print(f"server pid {pid} was not running")
    SERVER_FILE.unlink(missing_ok=True)


def server_status():
    state = _state()
    if server_healthy(state):
        info = api("GET", "/global/health", state)
        sessions = api("GET", "/session/status", state) or {}
        active = [k for k, v in sessions.items() if (v or {}).get("type") != "idle"]
        print(f"running at {URL} pid {state.get('pid')} version {info.get('version')} "
              f"node {state.get('node')} active sessions: {len(active)}")
    else:
        print(f"not running (expected at {URL})")


def list_models(state):
    data = api("GET", "/config/providers", state)
    out = []
    for p in data.get("providers", []):
        for mid, m in (p.get("models") or {}).items():
            cost = m.get("cost") or {}
            free = not cost.get("input") and not cost.get("output")
            out.append((f"{p['id']}/{mid}", free, (m.get("limit") or {}).get("context"),
                        (m.get("capabilities") or {}).get("toolcall")))
    return out


# ── policy ──────────────────────────────────────────────────────────────────

POLICY_TEMPLATE = {
    "$schema": "https://opencode.ai/config.json",
    "permission": {
        "edit": "allow",
        "read": "allow",
        "external_directory": "deny",
        "webfetch": "deny",
        "bash": {
            "*": "deny",
            "git status*": "allow",
            "git diff*": "allow",
            "git log*": "allow",
            "git show*": "allow",
            "ls*": "allow",
            "pwd": "allow",
            "node --check *": "allow",
        },
    },
}


def _is_deny(value):
    if value == "deny":
        return True
    return isinstance(value, dict) and value.get("*") == "deny"


def check_policy(path):
    """Return a list of problems with the opencode.json at path ([] = safe)."""
    try:
        cfg = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return [f"{path.name} missing"]
    except ValueError as e:
        return [f"{path.name} is not plain JSON ({e}); comments/JSONC cannot be verified"]
    return check_config(cfg)


def check_config(cfg):
    """Problems with a config dict: a file, or the merged config the server reports."""
    if cfg.get("permissions"):
        # 1.19 schema marks `permission` deprecated in favour of an ordered
        # `permissions` rule list whose semantics this script has not verified.
        return ["`permissions` (new rule-list format) is set; only the `permission` block is verified"]
    perm = cfg.get("permission")
    if not isinstance(perm, dict):
        return ["`permission` must be an object with per-tool rules (missing or a bare string)"]
    problems = []
    if not _is_deny(perm.get("bash")):
        problems.append('`permission.bash` must be "deny" or have "*": "deny" (allowlist the rest)')
    if not _is_deny(perm.get("external_directory")):
        problems.append('`permission.external_directory` must be "deny"')
    if isinstance(perm.get("bash"), dict):
        risky = [k for k, v in perm["bash"].items() if v == "allow" and k.split()[0] in
                 ("*", "sh", "bash", "zsh", "eval", "env", "xargs", "sudo", "curl", "wget", "rm")]
        if risky:
            problems.append(f"allowlist contains shell/network/destructive entries: {risky}")
    return problems


def policy_warnings(path):
    """Allowed patterns that hand OpenCode a general-purpose interpreter."""
    try:
        bash = json.loads(Path(path).read_text())["permission"]["bash"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    broad = re.compile(r"^(node|python3?|deno|bun|ruby|perl|npx|pnpm (exec|dlx)|npm exec|yarn dlx)( \*|\*)$")
    return [k for k, v in bash.items() if v == "allow" and broad.match(k)] if isinstance(bash, dict) else []


def cmd_init(args):
    repo = Path(args.repo).resolve()
    target = repo / POLICY_FILE
    if target.exists() or (repo / "opencode.jsonc").exists():
        problems = check_policy(target) if target.exists() else ["opencode.jsonc cannot be verified"]
        print(f"{target} already exists; not overwriting.")
        print("policy check: " + ("OK" if not problems else "; ".join(problems)))
        return EXIT_OK if not problems else EXIT_USAGE
    policy = json.loads(json.dumps(POLICY_TEMPLATE))
    for c in args.allow or []:
        policy["permission"]["bash"][c] = "allow"
    if args.model:
        policy["model"] = args.model
    target.write_text(json.dumps(policy, indent=2) + "\n")
    print(f"wrote {target}")
    problems = check_policy(target)
    if problems:
        print("WARNING: " + "; ".join(problems))
    for w in policy_warnings(target):
        print(f"WARNING: '{w}' lets OpenCode run arbitrary code (e.g. node -e); prefer exact commands")
    print("Commit it so new task worktrees inherit it (uncommitted, it is copied in per run).")
    return EXIT_OK


# ── worktrees ───────────────────────────────────────────────────────────────

def repo_root(path):
    root = git(path, "rev-parse", "--show-toplevel").strip()
    common = git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    # Always key off the main checkout, even if called from inside a task worktree.
    return Path(common).parent if common.endswith("/.git") else Path(root)


def worktree_path(repo, slug):
    return WORKTREES / repo.name / slug


def ensure_worktree(repo, slug, base):
    wt = worktree_path(repo, slug)
    branch = f"opencode/{slug}"
    if wt.exists():
        if not (wt / ".git").exists():
            die(f"{wt} exists but is not a git worktree; remove it or pick another --task")
        return wt, False
    if git(repo, "branch", "--list", branch).strip():
        die(f"branch {branch} exists without a worktree; `git -C {repo} branch -D {branch}` "
            f"or pick another --task")
    wt.parent.mkdir(parents=True, exist_ok=True)
    git(repo, "worktree", "add", "-b", branch, str(wt), base or "HEAD")
    return wt, True


def task_changes(wt):
    """Changes in a task worktree, minus the policy file the script copied in."""
    return {f: st for f, st in porcelain(wt).items() if not (f == POLICY_FILE and st == "??")}


def porcelain(wt):
    out = {}
    for line in git(wt, "status", "--porcelain=v1", "--untracked-files=all").splitlines():
        out[line[3:]] = line[:2]
    return out


# ── run ─────────────────────────────────────────────────────────────────────

def abort_busy_sessions(wt, state):
    """Abort every non-idle session in this worktree. One worktree = one task,
    so anything busy there is ours (e.g. still queued when the client was killed,
    before it had emitted its session id)."""
    q = urllib.request.quote(str(wt))
    try:
        status = api("GET", f"/session/status?directory={q}", state) or {}
    except Exception as e:
        print(f"[WARN] could not list sessions for {wt}: {e}")
        return []
    aborted = []
    for sid, st in status.items():
        if (st or {}).get("type") != "idle":
            try:
                api("POST", f"/session/{sid}/abort?directory={q}", state)
                aborted.append(sid)
            except Exception as e:
                print(f"[WARN] could not abort session {sid}: {e}")
    return aborted


def _reader(stream, q):
    for line in iter(stream.readline, ""):
        q.put(line)
    q.put(None)


def syntax_check(wt, files):
    errors, checked = [], 0
    for f in files:
        p = wt / f
        if not p.is_file():
            continue
        cmd = None
        if f.endswith(".py"):
            cmd = [sys.executable, "-m", "py_compile", str(p)]
        elif f.endswith((".js", ".mjs", ".cjs")) and shutil.which("node"):
            cmd = ["node", "--check", str(p)]
        elif f.endswith((".sh", ".bash")):
            cmd = ["bash", "-n", str(p)]
        elif f.endswith(".json"):
            try:
                json.loads(p.read_text())
            except ValueError as e:
                errors.append(f"{f}: {e}")
            checked += 1
            continue
        if cmd:
            checked += 1
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=wt)
            if r.returncode:
                errors.append(f"{f}: {(r.stderr or r.stdout).strip().splitlines()[0][:160]}")
    return checked, errors


def cmd_run(args):
    if not SLUG_RE.match(args.task):
        die("--task must be lowercase letters, digits and hyphens (max 49 chars)")
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text()
    else:
        prompt = args.prompt or ""
    if not prompt.strip():
        die("empty prompt")
    model = args.model or os.environ.get("OPENCODE_DELEGATE_MODEL") or DEFAULT_MODEL
    repo = repo_root(Path(args.repo).resolve())

    state = server_start(quiet=True)
    want = hashlib.sha256(SCRUB_PLUGIN.read_bytes()).hexdigest()
    if state.get("scrub_plugin") != want:
        busy = [k for k, v in (api("GET", "/session/status", state) or {}).items()
                if (v or {}).get("type") != "idle"]
        if busy:
            die("the running server was started without the current safety plugin and has "
                f"{len(busy)} active session(s); wait for them, then `server stop` and retry")
        print("[setup] restarting the server to load the current safety plugin")
        server_stop()
        state = server_start(quiet=True)
    models = {m[0]: m for m in list_models(state)}
    if model not in models:
        free = sorted(k for k, v in models.items() if v[1])
        die(f"model {model} not offered by the server. Free now: {', '.join(free) or 'none'}")

    def discard_if_new():
        if created:
            git(repo, "worktree", "remove", "--force", str(wt), check=False)
            git(repo, "branch", "-D", f"opencode/{args.task}", check=False)

    def refuse(problems, where):
        discard_if_new()
        die(f"refusing to delegate: unsafe or missing OpenCode policy in {where}:\n  - "
            + "\n  - ".join(problems)
            + f"\nFix: python3 {Path(__file__).resolve()} init {repo}  (then commit opencode.json)")

    created, wt = False, None
    # Check before creating anything, so a refusal leaves no worktree behind.
    if not worktree_path(repo, args.task).exists():
        problems = check_policy(repo / POLICY_FILE)
        if problems and not args.unsafe_policy:
            refuse(problems, repo)
    wt, created = ensure_worktree(repo, args.task, args.base)
    policy = wt / POLICY_FILE
    copied_policy = False
    if not policy.exists() and (repo / POLICY_FILE).exists():
        shutil.copy2(repo / POLICY_FILE, policy)  # uncommitted in the main checkout
        copied_policy = True
    elif (repo / POLICY_FILE).exists() and policy.read_bytes() != (repo / POLICY_FILE).read_bytes():
        print(f"[WARN] {POLICY_FILE} in the worktree differs from {repo / POLICY_FILE}; "
              f"the worktree's copy is the one enforced")
    problems = check_policy(policy)
    if problems and not args.unsafe_policy:
        refuse(problems, wt)
    for w in policy_warnings(policy):
        print(f"[WARN] policy allows '{w}': OpenCode can run arbitrary code through it")

    nvmrc = repo / ".nvmrc"
    if nvmrc.exists():
        want = "v" + nvmrc.read_text().strip().lstrip("v")
        if state.get("node") != want:
            print(f"[WARN] repo pins Node {want} (.nvmrc) but the server's shell has "
                  f"{state.get('node')}; OpenCode's checks will run on the wrong Node. Restart with "
                  f"OPENCODE_DELEGATE_PATH_PREPEND=<node {want} bin dir> (server stop, then run again)")

    if args.setup and created:
        print(f"[setup] {args.setup}")
        r = subprocess.run(args.setup, shell=True, cwd=wt, capture_output=True, text=True,
                           env=toolchain_env())
        if r.returncode:
            tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-15:])
            # Don't leave a half-set-up worktree that a retry would silently reuse.
            git(repo, "worktree", "remove", "--force", str(wt), check=False)
            git(repo, "branch", "-D", f"opencode/{args.task}", check=False)
            die(f"setup failed (exit {r.returncode}); worktree removed so a retry starts clean:\n{tail}")

    orphans = abort_busy_sessions(wt, state)
    if orphans:
        print(f"[WARN] aborted {len(orphans)} session(s) still running in this worktree: {', '.join(orphans)}")

    # The server caches each directory's config on first use; without this a
    # tightened allowlist is silently ignored (verified on 1.19.3).
    disposed_at = time.time()
    try:
        api("POST", f"/instance/dispose?directory={urllib.request.quote(str(wt))}", state)
    except Exception as e:
        print(f"[WARN] could not reset the server's cached config for {wt}: {e}")

    # Check what the server will actually enforce (merged global + project,
    # after the cache reset), not just the file.
    try:
        effective = api("GET", f"/config?directory={urllib.request.quote(str(wt))}", state) or {}
        problems = check_config(effective)
    except Exception as e:
        problems = [f"could not read the effective config from the server: {e}"]
    if problems and not args.unsafe_policy:
        refuse(problems, f"the server's effective config for {wt}")
    # The config request above re-created the instance, which loads plugins.
    hb = heartbeat_file(wt)
    try:
        fresh = json.loads(hb.read_text()).get("loaded", 0) / 1000 >= disposed_at - 1
    except (OSError, ValueError):
        fresh = False
    if not fresh:
        discard_if_new()
        die(f"refusing to delegate: the safety plugin did not load for {wt} "
            f"(no fresh heartbeat at {hb}); see {HOME / 'server.log'}")

    before = porcelain(wt)
    head = git(wt, "rev-parse", "HEAD").strip()
    print("=== OPENCODE START ===")
    print(f"task     : {args.task}  ({'new' if created else 'reused'} worktree)")
    print(f"worktree : {wt}")
    print(f"branch   : opencode/{args.task} @ {head[:10]}")
    print(f"model    : {model}")
    print(f"timeout  : {args.timeout}s")
    print("======================", flush=True)

    env = dict(os.environ, OPENCODE_SERVER_PASSWORD=state.get("password", ""))
    cmd = ["opencode", "run", "--attach", URL, "--dir", str(wt), "--auto", "-m", model,
           "--format", "json", "--title", f"delegate:{args.task}"]
    if args.variant:
        cmd += ["--variant", args.variant]
    cmd += ["--", prompt]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            stdin=subprocess.DEVNULL, env=env, cwd=wt, start_new_session=True)
    q = queue.Queue()
    threading.Thread(target=_reader, args=(proc.stdout, q), daemon=True).start()

    stats = dict(tool_calls=0, denied=[], tool_errors=0, tokens_in=0, tokens_out=0,
                 tokens_reasoning=0, tokens_cache_read=0, cost_usd=0.0, errors=[])
    reads, session_id, timed_out, last_text = {}, None, False, ""

    def stamp():
        return f"{int(time.time() - t0):>4}s"

    while True:
        remaining = args.timeout - (time.time() - t0)
        if remaining <= 0:
            timed_out = True
            break
        try:
            line = q.get(timeout=min(remaining, 5))
        except queue.Empty:
            if proc.poll() is not None and q.empty():
                break
            continue
        if line is None:
            break
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            print(f"{stamp()} [raw] {line[:200]}", flush=True)
            continue
        session_id = session_id or ev.get("sessionID")
        t, part = ev.get("type"), ev.get("part") or {}
        if t == "tool_use":
            st = part.get("state") or {}
            if st.get("status") not in ("completed", "error"):
                continue
            stats["tool_calls"] += 1
            tool, inp = part.get("tool", "?"), st.get("input") or {}
            target = (inp.get("filePath") or inp.get("command") or inp.get("pattern")
                      or inp.get("path") or "")
            extra = ""
            if tool == "edit":
                fd = (st.get("metadata") or {}).get("filediff") or {}
                if fd.get("additions") or fd.get("deletions"):
                    extra = f" (+{fd.get('additions', 0)}/-{fd.get('deletions', 0)})"
            if tool == "read" and target:
                reads[target] = reads.get(target, 0) + 1
                if reads[target] == 5:
                    print(f"{stamp()} [WARN] {target} read 5 times: OpenCode may be circling",
                          flush=True)
            shown = str(target).replace(str(wt) + "/", "")[:110]
            print(f"{stamp()} [{tool}] {shown}{extra}", flush=True)
            if st.get("status") == "error":
                msg = str(st.get("error") or st.get("output") or "")
                if DENIED_MARK in msg:
                    stats["denied"].append(f"{tool}: {shown}")
                    print(f"{stamp()} [DENIED] by opencode.json policy", flush=True)
                else:
                    stats["tool_errors"] += 1
                    print(f"{stamp()} [WARN] {msg.strip().splitlines()[0][:160] if msg.strip() else 'tool error'}",
                          flush=True)
        elif t == "text":
            txt = (part.get("text") or "").strip()
            if txt:
                last_text = txt
                print(f"{stamp()} [opencode] {txt[:600]}", flush=True)
        elif t == "step_finish":
            tok = part.get("tokens") or {}
            stats["tokens_in"] += tok.get("input") or 0
            stats["tokens_out"] += tok.get("output") or 0
            stats["tokens_reasoning"] += tok.get("reasoning") or 0
            stats["tokens_cache_read"] += (tok.get("cache") or {}).get("read") or 0
            stats["cost_usd"] += part.get("cost") or 0
        elif t == "error":
            err = ev.get("error") or {}
            msg = ((err.get("data") or {}).get("message") if isinstance(err, dict) else None) or str(err)
            stats["errors"].append(msg[:300])
            print(f"{stamp()} [ERROR] {msg[:300]}", flush=True)

    if timed_out:
        print(f"{stamp()} [TIMEOUT] aborting", flush=True)
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        rc = proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        rc = proc.wait()
    duration = round(time.time() - t0, 1)
    # Also covers a client that died early: nothing may keep editing after we report.
    aborted = abort_busy_sessions(wt, state)
    if aborted:
        session_id = session_id or aborted[0]
        print(f"[abort] stopped server-side session(s): {', '.join(aborted)}")

    after = porcelain(wt)
    changed = sorted(f for f, s in after.items() if before.get(f) != s
                     and not (copied_policy and f == POLICY_FILE))
    head_after = git(wt, "rev-parse", "HEAD").strip()
    commits = git(wt, "log", "--oneline", f"{head}..{head_after}").strip() if head_after != head else ""
    checked, syntax_errors = syntax_check(wt, changed)

    print()
    if timed_out:
        outcome, code = "timeout", EXIT_TIMEOUT
    elif stats["errors"] or (rc != 0 and not changed):
        outcome, code = "error", EXIT_ERROR
    elif not changed and not commits:
        outcome, code = "wrote_nothing", EXIT_NOTHING
    elif syntax_errors:
        outcome, code = "syntax_errors", EXIT_SYNTAX
    else:
        outcome, code = "ok", EXIT_OK
    print(f"=== OPENCODE {outcome.upper()} (opencode exit {rc}, {duration}s) ===")
    if commits:
        print("=== COMMITS CREATED BY OPENCODE (policy should have denied this) ===\n" + commits)
    if changed:
        print(f"=== CHANGED FILES ({len(changed)}) ===")
        stat = git(wt, "diff", "--stat", head).rstrip()
        if stat:
            print(stat)
        for f in changed:
            if after.get(f) == "??":
                print(f" {f} (new, untracked)")
    if checked:
        print(f"=== SYNTAX {'OK' if not syntax_errors else 'ERRORS'} ({checked} checked) ===")
        for e in syntax_errors:
            print(f"  {e}")
    if stats["denied"]:
        print(f"=== DENIED BY POLICY ({len(stats['denied'])}) ===")
        for d in stats["denied"][:20]:
            print(f"  {d}")
    tok = stats["tokens_in"] + stats["tokens_out"]
    print(f"tool calls {stats['tool_calls']} | tokens {tok:,} ({stats['tokens_in']:,} in, "
          f"{stats['tokens_out']:,} out) | cost ${stats['cost_usd']:.4f}")
    print(f"review: git -C {wt} diff {head[:10]}   |   session {session_id}")

    HOME.mkdir(parents=True, exist_ok=True)
    entry = dict(ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), delegate="opencode",
                 project=repo.name, repo=str(repo), task=args.task, worktree=str(wt), model=model,
                 session=session_id, outcome=outcome, exit_code=code, opencode_exit=rc,
                 timed_out=timed_out, timeout_secs=args.timeout, duration_secs=duration,
                 prompt_words=len(prompt.split()), files_changed=len(changed),
                 syntax_errors=len(syntax_errors), denied=len(stats["denied"]),
                 tool_errors=stats["tool_errors"], tool_calls=stats["tool_calls"],
                 tokens_in=stats["tokens_in"], tokens_out=stats["tokens_out"],
                 tokens_reasoning=stats["tokens_reasoning"],
                 tokens_cache_read=stats["tokens_cache_read"], cost_usd=round(stats["cost_usd"], 6))
    with open(RUN_LOG, "a") as fh:
        fh.write(json.dumps(entry) + "\n")
    return code


# ── inspection ──────────────────────────────────────────────────────────────

def task_worktree(args):
    repo = repo_root(Path(args.repo).resolve())
    wt = worktree_path(repo, args.task)
    if not wt.exists():
        die(f"no worktree for task {args.task} ({wt})")
    return repo, wt


def merge_base(repo, wt):
    return git(wt, "merge-base", "HEAD", git(repo, "rev-parse", "HEAD").strip(), check=False).strip()


def cmd_diff(args):
    repo, wt = task_worktree(args)
    base = merge_base(repo, wt) or "HEAD"
    sys.stdout.write(git(wt, "diff", base))
    untracked = [f for f, s in task_changes(wt).items() if s == "??"]
    for f in untracked:
        p = wt / f
        print(f"\n=== new untracked file: {f} ===")
        try:
            print(p.read_text()[:20000])
        except (UnicodeDecodeError, OSError):
            print("(binary or unreadable)")
    return EXIT_OK


def cmd_list(args):
    roots = [WORKTREES / repo_root(Path(args.repo).resolve()).name] if args.repo else \
        sorted(p for p in WORKTREES.glob("*") if p.is_dir())
    any_found = False
    for root in roots:
        for wt in sorted(p for p in root.glob("*") if (p / ".git").exists()):
            any_found = True
            n = len(task_changes(wt))
            print(f"{root.name}/{wt.name}: {n} changed file(s)  {wt}")
    if not any_found:
        print("no task worktrees")
    return EXIT_OK


def cmd_remove(args):
    repo, wt = task_worktree(args)
    dirty = task_changes(wt)
    if dirty and not args.force:
        die(f"{wt} has {len(dirty)} uncommitted change(s); review/commit them or pass --force")
    # --force is needed for the untracked copied policy file even when nothing else changed.
    git(repo, "worktree", "remove", "--force", str(wt))
    print(f"removed worktree {wt}")
    if args.delete_branch:
        git(repo, "branch", "-D" if args.force else "-d", f"opencode/{args.task}")
        print(f"deleted branch opencode/{args.task}")
    return EXIT_OK


def cmd_report(args):
    if not RUN_LOG.exists():
        print(f"no runs logged yet ({RUN_LOG})")
        return EXIT_OK
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.since) if args.since else None
    runs = []
    for line in RUN_LOG.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if args.project and r.get("project") != args.project:
            continue
        if cutoff and datetime.fromisoformat(r["ts"].replace("Z", "+00:00")) < cutoff:
            continue
        if args.fails and r.get("outcome") == "ok":
            continue
        runs.append(r)
    if not runs:
        print("no matching runs")
        return EXIT_OK
    by_model = {}
    for r in runs:
        by_model.setdefault(r.get("model", "?"), []).append(r)
    print(f"{'model':42} {'runs':>4} {'ok':>4} {'none':>4} {'t/o':>4} {'err':>4} {'syn':>4} "
          f"{'med s':>6} {'tokens':>10}")
    for m, rs in sorted(by_model.items()):
        c = lambda o: sum(1 for r in rs if r.get("outcome") == o)
        durs = sorted(r.get("duration_secs", 0) for r in rs)
        tok = sum(r.get("tokens_in", 0) + r.get("tokens_out", 0) for r in rs)
        print(f"{m[:42]:42} {len(rs):>4} {c('ok'):>4} {c('wrote_nothing'):>4} {c('timeout'):>4} "
              f"{c('error'):>4} {c('syntax_errors'):>4} {durs[len(durs) // 2]:>6.0f} {tok:>10,}")
    if args.fails:
        print()
        for r in runs[-20:]:
            print(f"{r['ts']} {r.get('project')}/{r.get('task')} {r.get('outcome')} {r.get('model')}")
    return EXIT_OK


# ── main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("server", help="manage the shared opencode server")
    s.add_argument("action", choices=["start", "stop", "status"])
    sub.add_parser("models", help="list models offered by the server")
    i = sub.add_parser("init", help="write a default-deny opencode.json")
    i.add_argument("repo")
    i.add_argument("--allow", action="append", metavar="PATTERN",
                   help='extra bash allow pattern, e.g. "pnpm check" or "pnpm test:unit*" (repeatable)')
    i.add_argument("--model", help="also pin this model in the project config")
    r = sub.add_parser("run", help="delegate one task")
    r.add_argument("--repo", required=True)
    r.add_argument("--task", required=True, help="slug; names the worktree and branch opencode/<task>")
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt")
    g.add_argument("--prompt-file")
    r.add_argument("--model")
    r.add_argument("--variant", help="reasoning effort variant, e.g. high")
    r.add_argument("--timeout", type=int, default=900, help="seconds (default 900; free models queue)")
    r.add_argument("--base", help="git ref for a NEW worktree (default HEAD of the main checkout)")
    r.add_argument("--setup", help="shell command run by this script (not OpenCode) in a NEW worktree, "
                                   "e.g. 'pnpm install --frozen-lockfile --offline'")
    r.add_argument("--unsafe-policy", action="store_true", help="delegate even if the policy check fails")
    for name in ("diff", "remove"):
        p = sub.add_parser(name)
        p.add_argument("--repo", required=True)
        p.add_argument("--task", required=True)
        if name == "remove":
            p.add_argument("--delete-branch", action="store_true")
            p.add_argument("--force", action="store_true")
    l = sub.add_parser("list")
    l.add_argument("--repo")
    rp = sub.add_parser("report")
    rp.add_argument("--since", type=int)
    rp.add_argument("--project")
    rp.add_argument("--fails", action="store_true")
    args = ap.parse_args()

    if args.cmd == "server":
        {"start": server_start, "stop": server_stop, "status": server_status}[args.action]()
        return EXIT_OK
    if args.cmd == "models":
        state = server_start(quiet=True)
        for mid, free, ctx, tools in sorted(list_models(state), key=lambda m: (not m[1], m[0])):
            print(f"{mid:50} {'FREE' if free else '    '} ctx={ctx} tools={tools}")
        return EXIT_OK
    return {"init": cmd_init, "run": cmd_run, "diff": cmd_diff, "list": cmd_list,
            "remove": cmd_remove, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
