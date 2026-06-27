import type { EscPosPrinter, PrintJob } from './interface'

export class FakePrinter implements EscPosPrinter {
  readonly jobs: PrintJob[] = []
  private _ready: boolean

  constructor(ready = true) {
    this._ready = ready
  }

  async isReady(): Promise<boolean> {
    return this._ready
  }

  async print(job: PrintJob): Promise<void> {
    if (!this._ready) throw new Error('Printer not ready')
    this.jobs.push(job)
  }

  clear(): void {
    this.jobs.length = 0
  }
}
