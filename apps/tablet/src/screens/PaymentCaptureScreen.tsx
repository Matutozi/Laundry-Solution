import React, { useEffect, useState } from 'react'
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'
import type { NativeStackScreenProps } from '@react-navigation/native-stack'
import { formatNaira } from '@wise-wash/shared'
import { getDatabase } from '../db'
import { OrderModel } from '../db/models/OrderModel'
import { recordPaymentLocally, getTotalPaidKobo, type PaymentMethod } from '../services/payments'
import type { RootStackParamList } from '../navigation'

type Props = NativeStackScreenProps<RootStackParamList, 'PaymentCapture'>

const METHODS: PaymentMethod[] = ['cash', 'transfer', 'pos']

function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

export function PaymentCaptureScreen({ route, navigation }: Props) {
  const { orderId, totalKobo } = route.params
  const [order, setOrder] = useState<OrderModel | null>(null)
  const [paidKobo, setPaidKobo] = useState(0)
  const [amountNaira, setAmountNaira] = useState('')
  const [method, setMethod] = useState<PaymentMethod>('cash')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const db = getDatabase()
    db.get<OrderModel>('orders').find(orderId).then(setOrder)
    getTotalPaidKobo(db, orderId).then(setPaidKobo)
  }, [orderId])

  const outstanding = totalKobo - paidKobo

  async function handlePay() {
    const naira = parseInt(amountNaira, 10)
    if (isNaN(naira) || naira <= 0) { setError('Enter a valid amount'); return }
    setError(null)
    setLoading(true)
    try {
      const db = getDatabase()
      await recordPaymentLocally(db, uuid(), orderId, naira * 100, method)
      const newPaid = await getTotalPaidKobo(db, orderId)
      setPaidKobo(newPaid)
      setAmountNaira('')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Payment failed')
    } finally {
      setLoading(false)
    }
  }

  function handleDone() {
    navigation.popToTop()
  }

  return (
    <View style={s.container}>
      <Text style={s.title}>Payment</Text>
      {order && <Text style={s.code}>Code: {order.pickupCode}</Text>}

      <View style={s.summary}>
        <Row label="Total" value={formatNaira(totalKobo)} />
        <Row label="Paid" value={formatNaira(paidKobo)} />
        <Row label="Outstanding" value={formatNaira(outstanding)} highlight={outstanding > 0} />
      </View>

      {outstanding > 0 && (
        <>
          <View style={s.row}>
            {METHODS.map(m => (
              <TouchableOpacity
                key={m}
                style={[s.chip, method === m && s.chipActive]}
                onPress={() => setMethod(m)}
              >
                <Text style={method === m ? s.chipTextActive : s.chipText}>{m}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <TextInput
            style={s.input}
            placeholder="Amount (₦)"
            keyboardType="number-pad"
            value={amountNaira}
            onChangeText={setAmountNaira}
          />
          {error && <Text style={s.error}>{error}</Text>}
          <TouchableOpacity style={s.btn} onPress={handlePay} disabled={loading}>
            {loading
              ? <ActivityIndicator color="#fff" />
              : <Text style={s.btnText}>Record Payment</Text>}
          </TouchableOpacity>
        </>
      )}

      <TouchableOpacity style={[s.btn, s.doneBtn]} onPress={handleDone}>
        <Text style={s.btnText}>Done</Text>
      </TouchableOpacity>
    </View>
  )
}

function Row({ label, value, highlight = false }: { label: string; value: string; highlight?: boolean }) {
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 }}>
      <Text style={{ fontSize: 16 }}>{label}</Text>
      <Text style={{ fontSize: 16, fontWeight: '700', color: highlight ? '#c00' : '#000' }}>{value}</Text>
    </View>
  )
}

const s = StyleSheet.create({
  container: { flex: 1, padding: 24 },
  title: { fontSize: 24, fontWeight: '700', marginBottom: 8 },
  code: { fontSize: 18, color: '#555', marginBottom: 20 },
  summary: { marginBottom: 24, padding: 16, backgroundColor: '#f5f5f5', borderRadius: 8 },
  row: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  chip: { padding: 8, borderRadius: 6, borderWidth: 1, borderColor: '#ccc' },
  chipActive: { backgroundColor: '#1a56db', borderColor: '#1a56db' },
  chipText: { color: '#333' },
  chipTextActive: { color: '#fff' },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    marginBottom: 12,
    width: 280,
  },
  error: { color: 'red', marginBottom: 8 },
  btn: {
    backgroundColor: '#1a56db',
    padding: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 12,
  },
  doneBtn: { backgroundColor: '#333' },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
})
