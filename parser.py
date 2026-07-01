"""
Модуль парсинга конкурсных списков для СПбПУ и СПбГУ.
"""

import logging
import re
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from config import SPBPU, SPBGU, HEADERS

logger = logging.getLogger(__name__)


class ProgramResult:
    """Результат поиска по одному направлению в одном вузе."""

    def __init__(
        self,
        university: str,
        program_name: str,
        position: int,
        position_original: int,
        score: Optional[int] = None,
        priority: Optional[int] = None,
        competitor_count: Optional[int] = None,
        total_budget: Optional[int] = None,
        total_applications: Optional[int] = None,
    ):
        self.university = university
        self.program_name = program_name
        self.position = position
        self.position_original = position_original
        self.score = score
        self.priority = priority
        self.competitor_count = competitor_count
        self.total_budget = total_budget
        self.total_applications = total_applications

    def to_dict(self) -> dict:
        return {
            "university": self.university,
            "program_name": self.program_name,
            "position": self.position,
            "position_original": self.position_original,
            "score": self.score,
            "priority": self.priority,
            "competitor_count": self.competitor_count,
            "total_budget": self.total_budget,
            "total_applications": self.total_applications,
        }

    @staticmethod
    def from_dict(data: dict) -> "ProgramResult":
        return ProgramResult(
            university=data["university"],
            program_name=data["program_name"],
            position=data["position"],
            position_original=data.get("position_original", 0),
            score=data.get("score"),
            priority=data.get("priority"),
            competitor_count=data.get("competitor_count"),
            total_budget=data.get("total_budget"),
            total_applications=data.get("total_applications"),
        )


def _count_real_competitors(
    applicants: list[dict],
    user_code: str,
    user_score: int,
    user_priority: int,
) -> int:
    """
    Считает реальных конкурентов:
      - балл выше, чем у пользователя
      - И приоритет конкурента >= приоритету пользователя
        (конкурент заинтересован в этом направлении не меньше)
    """
    count = 0
    for a in applicants:
        code = a.get("code", "")
        score = a.get("sum") or a.get("score") or 0
        priority = a.get("priority") or 0
        if code == user_code:
            continue
        if isinstance(score, int) and score > user_score and isinstance(priority, int) and priority <= user_priority:
            count += 1
    return count


# =====================================================================
#  ПАРСЕР СПбПУ
# =====================================================================

