import React, { useState } from 'react'
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'
import { Q } from '@nozbe/watermelondb'
import { formatNaira } from '@wise-wash/shared'
import { getDatabase } from '../db'
import { OrderModel } from '../db/models/OrderModel'
import { OrderLineModel } from '../db/models/OrderLineModel'
import { ServiceModel } from '../db/models/ServiceModel'
import { getTotalPaidKobo } from '../services/payments'
import { updateOrderStatusLocally } from '../services/orders'

interface LineDetail {
  serviceName: string
  pieceCount: number
  lineTotalKobo: number
}

interface OrderDetail {
  order: OrderModel
  lines: LineDetail[]
  paidKobo: number
}

export function PickupReleaseScreen() {
  const [code, setCode] = useState('')
  const [detail, setDetail] = useState<OrderDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [releasing, setReleasing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [released, setReleased] = useState(false)

  async function handleLookup() {
    setError(null)
    setDetail(null)
    setReleased(false)
    setLoading(true)
    try {
      const db = getDatabase()
      const orders = await db
        .get<OrderModel>('orders')
        .query(Q.where('pickup_code', code.trim().toUpperCase()))
        .fetch()
      const order = orders[0]
      if (!order) { setError('No order found for that code'); return }
      if (order.status === 'picked_up' || order.status === 'delivered') {
        setError('This order has already been picked up')
        return
      }

      const orderLines = await db
        .get<OrderLineModel>('order_lines')
        .query(Q.where('order_id', order.id))
        .fetch()

      const lineDetails: LineDetail[] = await Promise.all(
        orderLines.map(async l => {
          const svc = await db.get<ServiceModel>('services').find(l.serviceId).catch(() => null)
          return {
            serviceName: svc?.name ?? l.serviceId,
            pieceCount: l.pieceCount,
            lineTotalKobo: l.lineTotalKobo,
          }
        }),
      )

      const paidKobo = await getTotalPaidKobo(db, order.id)
      setDetail({ order, lines: lineDetails, paidKobo })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lookup failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleRelease() {
    if (!detail) return
    setReleasing(true)
    try {
      const db = getDatabase()
      await updateOrderStatusLocally(db, detail.order, 'picked_up')
      setReleased(true)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Release failed')
    } finally {
      setReleasing(false)
    }
  }

  return (
    <View style={s.container}>
      <Text style={s.title}>Pickup Release</Text>

      <View style={s.searchRow}>
        <TextInput
          style={s.codeInput}
          placeholder="Pickup code"
          autoCapitalize="characters"
          value={code}
          onChangeText={setCode}
        />
        <TouchableOpacity style={s.searchBtn} onPress={handleLookup} disabled={loading}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>Look up</Text>}
        </TouchableOpacity>
      </View>

      {error && <Text style={s.error}>{error}</Text>}

      {released && (
        <View style={s.successBanner}>
          <Text style={s.successText}>Released — order marked as picked up</Text>
        </View>
      )}

      {detail && !released && (
        <View style={s.card}>
          <Text style={s.cardTitle}>Code: {detail.order.pickupCode}</Text>
          <Text style={s.label}>Status: {detail.order.status}</Text>
          {detail.lines.map((l, i) => (
            <View key={i} style={s.lineRow}>
              <Text style={s.lineName}>{l.serviceName} ×{l.pieceCount}</Text>
              <Text>{formatNaira(l.lineTotalKobo)}</Text>
            </View>
          ))}
          <View style={s.divider} />
          <View style={s.lineRow}>
            <Text style={s.bold}>Total</Text>
            <Text style={s.bold}>{formatNaira(detail.order.totalKobo)}</Text>
          </View>
          <View style={s.lineRow}>
            <Text>Paid</Text>
            <Text>{formatNaira(detail.paidKobo)}</Text>
          </View>
          <View style={s.lineRow}>
            <Text style={detail.order.totalKobo - detail.paidKobo > 0 ? s.red : {}}>
              Outstanding
            </Text>
            <Text style={detail.order.totalKobo - detail.paidKobo > 0 ? s.red : {}}>
              {formatNaira(detail.order.totalKobo - detail.paidKobo)}
            </Text>
          </View>

          {detail.order.status === 'ready' ? (
            <TouchableOpacity style={s.releaseBtn} onPress={handleRelease} disabled={releasing}>
              {releasing
                ? <ActivityIndicator color="#fff" />
                : <Text style={s.btnText}>Release to Customer</Text>}
            </TouchableOpacity>
          ) : (
            <Text style={s.notReady}>Order is {detail.order.status} — not ready for pickup</Text>
          )}
        </View>
      )}
    </View>
  )
}

const s = StyleSheet.create({
  container: { flex: 1, padding: 24 },
  title: { fontSize: 24, fontWeight: '700', marginBottom: 20 },
  searchRow: { flexDirection: 'row', gap: 12, marginBottom: 16 },
  codeInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    padding: 12,
    fontSize: 20,
    letterSpacing: 2,
  },
  searchBtn: {
    backgroundColor: '#1a56db',
    padding: 12,
    borderRadius: 8,
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  error: { color: 'red', marginBottom: 12 },
  successBanner: { backgroundColor: '#d1fae5', padding: 16, borderRadius: 8 },
  successText: { color: '#065f46', fontWeight: '700', fontSize: 16 },
  card: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 16,
    marginTop: 8,
  },
  cardTitle: { fontSize: 22, fontWeight: '700', marginBottom: 12 },
  label: { color: '#555', marginBottom: 8 },
  lineRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },
  lineName: { flex: 1 },
  divider: { height: 1, backgroundColor: '#ddd', marginVertical: 8 },
  bold: { fontWeight: '700' },
  red: { color: '#c00', fontWeight: '700' },
  releaseBtn: {
    backgroundColor: '#059669',
    padding: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 16,
  },
  notReady: { color: '#888', marginTop: 12, fontStyle: 'italic' },
})
