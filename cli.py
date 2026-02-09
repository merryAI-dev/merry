#!/usr/bin/env python3
"""
VC Investment Agent - CLI Interface
"""

import asyncio
import click
from pathlib import Path

from agent import ConversationalVCAgent, InteractiveCriticAgent, __version__ as AGENT_VERSION
from shared.logging_config import setup_logging
from shared.file_utils import copy_to_temp

# 로깅 초기화 (CLI 시작 시 1회)
setup_logging()


@click.group()
@click.version_option(version=AGENT_VERSION)
def cli():
    """VC 투자 분석 에이전트 - 대화형 AI 분석 도구"""
    pass


@cli.command()
@click.option("--model", default="claude-opus-4-6", help="사용할 Claude 모델 (기본: Opus 4.5)")
@click.option(
    "--mode",
    type=click.Choice(["exit", "peer", "diagnosis", "report"], case_sensitive=False),
    default="exit",
    show_default=True,
    help="대화 모드",
)
def chat(model, mode):
    """대화형 모드로 에이전트와 소통"""

    click.echo("=" * 60)
    click.echo(f"VC Investment Agent - 대화형 모드 (mode: {mode})")
    click.echo("=" * 60)
    click.echo()

    try:
        agent = ConversationalVCAgent(model=model)
    except ValueError as e:
        click.echo(f"오류: {e}", err=True)
        click.echo()
        click.echo("설정 방법:")
        click.echo("1. .env 파일 생성:")
        click.echo('   echo "ANTHROPIC_API_KEY=your-key-here" > .env')
        click.echo()
        click.echo("2. 또는 환경변수 설정:")
        click.echo("   export ANTHROPIC_API_KEY=your-key-here")
        return

    click.echo("팁: 자연어로 질문하세요. 종료하려면 'exit' 입력")
    click.echo()

    async def run_chat():
        """비동기 채팅 루프"""
        while True:
            try:
                user_input = click.prompt("You", type=str)

                if user_input.lower() in ["exit", "quit", "종료"]:
                    click.echo("\n대화를 종료합니다.")
                    break

                if not user_input.strip():
                    continue

                # 에이전트 응답 스트리밍
                click.echo("Agent: ", nl=False)

                async for chunk in agent.chat(user_input, mode=mode):
                    click.echo(chunk, nl=False)
                click.echo()  # 줄바꿈
                click.echo()

            except KeyboardInterrupt:
                click.echo("\n\n대화를 종료합니다.")
                break
            except Exception as e:
                click.echo(f"\n오류 발생: {str(e)}", err=True)
                click.echo()

    # Python 3.10+ 호환: asyncio.run() 사용
    asyncio.run(run_chat())


@cli.command()
@click.option("--model", default="claude-opus-4-6", help="사용할 Claude 모델 (기본: Opus 4.5)")
@click.option("--language", default="Korean", show_default=True, help="응답 언어 (예: Korean, English)")
def critic(model, language):
    """근거/의견/피드백 비판을 포함하는 상호작용 에이전트"""

    click.echo("=" * 60)
    click.echo("Interactive Critic Agent - SDK 기반 대화형 모드")
    click.echo("=" * 60)
    click.echo()

    try:
        agent = InteractiveCriticAgent(model=model, response_language=language)
    except (ValueError, ImportError) as e:
        click.echo(f"오류: {e}", err=True)
        click.echo("claude-agent-sdk 설치 여부와 ANTHROPIC_API_KEY 설정을 확인하세요.")
        return

    click.echo("팁:")
    click.echo("  - 피드백 비판을 원하면 'feedback:'으로 시작하세요.")
    click.echo("  - 기록 초기화: 'reset'")
    click.echo("  - 종료: 'exit'")
    click.echo()

    async def run_chat():
        await agent.connect()
        while True:
            try:
                user_input = click.prompt("You", type=str)

                if user_input.lower() in ["exit", "quit", "종료"]:
                    click.echo("\n대화를 종료합니다.")
                    break

                if user_input.lower() in ["reset", "clear"]:
                    agent.reset()
                    click.echo("대화 기록을 초기화했습니다.\n")
                    continue

                if not user_input.strip():
                    continue

                click.echo("Agent: ", nl=False)
                async for chunk in agent.chat(user_input):
                    click.echo(chunk, nl=False)
                click.echo()
                click.echo()

            except KeyboardInterrupt:
                click.echo("\n\n대화를 종료합니다.")
                break
            except Exception as e:
                click.echo(f"\n오류 발생: {str(e)}", err=True)
                click.echo()

        await agent.close()

    asyncio.run(run_chat())


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--model", default="claude-opus-4-6", help="사용할 Claude 모델 (기본: Opus 4.5)")
@click.option(
    "--mode",
    type=click.Choice(["exit", "peer", "diagnosis", "report"], case_sensitive=False),
    default="exit",
    show_default=True,
    help="분석 모드",
)
def analyze(input_file, model, mode):
    """파일 빠른 분석"""

    click.echo(f"{input_file} 분석 중... (mode: {mode})")
    click.echo()

    # 파일을 temp 디렉토리로 복사 (보안 경로 제한 준수)
    success, temp_path, error = copy_to_temp(input_file)
    if not success:
        click.echo(f"오류: {error}", err=True)
        return

    click.echo(f"파일 준비 완료: {Path(temp_path).name}")

    try:
        agent = ConversationalVCAgent(model=model)
    except ValueError as e:
        click.echo(f"오류: {e}", err=True)
        return

    # 분석 요청 (temp 경로 사용)
    if mode == "diagnosis":
        prompt = (
            f"{temp_path} 파일을 분석하고 컨설턴트용 분석보고서 초안을 작성해줘. "
            "점수(문제/솔루션/사업화/자금조달/팀/조직/임팩트)와 근거도 함께 제시해줘."
        )
    elif mode == "report":
        prompt = (
            f"{temp_path} 파일을 분석하고 시장규모 근거를 추출해줘. "
            "인수인의견 스타일로 초안을 작성하고 확인 필요 항목도 정리해줘."
        )
    elif mode == "peer":
        prompt = f"{temp_path} 파일을 분석해줘"
    else:
        prompt = f"다음 파일을 분석하고 핵심 정보를 요약해줘: {temp_path}"

    click.echo("Agent: ")

    async def stream_response():
        async for chunk in agent.chat(prompt, mode=mode):
            click.echo(chunk, nl=False)
        click.echo()

    # Python 3.10+ 호환: asyncio.run() 사용
    asyncio.run(stream_response())


