import os
import re

import requests
from bs4 import BeautifulSoup

_EMPTY_FILING = {
    "text": None,
    "filing_date": None,
    "filing_type": None,
    "company": None,
    "accession_number": None,
}


def _get_headers():
    user_agent = os.environ.get("SEC_USER_AGENT", "stock-analyzer contact@example.com")
    return {"User-Agent": user_agent}


def _clean_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "lxml")
    text = soup.get_text(separator=" ")
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def download_10k(ticker: str) -> dict:
    try:
        # Step 1: resolve ticker to CIK via EDGAR company tickers JSON
        try:
            resp = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=_get_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            tickers_data = resp.json()
            cik = None
            for entry in tickers_data.values():
                if entry["ticker"].upper() == ticker.upper():
                    cik = str(entry["cik_str"]).zfill(10)
                    break
            if cik is None:
                return _EMPTY_FILING.copy()
        except Exception:
            return _EMPTY_FILING.copy()

        # Step 2: fetch submissions JSON to locate the latest 10-K filing
        try:
            resp = requests.get(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers=_get_headers(),
                timeout=10,
            )
            resp.raise_for_status()
            subs = resp.json()
            recent = subs["filings"]["recent"]
            forms = recent["form"]
            idx = next((i for i, f in enumerate(forms) if f == "10-K"), None)
            if idx is None:
                return _EMPTY_FILING.copy()
            accession_number = recent["accessionNumber"][idx]
            filing_date = recent["filingDate"][idx]
            company = subs["name"]
            primary_doc = recent.get("primaryDocument", [None] * (idx + 1))[idx]
            if not primary_doc:
                return _EMPTY_FILING.copy()
            accession_nodash = accession_number.replace("-", "")
            cik_int = int(cik)
        except Exception:
            return _EMPTY_FILING.copy()

        # Step 4: download and clean the primary document
        try:
            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik_int}"
                f"/{accession_nodash}/{primary_doc}"
            )
            resp = requests.get(doc_url, headers=_get_headers(), timeout=30)
            resp.raise_for_status()
            text = _clean_html(resp.text)
        except Exception:
            return _EMPTY_FILING.copy()

        return {
            "text": text,
            "filing_date": filing_date,
            "filing_type": "10-K",
            "company": company,
            "accession_number": accession_number,
        }
    except Exception:
        return _EMPTY_FILING.copy()
