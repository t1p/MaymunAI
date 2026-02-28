import tempfile
import unittest
from pathlib import Path
import textwrap
from unittest.mock import patch

from packs import loader


class TestPackRoutingIsolation(unittest.TestCase):
    def _write_yaml(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")

    def _write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_resolve_and_isolate_pack_configs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packs_dir = root / "packs"

            self._write_yaml(
                packs_dir / "index.yaml",
                """
                version: "1.0.0"
                default_pack: "mabiz"
                packs:
                  - name: "mabiz"
                    path: "mabiz"
                  - name: "mtla"
                    path: "mtla"
                routing:
                  by_chat_id:
                    "101": "mabiz"
                    "202": "mtla"
                """,
            )

            self._write_text(
                packs_dir / "mabiz" / "prompts" / "system.md",
                "MABIZ SYSTEM PROMPT",
            )
            self._write_text(
                packs_dir / "mtla" / "prompts" / "system.md",
                "MTLA SYSTEM PROMPT",
            )

            self._write_yaml(
                packs_dir / "mabiz" / "presets" / "model.yaml",
                """
                generation:
                  model: "gpt-4o-latest"
                  temperature: 0.2
                """,
            )
            self._write_yaml(
                packs_dir / "mtla" / "presets" / "model.yaml",
                """
                generation:
                  model: "gpt-4o-mini"
                  temperature: 0.4
                """,
            )

            self._write_yaml(
                packs_dir / "mabiz" / "guardrails.yaml",
                """
                output_limits:
                  max_message_length: 1111
                forbidden_topics:
                  - "mabiz-secret"
                """,
            )
            self._write_yaml(
                packs_dir / "mtla" / "guardrails.yaml",
                """
                output_limits:
                  max_message_length: 2222
                forbidden_topics:
                  - "mtla-secret"
                """,
            )

            with patch.object(loader, "PACKS_DIR", packs_dir), patch.object(
                loader, "PACK_INDEX_PATH", packs_dir / "index.yaml"
            ):
                idx = loader.load_pack_index()

                pack_a = loader.resolve_pack_for_context({"chat_id": "101"}, index_data=idx)
                pack_b = loader.resolve_pack_for_context({"chat_id": "202"}, index_data=idx)

                self.assertEqual(pack_a, "mabiz")
                self.assertEqual(pack_b, "mtla")

                prompt_a = loader.get_system_prompt_for_pack(pack_a, index_data=idx)
                prompt_b = loader.get_system_prompt_for_pack(pack_b, index_data=idx)
                self.assertNotEqual(prompt_a, prompt_b)

                preset_a = loader.get_pack_model_preset(pack_a, index_data=idx)
                preset_b = loader.get_pack_model_preset(pack_b, index_data=idx)
                self.assertNotEqual(
                    preset_a["generation"]["model"],
                    preset_b["generation"]["model"],
                )

                guardrails_a = loader.get_guardrails_for_pack(pack_a, index_data=idx)
                guardrails_b = loader.get_guardrails_for_pack(pack_b, index_data=idx)
                self.assertNotEqual(
                    guardrails_a["forbidden_topics"],
                    guardrails_b["forbidden_topics"],
                )

                # Меняем только один pack и проверяем, что второй не изменился.
                self._write_text(
                    packs_dir / "mabiz" / "prompts" / "system.md",
                    "MABIZ SYSTEM PROMPT UPDATED",
                )

                prompt_a_updated = loader.get_system_prompt_for_pack("mabiz", index_data=idx)
                prompt_b_after_update = loader.get_system_prompt_for_pack("mtla", index_data=idx)

                self.assertEqual(prompt_a_updated, "MABIZ SYSTEM PROMPT UPDATED")
                self.assertEqual(prompt_b_after_update, "MTLA SYSTEM PROMPT")


if __name__ == "__main__":
    unittest.main()
