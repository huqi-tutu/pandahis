"""汉书合传机械划块自动修复。"""

from __future__ import annotations

import unittest

from lib import blocks_workflow, gates
from lib.hanshu_hezhuan_autofix import (
    apply_cobio_patches,
    build_override_protagonists_manifest,
    try_build_mechanical_blocks,
    try_repair_hanshu_hezhuan_step1,
)


def test_hanshu_override_blocks_expand() -> None:
    for vol in ("054", "056", "057", "084", "087", "088"):
        work = "02汉书"
        idx = gates.load_paragraph_index(work, vol)
        draft, msg = try_build_mechanical_blocks(work, vol, idx, {"narrative_mode": "hezhuan"})
        assert draft is not None, msg
        errs = blocks_workflow.blocks_payload_errors(draft, expected_total=int(idx["total"]))
        assert not errs, f"{vol}: {errs}"
        expanded, expand_errs = blocks_workflow.expand_blocks(
            {**draft, "total_paragraphs": int(idx["total"])}
        )
        assert expanded is not None
        assert not expand_errs, f"{vol}: {expand_errs}"


def test_override_manifest_057_has_three_unique_protagonists() -> None:
    manifest = build_override_protagonists_manifest("057")
    assert manifest is not None
    protagonists = manifest["protagonists"]
    assert [item["name"] for item in protagonists] == ["刘参", "梁孝王", "刘揖"]
    assert all(item["category"] == "宗戚" for item in protagonists)


def test_cobio_patch_056() -> None:
    skeleton = {
        "segment_attribution": [{"paragraph": 8, "owners": [{"name": "周仁", "category": "文臣"}]}],
        "entries": [{"史略名称": "周仁", "史略分类": "文臣"}],
    }
    ok, msg = apply_cobio_patches("02汉书", "056", skeleton)
    assert ok
    assert "张欧" in msg
    p8 = next(r for r in skeleton["segment_attribution"] if r["paragraph"] == 8)
    owners = [o["name"] for o in p8["owners"]]
    assert "周仁" in owners and "张欧" in owners
    names = {e["史略名称"] for e in skeleton["entries"]}
    assert "张欧" in names


def test_cobio_patch_049_dual_ownership() -> None:
    skeleton = {
        "volume": "萧何曹参传",
        "segment_attribution": [
            {"paragraph": 7, "owners": [{"name": "曹参", "category": "文臣"}]},
        ],
        "entries": [
            {
                "史略名称": "萧何",
                "史略分类": "文臣",
                "paragraphs": [{"volume": "萧何曹参传", "paragraph_from": 2, "paragraph_to": 6}],
            },
            {
                "史略名称": "曹参",
                "史略分类": "文臣",
                "paragraphs": [{"volume": "萧何曹参传", "paragraph_from": 7, "paragraph_to": 11}],
            },
        ],
    }
    ok, msg = apply_cobio_patches("02汉书", "049", skeleton)
    assert ok
    assert "P7双归属萧何/曹参" in msg
    p7 = next(r for r in skeleton["segment_attribution"] if r["paragraph"] == 7)
    assert [o["name"] for o in p7["owners"]] == ["萧何", "曹参"]
    by_name = {entry["史略名称"]: entry["paragraphs"] for entry in skeleton["entries"]}
    assert by_name["萧何"] == [{"volume": "萧何曹参传", "paragraph_from": 2, "paragraph_to": 7}]
    assert by_name["曹参"] == [{"volume": "萧何曹参传", "paragraph_from": 7, "paragraph_to": 11}]


