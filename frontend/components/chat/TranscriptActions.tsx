"use client";

import { Download, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ChatMessage } from "@/lib/types";

type TranscriptActionsProps = {
  messages: ChatMessage[];
  onClear: () => void;
  onDownload: () => void;
};

export function TranscriptActions({ messages, onClear, onDownload }: TranscriptActionsProps) {
  function downloadTranscript() {
    const text = messages
      .map((message) => `${message.role.toUpperCase()}: ${message.content}`)
      .join("\n\n");
    const blob = new Blob([text || "No messages yet."], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "uni-navigator-transcript.txt";
    anchor.click();
    onDownload();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Button type="button" variant="secondary" size="sm" onClick={onClear}>
        <Trash2 size={16} aria-hidden="true" />
        Clear conversation
      </Button>
      <Button type="button" variant="ghost" size="sm" onClick={downloadTranscript}>
        <Download size={16} aria-hidden="true" />
        Download transcript
      </Button>
    </div>
  );
}
