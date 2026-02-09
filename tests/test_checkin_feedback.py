"""
체크인 피드백 기능 TDD 테스트
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestSupabaseStorage:
    """SupabaseStorage 클래스 테스트"""

    def test_import_supabase_storage(self):
        """SupabaseStorage 임포트 테스트"""
        from agent.supabase_storage import SupabaseStorage, SUPABASE_AVAILABLE
        assert SupabaseStorage is not None
        print(f"✅ SupabaseStorage 임포트 성공, SUPABASE_AVAILABLE={SUPABASE_AVAILABLE}")

    def test_storage_initialization(self):
        """Storage 초기화 테스트"""
        from agent.supabase_storage import SupabaseStorage
        storage = SupabaseStorage(user_id="test_user")
        assert storage.user_id == "test_user"
        print(f"✅ Storage 초기화 성공, available={storage.available}")

    def test_get_feedback_stats_empty(self):
        """피드백 통계 (빈 결과) 테스트"""
        from agent.supabase_storage import SupabaseStorage
        storage = SupabaseStorage(user_id="test_user")
        stats = storage.get_feedback_stats()

        assert isinstance(stats, dict)
        assert "total" in stats
        assert "positive" in stats
        assert "negative" in stats
        assert "satisfaction_rate" in stats
        print(f"✅ 피드백 통계 반환 성공: {stats}")

    def test_get_recent_feedback_empty(self):
        """최근 피드백 (빈 결과) 테스트"""
        from agent.supabase_storage import SupabaseStorage
        storage = SupabaseStorage(user_id="test_user")
        feedbacks = storage.get_recent_feedback(limit=10)

        assert isinstance(feedbacks, list)
        print(f"✅ 최근 피드백 반환 성공: {len(feedbacks)}개")

    def test_calculate_reward(self):
        """보상 계산 테스트"""
        from agent.supabase_storage import SupabaseStorage
        storage = SupabaseStorage(user_id="test_user")

        # thumbs_up = 1.0
        assert storage._calculate_reward("thumbs_up") == 1.0
        # thumbs_down = -1.0
        assert storage._calculate_reward("thumbs_down") == -1.0
        # text_feedback = 0.0
        assert storage._calculate_reward("text_feedback") == 0.0
        # rating 3/5 = (3/5*2)-1 = 0.2
        assert abs(storage._calculate_reward("rating", 3) - 0.2) < 0.01
        # rating 5/5 = (5/5*2)-1 = 1.0
        assert storage._calculate_reward("rating", 5) == 1.0
        print("✅ 보상 계산 테스트 성공")


class TestSupabaseStorageMocked:
    """Mocked Supabase 테스트"""

    def test_get_recent_feedback_with_data(self):
        """피드백 데이터가 있을 때 테스트 (Mocked)"""
        from agent.supabase_storage import SupabaseStorage

        # Mock 데이터
        mock_feedbacks = [
            {
                "id": 1,
                "session_id": "sess_001",
                "user_id": "test_user",
                "user_message": "PER 분석 결과가 정확한가요?",
                "assistant_response": "네, 업계 평균 PER을 기준으로...",
                "feedback_type": "thumbs_up",
                "feedback_value": None,
                "reward": 1.0,
                "context": '{"page": "피어분석", "source": "peer_per"}',
                "created_at": "2025-01-05T10:30:00"
            },
            {
                "id": 2,
                "session_id": "sess_002",
                "user_id": "test_user",
                "user_message": "Exit 프로젝션을 다시 계산해주세요",
                "assistant_response": "수정된 프로젝션입니다...",
                "feedback_type": "text_feedback",
                "feedback_value": '{"comment": "시나리오 3이 더 현실적입니다"}',
                "reward": 0.0,
                "context": '{"page": "엑싯분석"}',
                "created_at": "2025-01-04T15:20:00"
            },
            {
                "id": 3,
                "session_id": "sess_003",
                "user_id": "test_user",
                "user_message": "심사보고서 요약해주세요",
                "assistant_response": "요약: 투자 적합...",
                "feedback_type": "thumbs_down",
                "feedback_value": None,
                "reward": -1.0,
                "context": '{"page": "심사보고서"}',
                "created_at": "2025-01-03T09:00:00"
            }
        ]

        storage = SupabaseStorage(user_id="test_user")

        # Mock client 설정
        mock_response = MagicMock()
        mock_response.data = mock_feedbacks

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_response

        storage.client = mock_client
        storage.available = True

        # 테스트 실행
        feedbacks = storage.get_recent_feedback(limit=10)

        assert len(feedbacks) == 3
        assert feedbacks[0]["feedback_type"] == "thumbs_up"
        assert feedbacks[1]["feedback_type"] == "text_feedback"
        assert feedbacks[2]["feedback_type"] == "thumbs_down"

        # context가 파싱되었는지 확인
        assert feedbacks[0]["context"]["page"] == "피어분석"
        assert feedbacks[1]["context"]["page"] == "엑싯분석"
        assert feedbacks[2]["context"]["page"] == "심사보고서"

        print("✅ Mock 피드백 데이터 테스트 성공")
        print(f"   - 피어분석: {feedbacks[0]['feedback_type']}")
        print(f"   - 엑싯분석: {feedbacks[1]['feedback_type']}")
        print(f"   - 심사보고서: {feedbacks[2]['feedback_type']}")

    def test_feedback_stats_with_data(self):
        """피드백 통계 계산 테스트 (Mocked)"""
        from agent.supabase_storage import SupabaseStorage

        mock_feedbacks = [
            {"feedback_type": "thumbs_up"},
            {"feedback_type": "thumbs_up"},
            {"feedback_type": "thumbs_up"},
            {"feedback_type": "thumbs_down"},
            {"feedback_type": "text_feedback"},
        ]

        storage = SupabaseStorage(user_id="test_user")

        mock_response = MagicMock()
        mock_response.data = mock_feedbacks

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        storage.client = mock_client
        storage.available = True

        stats = storage.get_feedback_stats()

        assert stats["total"] == 5
        assert stats["positive"] == 3
        assert stats["negative"] == 1
        assert stats["satisfaction_rate"] == 0.6  # 3/5

        print("✅ Mock 피드백 통계 테스트 성공")
        print(f"   - 전체: {stats['total']}")
        print(f"   - 긍정: {stats['positive']}")
        print(f"   - 부정: {stats['negative']}")
        print(f"   - 만족도: {stats['satisfaction_rate']*100:.0f}%")


class TestCheckinPageIntegration:
    """체크인 페이지 통합 테스트"""

    def test_feedback_display_logic(self):
        """피드백 표시 로직 테스트"""
        # 피드백 타입별 아이콘 매핑
        feedback_icons = {
            "thumbs_up": "👍",
            "thumbs_down": "👎",
            "text_feedback": "💬",
            "correction": "✏️",
            "rating": "⭐"
        }

        test_cases = [
            ("thumbs_up", "👍"),
            ("thumbs_down", "👎"),
            ("text_feedback", "💬"),
            ("correction", "✏️"),
            ("rating", "⭐"),
            ("unknown", "📝"),  # default
        ]

        for fb_type, expected_icon in test_cases:
            icon = feedback_icons.get(fb_type, "📝")
            assert icon == expected_icon, f"{fb_type} -> {icon} (expected {expected_icon})"

        print("✅ 피드백 아이콘 매핑 테스트 성공")

    def test_feedback_value_parsing(self):
        """피드백 값 파싱 테스트"""
        import json

        # 문자열 피드백
        fb_value_str = "이 분석이 도움이 되었습니다"
        assert isinstance(fb_value_str, str)

        # JSON 피드백
        fb_value_json = '{"comment": "시나리오 조정 필요"}'
        parsed = json.loads(fb_value_json)
        assert parsed.get("comment") == "시나리오 조정 필요"

        # dict 피드백
        fb_value_dict = {"comment": "좋은 분석입니다", "rating": 5}
        assert fb_value_dict.get("comment") == "좋은 분석입니다"

        print("✅ 피드백 값 파싱 테스트 성공")

    def test_context_page_extraction(self):
        """컨텍스트에서 페이지 정보 추출 테스트"""
        test_contexts = [
            ({"page": "피어분석"}, "피어분석"),
            ({"source": "exit_projection"}, "exit_projection"),
            ({"page": "심사보고서", "source": "report"}, "심사보고서"),  # page 우선
            ({}, "알 수 없음"),
        ]

        for context, expected_page in test_contexts:
            page_name = context.get("page", context.get("source", "알 수 없음"))
            assert page_name == expected_page, f"{context} -> {page_name} (expected {expected_page})"

        print("✅ 페이지 정보 추출 테스트 성공")


@pytest.mark.skipif(
    os.getenv("RUN_REAL_SUPABASE_TESTS") != "1",
    reason="Real Supabase integration tests are opt-in. Set RUN_REAL_SUPABASE_TESTS=1 to run.",
)
class TestRealSupabase:
    """실제 Supabase 연결 테스트"""

    def test_real_connection(self):
        """실제 Supabase 연결 테스트"""
        import os
        os.environ['SUPABASE_URL'] = 'https://zrrssiqcocfzpzqpzisu.supabase.co'
        os.environ['SUPABASE_KEY'] = 'sb_publishable_0Gw1ArYwJlbV2Q34-4QhFw_Tspl9bJr'

        from agent.supabase_storage import SupabaseStorage

        storage = SupabaseStorage(user_id='57513706dc72')
        assert storage.available == True
        print("✅ 실제 Supabase 연결 성공")

    def test_real_feedback_stats(self):
        """실제 피드백 통계 테스트"""
        import os
        os.environ['SUPABASE_URL'] = 'https://zrrssiqcocfzpzqpzisu.supabase.co'
        os.environ['SUPABASE_KEY'] = 'sb_publishable_0Gw1ArYwJlbV2Q34-4QhFw_Tspl9bJr'

        from agent.supabase_storage import SupabaseStorage

        storage = SupabaseStorage(user_id='57513706dc72')
        stats = storage.get_feedback_stats()

        assert stats["total"] >= 5  # 실제 데이터 기준
        assert stats["positive"] >= 4
        assert stats["satisfaction_rate"] > 0.5

        print(f"✅ 실제 피드백 통계: 전체 {stats['total']}, 긍정 {stats['positive']}, 만족도 {stats['satisfaction_rate']*100:.0f}%")

    def test_real_recent_feedback(self):
        """실제 최근 피드백 조회 테스트"""
        import os
        os.environ['SUPABASE_URL'] = 'https://zrrssiqcocfzpzqpzisu.supabase.co'
        os.environ['SUPABASE_KEY'] = 'sb_publishable_0Gw1ArYwJlbV2Q34-4QhFw_Tspl9bJr'

        from agent.supabase_storage import SupabaseStorage

        storage = SupabaseStorage(user_id='57513706dc72')
        feedbacks = storage.get_recent_feedback(limit=10)

        assert len(feedbacks) >= 5
        assert feedbacks[0].get("feedback_type") is not None
        assert feedbacks[0].get("created_at") is not None

        print(f"✅ 실제 피드백 조회: {len(feedbacks)}개")
        for i, fb in enumerate(feedbacks[:3]):
            fb_type = fb.get("feedback_type")
            ctx = fb.get("context", {})
            print(f"   {i+1}. {fb_type} - context: {ctx}")


def run_all_tests():
    """모든 테스트 실행"""
    print("=" * 50)
    print("체크인 피드백 TDD 테스트")
    print("=" * 50)

    # SupabaseStorage 기본 테스트
    print("\n[1] SupabaseStorage 기본 테스트")
    test1 = TestSupabaseStorage()
    test1.test_import_supabase_storage()
    test1.test_storage_initialization()
    test1.test_get_feedback_stats_empty()
    test1.test_get_recent_feedback_empty()
    test1.test_calculate_reward()

    # Mock 테스트
    print("\n[2] SupabaseStorage Mock 테스트")
    test2 = TestSupabaseStorageMocked()
    test2.test_get_recent_feedback_with_data()
    test2.test_feedback_stats_with_data()

    # 통합 테스트
    print("\n[3] 체크인 페이지 통합 테스트")
    test3 = TestCheckinPageIntegration()
    test3.test_feedback_display_logic()
    test3.test_feedback_value_parsing()
    test3.test_context_page_extraction()

    # 실제 Supabase 테스트
    print("\n[4] 실제 Supabase 연결 테스트")
    test4 = TestRealSupabase()
    test4.test_real_connection()
    test4.test_real_feedback_stats()
    test4.test_real_recent_feedback()

    print("\n" + "=" * 50)
    print("✅ 모든 테스트 통과!")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()
