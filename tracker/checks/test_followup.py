import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import main
from logstash_client import ImportTransportError
from pymongo.errors import PyMongoError


class FollowupTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)

        self.path = Path(folder.name) / "source.jsonl"
        self.path.write_text("{}\n", encoding="utf-8")

        self.database = MagicMock()
        self.document = {
            "_id": "scrum17-check",
            "upload_id": "scrum17-check",
            "original_filename": "logs.jsonl",
            "expected_count": None,
            "indexed_count": 0,
            "rejected_count": 0,
        }

        self.patched("source_path", return_value=self.path)
        self.patched("inspect_source", return_value=1)
        self.patched(
            "iter_source_lines",
            return_value=iter([
                {"source_line": 1, "raw": "{}"},
            ]),
        )

        self.sender = self.patched("send_event")
        self.results = self.patched("collect_results")

        sleep = patch.object(main.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)

        quiet = patch.object(main.logging, "exception")
        quiet.start()
        self.addCleanup(quiet.stop)

    def patched(self, name, **kwargs):
        replacement = patch.object(main, name, **kwargs)
        result = replacement.start()
        self.addCleanup(replacement.stop)
        return result

    def run_import(self):
        main.process_import(self.database, self.document)

    def states(self):
        return [
            call.args[1]["$set"]
            for call in self.database.imports.update_one.call_args_list
            if "status" in call.args[1].get("$set", {})
        ]

    def test_fin_lecture_attend_indexation(self):
        self.results.side_effect = [
            (0, 0, None),
            (1, 0, None),
        ]

        self.run_import()

        self.assertEqual(
            [row["status"] for row in self.states()],
            ["EN_COURS", "TERMINE"],
        )
        self.assertTrue(self.states()[0]["reading_complete"])
        self.assertEqual(self.states()[0]["indexed_count"], 0)

    def test_resultats_manquants_finissent_en_echec(self):
        self.results.return_value = (0, 0, None)

        # Raccourcir uniquement l'attente de ce test.
        with patch.object(main, "RESULT_TIMEOUT", 0):
            self.run_import()

        states = self.states()

        self.assertEqual(states[0]["status"], "EN_COURS")
        self.assertEqual(states[-1]["status"], "ECHEC")
        self.assertEqual(
            states[-1]["error"]["code"], "INDEXING_ERROR"
        )
        self.assertEqual(states[-1]["rejected_count"], 0)

    def test_panne_http_ne_devient_pas_rejet_de_donnees(self):
        self.sender.side_effect = ImportTransportError(
            "LOGSTASH_UNAVAILABLE",
            "Transmission non confirmée.",
        )
        self.results.return_value = (0, 0, None)

        self.run_import()
        row = self.states()[-1]

        self.assertEqual(row["status"], "ECHEC")
        self.assertEqual(
            row["error"]["code"], "LOGSTASH_UNAVAILABLE"
        )
        self.assertEqual(row["rejected_count"], 0)
        self.assertFalse(row["reading_complete"])

    def test_echec_conserve_les_indexations_deja_constatees(self):
        self.sender.side_effect = ImportTransportError(
            "LOGSTASH_UNAVAILABLE",
            "Réponse HTTP non reçue.",
        )
        self.results.return_value = (1, 0, None)

        self.run_import()
        row = self.states()[-1]

        self.assertEqual(row["status"], "ECHEC")
        self.assertEqual(row["indexed_count"], 1)
        self.assertEqual(row["rejected_count"], 0)

    def test_tous_rejetes_produisent_echec(self):
        self.results.return_value = (0, 1, None)

        self.run_import()
        row = self.states()[-1]

        self.assertEqual(row["status"], "ECHEC")
        self.assertEqual(
            row["error"]["code"], "NO_INDEXED_EVENTS"
        )
        self.assertEqual(row["rejected_count"], 1)

    def test_panne_mongodb_permet_reprise(self):
        self.results.side_effect = PyMongoError(
            "MongoDB indisponible"
        )

        with self.assertRaises(PyMongoError):
            self.run_import()

        # Aucune finalisation tant que MongoDB est indisponible.
        self.assertEqual(self.states(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)