@cli.command()
@click.option("--model", default="claude-opus-4-6", help="사용할 Claude 모델 (기본: Opus 4.5)")
def test(model):
    """에이전트 연결 테스트"""

    click.echo("에이전트 연결 테스트 중...")

    try:
        agent = ConversationalVCAgent(model=model)
        click.echo(f"연결 성공! (모델: {model})")

        # 간단한 테스트
        click.echo("\n간단한 테스트:")
        response = agent.chat_sync("안녕? 간단히 자기소개해줘")
        click.echo(f"Agent: {response}")

    except ValueError as e:
        click.echo(f"연결 실패: {e}", err=True)
    except Exception as e:
        click.echo(f"오류: {str(e)}", err=True)


@cli.command()
@click.argument("goal_text", type=str)
@click.option("--file", "-f", help="엑셀 파일 경로")
@click.option("--params", "-p", help="추가 파라미터 (JSON 형식)")
@click.option("--model", default="claude-opus-4-6", help="사용할 Claude 모델 (기본: Opus 4.5)")
def goal(goal_text, file, params, model):
    """
    Goal 기반 자율 실행 (True Agent)

    Examples:
        vc-agent goal "투자 분석 완료" -f data.xlsx
        vc-agent goal "Exit 프로젝션 생성" -f data.xlsx -p '{"target_year": 2029}'
    """

    click.echo("=" * 60)
    click.echo("Autonomous VC Investment Agent")
    click.echo("=" * 60)
    click.echo()

    try:
        from agent.autonomous_agent import AutonomousVCAgent
        agent = AutonomousVCAgent(model=model)
    except (ImportError, ValueError) as e:
        click.echo(f"오류: {e}", err=True)
        if isinstance(e, ImportError):
            click.echo("claude-agent-sdk 설치 여부를 확인하세요.")
        return

    # 컨텍스트 구성
    context = {}
    if file:
        # 파일을 temp 디렉토리로 복사 (보안 경로 제한 준수)
        success, temp_path, error = copy_to_temp(file)
        if not success:
            click.echo(f"파일 오류: {error}", err=True)
            return
        click.echo(f"파일 준비 완료: {Path(temp_path).name}")
        context["excel_file"] = temp_path
    if params:
        import json
        try:
            additional_params = json.loads(params)
            context.update(additional_params)
        except json.JSONDecodeError:
            click.echo("파라미터 JSON 파싱 실패, 무시합니다", err=True)

    # Goal 실행
    async def run_goal():
        result = await agent.achieve_goal(
            goal=goal_text,
            context=context,
            verbose=True
        )

        # 결과 출력
        click.echo("\n" + "=" * 60)
        click.echo("실행 결과")
        click.echo("=" * 60)

        if result['achieved']:
            click.echo("Goal 달성!")
        else:
            click.echo("Goal 부분 달성")

        click.echo(f"\n응답 요약:")
        click.echo(f"  총 {len(result['response'])} 자의 응답을 생성했습니다.")
        click.echo(f"  {len(result['messages'])} 개의 메시지를 교환했습니다.")

    # Python 3.10+ 호환: asyncio.run() 사용
    asyncio.run(run_goal())


@cli.command()
def info():
    """에이전트 정보 표시"""

    click.echo("=" * 60)
    click.echo("VC Investment Agent v0.1.0 (True Agent)")
    click.echo("=" * 60)
    click.echo()
    click.echo("설명:")
    click.echo("  VC 투자 분석 및 Exit 프로젝션 자동화 AI 에이전트")
    click.echo("  Goal을 제시하면 자율적으로 계획하고 실행합니다")
    click.echo()
    click.echo("주요 기능:")
    click.echo("  - 투자 검토 엑셀 파일 자동 분석")
    click.echo("  - 다양한 Exit 시나리오 시뮬레이션")
    click.echo("  - PER, EV/Revenue, IRR, 멀티플 계산")
    click.echo("  - SAFE 전환, 콜옵션, 지분 희석 분석")
    click.echo("  - 맞춤형 Exit 프로젝션 엑셀 생성")
    click.echo()
    click.echo("사용법:")
    click.echo('  vc-agent goal "투자 분석 완료" -f file.xlsx  # 자율 실행')
    click.echo("  vc-agent chat                                 # 대화형 모드")
    click.echo("  vc-agent analyze FILE                         # 파일 분석")
    click.echo("  vc-agent test                                 # 연결 테스트")
    click.echo()
    click.echo("문서:")
    click.echo("  - QUICKSTART.md - 시작 가이드")
    click.echo("  - TRUE_AGENT_DESIGN.md - True Agent 설계")
    click.echo("  - AGENT_SDK_DESIGN.md - SDK 아키텍처")
    click.echo()


if __name__ == "__main__":
    cli()
