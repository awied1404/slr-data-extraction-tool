import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


TARGET_CATEGORY = "Target platform (RQ1)"
BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data-extraction-summary.csv"
DATA_ITEMS_PATH = BASE_DIR / "data-items.json"
SESSION_PATH = BASE_DIR / "other_tag_grouping_session.json"
EXPORT_PATH = BASE_DIR / "other_tag_grouping_export.json"


@dataclass
class QuestionGroupingState:
    terms: Dict[str, Set[str]] = field(default_factory=dict)


class OtherTagGroupingTool(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Other-Tag Value Grouper")
        self.resize(1500, 800)

        self.category = TARGET_CATEGORY
        self.csv_path = CSV_PATH
        self.data_items_path = DATA_ITEMS_PATH
        self.session_path = SESSION_PATH
        self.export_path = EXPORT_PATH

        self.question_data: Dict[str, Dict[str, Set[str]]] = self._load_other_tag_data()
        if not self.question_data:
            raise ValueError(
                f"No rows found for category '{self.category}' with tag='Other' in {self.csv_path}."
            )

        self.questions: List[str] = sorted(self.question_data.keys())
        self.predefined_terms_by_question: Dict[str, Set[str]] = self._load_predefined_terms()
        self.grouping_state: Dict[str, QuestionGroupingState] = {
            question: QuestionGroupingState(
                terms={term: set() for term in sorted(self.predefined_terms_by_question.get(question, set()))}
            )
            for question in self.questions
        }
        self.current_question_index = 0

        self.question_label = QLabel()
        self.ungrouped_list = QListWidget()
        self.term_list = QListWidget()
        self.grouped_values_list = QListWidget()

        self.term_input = QLineEdit()
        self.term_input.setPlaceholderText("Create a new general term")

        self.prev_btn = QPushButton("Previous Question")
        self.next_btn = QPushButton("Next Question")
        self.create_term_btn = QPushButton("Create Term")
        self.delete_term_btn = QPushButton("Delete Selected Term")
        self.assign_btn = QPushButton("Assign Selected Values -> Term")
        self.unassign_btn = QPushButton("<- Remove Selected Values From Term")
        self.save_session_btn = QPushButton("Save Session")
        self.export_btn = QPushButton("Export Grouping")

        self._setup_ui()
        restored_from_session = self._load_session()
        if not restored_from_session:
            self._load_export_fallbacks()
        self._refresh_view()

    def _setup_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)

        header_layout = QHBoxLayout()
        category_label = QLabel(f"Category: {self.category}")
        category_label.setStyleSheet("font-weight: bold;")
        self.question_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(category_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.prev_btn)
        header_layout.addWidget(self.next_btn)
        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.question_label)

        self.prev_btn.clicked.connect(self._go_previous_question)
        self.next_btn.clicked.connect(self._go_next_question)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Other raw_values (green = assigned to at least one term):"))
        self.ungrouped_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        left_layout.addWidget(self.ungrouped_list)

        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.addWidget(QLabel("General terms:"))
        self.term_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        center_layout.addWidget(self.term_list)

        term_create_layout = QHBoxLayout()
        term_create_layout.addWidget(self.term_input)
        term_create_layout.addWidget(self.create_term_btn)
        center_layout.addLayout(term_create_layout)
        center_layout.addWidget(self.delete_term_btn)

        action_layout = QVBoxLayout()
        action_layout.addWidget(self.assign_btn)
        action_layout.addWidget(self.unassign_btn)
        action_layout.addStretch(1)
        center_layout.addLayout(action_layout)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Values currently in selected term:"))
        self.grouped_values_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        right_layout.addWidget(self.grouped_values_list)

        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([620, 380, 620])

        main_layout.addWidget(splitter)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.save_session_btn)
        footer_layout.addWidget(self.export_btn)
        main_layout.addLayout(footer_layout)

        self.create_term_btn.clicked.connect(self._create_term)
        self.delete_term_btn.clicked.connect(self._delete_selected_term)
        self.assign_btn.clicked.connect(self._assign_selected_values)
        self.unassign_btn.clicked.connect(self._unassign_selected_values)
        self.save_session_btn.clicked.connect(self._save_session)
        self.export_btn.clicked.connect(self._export_grouping)
        self.term_list.itemSelectionChanged.connect(self._refresh_grouped_values_view)

    def _load_other_tag_data(self) -> Dict[str, Dict[str, Set[str]]]:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")

        question_data: Dict[str, Dict[str, Set[str]]] = {}
        with self.csv_path.open("r", encoding="utf-8", newline="") as file:
            header = file.readline().strip().split(",")
            expected = ["reviewer", "paper_id", "excluded", "category", "question", "raw_value", "tag"]
            if header != expected:
                file.seek(0)
                import csv

                reader = csv.DictReader(file)
                for row in reader:
                    self._add_row_if_relevant(row, question_data)
                return question_data

            import csv

            file.seek(0)
            reader = csv.DictReader(file)
            for row in reader:
                self._add_row_if_relevant(row, question_data)

        return question_data

    def _add_row_if_relevant(
        self, row: Dict[str, str], question_data: Dict[str, Dict[str, Set[str]]]
    ) -> None:
        category = (row.get("category") or "").strip()
        tag = (row.get("tag") or "").strip().lower()

        if category != self.category or tag != "other":
            return

        question = (row.get("question") or "").strip()
        raw_value = (row.get("raw_value") or "").strip()
        paper_id = (row.get("paper_id") or "").strip()

        if not question or not raw_value or not paper_id:
            return

        if question not in question_data:
            question_data[question] = {}
        if raw_value not in question_data[question]:
            question_data[question][raw_value] = set()
        question_data[question][raw_value].add(paper_id)

    def _current_question(self) -> str:
        return self.questions[self.current_question_index]

    def _load_predefined_terms(self) -> Dict[str, Set[str]]:
        if not self.data_items_path.exists():
            return {}

        try:
            with self.data_items_path.open("r", encoding="utf-8") as file:
                data_items = json.load(file)
        except (json.JSONDecodeError, OSError):
            return {}

        category_payload = data_items.get(self.category)
        if not isinstance(category_payload, dict):
            return {}

        predefined_terms: Dict[str, Set[str]] = {}
        for question, options_payload in category_payload.items():
            terms: Set[str] = set()

            if isinstance(options_payload, list):
                for option in options_payload:
                    if isinstance(option, str) and option.strip():
                        terms.add(option.strip())
            elif isinstance(options_payload, dict):
                nested_options = options_payload.get("options", [])
                if isinstance(nested_options, list):
                    for option in nested_options:
                        if isinstance(option, str) and option.strip():
                            terms.add(option.strip())

            if question in self.question_data and terms:
                predefined_terms[question] = terms

        return predefined_terms

    def _current_state(self) -> QuestionGroupingState:
        return self.grouping_state[self._current_question()]

    def _all_raw_values_for_current_question(self) -> Set[str]:
        return set(self.question_data[self._current_question()].keys())

    def _assigned_raw_values(self, question: str) -> Set[str]:
        assigned: Set[str] = set()
        for raw_values in self.grouping_state[question].terms.values():
            assigned.update(raw_values)
        return assigned

    def _refresh_view(self) -> None:
        question = self._current_question()
        self.question_label.setText(
            f"Question {self.current_question_index + 1}/{len(self.questions)}: {question}"
        )
        self._refresh_term_list()
        self._refresh_ungrouped_list()
        self._refresh_grouped_values_view()
        self.prev_btn.setEnabled(self.current_question_index > 0)
        self.next_btn.setEnabled(self.current_question_index < len(self.questions) - 1)

    def _refresh_term_list(self) -> None:
        current_selected = self._selected_term_name()
        self.term_list.clear()
        for term in sorted(self._current_state().terms.keys()):
            self.term_list.addItem(term)

        if current_selected:
            matches = self.term_list.findItems(current_selected, Qt.MatchFlag.MatchExactly)
            if matches:
                self.term_list.setCurrentItem(matches[0])

    def _refresh_ungrouped_list(self) -> None:
        question = self._current_question()
        all_values = self._all_raw_values_for_current_question()
        all_values_sorted = sorted(all_values)

        self.ungrouped_list.clear()
        assigned = self._assigned_raw_values(question)
        for raw_value in all_values_sorted:
            paper_ids = sorted(self.question_data[question][raw_value])
            assignment_count = sum(
                1 for values in self._current_state().terms.values() if raw_value in values
            )
            item_text = (
                f"{raw_value}  |  papers ({len(paper_ids)}): {', '.join(paper_ids)}"
                f"  |  in terms: {assignment_count}"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, raw_value)
            if raw_value in assigned:
                item.setForeground(Qt.GlobalColor.darkGreen)
            self.ungrouped_list.addItem(item)

    def _refresh_grouped_values_view(self) -> None:
        self.grouped_values_list.clear()
        term = self._selected_term_name()
        if not term:
            return

        question = self._current_question()
        values = sorted(self._current_state().terms.get(term, set()))
        for raw_value in values:
            paper_ids = sorted(self.question_data[question][raw_value])
            item_text = f"{raw_value}  |  papers ({len(paper_ids)}): {', '.join(paper_ids)}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, raw_value)
            self.grouped_values_list.addItem(item)

    def _selected_term_name(self) -> str:
        item = self.term_list.currentItem()
        return item.text() if item else ""

    def _go_previous_question(self) -> None:
        if self.current_question_index > 0:
            self.current_question_index -= 1
            self._refresh_view()

    def _go_next_question(self) -> None:
        if self.current_question_index < len(self.questions) - 1:
            self.current_question_index += 1
            self._refresh_view()

    def _create_term(self) -> None:
        term = self.term_input.text().strip()
        if not term:
            QMessageBox.warning(self, "Invalid term", "Please enter a non-empty term.")
            return

        state = self._current_state()
        if term in state.terms:
            QMessageBox.warning(self, "Duplicate term", "This term already exists.")
            return

        state.terms[term] = set()
        self.term_input.clear()
        self._refresh_term_list()
        matches = self.term_list.findItems(term, Qt.MatchFlag.MatchExactly)
        if matches:
            self.term_list.setCurrentItem(matches[0])
        self._refresh_grouped_values_view()

    def _delete_selected_term(self) -> None:
        term = self._selected_term_name()
        if not term:
            QMessageBox.warning(self, "No term selected", "Select a term to delete.")
            return

        state = self._current_state()
        state.terms.pop(term, None)
        self._refresh_view()

    def _assign_selected_values(self) -> None:
        term = self._selected_term_name()
        if not term:
            QMessageBox.warning(self, "No term selected", "Select a target term first.")
            return

        selected_items = self.ungrouped_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(
                self,
                "No values selected",
                "Select at least one raw_value from the values list.",
            )
            return

        state = self._current_state()
        for item in selected_items:
            raw_value = item.data(Qt.ItemDataRole.UserRole)
            if raw_value:
                state.terms[term].add(raw_value)

        self._refresh_ungrouped_list()
        self._refresh_grouped_values_view()

    def _unassign_selected_values(self) -> None:
        term = self._selected_term_name()
        if not term:
            QMessageBox.warning(self, "No term selected", "Select a term first.")
            return

        selected_items = self.grouped_values_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(
                self,
                "No values selected",
                "Select at least one raw_value from the term-values list.",
            )
            return

        state = self._current_state()
        for item in selected_items:
            raw_value = item.data(Qt.ItemDataRole.UserRole)
            if raw_value in state.terms[term]:
                state.terms[term].remove(raw_value)

        self._refresh_ungrouped_list()
        self._refresh_grouped_values_view()

    def _save_session(self) -> None:
        payload = {
            "category": self.category,
            "current_question_index": self.current_question_index,
            "grouping": {
                question: {
                    "terms": {
                        term: sorted(values)
                        for term, values in sorted(state.terms.items(), key=lambda item: item[0])
                    }
                }
                for question, state in sorted(self.grouping_state.items(), key=lambda item: item[0])
            },
        }

        with self.session_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)

        QMessageBox.information(self, "Saved", f"Session saved to {self.session_path}")

    def _load_session(self) -> bool:
        if not self.session_path.exists():
            return False

        try:
            with self.session_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (json.JSONDecodeError, OSError):
            return False

        session_category = payload.get("category")
        if isinstance(session_category, str) and session_category != self.category:
            return False

        grouping = payload.get("grouping", {})
        if isinstance(grouping, dict):
            for question, question_payload in grouping.items():
                if question not in self.grouping_state or not isinstance(question_payload, dict):
                    continue
                self._restore_question_terms(question, question_payload.get("terms", {}))

        idx = payload.get("current_question_index")
        if isinstance(idx, int) and 0 <= idx < len(self.questions):
            self.current_question_index = idx

        return True

    def _restore_question_terms(self, question: str, terms_payload: object) -> None:
        if not isinstance(terms_payload, dict):
            return

        valid_raw_values = self.question_data[question]
        restored_terms: Dict[str, Set[str]] = {
            term: set() for term in sorted(self.predefined_terms_by_question.get(question, set()))
        }

        for term, values_payload in terms_payload.items():
            if not isinstance(term, str) or not term.strip():
                continue

            values_source: object
            if isinstance(values_payload, dict):
                values_source = values_payload.get("raw_values", [])
            else:
                values_source = values_payload

            if not isinstance(values_source, list):
                values_source = []

            cleaned = {
                value
                for value in values_source
                if isinstance(value, str) and value in valid_raw_values
            }
            restored_terms[term.strip()] = cleaned

        self.grouping_state[question].terms = restored_terms

    def _load_export_fallbacks(self) -> bool:
        candidates: List[Path] = [self.export_path]

        for path in candidates:
            if not path.exists():
                continue

            try:
                with path.open("r", encoding="utf-8") as file:
                    payload = json.load(file)
            except (json.JSONDecodeError, OSError):
                continue

            if self._try_load_from_grouping_export_payload(payload):
                return True

        return False

    def _try_load_from_grouping_export_payload(self, payload: object) -> bool:
        if not isinstance(payload, dict):
            return False

        export_category = payload.get("category")
        if isinstance(export_category, str) and export_category != self.category:
            return False

        questions_payload = payload.get("questions")
        if not isinstance(questions_payload, dict):
            return False

        loaded_any = False
        for question, question_payload in questions_payload.items():
            if question not in self.grouping_state or not isinstance(question_payload, dict):
                continue
            self._restore_question_terms(question, question_payload.get("terms", {}))
            loaded_any = True

        return loaded_any

    def _export_grouping(self) -> None:
        questions_payload = {}

        for question in self.questions:
            terms_payload = {}
            state = self.grouping_state[question]

            for term, raw_values in sorted(state.terms.items(), key=lambda item: item[0]):
                aggregated_paper_ids: Set[str] = set()
                for raw_value in raw_values:
                    aggregated_paper_ids.update(self.question_data[question][raw_value])

                term_origin = (
                    "existing"
                    if term in self.predefined_terms_by_question.get(question, set())
                    else "new"
                )

                terms_payload[term] = {
                    "term_origin": term_origin,
                    "raw_values": sorted(raw_values),
                    "paper_ids": sorted(aggregated_paper_ids),
                    "paper_count": len(aggregated_paper_ids),
                }

            assigned_values = self._assigned_raw_values(question)
            ungrouped_values = sorted(set(self.question_data[question].keys()) - assigned_values)

            questions_payload[question] = {
                "terms": terms_payload,
                "ungrouped_raw_values": [
                    {
                        "raw_value": raw_value,
                        "paper_ids": sorted(self.question_data[question][raw_value]),
                        "paper_count": len(self.question_data[question][raw_value]),
                    }
                    for raw_value in ungrouped_values
                ],
            }

        payload = {
            "category": self.category,
            "source_csv": str(self.csv_path),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "questions": questions_payload,
        }

        with self.export_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)

        QMessageBox.information(self, "Export complete", f"Exported grouping to {self.export_path}")


def main() -> None:
    app = QApplication(sys.argv)

    try:
        window = OtherTagGroupingTool()
    except Exception as exc:
        QMessageBox.critical(None, "Startup error", str(exc))
        raise SystemExit(1) from exc

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
