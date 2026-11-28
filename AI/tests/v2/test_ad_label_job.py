"""광고 판별 배치 — 판정된 것만 쓰고, 쓸 수 없는 응답 · 호출 실패는 건너뛴다."""
import asyncio

import services.ad_label_job as job


class FakeQuery:
    def __init__(self, sb, table):
        self.sb, self.table, self.op, self.payload, self.filters = sb, table, "select", None, {}

    def select(self, *_):
        return self

    def is_(self, *_):
        return self

    def order(self, *_):
        return self

    def range(self, *_):
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def eq(self, k, v):
        self.filters[k] = v
        return self

    def execute(self):
        if self.op == "update":
            self.sb.updates.append((self.filters["id"], self.payload))
            return type("R", (), {"data": []})
        data = self.sb.posts if self.table == "influencer_posts" else [{"id": 1, "username": "u"}]
        return type("R", (), {"data": data})


class FakeSB:
    def __init__(self, posts):
        self.posts, self.updates = posts, []

    def table(self, name):
        return FakeQuery(self, name)


def test_hit_strings():
    assert job.hit_strings([{"rule": "disclosure.hashtag", "text": "#광고"}]) == ["disclosure.hashtag:#광고"]


def test_label_writes_only_decided(monkeypatch):
    results = {
        1: {"is_ad": True, "labeled_by": "RULE", "rule_hits": [{"rule": "disclosure.hashtag", "text": "#광고"}]},
        2: {"is_ad": False, "labeled_by": "LLM", "rule_hits": []},
        3: {"is_ad": None, "labeled_by": "LLM", "rule_hits": []},
    }

    async def fake_classify(caption, username, owned, llm=None):
        if caption == "boom":
            raise TimeoutError
        return results[int(caption)]

    monkeypatch.setattr(job, "classify_post", fake_classify)
    monkeypatch.setattr(job, "owned_brands", lambda: {"u": None})
    sb = FakeSB([{"id": i, "account_id": 1, "caption": c} for i, c in [(1, "1"), (2, "2"), (3, "3"), (4, "boom")]])

    summary = asyncio.run(job.label(sb))

    assert sorted(sb.updates) == [(1, {"is_ad": True, "ad_rule_hits": ["disclosure.hashtag:#광고"]}),
                                  (2, {"is_ad": False, "ad_rule_hits": []})]
    assert summary == {"targets": 4, "call_failed": 1, "llm_organic": 1, "rule_ad": 1, "unusable": 1}



def test_owned_brands_reads_raw_accounts(tmp_path):
    path = tmp_path / "accounts.json"
    path.write_text('[{"username": "a", "age_group": "30대", "focus": "x", '
                    '"owned_brands": [{"brand": "B", "aliases": ["비"]}]}, '
                    '{"username": "b", "age_group": "30대", "focus": "x"}]', encoding="utf-8")
    assert job.owned_brands(path) == {"a": [{"brand": "B", "aliases": ["비"]}], "b": None}


def test_real_accounts_file_has_owned_brands():
    assert job.owned_brands()["risabae_art"][0]["brand"] == "TWOSLASHFOUR"


def test_label_passes_owned_brands(monkeypatch):
    seen = []

    async def fake_classify(caption, username, owned, llm=None):
        seen.append((username, owned))
        return {"is_ad": True, "labeled_by": "RULE", "rule_hits": []}

    monkeypatch.setattr(job, "classify_post", fake_classify)
    monkeypatch.setattr(job, "owned_brands", lambda: {"u": [{"brand": "B", "aliases": []}]})
    asyncio.run(job.label(FakeSB([{"id": 1, "account_id": 1, "caption": "x"}])))
    assert seen == [("u", [{"brand": "B", "aliases": []}])]
