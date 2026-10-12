# Django-Owned AI Chat + Document Tools

## Context

The frontend (`frontend/apps/web`) currently runs chat and AI document-editing through a Next.js BFF route (`frontend/apps/web/app/api/chat/route.ts`) that calls DeepSeek directly, while the three document-editing "tools" (`insert_latex`, `replace_selection`, `find_and_replace`) execute entirely client-side in `frontend/apps/web/components/workspace/editor/latex-tools.tsx` against a browser-local zustand store backed by IndexedDB. The goal is full backend ownership: Django exposes a DRF chat endpoint that talks to DeepSeek, owns the tool definitions and executes them, and tracks AI-edited document state in the existing `Resume` model; the frontend becomes display-only. All user-created files are already modeled as `Resume` rows attached to a `Workspace` (one workspace → many resumes), so no new document model is needed.

## Approach

### Step 1 — Add `httpx` dependency

Edit `pyproject.toml` `[project] dependencies` list; append `"httpx==<latest>"`. No HTTP streaming client exists in the dependency set (confirmed: `uv.lock` and `pyproject.toml` contain no `httpx`/`openai`/`requests`). `httpx` is required for DeepSeek's streaming OpenAI-compatible `/chat/completions` endpoint (Django's test client and `urllib` do not provide incremental SSE reads).

### Step 2 — Add DeepSeek settings to `config/settings/base.py`

Append, after the `REST_FRAMEWORK` block, three settings read from env with defaults:

```python
DEEPSEEK_API_KEY = env("DEEPSEEK_API_KEY", default="")
DEEPSEEK_MODEL = env("DEEPSEEK_MODEL", default="deepseek-v4-pro")
DEEPSEEK_BASE_URL = env("DEEPSEEK_BASE_URL", default="https://api.deepseek.com")
```

Also add `DEEPSEEK_API_URL = DEEPSEEK_BASE_URL.rstrip("/") + "/chat/completions"` so the endpoint is derived once. No other config change; CORS is already open on `/api/` (`CORS_URLS_REGEX = r"^/api/.*$"`).

### Step 3 — Create `betterleaf/chat` app

Create files (no equivalent app exists; `betterleaf/resumes` handles resumes/compilation only):

- `betterleaf/chat/__init__.py` — empty.
- `betterleaf/chat/apps.py` — `class ChatConfig(AppConfig): name = "betterleaf.chat"`, mirroring `betterleaf/resumes/apps.py` `ResumesConfig`.
- `betterleaf/chat/migrations/__init__.py` — empty (no models in this app; chat is stateless, state lives on `Resume`).
- `betterleaf/chat/urls.py` — `app_name = "chat"`; `urlpatterns = [path("", ChatStreamView.as_view(), name="chat-stream")]`.

Add `"betterleaf.chat"` to `LOCAL_APPS` in `config/settings/base.py` (currently `["betterleaf.contrib.sites", "betterleaf.users", "betterleaf.resumes"]` region — read exact list and append).

### Step 4 — Define tool schemas and executors in `betterleaf/chat/tools.py`

Create the canonical tool definitions (JSON-schema, OpenAI function-calling format) and the Django-side executors that mutate `Resume.main_tex`. Replace the client-side definition in `latex-tools.tsx` (deleted in Step 9).

Tool list, exact names/params matching current client behavior:

```python
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "insert_latex",
            "description": "Insert LaTeX code at the current cursor position in the document",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "The LaTeX code to insert at the cursor position"}},
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replace_selection",
            "description": "Replace the currently selected text in the document with LaTeX code",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "The LaTeX code to replace the selection with"}},
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_and_replace",
            "description": "Find and replace text in the document. Use this to modify existing content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "find": {"type": "string", "description": "The exact text to find in the document"},
                    "replace": {"type": "string", "description": "The text to replace it with"},
                },
                "required": ["find", "replace"],
            },
        },
    },
]
```

