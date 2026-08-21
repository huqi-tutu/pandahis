"""Phase3 参考著作补回 / 格式报警单元测试。"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRANSLATE = ROOT / "historiography-translate"
sys.path.insert(0, str(TRANSLATE))

from lib.voice_postprocess import (  # noqa: E402
    autofix_voice_format,
    ensure_voice_reference_section,
    is_reference_only_failure,
    write_voice_alerts,
)


class TestVoiceRefs(unittest.TestCase):
    def test_restore_missing_refs_from_body(self) -> None:
        phase2 = (
            "旧稿正文。\n\n参考著作：\n1. 《01史记》\n2. 01史记·相关卷\n"
        )
        styled = (
            "新口语正文引了《汉书·高帝纪第一上》，也提到《史记》。"
        )
        out, note, alerts = ensure_voice_reference_section(
            styled,
            phase2,
            {"母本著作": "01史记", "主要史料出处": "《史记·卷8·高祖本纪》"},
            {"母本著作": "01史记"},
        )
        self.assertIn("参考著作", out)
        self.assertIn("汉书", out)
        self.assertNotIn("相关卷", out)
        self.assertTrue(note)
        self.assertTrue(alerts)
        self.assertTrue(all(a.get("severity") == "alert" for a in alerts))

    def test_autofix_bold_records_alert(self) -> None:
        out, fixes, alerts = autofix_voice_format(
            "他**真的**去了。\n\n参考著作：\n1. 《史记》"
        )
        self.assertNotIn("**", out)
        self.assertTrue(fixes)
        self.assertEqual(alerts[0]["code"], "voice_strip_markdown_bold")
        self.assertTrue(alerts[0]["auto_fixed"])

    def test_ref_only_failure(self) -> None:
        self.assertTrue(
            is_reference_only_failure(["文末缺少「参考著作」列表"])
        )
        self.assertFalse(
            is_reference_only_failure(
                ["文末缺少「参考著作」列表", "正文含「喊数/进度汇报」元叙述"]
            )
        )

    def test_write_alerts_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.voice.alerts.json"
            write_voice_alerts(
                path,
                entry_id="GLBL_00085",
                alerts=[
                    {
                        "severity": "alert",
                        "code": "voice_ref_rebuild",
                        "message": "test",
                        "auto_fixed": True,
                    }
                ],
            )
            doc = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(doc["alert_count"], 1)
            self.assertEqual(doc["severity"], "alert")


if __name__ == "__main__":
    unittest.main()
