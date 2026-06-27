import React, { useState } from 'react'
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'
import type { NativeStackScreenProps } from '@react-navigation/native-stack'
import { Q } from '@nozbe/watermelondb'
import { getDatabase } from '../db'
import { CustomerModel } from '../db/models/CustomerModel'
import { createCustomerLocally } from '../services/orders'
import type { RootStackParamList } from '../navigation'

type Props = NativeStackScreenProps<RootStackParamList, 'CustomerIntake'>

function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

export function CustomerIntakeScreen({ navigation }: Props) {
  const [phone, setPhone] = useState('')
  const [name, setName] = useState('')
  const [found, setFound] = useState<CustomerModel | null>(null)
  const [searched, setSearched] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSearch() {
    setError(null)
    setLoading(true)
    try {
      const db = getDatabase()
      const results = await db
        .get<CustomerModel>('customers')
        .query(Q.where('phone', phone.trim()))
        .fetch()
      setFound(results[0] ?? null)
      setSearched(true)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleCreate() {
    if (!name.trim()) { setError('Name is required'); return }
    setError(null)
    setLoading(true)
    try {
      const db = getDatabase()
      const customer = await createCustomerLocally(db, uuid(), name.trim(), phone.trim())
      navigation.navigate('OrderCreation', { customerId: customer.id, customerTier: customer.tier })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not create customer')
    } finally {
      setLoading(false)
    }
  }

  function handleSelect(customer: CustomerModel) {
    navigation.navigate('OrderCreation', {
      customerId: customer.id,
      customerTier: customer.tier,
    })
  }

  return (
    <View style={s.container}>
      <Text style={s.title}>Customer Lookup</Text>
      <TextInput
        style={s.input}
        placeholder="Phone number"
        keyboardType="phone-pad"
        value={phone}
        onChangeText={setPhone}
      />
      <TouchableOpacity style={s.btn} onPress={handleSearch} disabled={loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>Search</Text>}
      </TouchableOpacity>
      {error && <Text style={s.error}>{error}</Text>}
      {searched && found && (
        <TouchableOpacity style={s.customerCard} onPress={() => handleSelect(found)}>
          <Text style={s.customerName}>{found.name}</Text>
          <Text>{found.phone} · Tier {found.tier}</Text>
        </TouchableOpacity>
      )}
      {searched && !found && (
        <View style={s.newCustomer}>
          <Text style={s.subtitle}>No customer found. Create new?</Text>
          <TextInput
            style={s.input}
            placeholder="Full name"
            value={name}
            onChangeText={setName}
          />
          <TouchableOpacity style={s.btn} onPress={handleCreate} disabled={loading}>
            <Text style={s.btnText}>Create & Continue</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  )
}

const s = StyleSheet.create({
  container: { flex: 1, padding: 24 },
  title: { fontSize: 24, fontWeight: '700', marginBottom: 20 },
  subtitle: { fontSize: 16, marginBottom: 12 },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    fontSize: 16,
    width: 320,
  },
  btn: {
    backgroundColor: '#1a56db',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
    width: 320,
    marginBottom: 16,
  },
  btnText: { color: '#fff', fontWeight: '700' },
  error: { color: 'red', marginBottom: 8 },
  customerCard: {
    borderWidth: 1,
    borderColor: '#1a56db',
    borderRadius: 8,
    padding: 16,
    marginTop: 12,
    width: 320,
  },
  customerName: { fontWeight: '700', fontSize: 18, marginBottom: 4 },
  newCustomer: { marginTop: 20 },
})
