"""
Teaming MCP Server Entry Point
stdio 기반 MCP 서버 실행
"""

import asyncio
import sys
import json
from typing import Any, Dict

from .mcp_server import create_teaming_mcp_server, TEAMING_TOOLS


async def handle_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """MCP 요청 처리"""
    method = request.get("method")
    params = request.get("params", {})

    # 도구 목록 조회
    if method == "tools/list":
        server = create_teaming_mcp_server()
        return {
            "tools": server["tools"]
        }

    # 도구 실행
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        for func in TEAMING_TOOLS:
            if func._mcp_tool["name"] == tool_name:
                try:
                    result = await func(arguments)
                    return result
                except Exception as e:
                    return {
                        "content": [{
                            "type": "text",
                            "text": json.dumps({
                                "success": False,
                                "error": str(e)
                            }, ensure_ascii=False)
                        }],
                        "isError": True
                    }

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }, ensure_ascii=False)
            }],
            "isError": True
        }

    # 서버 정보
    elif method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "teaming",
                "version": "1.0.0"
            }
        }

    return {"error": f"Unknown method: {method}"}


async def main():
    """stdio 기반 MCP 서버 메인 루프"""
    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.readline
            )
            if not line:
                break

            request = json.loads(line.strip())
            response = await handle_request(request)

            # JSON-RPC 형식 응답
            output = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": response
            }
            print(json.dumps(output, ensure_ascii=False), flush=True)

        except json.JSONDecodeError as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            }
            print(json.dumps(error_response, ensure_ascii=False), flush=True)

        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error_response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
