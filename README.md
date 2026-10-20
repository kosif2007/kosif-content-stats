# KoSIF 콘텐츠 조회수

국문 홈페이지(kosif.org) 게시판·글별 조회수 대시보드. 화면: https://kosif2007.github.io/kosif-content-stats/

- 매월 1일 오전 10시, **KoSIF PC의 윈도우 작업 스케줄러**(작업 이름 `KoSIF 조회수 수집`)가 `scripts/run_collect.ps1`을 실행해 모든 공개 글을 한 번씩 열어 조회수를 읽고 이 저장소에 올린다. PC가 꺼져 있었으면 켜지는 대로 실행된다.
- GitHub Actions로는 못 돌린다: 카페24가 해외 데이터센터 접속에 로봇 확인(CUPID 쿠키) 페이지를 띄움. 이를 우회하지 않는다.
- 홈페이지는 글을 열 때마다 조회수가 +1 되므로, 글마다 수집기가 연 횟수(`visits`)를 기억해 두고 빼서 실제 조회수를 저장한다.
- 바로 갱신: PowerShell에서 `scripts\run_collect.ps1 -Force` (실행할 때마다 홈페이지 조회수가 글마다 +1).
- 기록: `logs/collect.log`(PC에만 있음). PC를 바꾸면 이 폴더를 새 PC에 받고 작업 스케줄러를 다시 등록해야 한다.

| 경로 | 내용 |
|---|---|
| `collector/collect.py` | 수집기(파이썬 표준 라이브러리만) |
| `data/posts.json` | 글별 제목·작성일·visits·최근 실제 조회수 |
| `data/snapshots/<날짜>.json` | 그날 글별 실제 조회수 |
| `index.html` | 대시보드 |
| `docs/` | 설계 메모 |

테스트: `python -m unittest discover -s tests`
