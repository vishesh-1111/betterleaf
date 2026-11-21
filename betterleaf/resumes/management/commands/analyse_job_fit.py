"""Run ``analyse_job_fit`` against a job description and a master resume file.

    python manage.py analyse_job_fit
    python manage.py analyse_job_fit --jd path/to/jd.txt --master path/to/master.json
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from betterleaf.resumes.services.llm import LLMError
from betterleaf.resumes.services.tailor.analyse import TailoringError
from betterleaf.resumes.services.tailor.analyse import analyse_job_fit
from betterleaf.resumes.services.tailor.assemble import build_tailored_resume_data
from betterleaf.resumes.services.tailor.master_view import add_missing_ids
from betterleaf.resumes.services.tailor.master_view import render_master_for_prompt

MOCK_DIR = Path(__file__).resolve().parents[2] / "mock"
DEFAULT_JD = MOCK_DIR / "sample_job_description.txt"
DEFAULT_MASTER = MOCK_DIR / "sample_master_resume.json"


class Command(BaseCommand):
    help = "Score a job description against a master resume with analyse_job_fit."

    def add_arguments(self, parser):
        parser.add_argument("--jd", type=Path, default=DEFAULT_JD,
                            help="Plain-text job description (default: mock sample).")
        parser.add_argument("--master", type=Path, default=DEFAULT_MASTER,
                            help="Master resume JSON as stored in "
                                 "MasterResume.structured_data (default: mock sample).")
        parser.add_argument("--show-prompt", action="store_true",
                            help="Print the master resume as the LLM sees it.")
        parser.add_argument("--tailored", action="store_true",
                            help="Also print the tailored resume data built from "
                                 "the selection.")

    def handle(self, *args, **options):
        job_text = self._read(options["jd"]).strip()
        try:
            master_raw = json.loads(self._read(options["master"]))
        except json.JSONDecodeError as exc:
            msg = f"{options['master']} is not valid JSON: {exc}"
            raise CommandError(msg) from exc

        # Same preparation the analyse_job task does before calling the LLM.
        master_data = add_missing_ids(master_raw)

        if options["show_prompt"]:
            self.stdout.write(render_master_for_prompt(master_data) + "\n")

        try:
            analysis = analyse_job_fit(job_text, master_data)
        except (TailoringError, LLMError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(analysis.model_dump_json(indent=2))

        if options["tailored"]:
            tailored = build_tailored_resume_data(master_data, analysis.selection)
            self.stdout.write("\n--- tailored resume data ---")
            self.stdout.write(json.dumps(tailored, indent=2, default=str))

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            msg = f"Cannot read {path}: {exc}"
            raise CommandError(msg) from exc
