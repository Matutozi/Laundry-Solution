import React, { useState } from 'react'
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'
import { useAuth } from '../context/AuthContext'
import { getApiClient } from '../api/client'

interface TokenResponse {
  access_token: string
  token_type: string
  branch_id: string
  staff_id: string
}

export function LoginScreen() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleLogin() {
    setError(null)
    setLoading(true)
    try {
      const res = await getApiClient().post<TokenResponse>('/auth/login', {
        email,
        password,
      })
      login(res.access_token, res.branch_id, res.staff_id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View style={s.container}>
      <Text style={s.title}>Wise-Wash</Text>
      <TextInput
        style={s.input}
        placeholder="Email"
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
      />
      <TextInput
        style={s.input}
        placeholder="Password"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />
      {error && <Text style={s.error}>{error}</Text>}
      <TouchableOpacity style={s.btn} onPress={handleLogin} disabled={loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>Sign in</Text>}
      </TouchableOpacity>
    </View>
  )
}

const s = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32 },
  title: { fontSize: 36, fontWeight: '700', marginBottom: 32 },
  input: {
    width: 320,
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    fontSize: 16,
  },
  error: { color: 'red', marginBottom: 8 },
  btn: {
    width: 320,
    backgroundColor: '#1a56db',
    padding: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
})
