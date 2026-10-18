export type QueuedWrite = {
  kind: "log-event" | "evidence-use" | "feedback";
  payload: Record<string, unknown> & { requestId: string; timestamp: string };
};
export class ResearchWriteQueue {
  constructor(options: { storage: Storage; send: (item: QueuedWrite) => Promise<unknown>; onChange: (pending: number, failed: boolean) => void });
  items: QueuedWrite[];
  enqueue(item: QueuedWrite): Promise<void>;
  flush(): Promise<void>;
}
