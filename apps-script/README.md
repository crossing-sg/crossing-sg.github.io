# Proposal form backend (Google Sheets and Apps Script)

`Code.gs` stores proposals and support from the website in a Google Sheet and returns aggregated results. Individual points are never returned to the website.

## First setup (about 10 minutes)

1. Create a new Google Sheet with the shared project Google account, for example "Crossing proposals (team only)". Share it only with the team.
2. In the Sheet: **Extensions → Apps Script**. Delete the sample code, paste the whole of `Code.gs`, and save.
3. In the editor, choose the function **`setup`** in the toolbar and click **Run**. Google asks for permission the first time: choose the project account → Advanced → Go to project (unsafe) → Allow. This creates the tabs `proposals` and `support` with their headers.
4. **Deploy → New deployment** → type **Web app**.
   - Execute as: **Me**
   - Who has access: **Anyone**
   - Click Deploy and copy the **Web app URL** (it ends with `/exec`).
5. Paste the URL into `website/js/site-config.js` as `appsScriptUrl: '...'`, then commit and push.
6. Test: open `<Web app URL>?view=summary` in the browser. It should show `{"proposals":0,"segments":0,"lastUpdated":"-"}`.

## Updating the script later

Edit the code, save, then **Deploy → Manage deployments → Edit (pencil) → Version: New version → Deploy**. The URL stays the same. A plain save does not change the live web app.

## Pilot settings

At the top of `Code.gs`:

| Setting | Pilot value | Full launch | Effect |
|---|---|---|---|
| `MIN_PROPOSALS` | 1 | 3 | Number of proposals before a segment appears on the map |
| `LINE_MIN` | 1 | 3 | Number of proposals before the mean crossing line is shown. With 1, a segment with a single proposal shows that resident's own points |

After changing either value, deploy a new version (see above).

## Reviewing entries (team)

| Tab | Column | What to do |
|---|---|---|
| `proposals` | `status` | Change `ok` to `rejected` for spam or entries outside a road. Rejected rows leave the totals the next time the map loads |
| `proposals` | `story_status` | New experiences arrive as `pending`. Change to `approved` to allow them on the map, or `rejected` |
| `support` | `status` | Change to `rejected` for obvious repeated clicks |

Do not delete rows, so the record of what was received stays complete. Do not share the Sheet outside the team, because it holds the marked points.

## What the website calls

| Call | Returns |
|---|---|
| POST `{kind: 'proposal', ...}` | `{ok, count, road}`, where `count` is the number of proposals on that segment |
| POST `{kind: 'support', seg_id}` | `{ok}` |
| GET `?view=segments` | Segments with 3 or more proposals: count, support, most requested type and reason, nearest crossing, mean crossing line |
| GET `?view=summary` | Total proposals, segments shown, date of the last proposal |
| GET `?view=csv` | The aggregated segment table as CSV (linked from the Methodology page) |
