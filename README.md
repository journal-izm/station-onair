# 📺 station-onair — 방송국 서버 (M·K 공용)

> AI 실시간 개표방송 시스템 · P1 팀 프로젝트

선관위 개표 데이터를 받아 이벤트를 감지하고, AI 기사 초안 → 기자 송고 → 데스크 승인을 거친 기사를 실시간 개표 웹과 20분 개표방송(AI 앵커 TTS + 지역 차트)으로 내보내는 서버입니다. M·K 방송국이 같은 코드를 설정(STATION_CODE)만 바꿔 실행합니다.

<p align="center"><img src="docs/img/station-onair_context.png" alt="전체 시스템에서 이 저장소의 위치" width="100%"></p>
<p align="center"><sub>전체 시스템에서 이 저장소의 위치</sub></p>

| 항목 | 내용 |
|---|---|
| 포트 | 8101 (M) · 8102 (K) |
| 맡는 영역 | 01 계정·인증, 03 방송국 개표 수신, 04 기사 자동 생성·송고, 05 데스크 승인·출고, 06 실시간 개표 웹, 07 개표 방송 송출 |
| 연결 저장소 | [nec-server](https://github.com/journal-izm/nec-server) |
| 전체 설계 | [election-onair](https://github.com/journal-izm/election-onair) |
| 설계 문서 폴더 | [Google Drive](https://drive.google.com/drive/folders/1nlaKXMnq60aUp-fv0_Upej-j6IBgHbLX) |
| 규모 | 요구 26 · 기능 22 · 화면 10 · API 22 · 테이블 15 |

## 🤝 API 계약 (두 저장소를 잇는 약속)

| API | 경로 | 제공 | 호출 |
|---|---|---|---|
| API-02-01 | `GET /nec/v1/elections/{electionId}` | nec-server | station-onair (M·K) |
| API-02-02 | `GET /nec/v1/elections/{electionId}/results?since_seq={n}` | nec-server | station-onair (M·K) |

이 형식을 바꾸는 PR은 상대 저장소 담당자의 확인을 받습니다.

## 🚀 실행

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # 값 채우기
python seed.py
uvicorn app.main:app --port 8101 --env-file .env.m   # M 방송국
uvicorn app.main:app --port 8102 --env-file .env.k   # K 방송국 (nec-server 먼저 실행)
```

## 📌 번호 체계

가운데 두 자리(영역 코드)가 같으면 같은 기능 묶음입니다. 번호는 전체 설계(election-onair)와 같습니다.

<p align="center"><img src="docs/img/station-onair_numbering.png" alt="이 저장소의 번호 범위" width="100%"></p>
<p align="center"><sub>이 저장소의 번호 범위</sub></p>

## 📚 설계 문서 8종

<details>
<summary><b>01 · 기획서 — 역할·범위·API 계약·일정</b></summary>

📄 원본: [Google Docs](https://docs.google.com/document/d/1KKLlXCzK7X0JBv-FClsOwtKQwVjJ1mH0jadzHJrBcfY/edit) · [Word 파일](docs/01_기획서_station-onair.docx)

### 범위
| 포함 | 제외 (nec-server 담당) |
|---|---|
| 기자 3·데스크 2 계정, 역할별 접근 | 선거 원천 데이터 보관 |
| 선관위 데이터 5초 수신·이벤트 감지 | 개표 집계 생성·시뮬레이터 |
| AI 기사 초안(LLM + RAG)·송고·승인 | 방송국 API 키 발급 |
| 실시간 개표 웹, 20분 송출 화면, TTS |  |

### 20분 방송 구성
<p align="center"><img src="docs/img/cuesheet.png" alt="20분 큐시트" width="100%"></p>
<p align="center"><sub>20분 큐시트</sub></p>

### 지켜야 할 원칙
- **사람 검수**: 기자 송고 + 데스크 승인 없이 웹·방송에 나가지 않는다 (NFR-03)
- **근거 표시**: 기사를 만든 이벤트·개표 수치를 함께 보여 준다
- **시점 표기**: ‘개표율 50% 시점’처럼 기준 시점을 쓴다

### 일정
<p align="center"><img src="docs/img/schedule.png" alt="P1 일정" width="100%"></p>
<p align="center"><sub>P1 일정</sub></p>


</details>

<details>
<summary><b>02 · 요구사항정의서 — 요구 26개와 추적표</b></summary>

📄 원본: [Google Docs](https://docs.google.com/document/d/1sFmb71wlfMpqxI_mKG-STgbYMIWIgmCB3wKnPhhu5qI/edit) · [Word 파일](docs/02_요구사항정의서_station-onair.docx)

### 영역 01 · 계정·인증
| 요구 ID | 요구사항명 | 내용 | 우선순위 | 관련 기능 |
|---|---|---|---|---|
| REQ-01-01 | 고정 계정 운영 | 회원가입 없이 기자 3개(reporter1~3)·데스크 2개(desk1~2) 계정만 미리 만들어 둔다. | 필수 | FN-01-01 |
| REQ-01-02 | 역할별 접근 제어 | 기자는 기사 작성·송고 화면만, 데스크는 승인·송출 제어 화면만 쓸 수 있다. | 필수 | FN-01-01 FN-01-02 |

### 영역 03 · 방송국 개표 수신
| 요구 ID | 요구사항명 | 내용 | 우선순위 | 관련 기능 |
|---|---|---|---|---|
| REQ-03-01 | 주기적 개표 수신 | M·K 방송국 서버는 5초마다 선관위 변경분을 받아 각자의 DB에 저장한다. | 필수 | FN-03-01 |
| REQ-03-02 | 개표 이벤트 감지 | 개표율 구간 돌파·1위 변동·당선 유력/확실/확정을 감지해 이벤트로 기록한다. | 필수 | FN-03-02 |
| REQ-03-03 | 수신 상태 확인 | 마지막 수신 시각·실패 횟수를 보여 주고, 실패하면 자동으로 다시 시도한다. | 권장 | FN-03-03 |

### 영역 04 · 기사 자동 생성·송고
| 요구 ID | 요구사항명 | 내용 | 우선순위 | 관련 기능 |
|---|---|---|---|---|
| REQ-04-01 | 기사 초안 자동 생성 | 이벤트가 생기면 개표 수치와 후보 이력·공약(RAG)으로 기사 초안을 자동 생성한다. | 필수 | FN-04-01 |
| REQ-04-02 | 방송 원고 동시 생성 | 웹 기사 본문과 함께 AI 앵커가 읽을 짧은 방송 원고(20~30초 분량)를 만든다. | 필수 | FN-04-01 |
| REQ-04-03 | 기자 자동 배정 | 생성된 초안은 기자 3명에게 차례로 자동 배정된다. | 필수 | FN-04-02 FN-04-03 |
| REQ-04-04 | 기사 수정·송고 | 기자는 초안을 확인·수정한 뒤 데스크로 송고한다. 반려 기사는 다시 고쳐 송고할 수 있다. | 필수 | FN-04-03 FN-04-04 FN-04-05 |

### 영역 05 · 데스크 승인·출고
| 요구 ID | 요구사항명 | 내용 | 우선순위 | 관련 기능 |
|---|---|---|---|---|
| REQ-05-01 | 송고 기사 확인 | 데스크는 송고된 기사를 도착 순서대로 보고 내용을 검토한다. | 필수 | FN-05-01 |
| REQ-05-02 | 승인 즉시 출고 | 데스크가 승인하면 기사는 바로 실시간 웹에 게시되고 방송 대기열에 들어간다. | 필수 | FN-05-02 |
| REQ-05-03 | 반려 | 데스크는 사유를 적어 반려할 수 있고, 기사는 담당 기자에게 돌아간다. | 필수 | FN-05-03 |
| REQ-05-04 | 검토 이력 | 누가 언제 승인·반려했는지 기록을 남긴다. | 권장 | FN-05-03 |

### 영역 06 · 실시간 개표 웹
| 요구 ID | 요구사항명 | 내용 | 우선순위 | 관련 기능 |
|---|---|---|---|---|
| REQ-06-01 | 전체 개표 현황 | 웹에서 전체 개표율·후보별 득표수·득표율·순위를 보여 준다. | 필수 | FN-06-01 |
| REQ-06-02 | 지역별 결과 | 5개 구의 1위 후보를 지도·차트로 보여 주고, 구를 누르면 상세 결과를 본다. | 필수 | FN-06-02 |
| REQ-06-03 | 실시간 기사 피드 | 승인된 기사가 새로고침 없이 웹에 바로 나타난다. | 필수 | FN-06-03 |
| REQ-06-04 | 공개 열람 | 실시간 개표 웹은 로그인 없이 누구나 볼 수 있다. | 필수 | FN-06-01 |

### 영역 07 · 개표 방송 송출
| 요구 ID | 요구사항명 | 내용 | 우선순위 | 관련 기능 |
|---|---|---|---|---|
| REQ-07-01 | 20분 큐시트 송출 | 카운트다운 1분 → 후보 소개 1분×3 → 실시간 개표 → 당선자 인터뷰 → 이력·공약 1분 → 마무리 10초 순서로 송출한다. | 필수 | FN-07-01 FN-07-03 |
| REQ-07-02 | AI 앵커 TTS 낭독 | 승인된 기사의 방송 원고를 TTS 음성으로 만들어 AI 앵커가 읽는다. | 필수 | FN-07-02 FN-07-03 |
| REQ-07-03 | 지역 차트 B-roll | 기사를 읽는 동안 그 기사의 지역 차트가 화면에 나온다. | 필수 | FN-07-04 |
| REQ-07-04 | 당선 영상 자동 편성 | 당선 확정 기사가 나가면 당선자의 인터뷰·이력·공약 영상을 이어서 편성한다. | 필수 | FN-07-05 |
| REQ-07-05 | 송출 제어 | 데스크는 송출 시작·일시정지·다음 항목 건너뛰기를 할 수 있다. | 필수 | FN-07-06 |

### 비기능 요구사항
| 요구 ID | 구분 | 요구사항명 | 내용 | 관련 기능 |
|---|---|---|---|---|
| NFR-01 | 성능 | 출고 지연 시간 | 승인 후 웹 표시 3초 이내, 방송 대기열 등록(TTS 생성 포함) 15초 이내. | FN-05-02 |
| NFR-02 | 보안 | 비밀 정보 보호 | 비밀번호는 해시로 저장, API 키·OpenAI 키는 .env에 두고 Git에 올리지 않는다. | FN-01-01 |
| NFR-03 | 윤리 | 사람 검수 원칙 | AI가 만든 기사는 기자·데스크 두 사람의 확인 없이 웹·방송에 나가지 않는다. | FN-04-05 FN-05-02 |
| NFR-05 | 화면 | 화면 규격 | 송출 화면 1920×1080, 실시간 개표 웹은 모바일에서도 읽힌다. | FN-06-01 FN-07-03 |

### 추적표
| 요구 ID | 기능 | 화면 | API | 테이블 |
|---|---|---|---|---|
| REQ-01-01 | FN-01-01 | SCR-01-01 | API-01-01 | TBL-01-01 |
| REQ-01-02 | FN-01-01 FN-01-02 | SCR-01-01 | API-01-01, API-01-02, API-01-03 | TBL-01-01 |
| REQ-03-01 | FN-03-01 | — | API-02-02 | TBL-03-01, TBL-03-02, TBL-03-03, TBL-03-05 |
| REQ-03-02 | FN-03-02 | — | — | TBL-03-03, TBL-03-04 |
| REQ-03-03 | FN-03-03 | SCR-03-01 | API-03-01, API-03-02 | TBL-03-05 |
| REQ-04-01 | FN-04-01 | — | — | TBL-03-04, TBL-04-01, TBL-04-02, TBL-04-03 |
| REQ-04-02 | FN-04-01 | — | — | TBL-03-04, TBL-04-01, TBL-04-02, TBL-04-03 |
| REQ-04-03 | FN-04-02 FN-04-03 | SCR-04-01 | API-04-01, API-04-05 | TBL-01-01, TBL-04-01 |
| REQ-04-04 | FN-04-03 FN-04-04 FN-04-05 | SCR-04-01, SCR-04-02 | API-04-01, API-04-02, API-04-03, API-04-04, API-04-05 | TBL-04-01 |
| REQ-05-01 | FN-05-01 | SCR-05-01 | API-04-05, API-05-01 | TBL-04-01 |
| REQ-05-02 | FN-05-02 | SCR-05-02 | API-05-02 | TBL-04-01, TBL-05-01, TBL-07-02, TBL-07-04 |
| REQ-05-03 | FN-05-03 | SCR-05-02 | API-05-03 | TBL-04-01, TBL-05-01 |
| REQ-05-04 | FN-05-03 | SCR-05-02 | API-05-03 | TBL-04-01, TBL-05-01 |
| REQ-06-01 | FN-06-01 | SCR-06-01 | API-06-01 | TBL-03-01, TBL-03-03 |
| REQ-06-02 | FN-06-02 | SCR-06-01, SCR-06-02 | API-06-02 | TBL-03-02, TBL-03-03 |
| REQ-06-03 | FN-06-03 | SCR-06-01, SCR-06-02 | API-06-03, API-06-04 | TBL-04-01 |
| REQ-06-04 | FN-06-01 | SCR-06-01 | API-06-01 | TBL-03-01, TBL-03-03 |
| REQ-07-01 | FN-07-01 FN-07-03 | SCR-07-01, SCR-07-02 | API-07-01, API-07-02, API-07-03, API-07-05 | TBL-07-01, TBL-07-02, TBL-07-03 |
| REQ-07-02 | FN-07-02 FN-07-03 | SCR-07-01 | API-07-02, API-07-03, API-07-05 | TBL-07-01, TBL-07-02, TBL-07-04 |
| REQ-07-03 | FN-07-04 | SCR-07-01 | API-06-02 | TBL-03-03 |
| REQ-07-04 | FN-07-05 | SCR-07-01, SCR-07-02 | API-07-02 | TBL-03-04, TBL-07-01, TBL-07-03 |
| REQ-07-05 | FN-07-06 | SCR-07-02 | API-07-04, API-07-05 | TBL-07-05 |
| NFR-01 | FN-05-02 | SCR-05-02 | API-05-02 | TBL-04-01, TBL-05-01, TBL-07-02, TBL-07-04 |
| NFR-02 | FN-01-01 | SCR-01-01 | API-01-01 | TBL-01-01 |
| NFR-03 | FN-04-05 FN-05-02 | SCR-04-02, SCR-05-02 | API-04-04, API-05-02 | TBL-04-01, TBL-05-01, TBL-07-02, TBL-07-04 |
| NFR-05 | FN-06-01 FN-07-03 | SCR-06-01, SCR-07-01 | API-06-01, API-07-02, API-07-03, API-07-05 | TBL-03-01, TBL-03-03, TBL-07-01, TBL-07-02 |


</details>

<details>
<summary><b>03 · 기능정의서 — 기능 22개·상태·업무 규칙</b></summary>

📄 원본: [Google Docs](https://docs.google.com/document/d/1WD54zhHx0ECbjprSiQlPDPDKJqiHfE9Q-3fSY3vcFIU/edit) · [Word 파일](docs/03_기능정의서_station-onair.docx)

<p align="center"><img src="docs/img/station-onair_func_tree.png" alt="기능 구조도" width="100%"></p>
<p align="center"><sub>기능 구조도</sub></p>

### 영역 01 · 계정·인증
| 기능 ID | 기능명 | 설명 | 요구 | 화면 | API | 테이블 |
|---|---|---|---|---|---|---|
| FN-01-01 | 로그인 | 아이디·비밀번호로 로그인, 역할(기자/데스크)에 맞는 첫 화면으로 이동 | REQ-01-01 REQ-01-02 NFR-02 | SCR-01-01 | API-01-01 | TBL-01-01 |
| FN-01-02 | 로그아웃·세션 확인 | 로그아웃, 새로고침 시 로그인 상태와 역할 확인 | REQ-01-02 | SCR-01-01 | API-01-02 API-01-03 | TBL-01-01 |

### 영역 03 · 방송국 개표 수신
| 기능 ID | 기능명 | 설명 | 요구 | 화면 | API | 테이블 |
|---|---|---|---|---|---|---|
| FN-03-01 | 주기적 개표 수신 | 5초마다 선관위 API 호출 → 최신 결과 표 갱신 | REQ-03-01 | — | API-02-02 | TBL-03-01 TBL-03-02 TBL-03-03 TBL-03-05 |
| FN-03-02 | 개표 이벤트 감지 | 직전 값과 비교해 이벤트(구간 돌파·1위 변동·당선) 기록 | REQ-03-02 | — | — | TBL-03-03 TBL-03-04 |
| FN-03-03 | 수신 상태 모니터 | 마지막 수신 시각·seq·실패 횟수 표시, 수동 즉시 수신 | REQ-03-03 | SCR-03-01 | API-03-01 API-03-02 | TBL-03-05 |

### 영역 04 · 기사 자동 생성·송고
| 기능 ID | 기능명 | 설명 | 요구 | 화면 | API | 테이블 |
|---|---|---|---|---|---|---|
| FN-04-01 | 기사 초안 자동 생성 | 이벤트 유형별 프롬프트 + 후보 자료 검색(RAG) → 제목·본문·방송 원고 생성 | REQ-04-01 REQ-04-02 | — | — | TBL-03-04 TBL-04-01 TBL-04-02 TBL-04-03 |
| FN-04-02 | 기자 자동 배정 | 기자 3명에게 차례로 배정하되, 미처리 초안이 3건 이상인 기자는 건너뜀 | REQ-04-03 | — | — | TBL-04-01 TBL-01-01 |
| FN-04-03 | 내 기사 목록 | 배정된 초안·반려 기사·송고 기사를 상태별로 조회 | REQ-04-03 REQ-04-04 | SCR-04-01 | API-04-01 API-04-05 | TBL-04-01 |
| FN-04-04 | 기사 편집 | 제목·본문·방송 원고 수정 및 임시 저장 | REQ-04-04 | SCR-04-02 | API-04-02 API-04-03 | TBL-04-01 |
| FN-04-05 | 송고 | 기사를 데스크로 보냄 (상태 DRAFT/REJECTED → SUBMITTED) | REQ-04-04 NFR-03 | SCR-04-02 | API-04-04 | TBL-04-01 |

### 영역 05 · 데스크 승인·출고
| 기능 ID | 기능명 | 설명 | 요구 | 화면 | API | 테이블 |
|---|---|---|---|---|---|---|
| FN-05-01 | 승인 대기 목록 | 송고 기사를 도착 순으로 조회, 새 송고 알림 | REQ-05-01 | SCR-05-01 | API-05-01 API-04-05 | TBL-04-01 |
| FN-05-02 | 승인(출고) | 승인 → 웹 게시 + TTS 생성 + 방송 대기열 등록 | REQ-05-02 NFR-01 NFR-03 | SCR-05-02 | API-05-02 | TBL-04-01 TBL-05-01 TBL-07-02 TBL-07-04 |
| FN-05-03 | 반려 | 사유와 함께 담당 기자에게 반환 | REQ-05-03 REQ-05-04 | SCR-05-02 | API-05-03 | TBL-04-01 TBL-05-01 |

### 영역 06 · 실시간 개표 웹
| 기능 ID | 기능명 | 설명 | 요구 | 화면 | API | 테이블 |
|---|---|---|---|---|---|---|
| FN-06-01 | 전체 개표 현황 | 전체 개표율·후보별 득표·순위 표시 | REQ-06-01 REQ-06-04 NFR-05 | SCR-06-01 | API-06-01 | TBL-03-01 TBL-03-03 |
| FN-06-02 | 지역별 결과 | 구별 1위 지도와 구 상세 차트 | REQ-06-02 | SCR-06-01 SCR-06-02 | API-06-02 | TBL-03-02 TBL-03-03 |
| FN-06-03 | 실시간 기사 피드 | 승인 기사 목록 + SSE로 새 기사·결과 갱신 받기 | REQ-06-03 | SCR-06-01 SCR-06-02 | API-06-03 API-06-04 | TBL-04-01 |

### 영역 07 · 개표 방송 송출
| 기능 ID | 기능명 | 설명 | 요구 | 화면 | API | 테이블 |
|---|---|---|---|---|---|---|
| FN-07-01 | 큐시트 관리 | 20분 구성표와 영상 파일 확인·순서 조정 | REQ-07-01 | SCR-07-02 | API-07-01 | TBL-07-01 TBL-07-03 |
| FN-07-02 | TTS 음성 생성 | 방송 원고를 앵커 음성 파일로 변환. 실패하거나 음성이 예상보다 짧으면(끝 문장 잘림) 1회 다시 생성 | REQ-07-02 | — | — | TBL-07-04 |
| FN-07-03 | 방송 대기열 송출 | 송출 화면이 다음 항목(영상/TTS)을 받아 재생 후 완료 보고. 같은 지역·유형의 더 새로운 기사가 승인되면 옛 기사는 건너뜀(SKIPPED) | REQ-07-01 REQ-07-02 NFR-05 | SCR-07-01 | API-07-02 API-07-03 API-07-05 | TBL-07-01 TBL-07-02 |
| FN-07-04 | 지역 차트 B-roll | 낭독 중인 기사의 지역 차트를 화면에 표시 | REQ-07-03 | SCR-07-01 | API-06-02 | TBL-03-03 |
| FN-07-05 | 당선 영상 자동 편성 | 당선 확정 기사 송출 뒤 당선자 인터뷰·이력·공약 영상 연결 | REQ-07-04 | SCR-07-01 SCR-07-02 | API-07-02 | TBL-07-01 TBL-07-03 TBL-03-04 |
| FN-07-06 | 송출 제어 | 시작·일시정지·재개·건너뛰기, 현재 상태 표시 | REQ-07-05 | SCR-07-02 | API-07-04 API-07-05 | TBL-07-05 |

### 기사 상태
<p align="center"><img src="docs/img/article_state.png" alt="기사 상태 전이" width="100%"></p>
<p align="center"><sub>기사 상태 전이</sub></p>

### 개표 이벤트
| 이벤트 | 뜻 | 조건 | 우선순위 |
|---|---|---|---|
| RATE_MILESTONE | 개표율 구간 돌파 | 전체 10·30·50·70·90·100%, 각 구 50·100% | 보통(5) |
| LEAD_CHANGE | 1위 변동 | 전체 또는 구에서 1위 후보가 바뀜 | 높음(3) |
| WIN_LIKELY | 당선 유력 | 개표율 50% 이상 + 1·2위 격차가 남은 표의 30% 이상 | 높음(2) |
| WIN_SURE | 당선 확실 | 1·2위 격차 > 남은 표의 60% (방송 판단 기준) | 최우선(1) |
| ELECTED | 당선 확정 | 1·2위 격차 > 남은 표 전부(수학적 확정) 또는 개표 100% | 최우선(1) |

### 업무 규칙
| 규칙 | 이름 | 내용 | 관련 기능 |
|---|---|---|---|
| BR-01 | 사람 검수 | APPROVED가 아닌 기사는 공개 API(API-06-03)·방송 대기열에 절대 나오지 않는다. | FN-05-02, FN-06-03 |
| BR-02 | 담당자만 수정 | 기자는 자기에게 배정된 기사만 수정·송고할 수 있다. 다른 기자 기사는 403. | FN-04-04, FN-04-05 |
| BR-03 | 수정 가능 상태 | DRAFT·REJECTED 상태에서만 수정 가능. SUBMITTED 이후 수정 요청은 409. | FN-04-04 |
| BR-04 | 동시 승인 방지 | 데스크 2명이 같은 기사를 동시에 처리하면 먼저 처리한 쪽만 반영, 나머지는 409 ‘이미 처리됨’. | FN-05-02, FN-05-03 |
| BR-05 | 기자 배정 | 기자 1→2→3 차례로 배정. 미처리 초안 3건 이상인 기자는 건너뛴다. | FN-04-02 |
| BR-06 | 오래된 기사 건너뛰기 | 같은 지역·같은 이벤트 유형의 더 새로운 기사가 승인되면 대기 중인 옛 기사는 SKIPPED. | FN-07-03 |
| BR-07 | 우선순위 | 대기열은 priority(당선 관련 1 → 일반 5) 다음 승인 시각 순으로 낭독. | FN-07-03 |
| BR-08 | TTS 재생성 | TTS 실패, 또는 음성 길이가 예상(글자 수 ÷ 6초)의 70% 미만이면 1회 다시 생성. 또 실패하면 SKIPPED + 데스크 경고 (웹 게시는 그대로). | FN-07-02 |
| BR-09 | 빈 대기열 | LIVE 구간에 읽을 기사가 없으면 전체 현황 차트 + 배경음악을 보여 준다 (승인 안 된 문장은 읽지 않음). | FN-07-03 |
| BR-10 | 당선 지연 대비 | 방송 16:30까지 당선 확정 기사가 나가지 않으면 데스크가 7·8번(인터뷰·이력)을 건너뛰고 LIVE를 이어 간다. | FN-07-05, FN-07-06 |


</details>

<details>
<summary><b>04 · 화면설계서 — 화면 10개</b></summary>

📄 원본: [Google Docs](https://docs.google.com/document/d/1HkSxvmTaYXbK2ovW3u0KGKGW-9P4o2LtCD_SvcLkoOQ/edit) · [Word 파일](docs/04_화면설계서_station-onair.docx)

| 화면 ID | 화면명 | 사용자 | URL |
|---|---|---|---|
| SCR-01-01 | 로그인 | 기자·데스크 | /login |
| SCR-03-01 | 개표 수신 모니터 | 데스크 | /desk/sync |
| SCR-04-01 | 기자 대시보드 (내 기사) | 기자 | /reporter |
| SCR-04-02 | 기사 편집·송고 | 기자 | /reporter/articles/{id} |
| SCR-05-01 | 데스크 승인 대기 목록 | 데스크 | /desk |
| SCR-05-02 | 기사 검토·승인/반려 | 데스크 | /desk/articles/{id} |
| SCR-06-01 | 실시간 개표 웹 (메인) | 누구나 | / |
| SCR-06-02 | 지역별 상세 | 누구나 | /regions/{code} |
| SCR-07-01 | 방송 송출 화면 (1920×1080) | OBS 캡처용 | /onair/screen |
| SCR-07-02 | 큐시트·송출 제어 | 데스크 | /desk/onair |

<p align="center"><img src="docs/img/screen_flow.png" alt="화면 흐름도" width="100%"></p>
<p align="center"><sub>화면 흐름도</sub></p>

<details>
<summary><b>SCR-01-01 로그인 <sub>(기자·데스크)</sub></b></summary>

기자·데스크 공용 로그인. 역할에 따라 기자 화면 또는 데스크 화면으로 이동

- 관련 기능: FN-01-01, FN-01-02
- 사용 API: API-01-01, API-01-02, API-01-03
- 사용 테이블: TBL-01-01

<p align="center"><img src="docs/img/SCR-01-01.png" alt="SCR-01-01 로그인" width="100%"></p>
<p align="center"><sub>SCR-01-01 로그인</sub></p>

| 번호 | 요소 | 설명 |
|---|---|---|
| 1 | 아이디 | reporter1~3, desk1~2 |
| 2 | 비밀번호 | 입력 후 Enter로 로그인 |
| 3 | 로그인 버튼 | 성공 시 기자→SCR-04-01, 데스크→SCR-05-01 |
| 4 | 오류 메시지 | 아이디·비밀번호 불일치 안내 |


</details>

<details>
<summary><b>SCR-03-01 개표 수신 모니터 <sub>(데스크)</sub></b></summary>

방송국 서버가 선관위 데이터를 잘 받고 있는지 확인

- 관련 기능: FN-03-03
- 사용 API: API-03-01, API-03-02
- 사용 테이블: TBL-03-05

<p align="center"><img src="docs/img/SCR-03-01.png" alt="SCR-03-01 개표 수신 모니터" width="100%"></p>
<p align="center"><sub>SCR-03-01 개표 수신 모니터</sub></p>

| 번호 | 요소 | 설명 |
|---|---|---|
| 1 | 수신 상태 표시등 | 정상(초록)·지연(노랑)·실패(빨강) |
| 2 | 마지막 수신 | 시각·seq·받은 행 수 |
| 3 | 즉시 수신 | 5초를 기다리지 않고 바로 받아 오기 |
| 4 | 최근 이벤트 | 감지된 개표 이벤트 목록 |
| 5 | 수신 로그 | 실패 시 오류 메시지 |


</details>

<details>
<summary><b>SCR-04-01 기자 대시보드 (내 기사) <sub>(기자)</sub></b></summary>

나에게 배정된 자동 생성 초안과 반려 기사를 한눈에 보는 첫 화면

- 관련 기능: FN-04-03
- 사용 API: API-04-01, API-04-05
- 사용 테이블: TBL-04-01

<p align="center"><img src="docs/img/SCR-04-01.png" alt="SCR-04-01 기자 대시보드 (내 기사)" width="100%"></p>
<p align="center"><sub>SCR-04-01 기자 대시보드 (내 기사)</sub></p>

| 번호 | 요소 | 설명 |
|---|---|---|
| 1 | 상태 탭 | 초안·반려·송고됨·출고됨 |
| 2 | 기사 카드 | 이벤트 유형·지역·생성 시각·제목 |
| 3 | 새 초안 알림 | SSE로 새 배정 즉시 표시 |
| 4 | 미니 개표 현황 | 전체 개표율·1·2위 격차 |
| 5 | 반려 사유 | 데스크가 남긴 메모 |


</details>

<details>
<summary><b>SCR-04-02 기사 편집·송고 <sub>(기자)</sub></b></summary>

AI 초안을 사실 확인하며 고친 뒤 데스크로 송고

- 관련 기능: FN-04-04, FN-04-05
- 사용 API: API-04-02, API-04-03, API-04-04
- 사용 테이블: TBL-04-01

<p align="center"><img src="docs/img/SCR-04-02.png" alt="SCR-04-02 기사 편집·송고" width="100%"></p>
<p align="center"><sub>SCR-04-02 기사 편집·송고</sub></p>

| 번호 | 요소 | 설명 |
|---|---|---|
| 1 | 근거 데이터 | 기사를 만든 이벤트와 개표 수치 (사실 확인용) |
| 2 | 제목 | 수정 가능 |
| 3 | 웹 기사 본문 | 수정 가능 |
| 4 | 방송 원고 | AI 앵커가 읽을 문장, 글자 수·예상 초 표시 |
| 5 | 참고 자료(RAG) | 초안에 쓰인 후보 이력·공약 출처 |
| 6 | 임시 저장 / 송고 | 송고하면 데스크 대기열로 |


</details>

<details>
<summary><b>SCR-05-01 데스크 승인 대기 목록 <sub>(데스크)</sub></b></summary>

송고된 기사를 도착 순서대로 보는 데스크 첫 화면

- 관련 기능: FN-05-01
- 사용 API: API-04-05, API-05-01
- 사용 테이블: TBL-04-01

<p align="center"><img src="docs/img/SCR-05-01.png" alt="SCR-05-01 데스크 승인 대기 목록" width="100%"></p>
<p align="center"><sub>SCR-05-01 데스크 승인 대기 목록</sub></p>

| 번호 | 요소 | 설명 |
|---|---|---|
| 1 | 대기 목록 | 송고 시각·기자·지역·제목, 오래된 순 |
| 2 | 대기 건수·평균 대기 시간 | 적체 확인 |
| 3 | 방송 대기열 미리보기 | 다음에 읽힐 기사 3건 |
| 4 | 상단 메뉴 | 승인 대기·수신 모니터·송출 제어 |


</details>

<details>
<summary><b>SCR-05-02 기사 검토·승인/반려 <sub>(데스크)</sub></b></summary>

기사와 근거 데이터를 나란히 보고 승인 또는 반려

- 관련 기능: FN-05-02, FN-05-03
- 사용 API: API-05-02, API-05-03
- 사용 테이블: TBL-04-01, TBL-05-01, TBL-07-02, TBL-07-04

<p align="center"><img src="docs/img/SCR-05-02.png" alt="SCR-05-02 기사 검토·승인/반려" width="100%"></p>
<p align="center"><sub>SCR-05-02 기사 검토·승인/반려</sub></p>

| 번호 | 요소 | 설명 |
|---|---|---|
| 1 | 근거 데이터 | 이벤트·최신 개표 수치 비교 (기사 숫자와 다르면 경고) |
| 2 | 기사 미리보기 | 웹에 나갈 모습 |
| 3 | 방송 원고 미리듣기 | TTS 미리듣기(선택) |
| 4 | 승인(출고) | 웹 게시 + 방송 대기열 등록 |
| 5 | 반려 | 사유 입력 필수 |


</details>

<details>
<summary><b>SCR-06-01 실시간 개표 웹 (메인) <sub>(누구나)</sub></b></summary>

개표 현황·지역 지도·실시간 기사를 보여 주는 공개 웹페이지

- 관련 기능: FN-06-01, FN-06-02, FN-06-03
- 사용 API: API-06-01, API-06-02, API-06-03, API-06-04
- 사용 테이블: TBL-03-01, TBL-03-02, TBL-03-03, TBL-04-01

<p align="center"><img src="docs/img/SCR-06-01.png" alt="SCR-06-01 실시간 개표 웹 (메인)" width="100%"></p>
<p align="center"><sub>SCR-06-01 실시간 개표 웹 (메인)</sub></p>

| 번호 | 요소 | 설명 |
|---|---|---|
| 1 | 전체 개표율 | 진행 막대와 갱신 시각 |
| 2 | 후보별 득표 | 득표수·득표율·순위, 당선 표시 |
| 3 | 지역 지도 | 구별 1위 후보 색, 누르면 SCR-06-02 |
| 4 | 실시간 기사 | 승인 기사가 맨 위에 추가 |
| 5 | 방송국 표시 | M 방송국 / K 방송국 |


</details>

<details>
<summary><b>SCR-06-02 지역별 상세 <sub>(누구나)</sub></b></summary>

선택한 구의 개표율·후보별 득표 차트와 그 지역 기사

- 관련 기능: FN-06-02, FN-06-03
- 사용 API: API-06-02, API-06-03, API-06-04
- 사용 테이블: TBL-03-02, TBL-03-03, TBL-04-01

<p align="center"><img src="docs/img/SCR-06-02.png" alt="SCR-06-02 지역별 상세" width="100%"></p>
<p align="center"><sub>SCR-06-02 지역별 상세</sub></p>

| 번호 | 요소 | 설명 |
|---|---|---|
| 1 | 지역 선택 | 5개 구 탭 |
| 2 | 지역 개표율 | 구 개표율과 갱신 시각 |
| 3 | 후보별 막대 차트 | 득표율 비교 (B-roll과 같은 차트) |
| 4 | 지역 기사 | 이 구 관련 승인 기사 |


</details>

<details>
<summary><b>SCR-07-01 방송 송출 화면 (1920×1080) <sub>(OBS 캡처용)</sub></b></summary>

OBS가 캡처해 방송하는 화면. 영상·AI 앵커·지역 차트·자막을 자동 재생

- 관련 기능: FN-07-03, FN-07-04, FN-07-05
- 사용 API: API-06-02, API-07-02, API-07-03, API-07-05
- 사용 테이블: TBL-03-03, TBL-03-04, TBL-07-01, TBL-07-02, TBL-07-03

<p align="center"><img src="docs/img/SCR-07-01.png" alt="SCR-07-01 방송 송출 화면 (1920×1080)" width="100%"></p>
<p align="center"><sub>SCR-07-01 방송 송출 화면 (1920×1080)</sub></p>

| 번호 | 요소 | 설명 |
|---|---|---|
| 1 | AI 앵커 영역 | 앵커 영상 + TTS 음성 |
| 2 | B-roll 차트 | 기사의 지역 차트 (지역 없으면 전체) |
| 3 | 하단 자막 | 방송 원고 요약 한 줄 |
| 4 | 득표 띠 | 후보별 득표율·전체 개표율 |
| 5 | LIVE·시계 | 남은 방송 시간 |
| 6 | 전체 화면 영상 | 카운트다운·후보 소개·인터뷰 등 영상 구간 |


</details>

<details>
<summary><b>SCR-07-02 큐시트·송출 제어 <sub>(데스크)</sub></b></summary>

20분 구성표 진행과 방송 대기열을 보고 송출을 제어

- 관련 기능: FN-07-01, FN-07-05, FN-07-06
- 사용 API: API-07-01, API-07-02, API-07-04, API-07-05
- 사용 테이블: TBL-03-04, TBL-07-01, TBL-07-03, TBL-07-05

<p align="center"><img src="docs/img/SCR-07-02.png" alt="SCR-07-02 큐시트·송출 제어" width="100%"></p>
<p align="center"><sub>SCR-07-02 큐시트·송출 제어</sub></p>

| 번호 | 요소 | 설명 |
|---|---|---|
| 1 | 큐시트 진행 | 10개 구간, 현재 구간 강조 |
| 2 | 제어 버튼 | 시작·일시정지·재개·건너뛰기 |
| 3 | 방송 대기열 | 승인 기사 TTS 순서·길이·상태 |
| 4 | 남은 시간 | 계획 대비 지연·여유 |
| 5 | 송출 화면 미리보기 | SCR-07-01 축소 화면 |


</details>


</details>

<details>
<summary><b>05 · DB설계서 — 테이블 15개</b></summary>

📄 원본: [Google Docs](https://docs.google.com/document/d/12Vidx7d936NgqQTf9hUYQh4u8-WvrEvUDXIg6u7LYhk/edit) · [Word 파일](docs/05_DB설계서_station-onair.docx)

<p align="center"><img src="docs/img/erd_station_a.png" alt="계정·수신·기사·승인" width="100%"></p>
<p align="center"><sub>계정·수신·기사·승인</sub></p>

<p align="center"><img src="docs/img/erd_station_b.png" alt="방송 송출" width="100%"></p>
<p align="center"><sub>방송 송출</sub></p>

<details>
<summary><b>전체 ERD</b></summary>

<p align="center"><img src="docs/img/erd_station.png" alt="station_db 전체" width="100%"></p>
<p align="center"><sub>station_db 전체</sub></p>


</details>

| 테이블 ID | 테이블명 | 설명 | 사용 기능 |
|---|---|---|---|
| TBL-01-01 | `users` | 기자·데스크 계정 (5개 고정) | FN-01-01 FN-01-02 FN-04-02 |
| TBL-03-01 | `candidate` | 후보자 (선관위에서 복제) | FN-03-01 FN-06-01 |
| TBL-03-02 | `region` | 개표 지역 (선관위에서 복제, 전체=ALL 포함) | FN-03-01 FN-06-02 |
| TBL-03-03 | `result_latest` | 지역·후보별 최신 결과 (웹·차트가 읽는 표) | FN-03-01 FN-03-02 FN-06-01 FN-06-02 FN-07-04 |
| TBL-03-04 | `count_event` | 감지된 개표 이벤트 (기사 생성의 출발점) | FN-03-02 FN-04-01 FN-07-05 |
| TBL-03-05 | `sync_log` | 선관위 수신 기록 | FN-03-01 FN-03-03 |
| TBL-04-01 | `article` | 기사 (자동 초안 → 송고 → 승인/반려) | FN-04-01 FN-04-02 FN-04-03 FN-04-04 FN-04-05 FN-05-01 FN-05-02 FN-05-03 FN-06-03 |
| TBL-04-02 | `prompt_template` | 이벤트 유형별 기사 생성 프롬프트 | FN-04-01 |
| TBL-04-03 | `candidate_doc` | 후보 이력·공약 자료 (RAG 원문) | FN-04-01 |
| TBL-05-01 | `article_review` | 데스크 승인·반려 이력 | FN-05-02 FN-05-03 |
| TBL-07-01 | `cue_sheet` | 20분 방송 구성표 | FN-07-01 FN-07-03 FN-07-05 |
| TBL-07-02 | `onair_queue` | 방송 대기열 (승인 기사 낭독 순서) | FN-05-02 FN-07-03 |
| TBL-07-03 | `media_asset` | 사전 제작 영상·음성 (오프닝 TTS 포함) | FN-07-01 FN-07-05 |
| TBL-07-04 | `tts_audio` | 기사 방송 원고 TTS 음성 | FN-05-02 FN-07-02 |
| TBL-07-05 | `onair_state` | 송출 상태 (1행) | FN-07-06 |

<details>
<summary><b>TBL-01-01 <code>users</code> — 기자·데스크 계정 (5개 고정)</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `user_id` | INTEGER | PK | N | 사용자 번호 |
| `login_id` | VARCHAR(30) | UK | N | reporter1 / desk1 |
| `password_hash` | VARCHAR(100) |  | N | bcrypt 해시 |
| `name` | VARCHAR(30) |  | N | 표시 이름 |
| `role` | VARCHAR(10) |  | N | REPORTER / DESK |
| `created_at` | DATETIME |  | N | 생성 시각 |


</details>

<details>
<summary><b>TBL-03-01 <code>candidate</code> — 후보자 (선관위에서 복제)</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `candidate_id` | INTEGER | PK | N | 선관위 후보 번호 |
| `ballot_no` | INTEGER |  | N | 기호 |
| `name` | VARCHAR(20) |  | N | 이름 |
| `party` | VARCHAR(30) |  | Y | 정당 |
| `color` | CHAR(7) |  | N | 차트 색 |


</details>

<details>
<summary><b>TBL-03-02 <code>region</code> — 개표 지역 (선관위에서 복제, 전체=ALL 포함)</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `region_code` | VARCHAR(10) | PK | N | ALL / EAST … |
| `name` | VARCHAR(20) |  | N | 전체 / 동구 |
| `electors` | INTEGER |  | N | 선거인 수 |
| `sort_order` | INTEGER |  | N | 표시 순서 |


</details>

<details>
<summary><b>TBL-03-03 <code>result_latest</code> — 지역·후보별 최신 결과 (웹·차트가 읽는 표)</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `region_code` | VARCHAR(10) | PK,FK | N | → region |
| `candidate_id` | INTEGER | PK,FK | N | → candidate |
| `votes` | INTEGER |  | N | 득표수 |
| `vote_rate` | DECIMAL(5,2) |  | N | 득표율(%) |
| `rank` | INTEGER |  | N | 지역 내 순위 |
| `counted_rate` | DECIMAL(5,2) |  | N | 지역 개표율(%) |
| `winner_flag` | VARCHAR(10) |  | Y | LIKELY / SURE / ELECTED |
| `updated_seq` | INTEGER |  | N | 반영한 seq |
| `updated_at` | DATETIME |  | N | 반영 시각 |


</details>

<details>
<summary><b>TBL-03-04 <code>count_event</code> — 감지된 개표 이벤트 (기사 생성의 출발점)</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `event_id` | INTEGER | PK | N | 이벤트 번호 |
| `event_type` | VARCHAR(20) |  | N | RATE_MILESTONE / LEAD_CHANGE / WIN_LIKELY / WIN_SURE / ELECTED |
| `region_code` | VARCHAR(10) | FK | N | → region (전체=ALL) |
| `candidate_id` | INTEGER | FK | Y | 관련 후보 |
| `payload` | JSON |  | N | 당시 수치 (개표율·득표·격차) |
| `seq` | INTEGER |  | N | 감지 seq |
| `detected_at` | DATETIME |  | N | 감지 시각 |


</details>

<details>
<summary><b>TBL-03-05 <code>sync_log</code> — 선관위 수신 기록</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `log_id` | INTEGER | PK | N | 로그 번호 |
| `requested_at` | DATETIME |  | N | 요청 시각 |
| `since_seq` | INTEGER |  | N | 요청 seq |
| `last_seq` | INTEGER |  | Y | 받은 마지막 seq |
| `row_count` | INTEGER |  | N | 받은 행 수 |
| `status` | VARCHAR(10) |  | N | OK / FAIL |
| `error_msg` | VARCHAR(200) |  | Y | 오류 내용 |


</details>

<details>
<summary><b>TBL-04-01 <code>article</code> — 기사 (자동 초안 → 송고 → 승인/반려)</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `article_id` | INTEGER | PK | N | 기사 번호 |
| `event_id` | INTEGER | FK | N | → count_event |
| `region_code` | VARCHAR(10) | FK | N | → region (B-roll 차트 지역) |
| `title` | VARCHAR(100) |  | N | 제목 |
| `body` | TEXT |  | N | 웹 기사 본문 |
| `anchor_script` | TEXT |  | N | 방송 원고 (TTS용) |
| `status` | VARCHAR(10) |  | N | DRAFT / SUBMITTED / REJECTED / APPROVED |
| `reporter_id` | INTEGER | FK | N | → users (담당 기자) |
| `desk_id` | INTEGER | FK | Y | → users (승인 데스크) |
| `rag_sources` | JSON |  | Y | 참고한 후보 자료 id |
| `ai_model` | VARCHAR(30) |  | N | 생성 모델명 |
| `created_at` | DATETIME |  | N | 생성 |
| `submitted_at` | DATETIME |  | Y | 송고 |
| `approved_at` | DATETIME |  | Y | 승인(=웹 게시) |


</details>

<details>
<summary><b>TBL-04-02 <code>prompt_template</code> — 이벤트 유형별 기사 생성 프롬프트</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `template_id` | INTEGER | PK | N | 번호 |
| `event_type` | VARCHAR(20) | UK | N | 이벤트 유형 |
| `system_prompt` | TEXT |  | N | 기자 역할·문체 지침 |
| `user_prompt` | TEXT |  | N | 수치가 들어갈 틀 |
| `active` | BOOLEAN |  | N | 사용 여부 |


</details>

<details>
<summary><b>TBL-04-03 <code>candidate_doc</code> — 후보 이력·공약 자료 (RAG 원문)</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `doc_id` | INTEGER | PK | N | 자료 번호 |
| `candidate_id` | INTEGER | FK | N | → candidate |
| `doc_type` | VARCHAR(10) |  | N | PROFILE(이력) / PLEDGE(공약) |
| `title` | VARCHAR(100) |  | N | 자료 제목 |
| `content` | TEXT |  | N | 본문 (벡터DB에 임베딩) |
| `source` | VARCHAR(200) |  | Y | 출처 |


</details>

<details>
<summary><b>TBL-05-01 <code>article_review</code> — 데스크 승인·반려 이력</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `review_id` | INTEGER | PK | N | 번호 |
| `article_id` | INTEGER | FK | N | → article |
| `desk_id` | INTEGER | FK | N | → users |
| `action` | VARCHAR(10) |  | N | APPROVE / REJECT |
| `comment` | VARCHAR(300) |  | Y | 반려 사유·메모 |
| `created_at` | DATETIME |  | N | 처리 시각 |


</details>

<details>
<summary><b>TBL-07-01 <code>cue_sheet</code> — 20분 방송 구성표</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `cue_id` | INTEGER | PK | N | 번호 |
| `order_no` | INTEGER |  | N | 순서 1~10 |
| `segment_type` | VARCHAR(10) |  | N | COUNTDOWN/ANCHOR/INTRO/LIVE/INTERVIEW/PROFILE/CLOSING |
| `title` | VARCHAR(50) |  | N | 구간 이름 |
| `planned_start_sec` | INTEGER |  | N | 계획 시작(초) |
| `duration_sec` | INTEGER |  | N | 길이(초) |
| `media_id` | INTEGER | FK | Y | → media_asset (영상 구간) |
| `trigger_type` | VARCHAR(20) |  | N | AUTO / ELECTED |
| `status` | VARCHAR(10) |  | N | READY / ON_AIR / DONE |


</details>

<details>
<summary><b>TBL-07-02 <code>onair_queue</code> — 방송 대기열 (승인 기사 낭독 순서)</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `queue_id` | INTEGER | PK | N | 번호 |
| `article_id` | INTEGER | FK,UK | N | → article |
| `tts_id` | INTEGER | FK | Y | → tts_audio (생성 전 NULL) |
| `region_code` | VARCHAR(10) | FK | N | B-roll 지역 |
| `priority` | INTEGER |  | N | 1=당선 관련, 5=일반 |
| `status` | VARCHAR(10) |  | N | PREPARING / WAITING / PLAYING / DONE / SKIPPED |
| `queued_at` | DATETIME |  | N | 등록 |
| `played_at` | DATETIME |  | Y | 송출 |


</details>

<details>
<summary><b>TBL-07-03 <code>media_asset</code> — 사전 제작 영상·음성 (오프닝 TTS 포함)</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `media_id` | INTEGER | PK | N | 번호 |
| `media_type` | VARCHAR(10) |  | N | COUNTDOWN/OPENING/INTRO/INTERVIEW/PROFILE/CLOSING/ANCHOR_LOOP |
| `candidate_id` | INTEGER | FK | Y | → candidate (후보별 영상) |
| `title` | VARCHAR(50) |  | N | 영상 제목 |
| `file_path` | VARCHAR(200) |  | N | /static/media/…mp4 · mp3 |
| `duration_sec` | INTEGER |  | N | 길이(초) |


</details>

<details>
<summary><b>TBL-07-04 <code>tts_audio</code> — 기사 방송 원고 TTS 음성</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `tts_id` | INTEGER | PK | N | 번호 |
| `article_id` | INTEGER | FK | N | → article |
| `voice` | VARCHAR(20) |  | N | 음성 이름 |
| `file_path` | VARCHAR(200) |  | N | /static/tts/….mp3 |
| `duration_sec` | DECIMAL(5,1) |  | N | 재생 길이 |
| `created_at` | DATETIME |  | N | 생성 시각 |


</details>

<details>
<summary><b>TBL-07-05 <code>onair_state</code> — 송출 상태 (1행)</b></summary>

| 컬럼 | 타입 | 키 | NULL | 설명 |
|---|---|---|---|---|
| `id` | INTEGER | PK | N | 항상 1 |
| `status` | VARCHAR(10) |  | N | STANDBY / ON_AIR / PAUSED / ENDED |
| `current_cue_id` | INTEGER | FK | Y | → cue_sheet |
| `current_queue_id` | INTEGER | FK | Y | → onair_queue |
| `started_at` | DATETIME |  | Y | 방송 시작 시각 |


</details>


</details>

<details>
<summary><b>06 · API명세서 — API 22개</b></summary>

📄 원본: [Google Docs](https://docs.google.com/document/d/1h8ubQvQaI6jBk3qCjWK2y_NdcLh4e_91j9PlsJgqS5Y/edit) · [Word 파일](docs/06_API명세서_station-onair.docx)

<p align="center"><img src="docs/img/station-onair_api_map.png" alt="API 지도" width="100%"></p>
<p align="center"><sub>API 지도</sub></p>

| API ID | 메서드 | 경로 | 이름 | 권한 |
|---|---|---|---|---|
| API-01-01 | POST | `/api/auth/login` | 로그인 | 없음 |
| API-01-02 | POST | `/api/auth/logout` | 로그아웃 | 로그인 |
| API-01-03 | GET | `/api/auth/me` | 내 정보·역할 | 로그인 |
| API-03-01 | GET | `/api/sync/status` | 수신 상태 | DESK |
| API-03-02 | POST | `/api/sync/run` | 즉시 수신 | DESK |
| API-04-01 | GET | `/api/articles?status={status}` | 내 기사 목록 | REPORTER |
| API-04-02 | GET | `/api/articles/{articleId}` | 기사 상세 | REPORTER·DESK |
| API-04-03 | PUT | `/api/articles/{articleId}` | 기사 수정(임시 저장) | REPORTER(담당자) |
| API-04-04 | POST | `/api/articles/{articleId}/submit` | 송고 | REPORTER(담당자) |
| API-04-05 | GET | `/api/newsroom/stream` | 뉴스룸 알림 (SSE) | REPORTER·DESK |
| API-05-01 | GET | `/api/desk/articles?status=SUBMITTED` | 승인 대기 목록 | DESK |
| API-05-02 | POST | `/api/desk/articles/{articleId}/approve` | 승인(출고) | DESK |
| API-05-03 | POST | `/api/desk/articles/{articleId}/reject` | 반려 | DESK |
| API-06-01 | GET | `/api/public/results` | 전체 개표 현황 | 없음(공개) |
| API-06-02 | GET | `/api/public/results/{regionCode}` | 지역별 결과 | 없음(공개) |
| API-06-03 | GET | `/api/public/articles?region={code}&limit=20` | 출고 기사 목록 | 없음(공개) |
| API-06-04 | GET | `/api/public/stream` | 실시간 알림 (SSE) | 없음(공개) |
| API-07-01 | GET | `/api/onair/cuesheet` | 큐시트 조회 | DESK |
| API-07-02 | GET | `/api/onair/next` | 다음 송출 항목 | DESK(송출 PC 로그인) |
| API-07-03 | POST | `/api/onair/queue/{queueId}/done` | 송출 완료 보고 | DESK(송출 PC 로그인) |
| API-07-04 | POST | `/api/onair/control` | 송출 제어 | DESK |
| API-07-05 | GET | `/api/onair/stream` | 송출 상태 알림 (SSE) | DESK |

<details>
<summary><b>영역 01 · 계정·인증 API</b></summary>

<p align="center"><img src="docs/img/api_01.png" alt="영역 01 API" width="100%"></p>
<p align="center"><sub>영역 01 API</sub></p>

#### API-01-01 `POST /api/auth/login` — 로그인
권한: 없음 · 테이블 TBL-01-01

요청
```json
{ "login_id": "reporter1", "password": "****" }
```
응답 200
```json
{ "user_id": 1, "name": "기자1", "role": "REPORTER" }  + 세션 쿠키
```
#### API-01-02 `POST /api/auth/logout` — 로그아웃
권한: 로그인 · 테이블 TBL-01-01

요청
```json
(없음)
```
응답 200
```json
{ "ok": true }
```
#### API-01-03 `GET /api/auth/me` — 내 정보·역할
권한: 로그인 · 테이블 TBL-01-01

요청
```json
(없음)
```
응답 200
```json
{ "user_id": 4, "name": "데스크1", "role": "DESK" }
```

</details>

<details>
<summary><b>영역 03 · 방송국 개표 수신 API</b></summary>

<p align="center"><img src="docs/img/api_03.png" alt="영역 03 API" width="100%"></p>
<p align="center"><sub>영역 03 API</sub></p>

#### API-03-01 `GET /api/sync/status` — 수신 상태
권한: DESK · 테이블 TBL-03-05, TBL-03-04

요청
```json
(없음)
```
응답 200
```json
{ "state": "OK", "last_seq": 42, "last_at": "20:31:05", "fail_count": 0,
  "recent_events": [ {"type":"LEAD_CHANGE","region":"EAST"} ] }
```
#### API-03-02 `POST /api/sync/run` — 즉시 수신
권한: DESK · 테이블 TBL-03-05, TBL-03-03

요청
```json
(없음)
```
응답 200
```json
{ "received": 5, "last_seq": 43, "new_events": 1 }
```

</details>

<details>
<summary><b>영역 04 · 기사 자동 생성·송고 API</b></summary>

<p align="center"><img src="docs/img/api_04.png" alt="영역 04 API" width="100%"></p>
<p align="center"><sub>영역 04 API</sub></p>

#### API-04-01 `GET /api/articles?status={status}` — 내 기사 목록
권한: REPORTER · 테이블 TBL-04-01

요청
```json
status = DRAFT | REJECTED | SUBMITTED | APPROVED (생략 시 전체)
```
응답 200
```json
[ { "article_id": 12, "title": "동구 개표율 50% 돌파…", "status": "DRAFT",
    "event_type": "RATE_MILESTONE", "region": "EAST", "created_at": "20:31:08" } ]
```
#### API-04-02 `GET /api/articles/{articleId}` — 기사 상세
권한: REPORTER·DESK · 테이블 TBL-04-01, TBL-03-04, TBL-05-01

요청
```json
(없음)
```
응답 200
```json
{ "article_id": 12, "title": "...", "body": "...", "anchor_script": "...",
  "event": {...수치...}, "rag_sources": [...], "reviews": [...] }
```
#### API-04-03 `PUT /api/articles/{articleId}` — 기사 수정(임시 저장)
권한: REPORTER(담당자) · 테이블 TBL-04-01

요청
```json
{ "title": "...", "body": "...", "anchor_script": "..." }
```
응답 200
```json
{ "article_id": 12, "status": "DRAFT", "updated": true }
```
#### API-04-04 `POST /api/articles/{articleId}/submit` — 송고
권한: REPORTER(담당자) · 테이블 TBL-04-01

요청
```json
(없음)
```
응답 200
```json
{ "article_id": 12, "status": "SUBMITTED", "submitted_at": "20:32:10" }
```
#### API-04-05 `GET /api/newsroom/stream` — 뉴스룸 알림 (SSE)
권한: REPORTER·DESK · 테이블 TBL-04-01, TBL-05-01

요청
```json
EventSource 연결 유지 (로그인 세션)
```
응답 200
```json
event: article.assigned  data: {"article_id":13, "reporter_id":1}
event: article.submitted data: {"article_id":12}
event: article.rejected  data: {"article_id":9, "comment":"..."}
```

</details>

<details>
<summary><b>영역 05 · 데스크 승인·출고 API</b></summary>

<p align="center"><img src="docs/img/api_05.png" alt="영역 05 API" width="100%"></p>
<p align="center"><sub>영역 05 API</sub></p>

#### API-05-01 `GET /api/desk/articles?status=SUBMITTED` — 승인 대기 목록
권한: DESK · 테이블 TBL-04-01

요청
```json
(없음)
```
응답 200
```json
[ { "article_id": 12, "reporter": "기자1", "title": "...", "submitted_at": "20:32:10",
    "waiting_sec": 35 } ]
```
#### API-05-02 `POST /api/desk/articles/{articleId}/approve` — 승인(출고)
권한: DESK · 테이블 TBL-04-01, TBL-05-01, TBL-07-02, TBL-07-04

요청
```json
{ "comment": "" }
```
응답 200
```json
{ "article_id": 12, "status": "APPROVED", "published": true,
  "queue_id": 7, "queue_status": "PREPARING" }
```
#### API-05-03 `POST /api/desk/articles/{articleId}/reject` — 반려
권한: DESK · 테이블 TBL-04-01, TBL-05-01

요청
```json
{ "comment": "득표수 최신 값으로 수정 바람" }
```
응답 200
```json
{ "article_id": 12, "status": "REJECTED" }
```

</details>

<details>
<summary><b>영역 06 · 실시간 개표 웹 API</b></summary>

<p align="center"><img src="docs/img/api_06.png" alt="영역 06 API" width="100%"></p>
<p align="center"><sub>영역 06 API</sub></p>

#### API-06-01 `GET /api/public/results` — 전체 개표 현황
권한: 없음(공개) · 테이블 TBL-03-01, TBL-03-02, TBL-03-03

요청
```json
(없음)
```
응답 200
```json
{ "counted_rate": 48.2, "updated_at": "20:31:05",
  "candidates": [ {"id":1,"name":"김하늘","votes":120345,"rate":44.1,"rank":1,"winner_flag":null} ],
  "regions": [ {"code":"EAST","leader_id":1,"counted_rate":51.3} ] }
```
#### API-06-02 `GET /api/public/results/{regionCode}` — 지역별 결과
권한: 없음(공개) · 테이블 TBL-03-02, TBL-03-03

요청
```json
regionCode = EAST | WEST | … | ALL
```
응답 200
```json
{ "region": "동구", "counted_rate": 51.3,
  "candidates": [ {"id":1,"votes":15210,"rate":46.4}, ... ] }
```
#### API-06-03 `GET /api/public/articles?region={code}&limit=20` — 출고 기사 목록
권한: 없음(공개) · 테이블 TBL-04-01

요청
```json
region 생략 시 전체
```
응답 200
```json
[ { "article_id": 12, "title": "...", "body": "...", "region": "EAST", "approved_at": "20:32:40" } ]
```
#### API-06-04 `GET /api/public/stream` — 실시간 알림 (SSE)
권한: 없음(공개) · 테이블 TBL-03-03, TBL-04-01

요청
```json
EventSource 연결 유지
```
응답 200
```json
event: results.updated   data: {"last_seq":43}
event: article.published data: {"article_id":12, "region":"EAST"}
```

</details>

<details>
<summary><b>영역 07 · 개표 방송 송출 API</b></summary>

<p align="center"><img src="docs/img/api_07.png" alt="영역 07 API" width="100%"></p>
<p align="center"><sub>영역 07 API</sub></p>

#### API-07-01 `GET /api/onair/cuesheet` — 큐시트 조회
권한: DESK · 테이블 TBL-07-01, TBL-07-03

요청
```json
(없음)
```
응답 200
```json
[ { "order_no": 1, "segment_type": "COUNTDOWN", "planned_start_sec": 0,
    "duration_sec": 60, "status": "DONE" }, ... ]
```
#### API-07-02 `GET /api/onair/next` — 다음 송출 항목
권한: DESK(송출 PC 로그인) · 테이블 TBL-07-01, TBL-07-02, TBL-07-03, TBL-07-04

요청
```json
(없음) — 송출 화면이 한 항목 재생을 마칠 때마다 호출
```
응답 200
```json
{ "kind": "TTS", "queue_id": 7, "audio": "/static/tts/12.mp3",
  "script": "...", "region_code": "EAST", "duration_sec": 24.5 }
또는 { "kind": "VIDEO", "cue_id": 7, "file": "/static/media/interview_1.mp4" }
```
#### API-07-03 `POST /api/onair/queue/{queueId}/done` — 송출 완료 보고
권한: DESK(송출 PC 로그인) · 테이블 TBL-07-02

요청
```json
{ "result": "DONE | ERROR" }
```
응답 200
```json
{ "queue_id": 7, "status": "DONE" }
```
#### API-07-04 `POST /api/onair/control` — 송출 제어
권한: DESK · 테이블 TBL-07-05, TBL-07-01

요청
```json
{ "action": "start | pause | resume | skip" }
```
응답 200
```json
{ "status": "ON_AIR", "current_cue": 6 }
```
#### API-07-05 `GET /api/onair/stream` — 송출 상태 알림 (SSE)
권한: DESK · 테이블 TBL-07-05, TBL-07-02

요청
```json
EventSource 연결 유지
```
응답 200
```json
event: onair.control  data: {"action":"pause"}
event: queue.ready    data: {"queue_id":7}
event: cue.changed    data: {"cue_id":7}
```

</details>


</details>

<details>
<summary><b>07 · 시스템설계도 — 구성·흐름·실행 설정</b></summary>

📄 원본: [Google Docs](https://docs.google.com/document/d/1lpr6eBaBaVGCySDEyHcX7D7mHrAGxhp_oH6rXwkDyJ8/edit) · [Word 파일](docs/07_시스템설계도_station-onair.docx)

<p align="center"><img src="docs/img/station-onair_context.png" alt="저장소 관계" width="100%"></p>
<p align="center"><sub>저장소 관계</sub></p>

<p align="center"><img src="docs/img/sys_arch.png" alt="구성도" width="100%"></p>
<p align="center"><sub>구성도</sub></p>

<p align="center"><img src="docs/img/seq_sync.png" alt="수신 → 초안" width="100%"></p>
<p align="center"><sub>수신 → 초안</sub></p>

<p align="center"><img src="docs/img/seq_approve.png" alt="송고 → 승인 → 웹·방송" width="100%"></p>
<p align="center"><sub>송고 → 승인 → 웹·방송</sub></p>

<p align="center"><img src="docs/img/seq_elected.png" alt="당선 → 영상 편성" width="100%"></p>
<p align="center"><sub>당선 → 영상 편성</sub></p>

<p align="center"><img src="docs/img/sys_deploy.png" alt="방송 당일 LAN 구성" width="100%"></p>
<p align="center"><sub>방송 당일 LAN 구성</sub></p>

| 변수 | M 예 |
|---|---|
| STATION_CODE | M |
| STATION_DB_URL | sqlite:///station_m.db |
| NEC_BASE_URL | http://서버IP:8000 |
| NEC_API_KEY | (비밀) |
| OPENAI_API_KEY | (비밀) |
| LLM_MODEL | gpt-6-luna |
| TTS_MODEL | gpt-4o-mini-tts |


</details>

<details>
<summary><b>08 · 개발환경검토서 — 기술·폴더 구조·규칙</b></summary>

📄 원본: [Google Docs](https://docs.google.com/document/d/1tJ9-umdY-piE-2IaUL9XPo_Kr9z82J5wQ9RKQ_Ph-c0/edit) · [Word 파일](docs/08_개발환경검토서_station-onair.docx)

<p align="center"><img src="docs/img/dev_stack.png" alt="권장 환경" width="100%"></p>
<p align="center"><sub>권장 환경</sub></p>

<p align="center"><img src="docs/img/station-onair_folder.png" alt="폴더 구조" width="100%"></p>
<p align="center"><sub>폴더 구조</sub></p>

### 저장소 규칙
- `.env`, `*.db`는 올리지 않고 `.env.example`만 올린다
- 브랜치: `main` ← `dev` ← `feature/영역코드-이름` (예: `feature/04-article-gen`)
- 커밋·PR 제목에 번호를 쓴다 (예: `FN-05-02 승인 API`)

</details>

