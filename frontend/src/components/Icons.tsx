interface IconProps {
  size?: number
}

function iconProps(size: number) {
  return {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }
}

export function DashboardIcon({ size = 18 }: IconProps) {
  return (
    <svg {...iconProps(size)}>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  )
}

export function OrdersIcon({ size = 18 }: IconProps) {
  return (
    <svg {...iconProps(size)}>
      <path d="M7 3h10a2 2 0 0 1 2 2v16l-3-2-2 2-2-2-2 2-2-2-3 2V5a2 2 0 0 1 2-2Z" />
      <path d="M9 8h6M9 12h6" />
    </svg>
  )
}

export function ProductsIcon({ size = 18 }: IconProps) {
  return (
    <svg {...iconProps(size)}>
      <path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z" />
      <path d="m4 7.5 8 4.5 8-4.5M12 12v9" />
    </svg>
  )
}

export function PlusIcon({ size = 18 }: IconProps) {
  return (
    <svg {...iconProps(size)}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}

export function RefreshIcon({ size = 16 }: IconProps) {
  return (
    <svg {...iconProps(size)}>
      <path d="M20 11a8 8 0 0 0-14.6-4.4L4 8" />
      <path d="M4 4v4h4M4 13a8 8 0 0 0 14.6 4.4L20 16" />
      <path d="M20 20v-4h-4" />
    </svg>
  )
}

export function ArrowLeftIcon({ size = 16 }: IconProps) {
  return (
    <svg {...iconProps(size)}>
      <path d="M19 12H5M11 18l-6-6 6-6" />
    </svg>
  )
}

export function ArrowRightIcon({ size = 16 }: IconProps) {
  return (
    <svg {...iconProps(size)}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  )
}

export function CheckIcon({ size = 18 }: IconProps) {
  return (
    <svg {...iconProps(size)}>
      <path d="m5 12 4.5 4.5L19 7" />
    </svg>
  )
}

export function AlertIcon({ size = 18 }: IconProps) {
  return (
    <svg {...iconProps(size)}>
      <path d="M12 3 2.5 20h19L12 3Z" />
      <path d="M12 9v5M12 17.5v.5" />
    </svg>
  )
}

export function StoreIcon({ size = 18 }: IconProps) {
  return (
    <svg {...iconProps(size)}>
      <path d="M4 10h16l-1.5-6h-13L4 10Z" />
      <path d="M5 10v10h14V10M9 20v-6h6v6" />
    </svg>
  )
}

export function CartIcon({ size = 18 }: IconProps) {
  return (
    <svg {...iconProps(size)}>
      <path d="M3 4h2l2.2 10.2a2 2 0 0 0 2 1.6h7.9a2 2 0 0 0 2-1.6L20 7H6" />
      <circle cx="10" cy="20" r="1.2" />
      <circle cx="18" cy="20" r="1.2" />
    </svg>
  )
}

export function MinusIcon({ size = 16 }: IconProps) {
  return (
    <svg {...iconProps(size)}>
      <path d="M5 12h14" />
    </svg>
  )
}

export function TrashIcon({ size = 16 }: IconProps) {
  return (
    <svg {...iconProps(size)}>
      <path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" />
    </svg>
  )
}