Executor interface — one function per tool, each takes the `Resume` and a dict of resolved args plus the cursor/selection context, mutates `resume.main_tex` and `resume.save(update_fields=["main_tex", "updated_at"])`, and returns a result dict:

```python
def insert_latex(resume, args, cursor) -> dict: ...
def replace_selection(resume, args, cursor, selection) -> dict: ...
def find_and_replace(resume, args) -> dict: ...
```

Behavioral contracts (must match current frontend semantics exactly):
- `insert_latex`: splice `args["code"]` into `main_tex` at byte offset `cursor`. If `cursor` is None, append to end. Return `{"success": True, "message": "Code inserted at cursor position"}`.
- `replace_selection`: if `selection` is None, return `{"success": False, "error": "No text is currently selected in the editor"}` WITHOUT mutating. Else replace `main_tex[selection["start"]:selection["end"]]` with `args["code"]`. Return `{"success": True, "message": "Selection replaced with code"}`.
- `find_and_replace`: `replaced = main_tex.replace(args["find"], args["replace"])`. If `replaced == main_tex` (no occurrence), return `{"success": False, "error": f'Could not find "{args["find"]}" in the document'}` WITHOUT saving. Else set and return `{"success": True, "message": f'Replaced "{args["find"]}" with "{args["replace"]}"'}`.

Result dict is returned as the tool-call `output` (JSON string) in the next round-trip to DeepSeek (Step 6).

### Step 5 — Serializer in `betterleaf/chat/serializers.py`

Create `ChatRequestSerializer(serializers.Serializer)` validating the incoming POST body with these fields and validation rules (mirrors the shape the `assistant-ui` transport sends, confirmed from `@assistant-ui/react-ai-sdk` + `ai` `DefaultChatTransport` source):

- `id = serializers.CharField(required=False, allow_blank=True)`
- `messages = serializers.ListField(child=serializers.DictField(), required=False, default=list)`
- `system = serializers.CharField(required=False, allow_blank=True, default="")`
- `tools = serializers.DictField(required=False, default=dict)`
- `resume_id = serializers.UUIDField(required=False)` — NEW, lets client name the target resume.
- `cursor = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=0)` — NEW, byte offset for insert_latex.
- `selection = serializers.DictField(required=False, allow_null=True, default=None)` — NEW, `{"start": int, "end": int}` for replace_selection.

The three NEW fields are the load-bearing addition: client must send cursor/selection because these live in the editor (CodeMirror), not the DB. Validate `selection`, if present, has int `start` and `end` keys with `end >= start`.

### Step 6 — Chat view + DeepSeek client + orchestration

Create `betterleaf/chat/deepseek.py` with the DeepSeek streaming call and SSE→UI-message-stream translation, and `betterleaf/chat/views.py` with the DRF view and tool loop.

**`deepseek.py` — `stream_chat(messages, system, tools) -> async iterator of dict chunks`:**

