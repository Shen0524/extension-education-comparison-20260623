import json
import re
import ssl
import urllib.parse
from html import unescape
from urllib.request import Request, urlopen

ctx = ssl._create_unverified_context()


def fetch(url):
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    return urlopen(req, timeout=30, context=ctx).read().decode("utf-8", "ignore")


def clean(html):
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    html = unescape(html)
    return re.sub(r"\s+", " ", html).strip()


def scrape_thu():
    courses = []
    for page in range(1, 34):
        url = "https://eec.thu.edu.tw/search/course?" + urllib.parse.urlencode(
            {
                "data_action_mode": "api",
                "page": page,
                "search_mode": "simple",
                "keyword_course": "",
            }
        )
        obj = json.loads(fetch(url))
        rows = re.findall(
            r"<tr\s+onclick=\"change_menu\('([^']+)'\)\"\s*>([\s\S]*?)</tr>",
            obj["fz_table_data_ui"],
        )
        for link, row in rows:
            text = clean(row)
            name = re.search(r"課程名稱\s*(.*?)\s*(?:招生中|已額滿|確定開課|屆別)", text)
            session = re.search(r"屆別：\s*(\d+)", text)
            date = re.search(r"開課時間\s*([0-9]{4}/[0-9]{2}/[0-9]{2})?", text)
            price = re.search(r"NT\$([0-9,]+)", text)
            status = [s for s in ["招生中", "已額滿", "確定開課"] if s in text]
            courses.append(
                {
                    "link": link,
                    "name": name.group(1).strip() if name else "",
                    "status": status,
                    "session": int(session.group(1)) if session else None,
                    "date": date.group(1) if date and date.group(1) else "",
                    "price": int(price.group(1).replace(",", "")) if price else None,
                }
            )
    return courses


def scrape_ncue():
    courses = []
    for page in range(1, 68):
        html = fetch(
            f"https://cee.ncue.edu.tw/course.php?page_num={page}&btype=&types=&srh=&get_state="
        )
        text = clean(html)
        start = text.find("全部課程 報名中")
        end = text.find("當前第")
        body = text[start:end] if start >= 0 and end > start else text
        for m in re.finditer(r"(20\d{2}/\d{2}/\d{2})\s+([^\s]+)\s+(.+?)\s+我要報名", body):
            courses.append(
                {
                    "date": m.group(1),
                    "category": m.group(2),
                    "name": m.group(3).strip(),
                }
            )
    return courses


def scrape_csmu_home():
    html = fetch("https://extservice.csmu.edu.tw/")
    text = clean(html)
    counts = {}
    for label in [
        "研究所學分班",
        "大學部學分班",
        "專業證照",
        "養生保健",
        "國高中營隊",
        "政府補助",
    ]:
        m = re.search(label + r"\s+(\d+)", text)
        if m:
            counts[label] = int(m.group(1))
    latest = re.findall(r"([^：]+?)\s*：\s*(20\d{2}/\d{2}/\d{2})", text)
    return {
        "counts_visible_on_homepage": counts,
        "latest_news_sample": latest[:10],
        "page_update_date": re.search(r"更新日期：\s*([0-9/]+)", text).group(1)
        if re.search(r"更新日期：\s*([0-9/]+)", text)
        else "",
    }


def summarize():
    ncue = scrape_ncue()
    thu = scrape_thu()
    csmu = scrape_csmu_home()
    thu_prices = [c["price"] for c in thu if c["price"] is not None]
    result = {
        "snapshot_date": "2026-06-23",
        "notes": [
            "Counts are public website snapshots, not official financial statements.",
            "NCUE and THU course counts include public database/listing pages and may include old, closed, or duplicated course rounds.",
            "CSMU homepage exposes category counts directly; full list pages may require category-specific navigation.",
        ],
        "ncue": {
            "public_listing_count": len(ncue),
            "category_counts": {
                c: sum(1 for x in ncue if x["category"] == c)
                for c in sorted(set(x["category"] for x in ncue))
            },
            "sample_courses": ncue[:20],
        },
        "thu": {
            "public_listing_count": len(thu),
            "status_counts": {
                s: sum(1 for x in thu if s in x["status"])
                for s in ["招生中", "已額滿", "確定開課"]
            },
            "price_count": len(thu_prices),
            "price_min": min(thu_prices) if thu_prices else None,
            "price_max": max(thu_prices) if thu_prices else None,
            "highest_session_courses": sorted(
                [x for x in thu if x["session"]], key=lambda x: x["session"], reverse=True
            )[:15],
            "high_price_courses": sorted(
                [x for x in thu if x["price"]], key=lambda x: x["price"], reverse=True
            )[:15],
            "sample_courses": thu[:20],
        },
        "csmu": csmu,
    }
    return result


if __name__ == "__main__":
    print(json.dumps(summarize(), ensure_ascii=False, indent=2))
