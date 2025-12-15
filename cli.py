#!/usr/bin/env python3
"""
VC Investment Agent - CLI Interface
"""

import asyncio
import click
from pathlib import Path

from agent import ConversationalVCAgent
from agent.autonomous_agent import AutonomousVCAgent


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """VC 투자 분석 에이전트 - 대화형 AI 분석 도구"""
    pass


@cli.command()
@click.option("--model", default="claude-opus-4-5-20251101", help="사용할 Claude 모델 (기본: Opus 4.5)")
def chat(model):
    """대화형 모드로 에이전트와 소통"""

    click.echo("=" * 60)
    click.echo("🤖 VC Investment Agent - 대화형 모드")
    click.echo("=" * 60)
    click.echo()

    try:
        agent = ConversationalVCAgent(model=model)
    except ValueError as e:
        click.echo(f"❌ 오류: {e}", err=True)
        click.echo()
        click.echo("설정 방법:")
        click.echo("1. .env 파일 생성:")
        click.echo('   echo "ANTHROPIC_API_KEY=your-key-here" > .env')
        click.echo()
        click.echo("2. 또는 환경변수 설정:")
        click.echo("   export ANTHROPIC_API_KEY=your-key-here")
        return

    click.echo("💡 팁: 자연어로 질문하세요. 종료하려면 'exit' 입력")
    click.echo()

    # 비동기 이벤트 루프
    loop = asyncio.get_event_loop()

    while True:
        try:
            user_input = click.prompt("You", type=str)

            if user_input.lower() in ["exit", "quit", "종료"]:
                click.echo("\n👋 대화를 종료합니다.")
                break

            if not user_input.strip():
                continue

            # 에이전트 응답 스트리밍
            click.echo("Agent: ", nl=False)

            async def stream_response():
                async for chunk in agent.chat(user_input):
                    click.echo(chunk, nl=False)
                click.echo()  # 줄바꿈

            loop.run_until_complete(stream_response())
            click.echo()

        except KeyboardInterrupt:
            click.echo("\n\n👋 대화를 종료합니다.")
            break
        except Exception as e:
            click.echo(f"\n❌ 오류 발생: {str(e)}", err=True)
            click.echo()


@cli.command()
@click.argument("excel_file", type=click.Path(exists=True))
@click.option("--model", default="claude-opus-4-5-20251101", help="사용할 Claude 모델 (기본: Opus 4.5)")
def analyze(excel_file, model):
    """엑셀 파일 빠른 분석"""

    click.echo(f"📊 {excel_file} 분석 중...")
    click.echo()

    try:
        agent = ConversationalVCAgent(model=model)
    except ValueError as e:
        click.echo(f"❌ 오류: {e}", err=True)
        return

    # 분석 요청
    prompt = f"다음 파일을 분석하고 핵심 정보를 요약해줘: {excel_file}"

    click.echo("Agent: ")

    async def stream_response():
        async for chunk in agent.chat(prompt):
            click.echo(chunk, nl=False)
        click.echo()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(stream_response())


@cli.command()
@click.option("--model", default="claude-opus-4-5-20251101", help="사용할 Claude 모델 (기본: Opus 4.5)")
def test(model):
    """에이전트 연결 테스트"""

    click.echo("🔌 에이전트 연결 테스트 중...")

    try:
        agent = ConversationalVCAgent(model=model)
        click.echo(f"✅ 연결 성공! (모델: {model})")

        # 간단한 테스트
        click.echo("\n간단한 테스트:")
        response = agent.chat_sync("안녕? 간단히 자기소개해줘")
        click.echo(f"Agent: {response}")

    except ValueError as e:
        click.echo(f"❌ 연결 실패: {e}", err=True)
    except Exception as e:
        click.echo(f"❌ 오류: {str(e)}", err=True)


@cli.command()
@click.argument("goal_text", type=str)
@click.option("--file", "-f", help="엑셀 파일 경로")
@click.option("--params", "-p", help="추가 파라미터 (JSON 형식)")
@click.option("--model", default="claude-opus-4-5-20251101", help="사용할 Claude 모델 (기본: Opus 4.5)")
def goal(goal_text, file, params, model):
    """
    🎯 Goal 기반 자율 실행 (True Agent)

    Examples:
        vc-agent goal "투자 분석 완료" -f data.xlsx
        vc-agent goal "Exit 프로젝션 생성" -f data.xlsx -p '{"target_year": 2029}'
    """

    click.echo("=" * 60)
    click.echo("🤖 Autonomous VC Investment Agent")
    click.echo("=" * 60)
    click.echo()

    try:
        agent = AutonomousVCAgent(model=model)
    except ValueError as e:
        click.echo(f"❌ 오류: {e}", err=True)
        return

    # 컨텍스트 구성
    context = {}
    if file:
        context["excel_file"] = file
    if params:
        import json
        try:
            additional_params = json.loads(params)
            context.update(additional_params)
        except json.JSONDecodeError:
            click.echo("⚠️  파라미터 JSON 파싱 실패, 무시합니다", err=True)

    # Goal 실행
    async def run_goal():
        result = await agent.achieve_goal(
            goal=goal_text,
            context=context,
            verbose=True
        )

        # 결과 출력
        click.echo("\n" + "=" * 60)
        click.echo("📊 실행 결과")
        click.echo("=" * 60)

        if result['achieved']:
            click.echo("✅ Goal 달성!")
        else:
            click.echo("⚠️  Goal 부분 달성")

        click.echo(f"\n📝 응답 요약:")
        click.echo(f"  총 {len(result['response'])} 자의 응답을 생성했습니다.")
        click.echo(f"  {len(result['messages'])} 개의 메시지를 교환했습니다.")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_goal())


@cli.command()
def info():
    """에이전트 정보 표시"""

    click.echo("=" * 60)
    click.echo("VC Investment Agent v0.1.0 (True Agent)")
    click.echo("=" * 60)
    click.echo()
    click.echo("📝 설명:")
    click.echo("  VC 투자 분석 및 Exit 프로젝션 자동화 AI 에이전트")
    click.echo("  Goal을 제시하면 자율적으로 계획하고 실행합니다")
    click.echo()
    click.echo("🛠️  주요 기능:")
    click.echo("  • 투자 검토 엑셀 파일 자동 분석")
    click.echo("  • 다양한 Exit 시나리오 시뮬레이션")
    click.echo("  • PER, EV/Revenue, IRR, 멀티플 계산")
    click.echo("  • SAFE 전환, 콜옵션, 지분 희석 분석")
    click.echo("  • 맞춤형 Exit 프로젝션 엑셀 생성")
    click.echo()
    click.echo("💬 사용법:")
    click.echo("  vc-agent goal \"투자 분석 완료\" -f file.xlsx  # 🆕 자율 실행")
    click.echo("  vc-agent chat                                 # 대화형 모드")
    click.echo("  vc-agent analyze FILE                         # 파일 분석")
    click.echo("  vc-agent test                                 # 연결 테스트")
    click.echo()
    click.echo("📚 문서:")
    click.echo("  • QUICKSTART.md - 시작 가이드")
    click.echo("  • TRUE_AGENT_DESIGN.md - True Agent 설계")
    click.echo("  • AGENT_SDK_DESIGN.md - SDK 아키텍처")
    click.echo()


if __name__ == "__main__":
    cli()
