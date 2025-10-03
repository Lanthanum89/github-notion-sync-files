# GitHub → Notion Portfolio Sync

This repo provides a simple, free way to keep your Notion database in sync with GitHub repos tagged with the topic `portfolio`.

## What it does
- Searches your GitHub account for repos with the topic **`portfolio`**
- UPSERT into a Notion database, matching rows by **Repo URL**
- Updates the following properties:
  - **Name** (Title)
  - **Repo URL** (URL)
  - **Summary** (from GitHub description)
  - **Tech** (top languages from GitHub; multi-select)
  - **Category** (simple heuristic)
  - **Status**, **IG Status**, **Priority** (defaults can be set)
  - **Date Added** (repo creation date)
  - **Demo Link**, **Next Post Hook** (left unchanged if not provided)
- Optionally **archives** Notion pages that no longer appear in the GitHub search results

## Prereqs
1. **Notion integration + database**
   - Create a Notion *internal integration* → copy **NOTION_TOKEN**
   - Share your database with the integration
   - Copy your **Database ID** (from the URL)
   - Database should have these properties (case-sensitive):
     - Name *(Title)*
     - Repo URL *(URL)*
     - Category *(Select)*
     - Tech *(Multi-select)*
     - Summary *(Rich text)*
     - Status *(Select)*
     - IG Status *(Select)*
     - Priority *(Select)*
     - Date Added *(Date)*
     - Demo Link *(URL)*
     - Next Post Hook *(Rich text)*

2. **GitHub**
   - Add the topic **`portfolio`** to each repo you want synced (`Repo → About → Topics`).
   - In your sync repository, set **Repository Secrets**:
     - `NOTION_TOKEN`
     - `NOTION_DATABASE_ID`
     - *(optional)* `GH_TOKEN` — PAT with `public_repo` scope for higher rate limits.
   - Set **Repository Variables**:
     - `GH_USERNAME` = your GitHub username (e.g. `Lanthanum89`).

## How to use
- Copy `sync_portfolio_to_notion.py` to the root of any repository (this one or a dedicated "ops" repo).
- Add the workflow file at `.github/workflows/portfolio-notion-sync.yml`.
- Commit + push.
- Run manually via **Actions → Sync Portfolio to Notion → Run workflow** or wait for 08:00 daily.

## Customise
- Change default selects via environment variables in the workflow:
  - `DEFAULT_STATUS`, `DEFAULT_PRIORITY`, `DEFAULT_IG_STATUS`
- Turn off archiving:
  - Set `ARCHIVE_MISSING: "false"`

## Safety
- The script only *updates/creates* by matching `Repo URL`. It does not delete; archiving toggles the page archived flag.
- Notion rate limits are respected by minimal requests; if you have many repos, increase schedule spacing.

---

Made by Laura (@codermumuk | @Lanthanum89) 💖
