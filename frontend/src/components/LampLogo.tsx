interface Props {
  size?: number
  className?: string
  label?: string
}

export default function LampLogo({ size = 32, className, label }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <path
        d="M14 3.5L14.7 6.2L17.2 6.8L14.7 7.4L14 10L13.3 7.4L10.8 6.8L13.3 6.2L14 3.5Z"
        fill="#f5c76e"
        opacity="0.95"
      />
      <path
        d="M15.5 10.5C15.5 10.5 16.8 8.8 18 9.8"
        stroke="#d97757"
        strokeWidth="0.9"
        strokeLinecap="round"
        opacity="0.55"
      />
      <ellipse cx="16" cy="13.2" rx="5.2" ry="1.6" fill="#d97757" opacity="0.85" />
      <path
        d="M10.2 14C9.4 17.2 9.6 20.8 11.2 23.2C12.6 25.2 14.8 26 16 26C17.2 26 19.4 25.2 20.8 23.2C22.4 20.8 22.6 17.2 21.8 14"
        stroke="#d97757"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="#d97757"
        fillOpacity="0.18"
      />
      <path d="M12 26H20" stroke="#d97757" strokeWidth="1.5" strokeLinecap="round" />
      <path
        d="M9.2 17.2C6.8 16.2 5.8 15 5.8 13.8C5.8 12.2 7.4 11.6 9.4 12.6"
        stroke="#d97757"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M22.8 16.8C25.4 15.2 26.6 17.2 24.8 19.4C23.4 21.2 21.4 20.4 21.8 18.6"
        stroke="#d97757"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  )
}
