# 용산꿈나무도서관 AI 혼잡도 안내 API (운영자 업로드 포함, Railway 배포용)

DB 없이 `records.json`(공용 표준 스키마) 기반으로 동작하는 FastAPI 백엔드입니다.
공개 조회 API(`/meta`, `/congestion/today`, `/stats`)와 운영자 전용 업로드 API
(`/admin/records`)를 함께 제공합니다.

## 1. 운영자 토큰 생성 (제일 먼저 하세요)

```bash
python scripts/generate_admin_token.py
```

출력된 토큰을 복사해서 **Railway 프로젝트 → Variables → `ADMIN_UPLOAD_TOKEN`** 에
등록하세요. 코드/저장소 어디에도 이 값을 적지 마세요. 도서관 PC의 갱신
프로그램에도 같은 값을 환경변수나 OS 자격 증명 관리자에 저장해서 씁니다.

토큰을 새로 발급하면 예전 토큰은 즉시 무효가 됩니다 (서버가 환경변수 하나만
비교하는 구조라서요). 유출이 의심되면 스크립트를 다시 실행해서 Railway
Variables 값만 교체하면 됩니다.

## 2. 로컬 실행

```bash
pip install -r requirements.txt
export ADMIN_UPLOAD_TOKEN=<generate_admin_token.py로 만든 값>   # Windows: set ADMIN_UPLOAD_TOKEN=...
uvicorn app.main:app --reload
```

`http://localhost:8000/docs`에서 Swagger UI로 바로 테스트할 수 있습니다.

## 3. Railway 배포

- 이 저장소를 Railway 프로젝트에 연결
- Variables에 `ADMIN_UPLOAD_TOKEN` 등록
- **Volume을 `data/` 경로에 마운트** — 안 하면 재배포/재시작 때마다
  `records.json`, 백업, 업로드 로그가 전부 사라집니다
- 시작 명령: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## 프로젝트 구조

```
app/
  core/
    config.py      # library_name, operating_hours, 혼잡도 경계, 경로, 업로드 토큰
    errors.py       # 공통 오류 응답 + 코드별 상태코드 매핑
    admin_auth.py   # 운영자 토큰 검증
  models/
    schemas.py      # RecordItem + 6절 API 응답 스키마
  services/
    validation.py    # records 검증 (하드 실패 vs 품질 경고 구분)
    records_store.py # records.json 원자적 교체 + 백업
    upload_log.py     # 업로드 CSV 로그
    aggregation.py     # 시간대 집계, baseline, 휴관일 판정
    congestion.py       # T04 혼잡도 판정 (midrank 백분위, 35/70 경계)
  routers/
    congestion.py  # GET /api/v1/congestion/today
    stats.py        # GET /api/v1/stats?date=
    meta.py          # GET /api/v1/meta
    admin.py          # POST /api/v1/admin/records
scripts/
  generate_admin_token.py  # 운영자 토큰 생성기
```

## API

### `GET /api/v1/meta`, `GET /api/v1/congestion/today`, `GET /api/v1/stats?date=`

전달하신 6절 규격 그대로 응답합니다. `data_status`는 `forecast` / `partial` /
`actual` / `closed`를 씁니다. 휴관일은 레코드에 `is_closed_day: true`가 있거나
`app/services/aggregation.py`의 `CLOSED_DATES` 집합에 날짜를 추가해서 지정합니다.

### `POST /api/v1/admin/records` (운영자 전용)

**Header**
```
Authorization: Bearer <ADMIN_UPLOAD_TOKEN>
Content-Type: application/json
```

**Body**: records 배열 그 자체 (12개 필수 필드 + 선택 품질 필드).

```json
[
  {
    "date": "2026-09-14", "day_of_week": "Mon", "gate": "front",
    "gate_name": "자료실.정문", "passage_id": "10.10.2.37A", "hour": 10,
    "in_count": 12, "out_count": 8, "total_in": 120, "total_out": 90,
    "is_partial": false, "source_file": "records-20260914.json"
  }
]
```

**성공 응답 (200)**
```json
{
  "accepted": true,
  "record_count": 1,
  "previous_backup": "records_20260914T090000000000Z.json",
  "warnings": [],
  "uploaded_at": "2026-09-14T00:00:00.000000+00:00"
}
```

`warnings`는 `HOURLY_TOTAL_MISMATCH`류 품질 경고(시간대 합계 ≠ 일일 총량)를
담습니다 — **업로드 자체는 막지 않습니다.**

**오류 코드**

| code | status | 상황 |
|---|---|---|
| `DATA_NOT_FOUND` | 404 | (조회 API) 해당 날짜 데이터 없음 |
| `INVALID_DATE` | 400 | 날짜 형식 오류 |
| `PROCESSING_ERROR` | 422 | records 필드/타입/범위 오류, 요일 불일치, 빈 배열 |
| `GATE_ROW_DUPLICATED` | 422 | 같은 date+gate+hour 중복 — **업로드 전체 거부** |
| `UNAUTHORIZED` | 401 | 토큰 없음/불일치/서버 미설정 |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Content-Type이 application/json 아님 |
| `PAYLOAD_TOO_LARGE` | 413 | 요청 크기 5MB 초과 |
| `INVALID_JSON` | 400 | JSON 파싱 실패 |

하드 실패 코드(`PROCESSING_ERROR`, `GATE_ROW_DUPLICATED` 등)가 나면 기존
`records.json`은 전혀 건드리지 않습니다.

## 동작 방식

1. 토큰 검증 (`hmac.compare_digest`, 타이밍 공격 방지)
2. Content-Type / 크기(5MB) 확인
3. `utf-8-sig`로 디코드 후 JSON 파싱
4. 스키마 검증 — 필드/타입/범위, day_of_week가 실제 요일과 일치하는지,
   date+gate+hour 중복 여부(`GATE_ROW_DUPLICATED`)는 하드 실패.
   시간대 합계 vs 일일 총량 불일치(`HOURLY_TOTAL_MISMATCH`류)는 경고로만 수집.
5. 통과 시: 기존 파일 백업(`data/backups/`) → `.tmp.json`에 기록(`fsync`) →
   `os.replace()`로 원자적 교체 (락으로 동시 업로드 직렬화)
6. 모든 시도를 `data/logs/upload_log.csv`에 기록

## 실제로 검증한 것

- `python scripts/generate_admin_token.py`로 만든 토큰으로 인증 성공/실패 확인
- 정상 업로드 → 200, `records.json` 교체 + 백업 생성 + 로그 기록
- 인증 없음/틀린 토큰 → 401, 파일 안 건드림
- day_of_week 불일치 → 422, 파일 안 건드림
- 같은 date+gate+hour 중복 → `GATE_ROW_DUPLICATED` 422
- hour 범위 밖 → 422
- 빈 배열 → 422 (전체 데이터 삭제 방지)
- Content-Type 틀림 → 415
- `/meta`가 정확히 요청하신 JSON 형태(operating_hours 포함)로 응답
- `/congestion/today`, `/stats`가 baseline/증감률/혼잡도까지 정상 계산
- 없는 날짜 조회 → `DATA_NOT_FOUND`, 잘못된 날짜 형식 → `INVALID_DATE`
