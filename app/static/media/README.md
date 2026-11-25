# 방송 영상 파일 넣는 곳

아래 이름으로 넣으면 송출 화면이 큐시트 순서대로 틉니다. 파일이 없으면 그 구간은 제목 화면(SLATE)으로 대신합니다.
영상은 용량이 커서 Git에 올리지 않습니다 (Google Drive 공유 폴더에 보관 → 송출 PC에 복사).

| 파일 | 구간 | 길이 |
|---|---|---|
| countdown.mp4 | 1. 개표 카운트다운 | 60초 |
| opening.mp4 | 2. 오프닝 멘트 (립싱크 아바타) | 30초 |
| intro_1.mp4 · intro_2.mp4 · intro_3.mp4 | 3~5. 기호 1·2·3 후보 소개 | 각 60초 |
| interview_1.mp4 · interview_2.mp4 · interview_3.mp4 | 7. 당선자 인터뷰 (당선자 것만 나감) | 60초 |
| profile_1.mp4 · profile_2.mp4 · profile_3.mp4 | 8. 당선자 지난 이력·공약 | 60초 |
| closing.mp4 | 10. 마무리 | 10초 |
| anchor_loop.mp4 | AI 앵커 자리 반복 영상 | 10~20초 |
| bgm.mp3 | 읽을 기사가 없을 때 배경음악 (Git에 올려도 됨) | 자유 |

진짜 영상이 나오기 전에는 테스트 영상으로 흐름을 점검할 수 있습니다: `python tools/make_test_media.py --short` (ffmpeg 필요, 이미 있는 파일은 건너뜀)

실존 영화·작품의 이름, 대사, 로고, 음악, 효과음은 쓰지 않습니다.