def test_cobio_patch_051_dual_ownership_chain() -> None:
    skeleton = {
        "volume": "樊郦滕灌傅靳周传",
        "segment_attribution": [
            {"paragraph": 7, "owners": [{"name": "夏侯婴", "category": "武将"}]},
            {"paragraph": 9, "owners": [{"name": "灌婴", "category": "武将"}]},
            {"paragraph": 12, "owners": [{"name": "傅宽", "category": "武将"}]},
            {"paragraph": 13, "owners": [{"name": "靳歙", "category": "武将"}]},
            {"paragraph": 14, "owners": [{"name": "周緤", "category": "武将"}]},
        ],
        "entries": [
            {"史略名称": "郦商", "史略分类": "武将", "paragraphs": [{"volume": "樊郦滕灌傅靳周传", "paragraph_from": 6, "paragraph_to": 6}]},
            {"史略名称": "夏侯婴", "史略分类": "武将", "paragraphs": [{"volume": "樊郦滕灌傅靳周传", "paragraph_from": 7, "paragraph_to": 8}]},
            {"史略名称": "灌婴", "史略分类": "武将", "paragraphs": [{"volume": "樊郦滕灌傅靳周传", "paragraph_from": 9, "paragraph_to": 11}]},
            {"史略名称": "傅宽", "史略分类": "武将", "paragraphs": [{"volume": "樊郦滕灌傅靳周传", "paragraph_from": 12, "paragraph_to": 12}]},
            {"史略名称": "靳歙", "史略分类": "武将", "paragraphs": [{"volume": "樊郦滕灌傅靳周传", "paragraph_from": 13, "paragraph_to": 13}]},
            {"史略名称": "周緤", "史略分类": "武将", "paragraphs": [{"volume": "樊郦滕灌傅靳周传", "paragraph_from": 14, "paragraph_to": 14}]},
        ],
    }
    ok, msg = apply_cobio_patches("02汉书", "051", skeleton)
    assert ok
    assert "P7双归属郦商/夏侯婴" in msg
    attr = {row["paragraph"]: row["owners"] for row in skeleton["segment_attribution"]}
    assert [o["name"] for o in attr[7]] == ["郦商", "夏侯婴"]
    assert [o["category"] for o in attr[7]] == ["武将", "武将"]
    assert [o["name"] for o in attr[9]] == ["夏侯婴", "灌婴"]
    assert [o["category"] for o in attr[9]] == ["武将", "武将"]
    assert [o["name"] for o in attr[12]] == ["灌婴", "傅宽"]
    assert [o["name"] for o in attr[13]] == ["傅宽", "靳歙"]
    assert [o["name"] for o in attr[14]] == ["靳歙", "周緤"]
    by_name = {entry["史略名称"]: entry["paragraphs"] for entry in skeleton["entries"]}
    assert by_name["郦商"] == [{"volume": "樊郦滕灌傅靳周传", "paragraph_from": 6, "paragraph_to": 7}]
    assert by_name["夏侯婴"] == [{"volume": "樊郦滕灌傅靳周传", "paragraph_from": 7, "paragraph_to": 9}]
    assert by_name["灌婴"] == [{"volume": "樊郦滕灌傅靳周传", "paragraph_from": 9, "paragraph_to": 12}]
    assert by_name["傅宽"] == [{"volume": "樊郦滕灌傅靳周传", "paragraph_from": 12, "paragraph_to": 13}]
    assert by_name["靳歙"] == [{"volume": "樊郦滕灌傅靳周传", "paragraph_from": 13, "paragraph_to": 14}]
    assert by_name["周緤"] == [{"volume": "樊郦滕灌傅靳周传", "paragraph_from": 14, "paragraph_to": 14}]


