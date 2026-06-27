import type { Database } from '@nozbe/watermelondb'
import type { ApiClient } from '../api/client'
import { applyPull, seedPricing } from './pull'
import { executePush } from './push'

export interface SyncResult {
  pullSeq: number
  pushSeq: number
  reassignedCodes: Record<string, string>
}

/**
 * Full sync cycle: pull server changes then push local changes.
 * Safe to call repeatedly — no-ops when nothing is pending.
 */
export async function syncNow(
  db: Database,
  api: ApiClient,
  deviceId: string,
): Promise<SyncResult> {
  const pullSeq = await applyPull(db, api)
  const { server_seq: pushSeq, reassigned_codes } = await executePush(db, api, deviceId)
  return { pullSeq, pushSeq, reassignedCodes: reassigned_codes }
}

export { seedPricing }
