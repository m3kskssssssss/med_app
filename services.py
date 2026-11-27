import os
import re
import unicodedata
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup

API_URL = "https://interview.psyonclinic.ru/api/v1/specialists"
CATALOG_URL = "https://interview.psyonclinic.ru/doctors"
TIMEOUT = 25


class SourceError(Exception):
    pass


def normalize(value):
    value = unicodedata.normalize("NFKC", value or "").lower().replace("ё", "е")
    return " ".join(re.findall(r"[а-яa-z0-9]+", value))


def similarity(a, b):
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def fetch_api_doctors():
    key = os.getenv("MEDICAL_API_KEY", "").strip()
    if not key:
        raise SourceError("Не задан MEDICAL_API_KEY. Добавьте ключ в файл .env.")

    doctors = []
    page = 1
    with requests.Session() as session:
        session.headers["Authorization"] = f"Bearer {key}"
        while len(doctors) < 200:
            try:
                response = session.get(API_URL, params={"page": page, "per_page": 50}, timeout=TIMEOUT)
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise SourceError(f"Medical API недоступен: {exc}") from exc

            items = payload.get("data", [])
            if not isinstance(items, list):
                raise SourceError("Medical API вернул неожиданную структуру данных.")
            for item in items:
                doctors.append({
                    "id": item.get("id"),
                    "name": " ".join(filter(None, [item.get("last_name"), item.get("first_name"), item.get("middle_name")])),
                    "specialty": item.get("specialty") or "—",
                    "experience": item.get("experience_years"),
                })
            current = payload.get("current_page", page)
            last = payload.get("last_page")
            if not items or len(doctors) >= 200 or (last is not None and current >= last):
                break
            page = current + 1
    return doctors[:200]


def fetch_catalog_doctors(pages=30):
    doctors = []
    with requests.Session() as session:
        for page in range(1, pages + 1):
            try:
                response = session.get(CATALOG_URL, params={"page": page}, timeout=TIMEOUT)
                response.raise_for_status()
            except requests.RequestException as exc:
                raise SourceError(f"Каталог недоступен (страница {page}): {exc}") from exc

            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.select("article.doctor-card")
            if not cards:
                raise SourceError(f"На странице {page} каталога не найдены карточки врачей.")
            for card in cards:
                link = card.select_one("h3 a")
                paragraphs = card.select("div.p-5 > p")
                specialty = paragraphs[0].get_text(" ", strip=True) if paragraphs else "—"
                experience_text = paragraphs[1].get_text(" ", strip=True) if len(paragraphs) > 1 else ""
                experience_match = re.search(r"\d+", experience_text)
                clinic = next((p.get_text(" ", strip=True) for p in paragraphs if "Медицин" in p.get_text()), None)
                price_tag = card.select_one("div.mt-5 > strong")
                doctors.append({
                    "id": link.get("href") if link else None,
                    "name": link.get_text(" ", strip=True) if link else "—",
                    "specialty": specialty,
                    "experience": int(experience_match.group()) if experience_match else None,
                    "clinic": clinic,
                    "price": price_tag.get_text(" ", strip=True) if price_tag else None,
                    "url": link.get("href") if link else None,
                })
    return doctors


def match_doctors(api_doctors, catalog_doctors):
    candidates = []
    for ai, api in enumerate(api_doctors):
        for ci, catalog in enumerate(catalog_doctors):
            if normalize(api["specialty"]) != normalize(catalog["specialty"]):
                continue
            name_score = similarity(api["name"], catalog["name"])
            api_parts = normalize(api["name"]).split()
            catalog_parts = normalize(catalog["name"]).split()
            exact = api_parts == catalog_parts or (
                len(api_parts) == len(catalog_parts) and sorted(api_parts) == sorted(catalog_parts)
            )
            same_surname = bool(api_parts and catalog_parts and api_parts[0] == catalog_parts[0])
            possible = not exact and name_score >= 0.72 and (
                same_surname or similarity(api_parts[0], catalog_parts[0]) >= 0.8
            )
            if exact:
                candidates.append((2, name_score, ai, ci, ""))
            elif possible:
                reason = f"Похожие ФИО (совпадение {name_score:.0%}); требуется ручная проверка."
                candidates.append((1, name_score, ai, ci, reason))

    matched_api = set()
    matched_catalog = set()
    results = []
    for rank, _, ai, ci, reason in sorted(candidates, key=lambda item: (-item[0], -item[1])):
        if ai in matched_api or ci in matched_catalog:
            continue
        matched_api.add(ai)
        matched_catalog.add(ci)
        api = api_doctors[ai]
        catalog = catalog_doctors[ci]
        results.append({
            "status": "matched" if rank == 2 else "possible",
            "name": catalog["name"],
            "specialty": catalog["specialty"],
            "api": api,
            "catalog": catalog,
            "reason": reason,
        })

    for ai, api in enumerate(api_doctors):
        if ai not in matched_api:
            results.append({"status": "api_only", "name": api["name"], "specialty": api["specialty"], "api": api, "catalog": None, "reason": "Нет подходящей записи в обработанных страницах каталога."})
    for ci, catalog in enumerate(catalog_doctors):
        if ci not in matched_catalog:
            results.append({"status": "catalog_only", "name": catalog["name"], "specialty": catalog["specialty"], "api": None, "catalog": catalog, "reason": "Нет подходящей записи среди полученных из Medical API."})

    for index, result in enumerate(results):
        result["index"] = index
    order = {"possible": 0, "matched": 1, "api_only": 2, "catalog_only": 3}
    return sorted(results, key=lambda item: (order[item["status"]], item["name"]))


def load_comparison():
    api = fetch_api_doctors()
    catalog = fetch_catalog_doctors()
    return match_doctors(api, catalog), len(api), len(catalog), (len(catalog) + 11) // 12
