export function HeroIllustration({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 480 310"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        {/* Front face — lighter at top, Toss blue */}
        <linearGradient id="hi-front" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#5BA5FF" />
          <stop offset="100%" stopColor="#2C7AF5" />
        </linearGradient>
        {/* Top face — highlight */}
        <linearGradient id="hi-top" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0%" stopColor="#7DC0FF" />
          <stop offset="100%" stopColor="#AEDAFF" />
        </linearGradient>
        {/* Right side — darkest */}
        <linearGradient id="hi-side" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1866D4" />
          <stop offset="100%" stopColor="#0D4BAA" />
        </linearGradient>
        {/* Ambient background glow */}
        <radialGradient id="hi-glow" cx="50%" cy="80%" r="55%">
          <stop offset="0%" stopColor="#D6EAFF" stopOpacity="1" />
          <stop offset="100%" stopColor="#F2F4F6" stopOpacity="0" />
        </radialGradient>
        {/* Floating card shadow */}
        <filter id="hi-card" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="8" stdDeviation="14" floodColor="#000000" floodOpacity="0.09" />
        </filter>
        {/* Bars shadow */}
        <filter id="hi-bars" x="-8%" y="-8%" width="116%" height="116%">
          <feDropShadow dx="4" dy="10" stdDeviation="10" floodColor="#1050B4" floodOpacity="0.14" />
        </filter>
      </defs>

      {/* ── Background glow ── */}
      <ellipse cx="240" cy="248" rx="215" ry="95" fill="url(#hi-glow)" />
      {/* Ground plane shadow */}
      <ellipse cx="228" cy="278" rx="190" ry="13" fill="#3182F6" opacity="0.06" />

      {/* ── 3D Isometric Bar Chart ── */}
      {/*
          Isometric shift: dx=+22 right, dy=-13 up  (for depth face)
          Base y=270, bar width=52
          Heights: 70, 110, 148, 182, 208
      */}
      <g filter="url(#hi-bars)">

        {/* Bar 1  x=30 h=70 */}
        <polygon points="30,200 82,200 82,270 30,270"    fill="url(#hi-front)" />
        <polygon points="30,200 82,200 104,187 52,187"   fill="url(#hi-top)" />
        <polygon points="82,200 104,187 104,257 82,270"  fill="url(#hi-side)" />
        <rect x="32" y="202" width="7" height="66" rx="2" fill="white" opacity="0.13" />

        {/* Bar 2  x=106 h=110 */}
        <polygon points="106,160 158,160 158,270 106,270"  fill="url(#hi-front)" />
        <polygon points="106,160 158,160 180,147 128,147"  fill="url(#hi-top)" />
        <polygon points="158,160 180,147 180,257 158,270"  fill="url(#hi-side)" />
        <rect x="108" y="162" width="7" height="106" rx="2" fill="white" opacity="0.13" />

        {/* Bar 3  x=182 h=148 */}
        <polygon points="182,122 234,122 234,270 182,270"  fill="url(#hi-front)" />
        <polygon points="182,122 234,122 256,109 204,109"  fill="url(#hi-top)" />
        <polygon points="234,122 256,109 256,257 234,270"  fill="url(#hi-side)" />
        <rect x="184" y="124" width="7" height="144" rx="2" fill="white" opacity="0.13" />

        {/* Bar 4  x=258 h=182 */}
        <polygon points="258,88 310,88 310,270 258,270"  fill="url(#hi-front)" />
        <polygon points="258,88 310,88 332,75 280,75"    fill="url(#hi-top)" />
        <polygon points="310,88 332,75 332,257 310,270"  fill="url(#hi-side)" />
        <rect x="260" y="90" width="7" height="178" rx="2" fill="white" opacity="0.13" />

        {/* Bar 5  x=334 h=208 */}
        <polygon points="334,62 386,62 386,270 334,270"  fill="url(#hi-front)" />
        <polygon points="334,62 386,62 408,49 356,49"    fill="url(#hi-top)" />
        <polygon points="386,62 408,49 408,257 386,270"  fill="url(#hi-side)" />
        <rect x="336" y="64" width="7" height="204" rx="2" fill="white" opacity="0.13" />
      </g>

      {/* ── Trend line through top-face centers ── */}
      {/* centers: (78,187) (154,147) (230,109) (306,75) (382,49) */}
      <path
        d="M78,187 C110,175 132,153 154,147 C176,141 208,113 230,109 C252,105 284,77 306,75 C328,73 358,51 382,49"
        stroke="#3182F6"
        strokeWidth="2.2"
        strokeDasharray="6,4"
        strokeLinecap="round"
        fill="none"
        opacity="0.42"
      />
      {/* Arrowhead at end of trend line */}
      <polygon
        points="393,43 381,46 384,57"
        fill="#3182F6"
        opacity="0.55"
      />

      {/* ── Floating card — top right (+127%) ── */}
      <g filter="url(#hi-card)">
        <rect x="390" y="14" width="84" height="74" rx="14" fill="white" />
        {/* Status dot */}
        <circle cx="460" cy="28" r="5" fill="#00C087" />
        <text x="402" y="34" fontSize="9" fill="#8B95A1"
              fontFamily="-apple-system,BlinkMacSystemFont,'Noto Sans KR',sans-serif">수익률</text>
        <text x="402" y="57" fontSize="21" fontWeight="800" fill="#191F28"
              fontFamily="-apple-system,BlinkMacSystemFont,'Noto Sans KR',sans-serif">+127%</text>
        <text x="402" y="74" fontSize="8" fill="#00C087"
              fontFamily="-apple-system,BlinkMacSystemFont,'Noto Sans KR',sans-serif">↑ 전월 대비 +24%p</text>
      </g>

      {/* ── Floating card — left (248건) ── */}
      <g filter="url(#hi-card)">
        <rect x="2" y="106" width="88" height="68" rx="14" fill="white" />
        <text x="14" y="126" fontSize="9" fill="#8B95A1"
              fontFamily="-apple-system,BlinkMacSystemFont,'Noto Sans KR',sans-serif">분석 건수</text>
        <text x="14" y="148" fontSize="18" fontWeight="800" fill="#191F28"
              fontFamily="-apple-system,BlinkMacSystemFont,'Noto Sans KR',sans-serif">248건</text>
        {/* Tiny bar chart */}
        <rect x="14"  y="156" width="9" height="6"  rx="1.5" fill="#3182F6" opacity="0.22" />
        <rect x="27"  y="153" width="9" height="9"  rx="1.5" fill="#3182F6" opacity="0.45" />
        <rect x="40"  y="150" width="9" height="12" rx="1.5" fill="#3182F6" opacity="0.7" />
        <rect x="53"  y="147" width="9" height="15" rx="1.5" fill="#3182F6" />
      </g>

      {/* ── Decorative sparkle & dots ── */}
      {/* Sparkle top-center */}
      <g opacity="0.28" transform="translate(210,44)">
        <line x1="0" y1="-7" x2="0" y2="7"  stroke="#3182F6" strokeWidth="1.8" strokeLinecap="round" />
        <line x1="-7" y1="0" x2="7" y2="0"  stroke="#3182F6" strokeWidth="1.8" strokeLinecap="round" />
        <line x1="-5" y1="-5" x2="5" y2="5" stroke="#3182F6" strokeWidth="1"   strokeLinecap="round" />
        <line x1="5" y1="-5" x2="-5" y2="5" stroke="#3182F6" strokeWidth="1"   strokeLinecap="round" />
      </g>
      {/* Sparkle right */}
      <g opacity="0.22" transform="translate(452,108)">
        <line x1="0" y1="-5" x2="0" y2="5"  stroke="#3182F6" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="-5" y1="0" x2="5" y2="0"  stroke="#3182F6" strokeWidth="1.5" strokeLinecap="round" />
      </g>
      {/* Floating dots */}
      <circle cx="168" cy="38" r="5"   fill="#3182F6" opacity="0.14" />
      <circle cx="180" cy="26" r="3"   fill="#3182F6" opacity="0.09" />
      <circle cx="152" cy="22" r="2.5" fill="#3182F6" opacity="0.07" />
      <circle cx="462" cy="152" r="4"  fill="#3182F6" opacity="0.11" />
      <circle cx="474" cy="140" r="2"  fill="#3182F6" opacity="0.07" />
    </svg>
  );
}
