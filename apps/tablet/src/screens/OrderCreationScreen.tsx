import React, { useEffect, useState } from 'react'
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'
import type { NativeStackScreenProps } from '@react-navigation/native-stack'
import { Q } from '@nozbe/watermelondb'
import { formatNaira } from '@wise-wash/shared'
import { getDatabase } from '../db'
import { ServiceModel } from '../db/models/ServiceModel'
import { PriceRuleModel } from '../db/models/PriceRuleModel'
import { createOrderLocally, type CreateOrderParams } from '../services/orders'
import { computeOrderTotal, type LineInput, type Turnaround } from '../services/pricing'
import { useAuth } from '../context/AuthContext'
import type { RootStackParamList } from '../navigation'

type Props = NativeStackScreenProps<RootStackParamList, 'OrderCreation'>

const TURNAROUNDS: Turnaround[] = ['regular', 'express', 'same_day']

function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

export function OrderCreationScreen({ route, navigation }: Props) {
  const { customerId, customerTier } = route.params
  const { branchId, attendantId, deviceId } = useAuth()

  const [services, setServices] = useState<ServiceModel[]>([])
  const [rules, setRules] = useState<PriceRuleModel[]>([])
  const [quantities, setQuantities] = useState<Record<string, string>>({})
  const [turnaround, setTurnaround] = useState<Turnaround>('regular')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const db = getDatabase()
    db.get<ServiceModel>('services').query().fetch().then(setServices)
    db.get<PriceRuleModel>('price_rules').query(Q.where('tier', customerTier)).fetch().then(setRules)
  }, [customerTier])

  const lineInputs: LineInput[] = services
    .map(s => ({ serviceId: s.id, pieceCount: parseInt(quantities[s.id] ?? '0', 10) || 0 }))
    .filter(l => l.pieceCount > 0)

  const ruleData = rules.map(r => ({
    serviceId: r.serviceId,
    tier: r.tier,
    priceKobo: r.priceKobo,
  }))

  const { totalKobo } = lineInputs.length > 0
    ? computeOrderTotal(lineInputs, customerTier, turnaround, ruleData)
    : { totalKobo: 0 }

  async function handleSubmit() {
    if (lineInputs.length === 0) { setError('Add at least one item'); return }
    if (!branchId || !attendantId) { setError('Not logged in to a branch'); return }
    setError(null)
    setLoading(true)
    try {
      const db = getDatabase()
      const params: CreateOrderParams = {
        id: uuid(),
        branchId,
        attendantId,
        customerId,
        turnaround,
        lines: lineInputs,
        deviceId,
        customerTier,
        rules: ruleData,
      }
      const order = await createOrderLocally(db, params)
      navigation.navigate('PaymentCapture', { orderId: order.id, totalKobo: order.totalKobo })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create order')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View style={s.container}>
      <Text style={s.title}>New Order</Text>

      {/* Turnaround selector */}
      <View style={s.row}>
        {TURNAROUNDS.map(t => (
          <TouchableOpacity
            key={t}
            style={[s.chip, turnaround === t && s.chipActive]}
            onPress={() => setTurnaround(t)}
          >
            <Text style={turnaround === t ? s.chipTextActive : s.chipText}>
              {t.replace('_', '-')}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Service list */}
      <FlatList
        data={services}
        keyExtractor={s => s.id}
        renderItem={({ item }) => (
          <View style={s.serviceRow}>
            <Text style={s.serviceName}>{item.name}</Text>
            <TextInput
              style={s.qtyInput}
              keyboardType="number-pad"
              placeholder="0"
              value={quantities[item.id] ?? ''}
              onChangeText={v => setQuantities(q => ({ ...q, [item.id]: v }))}
            />
          </View>
        )}
      />

      <Text style={s.total}>Total: {formatNaira(totalKobo)}</Text>
      {error && <Text style={s.error}>{error}</Text>}

      <TouchableOpacity style={s.btn} onPress={handleSubmit} disabled={loading}>
        {loading
          ? <ActivityIndicator color="#fff" />
          : <Text style={s.btnText}>Create Order</Text>}
      </TouchableOpacity>
    </View>
  )
}

const s = StyleSheet.create({
  container: { flex: 1, padding: 24 },
  title: { fontSize: 24, fontWeight: '700', marginBottom: 16 },
  row: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  chip: { padding: 8, borderRadius: 6, borderWidth: 1, borderColor: '#ccc' },
  chipActive: { backgroundColor: '#1a56db', borderColor: '#1a56db' },
  chipText: { color: '#333' },
  chipTextActive: { color: '#fff' },
  serviceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderColor: '#eee',
  },
  serviceName: { fontSize: 16, flex: 1 },
  qtyInput: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 6,
    padding: 8,
    width: 60,
    textAlign: 'center',
    fontSize: 16,
  },
  total: { fontSize: 22, fontWeight: '700', marginVertical: 16 },
  error: { color: 'red', marginBottom: 8 },
  btn: {
    backgroundColor: '#1a56db',
    padding: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
})
