import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))
import collect  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def read(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


def view_page(title, hits, date="25.03.04", cat="[공지사항]"):
    return (f'<div class="board-view"><div class="title"><div class="box"><h3><span>{cat}</span>{title}</h3>'
            f'<li class="view"><strong>조회수</strong> {hits:,}</strong></li>'
            f'<li class="date"><strong>작성일</strong> {date}</li>')


class FakeSite:
    """kosif.org 흉내: 글을 열면 조회수 +1, 화면에는 +1 이후 값."""

    def __init__(self, boards):
        self.hits = boards           # {(bo, id): 실제 조회수}
        self.listed = {}             # {bo: 목록에 보이는 id}

    def fetch(self, url):
        q = dict(p.split("=") for p in url.split("?")[1].split("&"))
        bo = q["bo_table"]
        if "wr_id" in q:
            k = (bo, int(q["wr_id"]))
            if k not in self.hits:
                return "<title>오류안내 페이지</title>"
            self.hits[k] += 1
            return view_page(f"글{k[1]}", self.hits[k])
        if q.get("page", "1") != "1":
            return ""
        return "".join(f'href="?bo_table={bo}&amp;wr_id={i}"' for i in self.listed.get(bo, []))


class ParseTests(unittest.TestCase):
    def test_real_view_page(self):
        got = collect.parse_view(read("view.html"))
        self.assertEqual(got["raw_hits"], 463)
        self.assertEqual(got["date"], "2025-12-05")
        self.assertEqual(got["cat"], "[공지사항]")
        self.assertTrue(got["title"].startswith("이벤트 당첨자 안내"))

    def test_not_found_page(self):
        self.assertIsNone(collect.parse_view(read("notfound.html")))

    def test_list_ids_only_that_board(self):
        ids = collect.parse_list_ids(read("list_s4_2.html"), "s4_2")
        self.assertIn(105, ids)
        self.assertNotIn(126, ids)  # s3_2 글은 빠져야 함

    def test_entities_and_commas(self):
        got = collect.parse_view(view_page("A &amp; B “따옴표”", 12345))
        self.assertEqual(got["title"], "A & B “따옴표”")
        self.assertEqual(got["raw_hits"], 12345)


class CollectTests(unittest.TestCase):
    def setUp(self):
        self._boards = collect.BOARDS
        self._pause = collect.PAUSE
        collect.BOARDS = [("s4_2", "소식", "KoSIF 소식")]
        collect.PAUSE = 0

    def tearDown(self):
        collect.BOARDS = self._boards
        collect.PAUSE = self._pause

    def test_first_run_subtracts_prior_and_own_visit(self):
        # 10/20 수동 수집으로 이미 한 번씩 열린 상태(실제 100, 화면엔 101)
        site = FakeSite({("s4_2", 1): 101, ("s4_2", 3): 51})
        site.listed["s4_2"] = [1]           # 3번은 목록에 없음 → 번호 탐색으로 찾아야 함
        posts = {}
        snap = collect.collect(site.fetch, posts, "2026-10-20")
        self.assertEqual(snap, {"s4_2/1": 100, "s4_2/3": 50})
        self.assertEqual(posts["s4_2/3"]["visits"], 2)

    def test_second_run_counts_only_real_views(self):
        site = FakeSite({("s4_2", 1): 101})
        site.listed["s4_2"] = [1]
        posts = {}
        collect.collect(site.fetch, posts, "2026-10-20")
        site.hits[("s4_2", 1)] += 7          # 그사이 실제 방문 7회
        site.hits[("s4_2", 2)] = 3           # 새 글: 실제 3회(우리가 열면 화면엔 4)
        snap = collect.collect(site.fetch, posts, "2026-11-01")
        self.assertEqual(snap["s4_2/1"], 107)
        self.assertEqual(snap["s4_2/2"], 3)

    def test_deleted_post_marked_and_excluded(self):
        site = FakeSite({("s4_2", 1): 11, ("s4_2", 2): 21})
        site.listed["s4_2"] = [1, 2]
        posts = {}
        collect.collect(site.fetch, posts, "2026-10-20")
        del site.hits[("s4_2", 2)]
        snap = collect.collect(site.fetch, posts, "2026-11-01")
        self.assertNotIn("s4_2/2", snap)
        self.assertEqual(posts["s4_2/2"]["deleted"], "2026-11-01")

    def test_site_down_gives_empty_snapshot(self):
        posts = {}
        snap = collect.collect(lambda url: None, posts, "2026-11-01")
        self.assertEqual(snap, {})


if __name__ == "__main__":
    unittest.main()