async def _spbpu_get_session(session: aiohttp.ClientSession) -> bool:
    try:
        async with session.get(
            SPBPU["main_page"],
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            return resp.status == 200
    except Exception as e:
        logger.error("СПбПУ: ошибка сессии: %s", e)
        return False


async def _spbpu_get_programs(session: aiohttp.ClientSession) -> list[dict]:
    """Получает список ВСЕХ специальностей бакалавриата (очная форма)."""
    seen_ids: set[int] = set()
    programs: list[dict] = []

    for condition in ("1", "2", "3", "4", "6"):
        try:
            async with session.post(
                SPBPU["get_code_list"],
                json={
                    "id_1": SPBPU["education_form"],
                    "id_2": condition,
                    "education_level": SPBPU["education_level"],
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                for item in data.get("code_list", []):
                    if item["id"] not in seen_ids:
                        seen_ids.add(item["id"])
                        programs.append(item)
        except Exception as e:
            logger.warning("СПбПУ: ошибка при условии %s: %s", condition, e)

    return programs


async def _spbpu_fetch_abit_list(
    session: aiohttp.ClientSession, program_id: str
) -> Optional[list[dict]]:
    params = {
        "filter_1": SPBPU["education_form"],
        "filter_2": "",
        "filter_3": program_id,
        "education_level": SPBPU["education_level"],
    }
    try:
        async with session.get(
            SPBPU["get_abit_list"],
            params=params,
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("results", [])
    except Exception as e:
        logger.error("СПбПУ: ошибка загрузки program_id=%s: %s", program_id, e)
        return None


async def _spbpu_get_direction_info(
    session: aiohttp.ClientSession, program_id: str
) -> Optional[dict]:
    try:
        async with session.post(
            SPBPU["get_direction_info"],
            json={
                "id_3": program_id,
                "education_level": SPBPU["education_level"],
                "condition": "1",
            },
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data[0] if isinstance(data, list) and data else None
    except Exception as e:
        logger.warning("СПбПУ: ошибка info program_id=%s: %s", program_id, e)
        return None


async def fetch_spbpu(user_code: str) -> list[dict]:
    results: list[dict] = []

    async with aiohttp.ClientSession(
        cookies={}, headers={"User-Agent": HEADERS["User-Agent"]}
    ) as session:
        if not await _spbpu_get_session(session):
            return results

        programs = await _spbpu_get_programs(session)
        if not programs:
            logger.warning("СПбПУ: не получен список специальностей")
            return results

        logger.info("СПбПУ: получено %d специальностей", len(programs))

        for prog in programs:
            program_id = str(prog["id"])
            program_title = prog["title"]

            abit_list = await _spbpu_fetch_abit_list(session, program_id)
            if abit_list is None:
                continue

            info = await _spbpu_get_direction_info(session, program_id)
            total_budget = (
                int(info["places"])
                if info and info.get("places") not in (None, "—")
                else None
            )
            total_apps = (
                int(info["applications"])
                if info and info.get("applications") not in (None, "—")
                else None
            )

            for entry in abit_list:
                if entry.get("code") == user_code:
                    position = int(entry.get("num", 0))
                    score = int(entry["sum"]) if entry.get("sum") else None
                    priority = int(entry["priority"]) if entry.get("priority") else None

                    has_original = (
                        entry.get("approval", "").strip().lower() == "получено"
                    )

                    position_original = 0
                    if has_original:
                        orig_count = 0
                        for e in abit_list:
                            if e.get("approval", "").strip().lower() == "получено":
                                orig_count += 1
                                if e.get("code") == user_code:
                                    position_original = orig_count

                    # Считаем реальных конкурентов
                    competitor_count = None
                    if score is not None and priority is not None:
                        competitor_count = _count_real_competitors(
                            abit_list, user_code, score, priority
                        )

                    results.append(
                        ProgramResult(
                            university=SPBPU["name"],
                            program_name=program_title,
                            position=position,
                            position_original=position_original,
                            score=score,
                            priority=priority,
                            competitor_count=competitor_count,
                            total_budget=total_budget,
                            total_applications=total_apps,
                        ).to_dict()
                    )
                    break

    return results


# =====================================================================
#  ПАРСЕР СПбГУ
# =====================================================================

async def _spbgu_get_report_meta(session: aiohttp.ClientSession) -> Optional[dict]:
    url = SPBGU["report_url"]
    try:
        async with session.get(
            url,
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                logger.warning("СПбГУ: report page вернул %d", resp.status)
                return None
            html = await resp.text()
    except Exception as e:
        logger.error("СПбГУ: ошибка загрузки report page: %s", e)
        return None

    soup = BeautifulSoup(html, "html.parser")
    meta_tag = soup.find("script", id="priem-list-02-report-meta")
    if not meta_tag:
        logger.warning("СПбГУ: meta-тег не найден")
        return None

    try:
        import json as j
        return j.loads(meta_tag.string)
    except Exception as e:
        logger.error("СПбГУ: ошибка парсинга meta JSON: %s", e)
        return None


def _spbgu_extract_specialities(meta: dict) -> list[dict]:
    specs: list[dict] = []
    sections = meta.get("sections", [])
    for section in sections:
        title_2 = (section.get("title_2") or "").strip().lower()
        if "заочн" in title_2:
            continue
        for sp in section.get("specialities", []):
            specs.append({
                "id": sp["id"],
                "title": f"{sp.get('code', '')} {sp.get('name', '')}".strip(),
            })
    return specs


async def _spbgu_fetch_speciality_data(
    session: aiohttp.ClientSession,
    report_id: str,
    speciality_ids: list[str],
    applicant_code: str = "",
) -> Optional[list[dict]]:
    payload = {
        "report_priem_list_02_id": report_id,
        "speciality_ids": speciality_ids,
        "filters": {
            "education_level_sort_order": SPBGU["education_level"],
            "report_upload_id": "",
            "faculty_name": "",
            "program_name": "",
            "speciality": "",
            "applicant_code": applicant_code,
            "education_form_name": "",
            "fin_source_name": "",
            "contract_status": "",
            "consent_status": "",
            "priority": "",
            "status": "",
            "is_foreign": "",
        },
    }
    headers = {**HEADERS, "X-Requested-With": "XMLHttpRequest"}
    try:
        async with session.post(
            SPBGU["api_data"],
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status != 200:
                logger.warning("СПбГУ: API вернул %d", resp.status)
                return None
            data = await resp.json()
            return data.get("blocks", [])
    except Exception as e:
        logger.error("СПбГУ: ошибка API: %s", e)
        return None


def _spbgu_parse_html_applicants(soup: BeautifulSoup) -> list[dict]:
    """
    Парсит HTML-таблицу и возвращает список всех абитуриентов
    с полями: code, score, priority.
    """
    applicants: list[dict] = []
    rows = soup.select("table.table tbody tr, table tbody tr, tbody tr")
    if not rows:
        rows = soup.find_all("tr")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        code_cell = cells[1].get_text(" ", strip=True)
        code_clean = re.sub(r"[\s\-–—\u00a0]", "", code_cell)
        if not code_clean:
            continue

        score = _extract_int(cells[2].get_text())
        priority = _extract_int(cells[7].get_text()) if len(cells) > 7 else None

        applicants.append({
            "code": code_clean,
            "score": score or 0,
            "priority": priority or 99,
        })

    return applicants


async def fetch_spbgu(user_code: str) -> list[dict]:
    results: list[dict] = []

    async with aiohttp.ClientSession(
        cookies={}, headers={"User-Agent": HEADERS["User-Agent"]}
    ) as session:
        meta = await _spbgu_get_report_meta(session)
        if not meta:
            return results

        report_id = meta.get("id")
        if not report_id:
            logger.error("СПбГУ: нет report_id в meta")
            return results

        specialities = _spbgu_extract_specialities(meta)
        if not specialities:
            logger.warning("СПбГУ: не найдено специальностей (очная форма)")
            return results

        logger.info("СПбГУ: найдено %d специальностей", len(specialities))

        user_code_clean = re.sub(r"[\s\-–—\u00a0]", "", user_code)
        batch_size = 10

        for i in range(0, len(specialities), batch_size):
            batch = specialities[i : i + batch_size]
            spec_ids = [s["id"] for s in batch]

            blocks = await _spbgu_fetch_speciality_data(
                session, report_id, spec_ids, applicant_code=user_code
            )
            if blocks is None:
                continue

            for block_idx, block in enumerate(blocks):
                html = block.get("html", "")
                if not html:
                    continue

                spec_title = batch[block_idx]["title"] if block_idx < len(batch) else "Неизвестно"
                soup = BeautifulSoup(html, "html.parser")
                applicants = _spbgu_parse_html_applicants(soup)

                # Ищем пользователя
                user_entry = None
                for a in applicants:
                    if a["code"] == user_code_clean:
                        user_entry = a
                        break

                if user_entry is None:
                    # Может код не полностью совпадает — проверим вхождение
                    for a in applicants:
                        if user_code_clean in a["code"] or a["code"] in user_code_clean:
                            user_entry = a
                            break

                if user_entry is None:
                    continue

                position = 0
                position_original = 0
                score = user_entry["score"]
                priority = user_entry["priority"]
                competitor_count = None

                # Считаем позицию и позицию среди оригиналов
                rows = soup.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue
                    code_cell = re.sub(r"[\s\-–—\u00a0]", "", cells[1].get_text(" ", strip=True))
                    if code_cell == user_code_clean or user_code_clean in code_cell:
                        pos = _extract_int(cells[0].get_text())
                        if pos:
                            position = pos
                        has_orig = any(
                            c.get_text(" ", strip=True).lower() in ("да", "есть", "получено", "представлен")
                            for c in cells
                        )
                        if has_orig:
                            position_original = 1  # упрощённо
                        break

                if score and priority and priority != 99:
                    competitor_count = _count_real_competitors(
                        applicants, user_code_clean, score, priority
                    )

                results.append(
                    ProgramResult(
                        university=SPBGU["name"],
                        program_name=spec_title,
                        position=position,
                        position_original=position_original,
                        score=score,
                        priority=priority if priority != 99 else None,
                        competitor_count=competitor_count,
                    ).to_dict()
                )

    return results


def _extract_int(text: str) -> Optional[int]:
    m = re.search(r"\d+", text.replace("\xa0", " ").strip())
    return int(m.group()) if m else None


# =====================================================================
#  УНИВЕРСАЛЬНАЯ ФУНКЦИЯ
# =====================================================================

async def fetch_all(user_code: str) -> dict[str, list[dict]]:
    import asyncio

    spbpu_task = asyncio.create_task(fetch_spbpu(user_code))
    spbgu_task = asyncio.create_task(fetch_spbgu(user_code))

    spbpu_results = await spbpu_task
    spbgu_results = await spbgu_task

    result: dict[str, list[dict]] = {}
    if spbpu_results:
        result[SPBPU["name"]] = spbpu_results
    if spbgu_results:
        result[SPBGU["name"]] = spbgu_results

    return result