def test_cobio_patch_052_dense_dual_ownership() -> None:
    skeleton = {
        "volume": "张周赵任申屠传",
        "segment_attribution": [
            {"paragraph": 2, "owners": [{"name": "张苍", "category": "文臣"}]},
            {"paragraph": 3, "owners": [{"name": "周昌", "category": "文臣"}]},
            {"paragraph": 4, "owners": [{"name": "赵尧", "category": "文臣"}]},
            {"paragraph": 5, "owners": [{"name": "任敖", "category": "文臣"}]},
            {"paragraph": 6, "owners": [{"name": "申屠嘉", "category": "文臣"}]},
        ],
        "entries": [
            {"史略名称": "张苍", "史略分类": "文臣", "paragraphs": [{"volume": "张周赵任申屠传", "paragraph_from": 2, "paragraph_to": 2}]},
            {"史略名称": "周昌", "史略分类": "文臣", "paragraphs": [{"volume": "张周赵任申屠传", "paragraph_from": 3, "paragraph_to": 3}]},
            {"史略名称": "赵尧", "史略分类": "文臣", "paragraphs": [{"volume": "张周赵任申屠传", "paragraph_from": 4, "paragraph_to": 4}]},
            {"史略名称": "任敖", "史略分类": "文臣", "paragraphs": [{"volume": "张周赵任申屠传", "paragraph_from": 5, "paragraph_to": 5}]},
            {"史略名称": "申屠嘉", "史略分类": "文臣", "paragraphs": [{"volume": "张周赵任申屠传", "paragraph_from": 6, "paragraph_to": 7}]},
        ],
    }
    ok, msg = apply_cobio_patches("02汉书", "052", skeleton)
    assert ok
    assert "P2双归属张苍/周昌" in msg
    attr = {row["paragraph"]: row["owners"] for row in skeleton["segment_attribution"]}
    assert [o["name"] for o in attr[2]] == ["张苍", "周昌"]
    assert [o["name"] for o in attr[3]] == ["周昌", "赵尧"]
    assert [o["name"] for o in attr[4]] == ["赵尧", "周昌"]
    assert [o["name"] for o in attr[5]] == ["任敖", "张苍"]
    assert [o["name"] for o in attr[6]] == ["张苍", "申屠嘉"]
    by_name = {entry["史略名称"]: entry["paragraphs"] for entry in skeleton["entries"]}
    assert by_name["张苍"] == [
        {"volume": "张周赵任申屠传", "paragraph_from": 2, "paragraph_to": 2},
        {"volume": "张周赵任申屠传", "paragraph_from": 5, "paragraph_to": 6},
    ]
    assert by_name["周昌"] == [{"volume": "张周赵任申屠传", "paragraph_from": 2, "paragraph_to": 4}]
    assert by_name["赵尧"] == [{"volume": "张周赵任申屠传", "paragraph_from": 3, "paragraph_to": 4}]
    assert by_name["任敖"] == [{"volume": "张周赵任申屠传", "paragraph_from": 5, "paragraph_to": 5}]
    assert by_name["申屠嘉"] == [{"volume": "张周赵任申屠传", "paragraph_from": 6, "paragraph_to": 7}]


def test_cobio_patch_057_strict_dual_ownership() -> None:
    skeleton = {
        "volume": "文三王传",
        "segment_attribution": [
            {"paragraph": 2, "owners": [{"name": "刘参", "category": "宗戚"}]},
            {"paragraph": 4, "owners": [{"name": "梁孝王", "category": "宗戚"}]},
            {"paragraph": 5, "owners": [{"name": "刘揖", "category": "宗戚"}]},
        ],
        "entries": [
            {
                "史略名称": "刘参",
                "史略分类": "宗戚",
                "paragraphs": [{"volume": "文三王传", "paragraph_from": 2, "paragraph_to": 2}],
            },
            {
                "史略名称": "梁孝王",
                "史略分类": "宗戚",
                "paragraphs": [{"volume": "文三王传", "paragraph_from": 3, "paragraph_to": 4}],
            },
            {
                "史略名称": "刘揖",
                "史略分类": "宗戚",
                "paragraphs": [{"volume": "文三王传", "paragraph_from": 5, "paragraph_to": 5}],
            },
        ],
    }
    ok, msg = apply_cobio_patches("02汉书", "057", skeleton)
    assert ok
    assert "P2双归属" in msg
    attr = {row["paragraph"]: row["owners"] for row in skeleton["segment_attribution"]}
    assert [o["name"] for o in attr[2]] == ["梁孝王", "刘参", "刘揖"]
    assert [o["name"] for o in attr[4]] == ["梁孝王", "刘参"]
    assert [o["name"] for o in attr[5]] == ["刘揖", "梁孝王"]
    by_name = {entry["史略名称"]: entry["paragraphs"] for entry in skeleton["entries"]}
    assert by_name["刘参"] == [
        {"volume": "文三王传", "paragraph_from": 2, "paragraph_to": 2},
        {"volume": "文三王传", "paragraph_from": 4, "paragraph_to": 4},
    ]
    assert by_name["梁孝王"] == [
        {"volume": "文三王传", "paragraph_from": 2, "paragraph_to": 9}
    ]
    assert by_name["刘揖"] == [
        {"volume": "文三王传", "paragraph_from": 2, "paragraph_to": 2},
        {"volume": "文三王传", "paragraph_from": 5, "paragraph_to": 5},
    ]


