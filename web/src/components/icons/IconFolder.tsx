export function IconFolder({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        {/* Folder body front */}
        <linearGradient id="if-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#5BA5FF" />
          <stop offset="100%" stopColor="#2C7AF5" />
        </linearGradient>
        {/* Folder top face */}
        <linearGradient id="if-top" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0%" stopColor="#7DC0FF" />
          <stop offset="100%" stopColor="#B8DCFF" />
        </linearGradient>
        {/* Folder tab */}
        <linearGradient id="if-tab" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#74B8FF" />
          <stop offset="100%" stopColor="#4A96FF" />
        </linearGradient>
        {/* Side face */}
        <linearGradient id="if-side" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1866D4" />
          <stop offset="100%" stopColor="#0D4BAA" />
        </linearGradient>
        <filter id="if-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="1" dy="3" stdDeviation="2.5" floodColor="#1050B4" floodOpacity="0.18" />
        </filter>
      </defs>

      <g filter="url(if-shadow)">
        {/* Folder body front face */}
        <rect x="4" y="16" width="28" height="18" rx="3" fill="url(#if-body)" />
        {/* Folder top face (isometric top) */}
        <polygon points="4,16 32,16 36,11 8,11"      fill="url(#if-top)" />
        {/* Folder side face */}
        <polygon points="32,16 36,11 36,29 32,34"    fill="url(#if-side)" />
        {/* Tab on top-left */}
        <path d="M4,16 L4,13 Q4,11 6,11 L14,11 Q16,11 17,13 L18,16 Z"
              fill="url(#if-tab)" />
        {/* Tab top face */}
        <polygon points="4,13 18,16 22,13 8,10"      fill="url(#if-top)" opacity="0.85" />

        {/* Document lines inside */}
        <rect x="8"  y="21" width="16" height="2" rx="1" fill="white" opacity="0.45" />
        <rect x="8"  y="25" width="12" height="2" rx="1" fill="white" opacity="0.3" />
        <rect x="8"  y="29" width="10" height="2" rx="1" fill="white" opacity="0.2" />
      </g>

      {/* Specular highlight */}
      <rect x="5" y="17" width="5" height="16" rx="2" fill="white" opacity="0.1" />
    </svg>
  );
}
