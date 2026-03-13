"use client";

import * as React from "react";

/* ------------------------------------------------------------------ */
/*  Style constants – Robinhood light theme                           */
/* ------------------------------------------------------------------ */

const COLOR = {
  green: "#00C805",
  bg: "#FFFFFF",
  text: "#1A1D21",
  muted: "#6F7780",
  border: "#E3E5E8",
} as const;

/* ------------------------------------------------------------------ */
/*  Keyframe definitions injected once via <style>                    */
/* ------------------------------------------------------------------ */

const KEYFRAMES = `
@keyframes scan-sweep {
  0%   { top: 0%; }
  100% { top: 100%; }
}

@keyframes grid-fade {
  0%, 100% { opacity: 0.04; }
  50%      { opacity: 0.08; }
}

@keyframes checkmark-flash {
  0%   { opacity: 0; transform: scale(0.5); }
  50%  { opacity: 1; transform: scale(1.15); }
  100% { opacity: 1; transform: scale(1); }
}

@keyframes progress-pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.7; }
}

@keyframes fade-out {
  0%   { opacity: 1; }
  100% { opacity: 0; }
}
`;

/* ------------------------------------------------------------------ */
/*  Props                                                             */
/* ------------------------------------------------------------------ */

export interface ScanningOverlayProps {
  /** Whether the scanning animation is active. */
  scanning: boolean;
  /** Progress percentage (0–100). */
  progress: number;
  /** Name of the file being scanned. */
  filename: string;
  /** Document preview area rendered beneath the overlay. */
  children?: React.ReactNode;
}

/* ------------------------------------------------------------------ */
/*  Component                                                         */
/* ------------------------------------------------------------------ */

