"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import {
  AssistantChatTransport,
  useChatRuntime,
} from "@assistant-ui/react-ai-sdk";
import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";
import { Toaster } from "@/components/ui/sonner";
import { useKeyboardShortcuts } from "@/hooks/use-keyboard-shortcuts";
import { useDocumentStore } from "@/stores/document-store";

export function RootProvider({ children }: { children: ReactNode }) {
  const runtime = useChatRuntime({
    transport: new AssistantChatTransport({
      api: process.env.NEXT_PUBLIC_CHAT_API_URL ?? `${process.env.NEXT_PUBLIC_API_URL}/api/chat/`,
      credentials: "include",
      headers: () => {
        const match = document.cookie
          .split("; ")
          .find((c) => c.startsWith("csrftoken="));
        return { "X-CSRFToken": match?.slice("csrftoken=".length) ?? "" };
      },
      prepareSendMessagesRequest: async (opts) => {
        const state = useDocumentStore.getState();
        const activeFile = state.files.find((f) => f.id === state.activeFileId);
        return {
          ...opts,
          body: {
            ...opts.body,
            messages: opts.messages,
            resume_id: activeFile?.resumeId ?? undefined,
          },
        };
      },
    }),
  });

  useKeyboardShortcuts();

  return (
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
      <AssistantRuntimeProvider runtime={runtime}>
        {children}
        <Toaster />
      </AssistantRuntimeProvider>
    </ThemeProvider>
  );
}
