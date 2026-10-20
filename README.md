# KoSIF 콘텐츠 조회수

국문 홈페이지(kosif.org) 게시판·글별 조회수 대시보드. 화면: https://kosif2007.github.io/kosif-content-stats/

- 매월 1일 오전 9시(한국) GitHub Actions가 모든 공개 글을 한 번씩 열어 조회수를 읽는다.
- 홈페이지는 글을 열 때마다 조회수가 +1 되므로, 글마다 수집기가 연 횟수(`visits`)를 기억해 두고 빼서 실제 조회수를 저장한다.
- 바로 갱신: Actions → 「조회수 수집」 → Run workflow (누를 때마다 홈페이지 조회수가 글마다 +1).

| 경로 | 내용 |
|---|---|
| `collector/collect.py` | 수집기(파이썬 표준 라이브러리만) |
| `data/posts.json` | 글별 제목·작성일·visits·최근 실제 조회수 |
| `data/snapshots/<날짜>.json` | 그날 글별 실제 조회수 |
| `index.html` | 대시보드 |
| `docs/` | 설계 메모 |

테스트: `python -m unittest discover -s tests`
