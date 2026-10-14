
import csv
import json
import os
import re
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

INPUT_FILE = Path("requiredsoftwares.csv")
OUTPUT_FILE = Path("latest_versions.csv")


def find_latest_version(name, current_version, url):
    prompt = f"""
Find the latest stable, generally available release of this software.

Software: {name}
Existing version: {current_version or "Not provided"}
Official or reference URL: {url or "Not provided"}

Use web search to verify the release from an official website,
official release page, or official repository.

Return only a JSON object with these fields:
{{
  "name": "software name",
  "latest_version": "version string",
  "release_url": "URL of the supporting source",
  "status": "verified or unverified"
}}

Do not invent a version. If you cannot verify it, use
"latest_version": "Unknown" and "status": "unverified".
Prefer stable releases, not beta, alpha, or release candidates.
"""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1200,
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 3,
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )

    text_blocks = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ]

    text = "\n".join(text_blocks)
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError(f"No JSON result returned for {name}")

    result = json.loads(match.group())

    return {
        "sno": "",
        "name": name,
        "current_version": current_version,
        "latest_version": result.get("latest_version", "Unknown"),
        "release_url": result.get("release_url", url),
        "status": result.get("status", "unverified"),
    }


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_FILE}")

    with INPUT_FILE.open(
        "r", newline="", encoding="utf-8-sig"
    ) as source:
        reader = csv.DictReader(source)

        required = {"sno", "name", "version", "url"}
        if not reader.fieldnames or not required.issubset(
            reader.fieldnames
        ):
            raise ValueError(
                "CSV headers must include sno, name, version, url"
            )

        software_list = list(reader)

    results = []

    for item in software_list:
        name = (item.get("name") or "").strip()
        if not name:
            continue

        print(f"Checking latest release: {name}")

        try:
            result = find_latest_version(
                name,
                (item.get("version") or "").strip(),
                (item.get("url") or "").strip(),
            )
            result["sno"] = item.get("sno", "")
        except Exception as error:
            print(f"Could not verify {name}: {error}")
            result = {
                "sno": item.get("sno", ""),
                "name": name,
                "current_version": item.get("version", ""),
                "latest_version": "Unknown",
                "release_url": item.get("url", ""),
                "status": "unverified",
            }

        results.append(result)

    fields = [
        "sno",
        "name",
        "current_version",
        "latest_version",
        "release_url",
        "status",
    ]

    with OUTPUT_FILE.open(
        "w", newline="", encoding="utf-8"
    ) as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nReport saved to: {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
