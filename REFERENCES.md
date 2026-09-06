# 참고 자료 — 주소 모음

> 책의 **참고문헌·더 읽을거리** 는 이름과 쓰임만 적고, 주소는 여기 둡니다. 인쇄된 주소는 죽지만 이 파일은 고칠 수 있습니다.
> 마지막 확인 — **2026-09-06**. 링크가 죽었으면 이슈로 알려 주세요.
>
> 여기 있는 이름이 곧 추천은 아닙니다. **이 책이 실제로 쓰거나 시험한 것** 만 적었고, 폐기한 것도 사유와 함께 남겼습니다.

---

## 1. 얼굴 — 립싱크와 리타게팅

| 이름 | 주소 | 이 책에서 |
|---|---|---|
| Wav2Lip | github.com/Rudrabha/Wav2Lip | Ch10 — 가장 빠른 첫 성공. 옛 코드를 현재 환경에 맞추는 과정까지 |
| MuseTalk | github.com/TMElyralab/MuseTalk | Ch11 — Track A의 립싱크 단계(230초 중 195.8초) |
| LivePortrait | github.com/KwaiVGI/LivePortrait | Ch12·Ch13 — 리타게팅. 동물 모드가 비사람 트랙의 근거 |
| X-Pose | github.com/IDEA-Research/X-Pose | Ch12 §7 — 동물 모드가 쓰는 키포인트 검출기(커스텀 CUDA 빌드) |
| SadTalker | github.com/OpenTalker/SadTalker | Ch05 §4 — 4단(원샷 오디오→영상) 계열의 대표 |

## 2. 목소리 — TTS와 클로닝

| 이름 | 주소 | 이 책에서 |
|---|---|---|
| edge-tts | github.com/rany2/edge-tts | 기본 TTS. Ch21 §5 실측의 기준선 |
| Chatterbox (다국어) | github.com/resemble-ai/chatterbox | Ch03 §3 · Ch03+ — 셀프호스트 클로닝 베이스(실측 3.0GB) |
| OpenVoice | github.com/myshell-ai/OpenVoice | 음색 변환 계열. 온라인 부록 K §5 |
| LoRA (저계수 적응) | arxiv.org/abs/2106.09685 | Ch03+ — 어댑터 22.5MB · 핫스왑의 원리 |
| XTTS 계열 | — | **폐기.** 한국어 끝음절이 늘어짐(부록 C §6) |

## 3. 3D 아바타 — 브라우저

| 이름 | 주소 | 이 책에서 |
|---|---|---|
| VRM 규격 | vrm.dev | Ch18 — 표준 뼈·표정 이름. 모델 교체가 코드 수정 없이 되는 근거 |
| three-vrm | github.com/pixiv/three-vrm | Ch18 — VRM 로더 |
| three.js | threejs.org | Ch18 — 브라우저 렌더 |
| Mixamo | mixamo.com | Ch18 §7 — 단위·휴식 포즈가 다른 파일의 사례 |
| VRoid Studio | vroid.com/studio | 캐릭터 제작 |

## 4. 시간 — 동기화와 컨테이너

| 이름 | 주소 | 이 책에서 |
|---|---|---|
| FFmpeg | ffmpeg.org | Ch14 · Ch09 — mux · 무음 검출 |
| NTSC 프레임률 30000/1001 | — | Ch14 — 29/30 반올림이 만든 드리프트 |
| ITU-R BT.1359 | itu.int (BT 시리즈 권고) | Ch14 — 립싱크 허용 오차 +90ms / −185ms |
| WebRTC (AEC·NS·AGC) | webrtc.org | Ch23 §4 — 자기 목소리 제거를 직접 만들지 않는 이유 |
| Docker | docs.docker.com | Ch28 — 렌더 잡을 통째로 굽기 |

## 5. 머리 — LLM · 검색 · 평가

| 이름 | 주소 | 이 책에서 |
|---|---|---|
| Google Gemini API | ai.google.dev | Ch07 · Ch21 · Ch22 — 지연 실측과 페르소나 실험 |
| 네이티브 오디오(S2S) | ai.google.dev (Live API 문서) | Ch21 §5 — 첫 소리 0.67초, 그리고 그때 잃는 것 |
| RAG | arxiv.org/abs/2005.11401 | Ch25 — 검색 증강 생성의 원 논문 |
| FastAPI | fastapi.tiangolo.com | Ch21 · Ch28 — 서버 |

## 6. 손 — 수어와 통역

| 이름 | 주소 | 이 책에서 |
|---|---|---|
| MediaPipe | ai.google.dev/edge/mediapipe | Ch23+ §6 — 상체·양손 키포인트(Holistic) |
| AI-Hub | aihub.or.kr | Ch23+ §6 — 한국수어 영상 데이터(이용 조건은 제공 기관 공지) |

## 7. 표시 · 출처 · 책임

| 이름 | 주소 | 이 책에서 |
|---|---|---|
| C2PA | c2pa.org | 부록 G §4 — 콘텐츠 출처·이력 표준 |
| SynthID | deepmind.google/technologies/synthid | 부록 G §4 — 생성 과정에 신호를 심는 접근 |
| AI 생성물 표시 의무(2026) | 각 기관 최신 고시 | Ch29 §3 — 조문·시행령은 바뀌므로 본문은 요지만 |

## 8. 이 책이 만든 근거

| 위치 | 무엇 |
|---|---|
| `code/*/_work/*.json` | 본문 수치의 원본. 어떤 스크립트가 어떤 숫자를 냈는지는 부록 C §7 |
| `scripts/claims_audit.py` | 본문의 수치가 위 파일들과 맞는지 대조하는 게이트 |
| `draft/appendix/appF_failure_catalog.md` | 실패 50종 — 접은 경로와 그 사유 |
