export type RootStackParamList = {
  Login: undefined
  CustomerIntake: undefined
  OrderCreation: { customerId: string; customerTier: number }
  PaymentCapture: { orderId: string; totalKobo: number }
  PickupRelease: undefined
}
