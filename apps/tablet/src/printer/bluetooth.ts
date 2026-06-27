/**
 * Real ESC-POS Bluetooth printer.
 *
 * Wire up a library such as:
 *   - react-native-bluetooth-escpos-printer
 *   - react-native-thermal-receipt-printer-image-qr
 *
 * Both require a native module and therefore need the Expo dev-client build.
 * Install the chosen library, import it here, and implement the two methods.
 */
import type { EscPosPrinter, PrintJob } from './interface'
import { formatReceiptText } from './interface'

export class BluetoothPrinter implements EscPosPrinter {
  async isReady(): Promise<boolean> {
    // TODO: check Bluetooth state and paired device list
    throw new Error('BluetoothPrinter.isReady() not implemented — needs native module')
  }

  async print(job: PrintJob): Promise<void> {
    const text = formatReceiptText(job)
    // TODO: write `text` to the Bluetooth ESC/POS printer
    void text
    throw new Error('BluetoothPrinter.print() not implemented — needs native module')
  }
}
