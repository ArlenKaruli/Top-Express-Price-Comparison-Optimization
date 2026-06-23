import json
import os
import re
import sys
import time
import uuid
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path


CONFIG_FILENAME = "queue_client_config.json"
AGENT_PATTERN = re.compile(r"m\d{2}", re.IGNORECASE)
DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y")


def application_directory():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def load_config():
    config_path = application_directory() / CONFIG_FILENAME
    try:
        with config_path.open(encoding="utf-8") as source:
            config = json.load(source)
    except FileNotFoundError:
        raise RuntimeError(f"Mungon skedari i konfigurimit: {config_path}") from None
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Konfigurimi nuk mund te lexohet: {error}") from None

    queue_root = str(config.get("queue_root", "")).strip()
    if not queue_root:
        raise RuntimeError("Konfigurimi duhet te permbaje queue_root.")
    return (
        Path(queue_root),
        max(1, int(config.get("poll_seconds", 2))),
        max(30, int(config.get("request_timeout_seconds", 300))),
    )


def prompt_agent_code():
    while True:
        agent_code = input("Kodi i agjentit (p.sh. m01): ").strip().lower()
        if AGENT_PATTERN.fullmatch(agent_code):
            return agent_code
        print("Kodi duhet te jete ne formatin m01, m02, etj.")


def parse_date(value):
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise ValueError


def prompt_date(label):
    while True:
        value = input(f"{label} (YYYY-MM-DD): ").strip()
        try:
            return parse_date(value)
        except ValueError:
            print("Date e pavlefshme. Perdorni YYYY-MM-DD, DD.MM.YYYY ose DD/MM/YYYY.")


def prompt_date_range():
    while True:
        start_date = prompt_date("Data e fillimit")
        end_date = prompt_date("Data e mbarimit")
        if end_date >= start_date:
            return start_date, end_date
        print("Data e mbarimit nuk mund te jete para dates se fillimit.")


def six_months_before(value):
    month_index = value.year * 12 + value.month - 1 - 6
    year, month_offset = divmod(month_index, 12)
    month = month_offset + 1
    return value.replace(day=min(value.day, monthrange(year, month)[1]), year=year, month=month)


def ask_to_change_dates():
    while True:
        choice = input("Deshironi t'i ndryshoni datat? Po [p] Jo [j]: ").strip().lower()
        if choice in {"p", "po", "y", "yes"}:
            return True
        if choice in {"j", "jo", "n", "no"}:
            return False
        print("Zgjedhje e pavlefshme. Ju lutem shkruani p ose j.")


def queue_directories(queue_root):
    directories = {
        "requests": queue_root / "Requests",
        "results": queue_root / "Results",
        "errors": queue_root / "Errors",
    }
    unavailable = [name for name, path in directories.items() if not path.is_dir()]
    if unavailable:
        raise RuntimeError(
            "Nuk u gjeten dosjet e radhes: " + ", ".join(unavailable)
        )
    return directories


def submit_request(requests_directory, agent_code, start_date, end_date):
    request_id = str(uuid.uuid4())
    request_path = requests_directory / f"{request_id}.json"
    temporary_path = request_path.with_suffix(".json.tmp")
    payload = {
        "request_id": request_id,
        "agent": agent_code,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    temporary_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_path, request_path)
    return request_id


def wait_for_result(directories, request_id, poll_seconds, timeout_seconds):
    completion_path = directories["results"] / f"{request_id}.json"
    error_path = directories["errors"] / f"{request_id}.json"
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        if completion_path.is_file():
            try:
                completion = json.loads(completion_path.read_text(encoding="utf-8"))
                filename = str(completion["filename"])
                result_path = directories["results"] / filename
                if Path(filename).name != filename or result_path.suffix.lower() != ".xlsx":
                    raise ValueError
            except (KeyError, OSError, ValueError, json.JSONDecodeError):
                raise RuntimeError("Rezultati i raportit eshte i pavlefshem.") from None
            try:
                completion_path.unlink()
            except OSError:
                pass
            if result_path.is_file():
                return result_path
            raise RuntimeError("Skedari i raportit mungon.")
        if error_path.is_file():
            try:
                detail = json.loads(error_path.read_text(encoding="utf-8")).get("error")
            except (OSError, json.JSONDecodeError):
                detail = None
            try:
                error_path.unlink()
            except OSError:
                pass
            raise RuntimeError(detail or "Raporti nuk mund te krijohet.")
        time.sleep(poll_seconds)

    raise RuntimeError("Koha e pritjes per raportin perfundoi.")


def save_result_locally(result_path):
    return result_path


def main():
    print("Kontrolli i cmimeve nga dokumentet FS dhe KFS")
    try:
        queue_root, poll_seconds, timeout_seconds = load_config()
        directories = queue_directories(queue_root)
    except RuntimeError as error:
        print(f"Gabim konfigurimi: {error}")
        input("Shtypni Enter per te dale...")
        return 1

    end_date = date.today()
    start_date = six_months_before(end_date)
    print(f"Data e fillimit: {start_date:%d.%m.%Y}")
    print(f"Data e mbarimit: {end_date:%d.%m.%Y}")
    if ask_to_change_dates():
        start_date, end_date = prompt_date_range()

    agent_code = prompt_agent_code()
    try:
        request_id = submit_request(
            directories["requests"], agent_code, start_date, end_date
        )
        print("Kerkesa u dergua. Duke pritur raportin...")
        result_path = wait_for_result(
            directories, request_id, poll_seconds, timeout_seconds
        )
        output_path = save_result_locally(result_path)
    except (OSError, RuntimeError) as error:
        print(f"Raporti nuk u krijua: {error}")
        input("Shtypni Enter per te dale...")
        return 1

    print(f"U krijua skedari: {output_path.name}")
    try:
        os.startfile(output_path)
    except OSError as error:
        print(f"Skedari u krijua, por nuk u hap automatikisht: {error}")
        input("Shtypni Enter per te dale...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
