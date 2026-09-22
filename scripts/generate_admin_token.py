"""운영자 업로드 API 토큰 생성기.

이 스크립트를 실행하면 안전한 난수 토큰을 생성해서 출력합니다.
생성된 값을 그대로 복사해서 다음 두 곳에만 붙여넣으세요. 절대 코드/저장소에 넣지 마세요.

  1) Railway 프로젝트 → Variables → ADMIN_UPLOAD_TOKEN
  2) 도서관 PC 갱신 프로그램의 환경변수 또는 OS 자격 증명 관리자

실행:
    python scripts/generate_admin_token.py
"""
import secrets


def generate_token(num_bytes: int = 32) -> str:
    """URL-safe, 32바이트(256비트) 기본 난수 토큰. secrets 모듈은 암호학적으로 안전합니다."""
    return secrets.token_urlsafe(num_bytes)


if __name__ == "__main__":
    token = generate_token()
    print("새 운영자 업로드 토큰이 생성되었습니다.")
    print()
    print(token)
    print()
    print("이 값을 Railway Variables의 ADMIN_UPLOAD_TOKEN에 그대로 등록하세요.")
    print("이 창을 닫으면 다시 볼 수 없으니 지금 바로 복사해두세요.")
