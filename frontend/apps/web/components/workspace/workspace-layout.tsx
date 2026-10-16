"use client";

import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Sidebar } from "./sidebar";
import { LatexEditor } from "./editor/latex-editor";
import { PdfPreview } from "./preview/pdf-preview";
import { useProjectInit } from "@/hooks/use-project-init";
import { useDocumentStore } from "@/stores/document-store";
import Link from "next/link";
import "@/styles/workspace.css";

function LeafMark({ stroke = "currentColor" }: { stroke?: string }) {
  return (
    <svg className="ws-leaf" viewBox="-3 0 27 36" aria-hidden="true">
      <path
        d="M9 33.5V13"
        stroke={stroke}
        strokeWidth="4.6"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M9 14C8.5 6 14.5 1 23 1.2 23.2 9.5 17.5 15 9 14Z"
        fill="#2e7d5b"
      />
      <path
        d="M9.6 13.4L20.5 3.4"
        stroke="#f2f4f0"
        strokeWidth="1.2"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M9 21.5C11 17.8 15.5 17.2 19.8 18.2 18.8 22 14 23.6 9 21.5Z"
        fill="#2e7d5b"
      />
      <path
        d="M9 21.5C7 17.8 2.5 17.2-1.8 18.2-.8 22 4 23.6 9 21.5Z"
        fill="#2e7d5b"
      />
    </svg>
  );
}

export function WorkspaceLayout() {
  useProjectInit();
  const initialized = useDocumentStore((s) => s.initialized);

  return (
    <div className="bl-ws flex h-full flex-col">
      <header className="ws-top">
        <Link href="/" className="ws-brand" aria-label="Betterleaf home">
          <span className="ws-brand">
            Betterlea
            <LeafMark />
          </span>
        </Link>
        <span className="ws-sub">LaTeX resume workspace</span>
      </header>

      {!initialized ? (
        <div className="flex h-full items-center justify-center">
          <div style={{ color: "var(--muted)" }}>Loading…</div>
        </div>
      ) : (
        <PanelGroup direction="horizontal" className="min-h-0 flex-1">
          <Panel defaultSize={15} minSize={10} maxSize={25}>
            <Sidebar />
          </Panel>

          <PanelResizeHandle className="resize-handle" />

          <Panel defaultSize={42.5} minSize={25}>
            <LatexEditor />
          </Panel>

          <PanelResizeHandle className="resize-handle" />

          <Panel defaultSize={42.5} minSize={25}>
            <PdfPreview />
          </Panel>
        </PanelGroup>
      )}
    </div>
  );
}