def test_cobio_patch_083_same_paragraph_handoff() -> None:
    skeleton = {
        "volume": "隽疏于薛平彭传",
        "segment_attribution": [
            {"paragraph": 15, "owners": [{"name": "平当", "category": "文臣"}]},
        ],
        "entries": [
            {
                "史略名称": "薛广德",
                "史略分类": "文臣",
                "paragraphs": [{"volume": "隽疏于薛平彭传", "paragraph_from": 14, "paragraph_to": 14}],
            },
            {
                "史略名称": "平当",
                "史略分类": "文臣",
                "paragraphs": [{"volume": "隽疏于薛平彭传", "paragraph_from": 15, "paragraph_to": 17}],
            },
        ],
    }
    ok, msg = apply_cobio_patches("02汉书", "083", skeleton)
    assert ok
    assert "P15双归属薛广德/平当" in msg
    attr = {row["paragraph"]: row["owners"] for row in skeleton["segment_attribution"]}
    assert [o["name"] for o in attr[15]] == ["薛广德", "平当"]
    by_name = {entry["史略名称"]: entry["paragraphs"] for entry in skeleton["entries"]}
    assert by_name["薛广德"] == [{"volume": "隽疏于薛平彭传", "paragraph_from": 14, "paragraph_to": 15}]
    assert by_name["平当"] == [{"volume": "隽疏于薛平彭传", "paragraph_from": 15, "paragraph_to": 17}]


def test_cobio_patch_084_dual_ownership() -> None:
    skeleton = {
        "volume": "王贡两龚鲍传",
        "segment_attribution": [
            {"paragraph": 17, "owners": [{"name": "龚胜", "category": "文臣"}]},
            {"paragraph": 20, "owners": [{"name": "龚舍", "category": "文臣"}]},
        ],
        "entries": [
            {"史略名称": "王吉", "史略分类": "文臣", "paragraphs": [{"volume": "王贡两龚鲍传", "paragraph_from": 4, "paragraph_to": 10}]},
            {"史略名称": "贡禹", "史略分类": "文臣", "paragraphs": [{"volume": "王贡两龚鲍传", "paragraph_from": 11, "paragraph_to": 16}]},
            {"史略名称": "龚胜", "史略分类": "文臣", "paragraphs": [{"volume": "王贡两龚鲍传", "paragraph_from": 17, "paragraph_to": 19}, {"volume": "王贡两龚鲍传", "paragraph_from": 21, "paragraph_to": 21}]},
            {"史略名称": "龚舍", "史略分类": "文臣", "paragraphs": [{"volume": "王贡两龚鲍传", "paragraph_from": 20, "paragraph_to": 20}]},
            {"史略名称": "鲍宣", "史略分类": "文臣", "paragraphs": [{"volume": "王贡两龚鲍传", "paragraph_from": 22, "paragraph_to": 27}]},
        ],
    }
    ok, msg = apply_cobio_patches("02汉书", "084", skeleton)
    assert ok
    assert "P17双归属龚胜/龚舍" in msg
    assert "P20双归属龚胜/龚舍" in msg
    attr = {row["paragraph"]: row["owners"] for row in skeleton["segment_attribution"]}
    assert [o["name"] for o in attr[17]] == ["龚胜", "龚舍"]
    assert [o["name"] for o in attr[20]] == ["龚胜", "龚舍"]
    by_name = {entry["史略名称"]: entry["paragraphs"] for entry in skeleton["entries"]}
    assert by_name["龚胜"] == [{"volume": "王贡两龚鲍传", "paragraph_from": 17, "paragraph_to": 21}]
    assert by_name["龚舍"] == [
        {"volume": "王贡两龚鲍传", "paragraph_from": 17, "paragraph_to": 17},
        {"volume": "王贡两龚鲍传", "paragraph_from": 20, "paragraph_to": 20},
    ]


def test_087_override_uses_strict_single_owner_boundaries() -> None:
    work = "02汉书"
    vol = "087"
    idx = gates.load_paragraph_index(work, vol)
    draft, msg = try_build_mechanical_blocks(work, vol, idx, {"narrative_mode": "hezhuan"})
    assert draft is not None, msg
    blocks = draft["blocks"]
    assert [(b["name"], b["paragraph_from"], b["paragraph_to"]) for b in blocks] == [
        ("眭弘", 2, 2),
        ("夏侯始昌", 3, 3),
        ("夏侯胜", 4, 8),
        ("京房", 9, 14),
        ("翼奉", 15, 22),
        ("李寻", 23, 33),
    ]