export function ScanningOverlay({
  scanning,
  progress,
  filename,
  children,
}: ScanningOverlayProps) {
  const clampedProgress = Math.min(100, Math.max(0, progress));

  // Track when scanning just completed so we can show the checkmark.
  const [showCheck, setShowCheck] = React.useState(false);
  const prevScanningRef = React.useRef(scanning);

  React.useEffect(() => {
    if (prevScanningRef.current && !scanning && clampedProgress >= 100) {
      setShowCheck(true);
      const timer = setTimeout(() => setShowCheck(false), 1600);
      return () => clearTimeout(timer);
    }
    prevScanningRef.current = scanning;
  }, [scanning, clampedProgress]);

  return (
    <>
      {/* Inject keyframes once */}
      <style>{KEYFRAMES}</style>

      <div
        style={{
          position: "relative",
          width: "100%",
          background: COLOR.bg,
          border: `1px solid ${COLOR.border}`,
          borderRadius: 12,
          overflow: "hidden",
        }}
      >
        {/* ---- Header bar ---- */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 16px",
            borderBottom: `1px solid ${COLOR.border}`,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <FileIcon color={scanning ? COLOR.green : COLOR.muted} />
            <span
              style={{
                fontSize: 14,
                fontWeight: 500,
                color: COLOR.text,
                maxWidth: 220,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
              title={filename}
            >
              {filename}
            </span>
          </div>

          <span
            style={{
              fontSize: 13,
              fontWeight: 600,
              fontVariantNumeric: "tabular-nums",
              color: scanning ? COLOR.green : COLOR.muted,
              animation: scanning ? "progress-pulse 1.5s ease-in-out infinite" : "none",
            }}
          >
            {scanning
              ? `${Math.round(clampedProgress)}%`
              : clampedProgress >= 100
                ? "Complete"
                : `${Math.round(clampedProgress)}%`}
          </span>
        </div>

        {/* ---- Progress bar ---- */}
        <div
          style={{
            height: 2,
            background: COLOR.border,
            position: "relative",
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${clampedProgress}%`,
              background: COLOR.green,
              transition: "width 0.3s ease",
            }}
          />
        </div>

        {/* ---- Document preview area ---- */}
        <div
          style={{
            position: "relative",
            minHeight: 280,
          }}
        >
          {/* Grid pattern overlay */}
          {scanning && (
            <div
              aria-hidden="true"
              style={{
                position: "absolute",
                inset: 0,
                zIndex: 1,
                pointerEvents: "none",
                backgroundImage: `
                  linear-gradient(${COLOR.green}11 1px, transparent 1px),
                  linear-gradient(90deg, ${COLOR.green}11 1px, transparent 1px)
                `,
                backgroundSize: "24px 24px",
                animation: "grid-fade 3s ease-in-out infinite",
              }}
            />
          )}

          {/* Laser scan line */}
          {scanning && (
            <div
              aria-hidden="true"
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                height: 2,
                zIndex: 2,
                pointerEvents: "none",
                background: COLOR.green,
                boxShadow: `
                  0 0 8px 2px ${COLOR.green},
                  0 0 24px 4px ${COLOR.green}66,
                  0 0 48px 8px ${COLOR.green}33
                `,
                animation: "scan-sweep 2.4s ease-in-out infinite",
              }}
            >
              {/* Gradient trail above the laser */}
              <div
                style={{
                  position: "absolute",
                  bottom: "100%",
                  left: 0,
                  right: 0,
                  height: 40,
                  background: `linear-gradient(to bottom, transparent, ${COLOR.green}18)`,
                  pointerEvents: "none",
                }}
              />
              {/* Gradient trail below the laser */}
              <div
                style={{
                  position: "absolute",
                  top: "100%",
                  left: 0,
                  right: 0,
                  height: 12,
                  background: `linear-gradient(to top, transparent, ${COLOR.green}10)`,
                  pointerEvents: "none",
                }}
              />
            </div>
          )}

          {/* Children (document preview) */}
          <div style={{ position: "relative", zIndex: 0 }}>{children}</div>

          {/* Corner brackets – scanning indicator */}
          {scanning && <ScanCorners color={COLOR.green} />}

          {/* Completion checkmark */}
          {showCheck && (
            <div
              aria-label="Scan complete"
              style={{
                position: "absolute",
                inset: 0,
                zIndex: 10,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: `${COLOR.bg}cc`,
                animation: "fade-out 1.6s ease forwards",
              }}
            >
              <div
                style={{
                  width: 64,
                  height: 64,
                  borderRadius: "50%",
                  background: COLOR.green,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  animation: "checkmark-flash 0.5s ease-out forwards",
                }}
              >
                <svg
                  width={32}
                  height={32}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke={COLOR.bg}
                  strokeWidth={3}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                    */
/* ------------------------------------------------------------------ */

/** Small document icon for the header. */
function FileIcon({ color }: { color: string }) {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="8" y1="13" x2="16" y2="13" />
      <line x1="8" y1="17" x2="16" y2="17" />
    </svg>
  );
}

/** Animated corner brackets that frame the scanning area. */
function ScanCorners({ color }: { color: string }) {
  const size = 20;
  const thickness = 2;
  const offset = 8;

  const cornerStyle = (
    top: boolean,
    left: boolean,
  ): React.CSSProperties => ({
    position: "absolute",
    width: size,
    height: size,
    pointerEvents: "none",
    zIndex: 3,
    ...(top ? { top: offset } : { bottom: offset }),
    ...(left ? { left: offset } : { right: offset }),
    borderColor: color,
    borderStyle: "solid",
    borderWidth: 0,
    ...(top && left && { borderTopWidth: thickness, borderLeftWidth: thickness }),
    ...(top && !left && { borderTopWidth: thickness, borderRightWidth: thickness }),
    ...(!top && left && { borderBottomWidth: thickness, borderLeftWidth: thickness }),
    ...(!top && !left && { borderBottomWidth: thickness, borderRightWidth: thickness }),
    opacity: 0.6,
  });

  return (
    <>
      <div aria-hidden="true" style={cornerStyle(true, true)} />
      <div aria-hidden="true" style={cornerStyle(true, false)} />
      <div aria-hidden="true" style={cornerStyle(false, true)} />
      <div aria-hidden="true" style={cornerStyle(false, false)} />
    </>
  );
}
