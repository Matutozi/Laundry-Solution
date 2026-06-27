export interface PrintJob {
  pickupCode: string
  customerName: string
  lines: Array<{ serviceName: string; pieceCount: number; lineTotalKobo: number }>
  totalKobo: number
  paidKobo: number
  outstandingKobo: number
  staffName: string
  printedAt: string
}

export interface EscPosPrinter {
  /** Returns true when a Bluetooth printer is paired and reachable. */
  isReady(): Promise<boolean>
  /** Print a receipt. Resolves when the printer confirms receipt. */
  print(job: PrintJob): Promise<void>
}

export function formatReceiptText(job: PrintJob): string {
  const naira = (k: number) => `₦${(k / 100).toLocaleString('en-NG', { minimumFractionDigits: 2 })}`
  const lines = [
    '==============================',
    '        WISE-WASH',
    '==============================',
    `Code: ${job.pickupCode}`,
    `Customer: ${job.customerName}`,
    `Date: ${job.printedAt}`,
    '------------------------------',
    ...job.lines.map(
      l => `${l.serviceName} x${l.pieceCount}`.padEnd(20) + naira(l.lineTotalKobo).padStart(10),
    ),
    '------------------------------',
    'Total:'.padEnd(20) + naira(job.totalKobo).padStart(10),
    'Paid:'.padEnd(20) + naira(job.paidKobo).padStart(10),
    'Balance:'.padEnd(20) + naira(job.outstandingKobo).padStart(10),
    '------------------------------',
    `Staff: ${job.staffName}`,
    '==============================',
  ]
  return lines.join('\n')
}