def test_cobio_patch_087_restores_suihong_handoff_paragraph() -> None:
    skeleton = {
        "volume": "眭两夏侯京翼李传",
        "segment_attribution": [
            {"paragraph": 3, "owners": [{"name": "夏侯始昌", "category": "文臣"}]},
        ],
        "entries": [
            {"史略名称": "眭弘", "史略分类": "文臣", "paragraphs": [{"volume": "眭两夏侯京翼李传", "paragraph_from": 2, "paragraph_to": 2}]},
            {"史略名称": "夏侯始昌", "史略分类": "文臣", "paragraphs": [{"volume": "眭两夏侯京翼李传", "paragraph_from": 3, "paragraph_to": 3}]},
        ],
    }
    ok, msg = apply_cobio_patches("02汉书", "087", skeleton)
    assert ok
    assert "P3双归属眭弘/夏侯始昌" in msg
    attr = {row["paragraph"]: row["owners"] for row in skeleton["segment_attribution"]}
    assert [o["name"] for o in attr[3]] == ["眭弘", "夏侯始昌"]
    by_name = {entry["史略名称"]: entry["paragraphs"] for entry in skeleton["entries"]}
    assert by_name["眭弘"] == [{"volume": "眭两夏侯京翼李传", "paragraph_from": 2, "paragraph_to": 3}]


def test_cobio_patches_idempotent_after_first_apply() -> None:
    skeleton = {
        "volume": "文三王传",
        "segment_attribution": [
            {
                "paragraph": 2,
                "owners": [
                    {"name": "梁孝王", "category": "宗戚"},
                    {"name": "刘参", "category": "宗戚"},
                    {"name": "刘揖", "category": "宗戚"},
                ],
            },
            {
                "paragraph": 4,
                "owners": [
                    {"name": "梁孝王", "category": "宗戚"},
                    {"name": "刘参", "category": "宗戚"},
                ],
            },
            {
                "paragraph": 5,
                "owners": [
                    {"name": "刘揖", "category": "宗戚"},
                    {"name": "梁孝王", "category": "宗戚"},
                ],
            },
        ],
        "entries": [
            {
                "史略名称": "刘参",
                "史略分类": "宗戚",
                "paragraphs": [
                    {"volume": "文三王传", "paragraph_from": 2, "paragraph_to": 2},
                    {"volume": "文三王传", "paragraph_from": 4, "paragraph_to": 4},
                ],
            },
            {
                "史略名称": "梁孝王",
                "史略分类": "宗戚",
                "paragraphs": [{"volume": "文三王传", "paragraph_from": 2, "paragraph_to": 9}],
            },
            {
                "史略名称": "刘揖",
                "史略分类": "宗戚",
                "paragraphs": [
                    {"volume": "文三王传", "paragraph_from": 2, "paragraph_to": 2},
                    {"volume": "文三王传", "paragraph_from": 5, "paragraph_to": 5},
                ],
            },
        ],
    }
    ok, msg = apply_cobio_patches("02汉书", "057", skeleton)
    assert not ok
    assert msg == ""


def test_repair_writes_valid_blocks() -> None:
    work = "02汉书"
    for vol in ("056", "057"):
        idx = gates.load_paragraph_index(work, vol)
        bp = blocks_workflow.blocks_path(work, vol)
        if bp.exists():
            bp.unlink()
        ok, msg = try_repair_hanshu_hezhuan_step1(work, vol, idx)
        assert ok, msg
        vok, vmsg = blocks_workflow.blocks_valid(bp, idx)
        assert vok, vmsg
        bp.unlink(missing_ok=True)


class TestHanshuHezhuanAutofix(unittest.TestCase):
    def test_hanshu_override_blocks_expand(self) -> None:
        test_hanshu_override_blocks_expand()

    def test_override_manifest_057_has_three_unique_protagonists(self) -> None:
        test_override_manifest_057_has_three_unique_protagonists()

    def test_cobio_patch_049_dual_ownership(self) -> None:
        test_cobio_patch_049_dual_ownership()

    def test_cobio_patch_051_dual_ownership_chain(self) -> None:
        test_cobio_patch_051_dual_ownership_chain()

    def test_cobio_patch_052_dense_dual_ownership(self) -> None:
        test_cobio_patch_052_dense_dual_ownership()

    def test_cobio_patch_056(self) -> None:
        test_cobio_patch_056()

    def test_cobio_patch_057_strict_dual_ownership(self) -> None:
        test_cobio_patch_057_strict_dual_ownership()

    def test_cobio_patches_idempotent_after_first_apply(self) -> None:
        test_cobio_patches_idempotent_after_first_apply()

    def test_repair_writes_valid_blocks(self) -> None:
        test_repair_writes_valid_blocks()


if __name__ == "__main__":
    unittest.main()
