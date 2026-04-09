const LOGOUT_ERROR_MESSAGE = "로그아웃에 실패했습니다.";

export async function requestLogout(
  fetchImpl: typeof fetch = fetch,
): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    const response = await fetchImpl("/api/auth/logout", { method: "POST" });
    if (!response.ok) {
      return { ok: false, error: LOGOUT_ERROR_MESSAGE };
    }
    return { ok: true };
  } catch {
    return { ok: false, error: LOGOUT_ERROR_MESSAGE };
  }
}
