export function IconChart({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="ic-front" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#5BA5FF" />
          <stop offset="100%" stopColor="#2C7AF5" />
        </linearGradient>
        <linearGradient id="ic-top" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0%" stopColor="#7DC0FF" />
          <stop offset="100%" stopColor="#AEDAFF" />
        </linearGradient>
        <linearGradient id="ic-side" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1866D4" />
          <stop offset="100%" stopColor="#0D4BAA" />
        </linearGradient>
        <filter id="ic-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="1" dy="2" stdDeviation="2" floodColor="#1050B4" floodOpacity="0.18" />
        </filter>
      </defs>

      <g filter="url(#ic-shadow)">
        {/* Bar 1 — short */}
        <polygon points="4,26 10,26 10,32 4,32"   fill="url(#ic-front)" />
        <polygon points="4,26 10,26 14,23 8,23"   fill="url(#ic-top)" />
        <polygon points="10,26 14,23 14,29 10,32" fill="url(#ic-side)" />

        {/* Bar 2 — medium */}
        <polygon points="15,20 21,20 21,32 15,32"  fill="url(#ic-front)" />
        <polygon points="15,20 21,20 25,17 19,17"  fill="url(#ic-top)" />
        <polygon points="21,20 25,17 25,29 21,32"  fill="url(#ic-side)" />

        {/* Bar 3 — tall */}
        <polygon points="26,12 32,12 32,32 26,32"  fill="url(#ic-front)" />
        <polygon points="26,12 32,12 36,9 30,9"    fill="url(#ic-top)" />
        <polygon points="32,12 36,9 36,29 32,32"   fill="url(#ic-side)" />
      </g>

      {/* Trend arrow */}
      <path d="M7,24 L18,18 L29,11" stroke="#3182F6" strokeWidth="1.4"
            strokeDasharray="3,2" strokeLinecap="round" fill="none" opacity="0.5" />
      <polygon points="32,9 28,11 30,14" fill="#3182F6" opacity="0.55" />
    </svg>
  );
}
