/**
 * darwin extension for pi.
 *
 * 1. Routes the built-in tools (read, write, edit, bash) into the session's sandbox container
 *    with `docker exec`: pi itself runs on the host, the agent's commands never do.
 * 2. Adds the darwin tools, thin forwarders to the orchestrator's local API, where all the
 *    logic lives: perft_check, submit, experiments, run_job, lichess_losses.
 *
 * Configuration comes from the environment set by the orchestrator: DARWIN_SANDBOX,
 * DARWIN_DOCKER, DARWIN_TOOLS_URL, DARWIN_TOOLS_TOKEN.
 */

import { spawn } from "node:child_process";
import {
	type BashOperations,
	createBashToolDefinition,
	createEditToolDefinition,
	createReadToolDefinition,
	createWriteToolDefinition,
	type EditOperations,
	type ExtensionAPI,
	type ReadOperations,
	type WriteOperations,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const WORKDIR = "/genome";
const DEFAULT_BASH_TIMEOUT_S = 600;

function env(name: string): string {
	const value = process.env[name];
	if (!value) throw new Error(`${name} is not set`);
	return value;
}

const sandbox = env("DARWIN_SANDBOX");
const dockerBin = process.env.DARWIN_DOCKER ?? "docker";
const toolsUrl = env("DARWIN_TOOLS_URL");
const toolsToken = env("DARWIN_TOOLS_TOKEN");

// pi resolves relative paths against its own working folder on the host, an empty folder
// the agent never sees: map it onto the sandbox's /genome.
const hostCwd = process.cwd();
function inside(path: string): string {
	if (path === hostCwd) return WORKDIR;
	if (path.startsWith(`${hostCwd}/`)) return WORKDIR + path.slice(hostCwd.length);
	return path;
}

/** Runs `sh -c script` in the sandbox with positional args, never interpolated. */
function inSandbox(script: string, args: string[], input?: Buffer): Promise<Buffer> {
	return new Promise((resolve, reject) => {
		const child = spawn(dockerBin, ["exec", "-i", sandbox, "sh", "-c", script, "sh", ...args], {
			stdio: ["pipe", "pipe", "pipe"],
		});
		const out: Buffer[] = [];
		const err: Buffer[] = [];
		child.stdout.on("data", (d: Buffer) => out.push(d));
		child.stderr.on("data", (d: Buffer) => err.push(d));
		child.on("error", reject);
		child.on("close", (code) => {
			if (code === 0) resolve(Buffer.concat(out));
			else reject(new Error(Buffer.concat(err).toString().trim() || `exit ${code}`));
		});
		child.stdin.end(input ?? Buffer.alloc(0));
	});
}

const readOps: ReadOperations = {
	readFile: (p) => inSandbox('cat -- "$1"', [inside(p)]),
	access: (p) => inSandbox('test -r "$1"', [inside(p)]).then(() => undefined),
	detectImageMimeType: async () => null,
};

const writeOps: WriteOperations = {
	writeFile: (p, content) =>
		inSandbox('mkdir -p "$(dirname "$1")" && cat > "$1"', [inside(p)], Buffer.from(content)).then(
			() => undefined,
		),
	mkdir: (dir) => inSandbox('mkdir -p "$1"', [inside(dir)]).then(() => undefined),
};

const editOps: EditOperations = {
	readFile: readOps.readFile,
	writeFile: writeOps.writeFile,
	access: (p) => inSandbox('test -r "$1" && test -w "$1"', [inside(p)]).then(() => undefined),
};

const bashOps: BashOperations = {
	exec: (command, cwd, { onData, signal, timeout }) =>
		new Promise((resolve, reject) => {
			// The time limit is enforced inside the container: killing the docker client
			// alone would leave the command running there.
			const limit = String(Math.ceil(timeout ?? DEFAULT_BASH_TIMEOUT_S));
			const script = 'cd "$1" && exec timeout -s KILL "$2" bash -c "$3"';
			const child = spawn(dockerBin, ["exec", sandbox, "sh", "-c", script, "sh", inside(cwd), limit, command], {
				stdio: ["ignore", "pipe", "pipe"],
			});
			child.stdout.on("data", onData);
			child.stderr.on("data", onData);
			const onAbort = () => child.kill();
			signal?.addEventListener("abort", onAbort, { once: true });
			child.on("error", reject);
			child.on("close", (code) => {
				signal?.removeEventListener("abort", onAbort);
				if (signal?.aborted) reject(new Error("aborted"));
				else if (code === 137) reject(new Error(`timeout:${limit}`));
				else resolve({ exitCode: code });
			});
		}),
};

async function callOrchestrator(tool: string, params: unknown, signal?: AbortSignal): Promise<string> {
	const response = await fetch(`${toolsUrl}/tools/${tool}`, {
		method: "POST",
		headers: { "content-type": "application/json", authorization: `Bearer ${toolsToken}` },
		body: JSON.stringify(params ?? {}),
		signal,
	});
	const body = (await response.json()) as { text?: string; detail?: string };
	if (!response.ok) throw new Error(body.detail ?? `orchestrator answered ${response.status}`);
	return body.text ?? "";
}

function forwarder(name: string, label: string, description: string, parameters: ReturnType<typeof Type.Object>) {
	return {
		name,
		label,
		description,
		parameters,
		async execute(_id: string, params: unknown, signal?: AbortSignal) {
			const text = await callOrchestrator(name, params, signal);
			return { content: [{ type: "text" as const, text }], details: {} };
		},
	};
}

export default function (pi: ExtensionAPI) {
	pi.registerTool(createReadToolDefinition(WORKDIR, { operations: readOps }));
	pi.registerTool(createWriteToolDefinition(WORKDIR, { operations: writeOps }));
	pi.registerTool(createEditToolDefinition(WORKDIR, { operations: editOps }));
	pi.registerTool(createBashToolDefinition(WORKDIR, { operations: bashOps }));

	pi.registerTool(
		forwarder(
			"perft_check",
			"Perft check",
			"Ask the referee to verify your move generator. Build first (cargo build --release): it tests target/release/genome. Without fen: random positions, reports the first wrong move. With fen: that position only, at the given depth.",
			Type.Object({
				depth: Type.Optional(Type.Integer({ minimum: 1, maximum: 4, description: "Default 3" })),
				fen: Type.Optional(Type.String({ description: "Debug one position" })),
			}),
		),
	);
	pi.registerTool(
		forwarder(
			"submit",
			"Submit",
			"Commit the working tree as your candidate and hand it to the referee. Ends this session: stop working after it returns.",
			Type.Object({
				hypothesis: Type.String({ description: "What you changed and the effect you expect, one or two sentences" }),
				lesson_for_previous: Type.Optional(
					Type.String({ description: "One-line lesson from the previous experiment's verdict, if you were given one" }),
				),
			}),
		),
	);
	pi.registerTool(
		forwarder(
			"experiments",
			"Experiments",
			"Search past experiments: hypothesis, verdict, gate details, lesson. Without query: the most recent ones.",
			Type.Object({
				query: Type.Optional(Type.String()),
				limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 30 })),
			}),
		),
	);
	pi.registerTool(
		forwarder(
			"run_job",
			"Run job",
			"Start a long CPU-only job (self-play, training) on a snapshot of the working tree, or read the status of jobs. Output files go to /job/out and become readable at /jobs/<id>/out in later sessions.",
			Type.Object({
				action: Type.Union([Type.Literal("start"), Type.Literal("status")]),
				command: Type.Optional(Type.String({ description: "Shell command run in /job/src (start only)" })),
				hours: Type.Optional(Type.Number({ minimum: 0.1, maximum: 12 })),
			}),
		),
	);
	pi.registerTool(
		forwarder(
			"lichess_losses",
			"Lichess losses",
			"Read recent games the champion lost on Lichess, each with the move where Stockfish saw the evaluation drop the most. It points at the mistake, not at the fix.",
			Type.Object({
				limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 10, description: "Default 5" })),
			}),
		),
	);

	pi.on("before_agent_start", async (event) => ({
		systemPrompt: event.systemPrompt.replace(/Current working directory: .*/, `Current working directory: ${WORKDIR}`),
	}));
}