- Build OpenAI-format request body: `{"model": settings.DEEPSEEK_MODEL, "messages": messages, "stream": True, "tools": TOOL_SCHEMAS if tools else (omit)}`.
- `POST settings.DEEPSEEK_API_URL` with `Authorization: Bearer {settings.DEEPSEEK_API_KEY}`, `Content-Type: application/json`, using `httpx.AsyncClient.stream("POST", ...)`.
- Iterate `response.aiter_lines()`; DeepSeek emits `data: {json}` lines and a final `data: [DONE]`. For each line with `data:` and not `[DONE]`, `json.loads`, read `choices[0].delta` and `choices[0].finish_reason`.
- Accumulate `delta.content` into the current text part; accumulate `delta.tool_calls` (indexed) `function.name` + `function.arguments` fragments.
- Yield UI-message-stream chunks (the exact schema the browser's `uiMessageChunkSchema` validates — confirmed from `ai` SDK source `frontend/node_modules/ai/dist/index.js` lines ~4725+):

  - On first content: `{"type": "start", "messageId": "<uuid>"}` then `{"type": "text-start", "id": "<uuid>"}`.
  - Each text token: `{"type": "text-delta", "id": "<same-text-id>", "delta": "<token>"}`.
  - When content ends but tool_calls began: `{"type": "text-end", "id": "<text-id>"}` then per tool call: `{"type": "tool-input-start", "toolCallId": "<call-id>", "toolName": "<name>"}`, stream `{"type": "tool-input-delta", "toolCallId": "<call-id>", "inputTextDelta": "<args-fragment>"}` as args arrive, and on arguments complete emit `{"type": "tool-input-available", "toolCallId": "<call-id>", "toolName": "<name>", "input": <parsed json args>}`.
  - `finish_reason` `"tool_calls"` → end with `{"type": "finish", "finishReason": "tool-calls"}`.
  - `finish_reason` `"stop"` → `{"type": "text-end", "id": "<text-id>"}` (if not yet) then `{"type": "finish", "finishReason": "stop"}`.

**`views.py` — `ChatStreamView(APIView)`:**

```python
class ChatStreamView(APIView):
    permission_classes = [AllowAny]
    def post(self, request): ...
```

Flow inside `post`:
1. `s = ChatRequestSerializer(data=request.data); s.is_valid(raise_exception=True)`.
2. Resolve resume: if `resume_id` supplied, `Resume.objects.filter(id=resume_id, workspace__user=request.user if auth else ...).get()` — actually resolve via `get_workspace(request)` from `betterleaf.resumes.auth` then `.resumes.filter(id=resume_id).get()`; if no `resume_id`, pick the workspace's most recently updated `Resume` (`workspace.resumes.order_by("-updated_at").first()`). If none exist, return DRF `Response({"error": "No resume available"}, status=400)`.
3. Reuse `use-document-context` semantics: if `system` is empty, build it from the resume — `f'You are editing a LaTeX document named "{resume.title}".

Here is the current content of the document:

```latex
{resume.main_tex}
```'`. (SYSTEM_PROMPT moved to a module constant `SYSTEM_PROMPT` in `deepseek.py`; prepend it to request `system`.)
4. Build DeepSeek `messages` from the request `messages` field directly (client already sends OpenAI-compatible message objects — pass through, no conversion).
5. Run the tool loop (replicate `streamText` + `stepCountIs(10)`):
   - `steps = 0`; loop:
     - Stream via `stream_chat(...)` yielding chunks; buffer tool-call dicts as they complete.
     - If tool calls present and `steps < 10`: for each tool call, resolve `args = input`, lookup executor in `tools.py`, call it with `(resume, args, cursor, selection)`, collect `{"tool_call_id": call_id, "tool_name": name, "output": json.dumps(result_dict)}`. Emit the tool-input chunks already streamed; then `steps += 1`; append assistant tool-call message + tool result messages to `messages`; continue loop.
     - Else (no tool calls, or `steps == 10`): break; final `finish` chunk already emitted.
   - When `steps` reaches 10 with remaining tool calls, stop calling tools and emit `{"type": "finish", "finishReason": "stop"}` (mirror `stepCountIs(10)` hard stop).
6. Return `StreamingHttpResponse(gen(), content_type="text/event-stream")` with headers `{"X-Vercel-AI-UI-Message-Stream": "v1", "Cache-Control": "no-cache", "Connection": "keep-alive"}` (the `x-vercel-ai-ui-message-stream: v1` header is what distinguishes UI message stream; the browser requires it).

**SSE encoding in the view** — the generator must emit, per chunk, exactly `f"data: {json.dumps(chunk)}\n\n"` (confirmed wire format from `JsonToSseTransformStream` in `ai` SDK: `data: ${JSON.stringify(part)}\n\n`).

Error handling: wrap DeepSeek call; on `httpx` transport error / non-200, yield one chunk `{"type": "error", "errorText": "<message>"}` and return. On `DEEPSEEK_API_KEY == ""`, return DRF `Response({"error": "DeepSeek not configured"}, status=503)` before streaming.

### Step 7 — Wire routes into `config/api_router.py`

Append to `urlpatterns` in `config/api_router.py`:

```python
path("chat/", include("betterleaf.chat.urls")),
```

(add `from django.urls import include` if not already imported — it currently imports only `path`). This yields endpoint `POST /api/chat/`.

### Step 8 — Frontend: repoint chat transport and send cursor/selection + resume_id

- `frontend/apps/web/app/provider.tsx`: replace `useChatRuntime({ sendAutomaticallyWhen: lastAssistantMessageIsCompleteWithToolCalls })` with a transport that targets Django and injects the per-message context. Import `DefaultChatTransport` from `ai` and construct:

  ```ts
  const transport = new DefaultChatTransport({
    api: process.env.NEXT_PUBLIC_CHAT_API_URL ?? "/api/chat",
    prepareSendMessagesRequest: async (opts) => ({
      ...opts,
      body: {
        ...opts.body,
        resume_id: useDocumentStore.getState().activeFileId, // map active file -> resume id (see note)
        cursor: useDocumentStore.getState().cursorPosition,
        selection: useDocumentStore.getState().selectionRange,
      },
    }),
  });
  useChatRuntime({ sendAutomaticallyWhen: lastAssistantMessageIsCompleteWithToolCalls, transport });
  ```

  Note: `activeFileId` is a browser-generated id, not a Django `Resume.id`. The id mapping must be reconciled — see Step 11. In this step, send `resume_id` only if `activeFileId` maps to a known Django resume; otherwise omit (server uses latest resume).

- `frontend/apps/web/hooks/use-document-context.ts`: DELETE this file and its import/render usage — Django now builds the system context server-side from `Resume.main_tex`. Remove any remaining reference (`<RemoveSystemContext/>` or equivalent) — locate by `grep "useDocumentContext" ` returning `use-document-context.ts` and `ai-drawer.tsx`/`thread.tsx` if imported; delete import + usages.

### Step 9 — Frontend: remove client-side tool runners

Delete `frontend/apps/web/components/workspace/editor/latex-tools.tsx`. It is rendered only in `frontend/apps/web/components/workspace/editor/latex-editor.tsx` (`import { LatexTools } from "./latex-tools"` and `<LatexTools />`); remove both the import and the JSX usage. The client no longer defines tools; Django sends `tool-input-available` and the assistant-ui runtime will handle it as a backend tool (no client `useAssistantTool` remains).

### Step 10 — Frontend: delete the Next.js chat BFF

Delete `frontend/apps/web/app/api/chat/route.ts`. This removes the hardcoded DeepSeek key `sk-e7f2be9a4bb8412dad9648e633ec11dd` (line 16) and the client-server call path. Also delete `frontend/apps/web/app/api/compile/route.ts` only if compile is also being moved to Django — it is NOT part of this plan's scope, so leave it and note the boundary inline (compile still routes Next.js → Python `/compile` 7030; migration of compile is out of scope for this plan).

### Step 11 — Reconcile editor file identity with `Resume`

The editor's `files`/`activeFileId` are client-generated random ids (`generateId()` in `document-store.ts`); Django `Resume.id` is a UUID. Load-bearing decision: introduce a stable mapping by storing the Django `Resume.id` on `ProjectFile`. Concretely, extend `ProjectFile` in `frontend/apps/web/stores/document-store.ts` with an optional field `resumeId?: string`. When the editor creates/persists a document, it calls `POST /api/resumes/` (existing `ResumeViewSet.create`) with `{"title": <file name>, "template": "jakes"}`; the returned `ResumeSerializer` data includes `id`; store it as `resumeId` on that file. On save, `PATCH /api/resumes/{resumeId}/` with `{"main_tex": <active file content>}` (existing `ResumeViewSet.partial_update`, `main_tex` is writable). This makes `resume_id` in Step 8 resolvable to a real row.

Autosave behavior: replace the IndexedDB-only persistence with a debounced `PATCH`. Keep IndexedDB as a cold cache only if desired, but Django is now source of truth. Minimum viable: `latex-editor.tsx` `setContent` handler (in `handleDocChange`/the CodeMirror update at line ~318 `setContent(update.state.doc.toString())`) additionally schedules a 800ms-debounced `PATCH /api/resumes/{resumeId}/` with the new text; on first load with no `resumeId`, POST to create the resume.

## Critical files & anchors

- `frontend/apps/web/app/api/chat/route.ts` — delete; source of the hardcoded key and the existing `streamText`/`toUIMessageStreamResponse` semantics to replicate.
- `frontend/apps/web/components/workspace/editor/latex-tools.tsx` — delete; source of the three tool names/params/result messages to mirror in `tools.py`.
- `betterleaf/resumes/models.py` — `Resume` (`main_tex`, `workspace` FK) is the document; no new model.
- `betterleaf/resumes/views.py` `ResumeViewSet` — reuse for `POST`/`PATCH`; `main_tex` already writable in `ResumeSerializer`.
- `config/api_router.py` + `config/settings/base.py` — route registration and env/defaults.
- `frontend/node_modules/ai/dist/index.js` `uiMessageChunkSchema` (~line 4725) and `JsonToSseTransformStream` (~line 4583) — authoritative wire schema and `data: {json}\n\n` framing (read-only reference).

## Verification

1. `cd /home/vishesh/betterleaf && python manage.py check` — no import/path errors after wiring `betterleaf.chat` into `LOCAL_APPS` and router.
2. End-to-end (manual, requires `DEEPSEEK_API_KEY` set and `npm run dev` for frontend + Django dev server):
   - Start Django (`python manage.py runserver`), ensure `redis`/Postgres per `docker-compose.local.yml`.
   - Open the web app in a browser, load a document, run `curl -N -X POST http://localhost:8000/api/chat/ -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"add a table to my resume"}],"resume_id":"<id>"}'` and observe a stream of `data: {"type":"text-start"...}` through `data: {"type":"finish"...}` lines; confirm no line violates the chunk schema (e.g. open the app and confirm text renders).
   - In the browser, send "insert \\textbf{hello} at the cursor" and confirm the text appears in the editor AND a `PATCH /api/resumes/{id}/` persists `main_tex` containing `\textbf{hello}` (verify via Django shell or re-GET).
4. Regression: existing resume tests still pass (`python manage.py test betterleaf.resumes`).

## Assumptions & contingencies

- **Auth model**: keep `AllowAny` on the chat endpoint and resolve workspace via `get_workspace` (`bl_session` cookie or session user), matching the rest of the anonymous workspace flow. If authenticated-only chat is later desired, swap `AllowAny` → `HasWorkspace` and add the `bl_session` cookie handling on the client (frontend must send credentials).
- **Frontend file→resume identity**: assume introducing `ProjectFile.resumeId` is acceptable. If the editor must stay purely local-first until explicit save, instead drop `resume_id` in chat requests and always operate on the workspace's latest `Resume` — the tool executors already fall back to latest-`Resume` when `resume_id` is absent.
- **Cursor/selection transport**: assume cursor is a byte offset into `main_tex`. If CodeMirror positions are UTF-16 offsets (not bytes), the `insert_latex`/`replace_selection` splice in `tools.py` must use them against a Python `str` (which indexes by codepoint) — pre-decide: index by codepoint, and only if browser sends UTF-16 units, convert by re-encoding the prefix.
- **DeepSeek tool-call format**: assume OpenAI-compatible `choices[0].delta.tool_calls` with `index`/`id`/`function.name`/`function.arguments` fragments. If DeepSeek instead returns `finish_reason` only with a separate non-streamed tool-call object, fall back to a second non-streaming call to collect `message.tool_calls` for that step (store a note; do not stall).
