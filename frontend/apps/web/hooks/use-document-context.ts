"use client";

import { useEffect } from "react";
import { useAui } from "@assistant-ui/store";
import { useDocumentStore } from "@/stores/document-store";

export function useDocumentContext() {
  const aui = useAui();
  const files = useDocumentStore((s) => s.files);
  const activeFileId = useDocumentStore((s) => s.activeFileId);
  const selectionRange = useDocumentStore((s) => s.selectionRange);

  const activeFile = files.find((f) => f.id === activeFileId);
  const fileName = activeFile?.name ?? "document.tex";
  const content = activeFile?.content ?? "";

  const hasSelection = selectionRange !== null;
  const selectedText = hasSelection
    ? content.slice(selectionRange.start, selectionRange.end)
    : null;

  useEffect(() => {
    const selectionInfo = hasSelection
      ? `The user has selected the following text:\n\`\`\`\n${selectedText}\n\`\`\`\nYou can use the replace_selection tool to replace this text.`
      : "The user has NOT selected any text. Do NOT use the replace_selection tool.";

    return aui.modelContext().register({
      getModelContext: () => ({
        system: `The user is currently editing a LaTeX document named "${fileName}".

Here is the current content of the document:
\`\`\`latex
${content}
\`\`\`

${selectionInfo}

When helping the user, reference this document and provide relevant suggestions.`,
      }),
    });
  }, [aui, fileName, content, hasSelection, selectedText]);
}
