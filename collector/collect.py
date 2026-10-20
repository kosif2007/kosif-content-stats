"""kosif.org 게시판 조회수 수집기.

글 보기 페이지에만 조회수가 나오고, 열 때마다 +1 된다(화면 값은 +1 이후 값).
그래서 글마다 우리가 연 횟수(visits)를 기억해 두고 빼서 실제 조회수를 구한다.
"""
import datetime as dt
import html as htmllib
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://kosif.org/bbs/board.php"
# (코드, 메뉴, 게시판 이름) — 온라인문의(s1_7)·비공개(s4_4)는 제외
BOARDS = [
    ("s2_2_2", "활동", "ESG 정책·법 Updates"),
    ("s2_3_2", "활동", "지속가능금융 Updates"),
    ("s2_4_2", "활동", "RE100 Updates"),
    ("s2_5_2", "활동", "EV100 Updates"),
    ("s2_6_2", "활동", "CoREi Updates"),
    ("s2_7_2", "활동", "TCFD Updates"),
    ("s2_8_2", "활동", "SBTi Updates"),
    ("s2_9_2", "활동", "PCAF Updates"),
    ("s2_10_2", "활동", "EnergyTag Updates"),
    ("s3_2", "CDP", "CDP 공지사항"),
    ("s3_3", "CDP", "CDP FAQ"),
    ("s3_4", "CDP", "CDP Resources"),
    ("s4_2", "소식", "KoSIF 소식"),
    ("s4_3", "소식", "인사이트"),
    ("s4_5", "소식", "행사자료"),
    ("s4_6", "소식", "보도자료"),
    ("s4_7", "소식", "정기간행물"),
    ("s5_1", "자료실", "자료실"),
]
# 목록에서 파일을 바로 받는 구조라 글을 열 일이 없어 조회수가 거의 안 쌓이는 게시판
UNMEASURED = {"s3_4", "s4_7"}
PROBE_MARGIN = 15     # 알려진 최대 글 번호 뒤로 더 확인할 개수(새 글·목록에 없는 글 찾기)
MAX_LIST_PAGES = 60
WORKERS = 4
PAUSE = 0.15
UA = "KoSIF-content-stats/1.0 (monthly view-count snapshot)"

_VIEW = re.compile(r'<li class="view"><strong>조회수</strong>\s*([\d,]+)')
_DATE = re.compile(r'<li class="date"><strong>작성일</strong>\s*(\d{2})\.(\d{2})\.(\d{2})')
_H3 = re.compile(r'<div class="board-view">.*?<h3>(.*?)</h3>', re.S)
_SPAN = re.compile(r'^\s*<span>(.*?)</span>', re.S)
_TAG = re.compile(r"<[^>]+>")


def _text(s):
    return re.sub(r"\s+", " ", htmllib.unescape(_TAG.sub("", s))).strip()


def parse_view(page):
    """글 보기 페이지 → {title, cat, raw_hits, date} / 글이 없으면 None."""
    v = _VIEW.search(page)
    h = _H3.search(page)
    if not v or not h:
        return None
    inner = h.group(1)
    m = _SPAN.match(inner)
    cat = _text(m.group(1)) if m else ""
    title = _text(inner[m.end():] if m else inner)
    d = _DATE.search(page)
    date = f"20{d.group(1)}-{d.group(2)}-{d.group(3)}" if d else ""
    return {"title": title, "cat": cat, "raw_hits": int(v.group(1).replace(",", "")), "date": date}


def parse_list_ids(page, bo):
    """목록 페이지에서 그 게시판의 글 번호만 뽑는다."""
    pat = re.compile(r"bo_table=" + re.escape(bo) + r"&(?:amp;)?wr_id=(\d+)")
    return {int(x) for x in pat.findall(page)}


def real_hits(raw, visits):
    return max(0, raw - visits)


def key(bo, wid):
    return f"{bo}/{wid}"


def collect(fetch, posts, today, first_run_prior=1):
    """한 번 수집. fetch(url) -> str|None. posts(dict)를 고쳐 쓰고 그날 스냅샷을 돌려준다.

    first_run_prior: posts가 비어 있을 때(첫 실행) 이미 한 번씩 열었던 횟수(2026-10-20 수동 수집).
    """
    first = not posts
    snap = {}
    jobs = []
    for bo, _menu, _name in BOARDS:
        ids = {p["id"] for p in posts.values() if p["bo"] == bo}
        for page in range(1, MAX_LIST_PAGES + 1):
            html = fetch(f"{BASE}?bo_table={bo}&page={page}") or ""
            found = parse_list_ids(html, bo)
            if not found - ids and page > 1:
                break
            ids |= found
        top = max(ids) if ids else 0
        jobs += [(bo, wid) for wid in range(1, top + PROBE_MARGIN + 1)]

    def one(job):
        bo, wid = job
        time.sleep(PAUSE)
        return job, parse_view(fetch(f"{BASE}?bo_table={bo}&wr_id={wid}") or "")

    with ThreadPoolExecutor(WORKERS) as ex:
        results = list(ex.map(one, jobs))

    for (bo, wid), got in results:
        k = key(bo, wid)
        p = posts.get(k)
        if got is None:
            if p and not p.get("deleted"):
                p["deleted"] = today
            continue
        if p is None:
            p = posts[k] = {"bo": bo, "id": wid, "visits": first_run_prior if first else 0}
        p.pop("deleted", None)
        p["visits"] += 1
        p.update(title=got["title"], cat=got["cat"], date=got["date"],
                 hits=real_hits(got["raw_hits"], p["visits"]))
        snap[k] = p["hits"]
    return snap


def make_fetch():
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", UA)]

    def fetch(url):
        for attempt in range(3):
            try:
                with opener.open(url, timeout=30) as r:
                    return r.read().decode("utf-8", "replace")
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(2 * (attempt + 1))
        return None
    return fetch


def main(data_dir):
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    day = today.strftime("%Y-%m-%d")
    posts_path = os.path.join(data_dir, "posts.json")
    posts = {}
    if os.path.exists(posts_path):
        with open(posts_path, encoding="utf-8") as f:
            posts = json.load(f)
    fetch = make_fetch()
    fetch(f"{BASE}?bo_table={BOARDS[0][0]}")  # 세션 쿠키를 먼저 받아 둔다
    snap = collect(fetch, posts, day)
    if not snap:
        print("글을 하나도 읽지 못했습니다. 저장하지 않고 끝냅니다.", file=sys.stderr)
        return 1

    os.makedirs(os.path.join(data_dir, "snapshots"), exist_ok=True)
    with open(posts_path, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=0, sort_keys=True)
    with open(os.path.join(data_dir, "snapshots", f"{day}.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, sort_keys=True, separators=(",", ":"))
    idx_path = os.path.join(data_dir, "snapshots", "index.json")
    idx = {"snapshots": []}
    if os.path.exists(idx_path):
        with open(idx_path, encoding="utf-8") as f:
            idx = json.load(f)
    idx["snapshots"] = sorted(set(idx["snapshots"]) | {day})
    idx["updated"] = today.isoformat(timespec="minutes")
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    with open(os.path.join(data_dir, "boards.json"), "w", encoding="utf-8") as f:
        json.dump([{"code": c, "menu": m, "board": n, "measurable": c not in UNMEASURED}
                   for c, m, n in BOARDS], f, ensure_ascii=False, indent=1)
    print(f"{day}: 글 {len(snap)}개 수집")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data"))
