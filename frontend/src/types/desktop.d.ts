export {}

declare global {
  interface Window {
    stockwiseDesktop?: {
      getApiBaseUrl(): Promise<string>
    }
  }
}
