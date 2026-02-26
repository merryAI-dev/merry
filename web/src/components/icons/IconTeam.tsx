export function IconTeam({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        {/* Avatar gradients */}
        <radialGradient id="it-a1" cx="40%" cy="35%" r="60%">
          <stop offset="0%" stopColor="#7DC0FF" />
          <stop offset="100%" stopColor="#2C7AF5" />
        </radialGradient>
        <radialGradient id="it-a2" cx="40%" cy="35%" r="60%">
          <stop offset="0%" stopColor="#A78BFA" />
          <stop offset="100%" stopColor="#7C3AED" />
        </radialGradient>
        <radialGradient id="it-a3" cx="40%" cy="35%" r="60%">
          <stop offset="0%" stopColor="#6EE7B7" />
          <stop offset="100%" stopColor="#059669" />
        </radialGradient>
        <filter id="it-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#000" floodOpacity="0.1" />
        </filter>
      </defs>

      <g filter="url(#it-shadow)">
        {/* Avatar 3 (right, back) */}
        <circle cx="25" cy="15" r="9" fill="url(#it-a3)" />
        {/* Face highlight */}
        <ellipse cx="22" cy="12" rx="3" ry="2" fill="white" opacity="0.2" />
        {/* Tiny body silhouette */}
        <path d="M17,24 Q16,30 18,32 Q22,34 28,32 Q30,30 33,24 Q29,22 25,22 Q21,22 17,24Z"
              fill="url(#it-a3)" opacity="0.7" />

        {/* Avatar 2 (middle) */}
        <circle cx="18" cy="14" r="9" fill="url(#it-a2)" />
        <ellipse cx="15" cy="11" rx="3" ry="2" fill="white" opacity="0.2" />
        <path d="M10,23 Q9,29 11,31 Q15,33 21,31 Q23,29 26,23 Q22,21 18,21 Q14,21 10,23Z"
              fill="url(#it-a2)" opacity="0.7" />

        {/* Avatar 1 (left, front) */}
        <circle cx="11" cy="15" r="9" fill="url(#it-a1)" />
        <ellipse cx="8"  cy="12" rx="3" ry="2" fill="white" opacity="0.25" />
        <path d="M3,24 Q2,30 4,32 Q8,34 14,32 Q16,30 19,24 Q15,22 11,22 Q7,22 3,24Z"
              fill="url(#it-a1)" opacity="0.7" />
      </g>

      {/* Online indicator dot */}
      <circle cx="17" cy="7" r="3.5" fill="#00C087" />
      <circle cx="17" cy="7" r="2"   fill="white" opacity="0.5" />
    </svg>
  );
}
