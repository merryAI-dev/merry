"use client";

import * as React from "react";
import { WifiOff } from "lucide-react";

function useOnlineStatus() {
  const [online, setOnline] = React.useState(true);

  React.useEffect(() => {
    // Set initial state from navigator (only in browser).
    setOnline(navigator.onLine);

    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);

    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  return online;
}

export function NetworkBanner() {
  const online = useOnlineStatus();
  const [dismissed, setDismissed] = React.useState(false);

  // Reset dismissed state when coming back online then going offline again.
  React.useEffect(() => {
    if (online) setDismissed(false);
  }, [online]);

  if (online || dismissed) return null;

  return (
    <div role="alert" className="fixed left-0 right-0 top-0 z-[60] flex items-center justify-center gap-2 bg-amber-500 px-4 py-2 text-sm font-medium text-white shadow-md">
      <WifiOff className="h-4 w-4" aria-hidden="true" />
      <span>네트워크 연결이 끊겼습니다. 일부 기능이 제한될 수 있습니다.</span>
      <button
        onClick={() => setDismissed(true)}
        className="ml-2 rounded px-2 py-0.5 text-xs opacity-80 transition-opacity hover:opacity-100"
        aria-label="네트워크 알림 닫기"
      >
        닫기
      </button>
    </div>
  );
}
