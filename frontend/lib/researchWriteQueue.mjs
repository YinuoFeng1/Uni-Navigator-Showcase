// Keep failed writes and their original IDs/timestamps until acknowledgement.
export class ResearchWriteQueue {
  constructor({ storage, send, onChange = () => {} }) {
    this.storage = storage;
    this.send = send;
    this.onChange = onChange;
    this.key = "uni-navigator-pending-writes-v1";
    this.items = JSON.parse(storage.getItem(this.key) || "[]");
    this.running = null;
    this.failed = false;
  }

  persist() {
    try {
      this.storage.setItem(this.key, JSON.stringify(this.items));
    } catch (error) {
      this.failed = true;
      throw error;
    } finally {
      this.onChange(this.items.length, this.failed);
    }
  }

  async enqueue(item) {
    if (!this.items.some((pending) => pending.payload.requestId === item.payload.requestId)) {
      this.items.push(item);
      this.persist();
    }
    await this.flush();
    if (this.items.length && !this.failed) await this.flush();
    if (this.items.some((pending) => pending.payload.requestId === item.payload.requestId)) {
      throw new Error("Research activity not saved. Retry the pending writes.");
    }
  }

  flush() {
    if (this.running) return this.running;
    this.running = this.drain().finally(() => { this.running = null; });
    return this.running;
  }

  async drain() {
    this.failed = false;
    this.persist();
    while (this.items.length) {
      try {
        await this.send(this.items[0]);
      } catch {
        this.failed = true;
        this.persist();
        return;
      }
      this.items.shift();
      this.persist();
    }
  }
}
