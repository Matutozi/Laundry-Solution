import React from 'react'
import { NavigationContainer } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { GestureHandlerRootView } from 'react-native-gesture-handler'
import { AuthProvider, useAuth } from './src/context/AuthContext'
import { LoginScreen } from './src/screens/LoginScreen'
import { CustomerIntakeScreen } from './src/screens/CustomerIntakeScreen'
import { OrderCreationScreen } from './src/screens/OrderCreationScreen'
import { PaymentCaptureScreen } from './src/screens/PaymentCaptureScreen'
import { PickupReleaseScreen } from './src/screens/PickupReleaseScreen'
import type { RootStackParamList } from './src/navigation'

const Stack = createNativeStackNavigator<RootStackParamList>()

function AppNavigator() {
  const { token } = useAuth()

  return (
    <Stack.Navigator screenOptions={{ headerShown: true }}>
      {!token ? (
        <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
      ) : (
        <>
          <Stack.Screen name="CustomerIntake" component={CustomerIntakeScreen} options={{ title: 'Customer' }} />
          <Stack.Screen name="OrderCreation" component={OrderCreationScreen} options={{ title: 'New Order' }} />
          <Stack.Screen name="PaymentCapture" component={PaymentCaptureScreen} options={{ title: 'Payment' }} />
          <Stack.Screen name="PickupRelease" component={PickupReleaseScreen} options={{ title: 'Pickup' }} />
        </>
      )}
    </Stack.Navigator>
  )
}

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <AuthProvider>
        <NavigationContainer>
          <AppNavigator />
        </NavigationContainer>
      </AuthProvider>
    </GestureHandlerRootView>
  )
}
