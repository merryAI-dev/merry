function isUnauthorizedError(error?: string) {
  return error === "UNAUTHORIZED" || error?.startsWith("UNAUTHORIZED:") === true;
}

export function formatParseError(error?: string): string {
  if (isUnauthorizedError(error)) {
    return "Ralph Playground를 사용하려면 로그인 상태가 필요합니다.";
  }

  switch (error) {
    case "FILE_REQUIRED":
      return "분석할 PDF 파일을 먼저 업로드하세요.";
    case "PDF_ONLY":
      return "PDF 파일만 업로드할 수 있습니다.";
    case "FILE_TOO_LARGE":
      return "PDF 파일이 너무 큽니다. 50MB 이하 파일로 다시 시도하세요.";
    case "PARSE_TIMEOUT":
      return "문서 파싱 시간이 초과되었습니다. 페이지 수를 줄이거나 문서를 나눠서 다시 시도하세요.";
    case "PARSE_STDOUT_LIMIT":
    case "PARSE_STDERR_LIMIT":
      return "파서 출력이 비정상적으로 커져 중단되었습니다.";
    case "PARSE_EMPTY_OUTPUT":
    case "PARSE_OUTPUT_INVALID":
      return "문서 파싱 결과를 읽지 못했습니다. 잠시 후 다시 시도하세요.";
    case "PARSER_EXITED":
    case "PARSER_SPAWN_FAILED":
      return "문서 파서 실행에 실패했습니다.";
    default:
      return error ?? "알 수 없는 오류";
  }
}

export function formatCheckError(error?: string): string {
  if (isUnauthorizedError(error)) {
    return "Ralph Playground를 사용하려면 로그인 상태가 필요합니다.";
  }

  switch (error) {
    case "TEXT_REQUIRED":
      return "검사할 문서 텍스트가 없습니다.";
    case "CONDITIONS_REQUIRED":
      return "검사 조건을 하나 이상 입력하세요.";
    case "TEXT_TOO_LARGE":
      return "추출 텍스트가 너무 깁니다. 페이지 수를 줄이거나 문서를 나눠서 다시 시도하세요.";
    case "CHECK_TIMEOUT":
      return "조건 검사 시간이 초과되었습니다. 조건 수를 줄이거나 문서를 나눠서 다시 시도하세요.";
    case "CHECK_STDOUT_LIMIT":
    case "CHECK_STDERR_LIMIT":
      return "조건 검사 출력이 비정상적으로 커져 중단되었습니다.";
    case "CHECK_EMPTY_OUTPUT":
    case "CHECK_OUTPUT_INVALID":
      return "조건 검사 결과를 읽지 못했습니다. 잠시 후 다시 시도하세요.";
    case "CHECKER_EXITED":
    case "CHECKER_SPAWN_FAILED":
      return "조건 검사 프로세스 실행에 실패했습니다.";
    default:
      return error ?? "알 수 없는 오류";
  }
}
