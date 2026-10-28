export function formatMoney(
  cents: number | null | undefined,
  currency = 'USD',
): string {
  if (cents === null || cents === undefined) {
    return '—'
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(cents / 100)
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))
}

export function shortId(id: string): string {
  return id.slice(0, 8).toUpperCase()
}

export function itemCount(items: Array<{ quantity: number }>): number {
  return items.reduce((total, item) => total + item.quantity, 0)
}
