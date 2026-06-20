---
name: law-agent-e2e-eval
description: >
  法律搜尋 Agent 的端對端（E2E）行為測試。會先預測一批測試問題
  應該走哪些 node、哪些 retrieve 策略、是否該觸發 rewrite/force_end，
  以及回答品質的合理範圍，再真的用 `make chat` 跟 Agent 對話，
  解析每個節點印出的 log 還原實際執行軌跡，跟預測結果比對，
  整理出哪裡符合預期、哪裡不符合、回答品質如何，以及修改建議。
  修改 `src/agent/graph.py`、任何 `src/agent/nodes/*.py` 的控制流程
  （routing、條件邊、State 欄位語意），或修改任何節點的 system
  prompt 文字之後，務必執行這個 skill 當作 E2E regression test，
  並用它在修改前後各跑一次，比較行為有沒有變好或變壞。
  當使用者說「幫我測試 agent 修改前後的差異」「跑一下 agent 的
  E2E 測試」「這個 prompt 改完整體表現有變好嗎」時也要使用。
---

# Agent 端對端行為測試

## 為什麼需要這個，而不是 `make test`

`make test` 跑的是單元測試，每個節點的依賴（LLM、ChunkBuilder、
NxLawGraph）都是 mock 的——保證的是「給定輸入，這個節點的程式碼
邏輯對不對」，無法保證「真正的 LLM 在真正的法規資料庫上，整條
`analyze_query → retrieve → grade_documents → generate` 走起來
合不合理」。

prompt 文字的調整（措辭、範例、規則）通常不會讓任何單元測試變
紅——mock 的 LLM 回應是寫死的，prompt 怎麼改都不影響 mock 的輸出。
但 prompt 文字正是最常見、影響面卻最不可預期的修改：换一個措辭，
LLM 可能從「選 law:semantic」變成「選 law:hyde」，或從「誠實說找
不到」變成「開始編造法條內容」。這類退步只有真的呼叫一次 LLM、
看它實際選了什麼、答了什麼，才會發現。

這個 skill 就是補上這一塊：用真實的 `make chat` 對話一輪，
把每個 node 印出的 log 解析回「實際執行了什�么」，跟「照理說應該
執行什麼」做比對。

## 核心流程

1. **預測**：針對每個測試問題，依照目前 `analyze_query.py` 的
   intent 分類規則與 `strategy_registry.py` 的策略表，推算這題
   應該被分到哪個 intent、走哪個（或哪幾個）retrieve 策略、
   是否該觸發 rewrite_query 重試或最終 force_end，以及回答內容
   合理的範圍（該提到什麼概念、絕對不該說什麼）。
   預設測試集在 `cases/default.json`，每筆案例已包含預測欄位
   `predicted` 與 `expected_answer`，可以直接用，或視當次修改的
   範圍新增/調整案例（例如改了 rewrite_query 的 prompt，就該針對
   會觸發 rewrite 的案例多寫幾筆)。
2. **執行**：用 `scripts/run_eval.py` 把整批問題送進 `make chat`，
   一次 session 跑完（每輪對話 State 都會重建，互不汙染，這樣做
   只是省下重複載入法規圖/Chroma 的時間）。
3. **還原執行軌跡**：腳本會解析 stdout 裡每個節點印出的
   `[analyze_query]` `[retrieve]` `[grade]` `[rewrite]` `[generate]`
   log，還原成結構化的 `trace.json`（見下方〈log 訊號對照表〉）。
4. **比對與寫報告**：讀 `trace.json`（不要去讀 `raw_log.txt`，
   除非某筆案例的訊號對不上、需要回頭查原始 log 除錯——`trace.json`
   夠精簡，`raw_log.txt` 可能很長，沒事不要把它整份載入 context），
   逐案比對預測 vs 實際，寫成 `report.md`。
5. **修改前後比較**：分別在改動前、改動後各跑一次（用 `--label`
   區分），再比較兩份 `report.md` / `trace.json`，整理出這次改動
   讓哪些案例變好、哪些變差。

## 怎麼執行

```bash
# 在 repo 根目錄執行，前提：已 `make build-chunks`，.env 有 GEMINI_API_KEY
python3 .claude/skills/law-agent-e2e-eval/scripts/run_eval.py \
  --cases .claude/skills/law-agent-e2e-eval/cases/default.json \
  --label before-fix
```

腳本只用標準函式庫，不需要 `uv run`（它內部用 subprocess 呼叫
`make chat`，`make chat` 自己才會用 `uv run`）。

執行完會印出每筆案例的 retrieve 策略與是否觸發 force_end 的速覽，
並把結果寫到：

```
.claude/skills/law-agent-e2e-eval/runs/<run_id>/
├── raw_log.txt   # make chat 完整原始輸出（debug 用）
├── trace.json    # 解析後的結構化執行軌跡，逐案比對時讀這個
└── meta.json     # 跑這次測試時的 git commit/branch/是否有未 commit 變更
```

`run_id` 預設是時間戳記，加 `--label` 會附加在後面（例如
`20260620-143000-before-fix`），方便之後比較時辨認。

整批案例會在同一個 `make chat` session 內依序送出，單個問題若卡住
（網路問題、無限重試）整個 subprocess 會在
`--timeout-per-case`（預設 90 秒）× 案例數 + 60 秒後逾時，逾時會
把已經拿到的部分輸出存下來，方便回頭查是哪一題卡住。

如果 `trace.json` 裡的案例數量比預期少，先看腳本印在 stderr 的
警告，再去翻 `raw_log.txt` 開頭——最常見的原因是 Chroma 還沒
`make build-chunks`，或 `.env` 沒有 `GEMINI_API_KEY`，這種情況
`make chat` 會在還沒進對話迴圈前就直接退出，一筆 `你: ` 都不會
出現。

## log 訊號對照表

腳本解析的所有訊號都來自各節點現有的 `print()`，不是額外加的。
如果之後在 `src/agent/nodes/*.py` 改了這些 print 的文字格式，
要同步更新 `scripts/run_eval.py` 裡對應的正規表達式，否則這個
skill 會悄悄停止偵測到該訊號（trace.json 裡對應欄位會變成空的，
而不是報錯——這是目前唯一需要手動留意的地方）。

| trace.json 欄位 | 來源 print | 代表什麼 |
|---|---|---|
| `intent` / `complexity` | `[analyze_query]: 分類意圖與複雜度: {...}` | LLM 分類出的意圖與複雜度 |
| `retrieve_strategies` | `[retrieve] strategy=...` | 這輪實際執行（可能多筆）的 retrieve 策略，比 `analyze_strategy_lines` 更貼近 ground truth |
| `pcode_misses` / `article_misses` | `[retrieve] 找不到 pcode/條文：...` | direct_lookup 查無資料的法律名稱/條號 |
| `documents_retrieved` | `[retrieve] 共取得 N 份文件` | 每次 retrieve（含 rewrite 重試）取得的文件數，list 因為可能有多輪 |
| `grade_results` | `[grade] 保留 N/M 個文件` | 每輪 grading 的保留比例，list 因為可能有多輪 |
| `rewrite_count` | `[rewrite] 第 N 次重寫` | 這輪對話總共觸發了幾次 rewrite_query |
| `hallucination_checks` / `answer_quality_checks` | `[generate] 幻覺檢查/回答品質：✓\|✗` | 每次 generate（含 regenerate）的把關結果，list 因為可能多輪 |
| `force_end` | 回答內文是否含 force_end 固定模板的開頭句 | **目前 `force_end_node` 本身沒有 print log**，只能用它生成的固定文字當代理訊號偵測，不夠直接；如果之後要讓這個訊號更可靠，可以考慮幫 `force_end_node` 補一行 `print("[force_end] ...")`（這屬於程式碼修改，不在本 skill 範圍內，需要另外確認） |
| `answer` | `Agent: ...`（chat loop 印出的最終回答） | 這輪對話最終回給使用者的文字 |

多輪 rewrite 時，`retrieve_strategies` / `documents_retrieved` /
`grade_results` 會把每輪的訊號攤平彙整在同一個 list 裡，不會標出
「這是第幾輪重試的結果」——對「整體有沒有跑過某個分支」夠用，
但如果需要逐輪拆開看，要回頭讀 `raw_log.txt`。

## 寫 report.md

比對時固定用這個結構：

```markdown
# Agent E2E 測試報告 — <run_id>

git: <commit> (<branch>)<dirty 的話標註 uncommitted changes>

## 案例比對

| 案例 | 預測 strategy | 實際 strategy | 符合？ | rewrite/force_end | 備註 |
|---|---|---|---|---|---|
| direct_lookup_prefix | law:direct_lookup | law:direct_lookup | ✓ | - | |
...

## 回答品質

針對每個案例，讀 trace.json 的 `answer` 欄位，對照
`expected_answer` 的 `must_not_include` / `should_mention`：
逐案說明回答有沒有踩到不該說的話、有沒有提到該提到的概念、
論述是否真的有第二段法條依據支撐（這部分要實際讀回答內容判斷，
無法只靠 regex 比對，需要你自己讀過再下結論）。

## 整體總結

- 做得好的地方：
- 沒做好的地方：
- 整體回答品質：
- 改進建議：
```

`符合？` 欄位的判斷標準：strategy 完全一致才算 ✓，如果
`predicted.retrieve_strategies` 是 `null`（像 comparison 案例，
因為 LLM 分解結果允許有彈性），改成檢查 `notes` 裡寫的判斷依據
（例如「子查詢數量 >= 2 且涵蓋兩個面向」），不要硬套字串相等。

## 修改前後比較

1. 改動前先跑一次：`--label before-<簡短描述>`
2. 套用程式碼/prompt 修改
3. 再跑一次：`--label after-<簡短描述>`
4. 兩份 `report.md` 都讀過後，額外寫一段「差異總結」：哪些案例
   從不符合變符合（進步）、哪些從符合變不符合（退步），以及
   回答品質主觀上有沒有變化。退步的案例要specifically點出是哪個
   節點的行為變了，不要只說「變差了」。

`runs/` 目錄預設不會被 git 追蹤（內容是測試輸出，不是程式碼或
文件）。如果某次比較的結果值得留存當作長期 baseline（例如重大
prompt 改版前後的對照），把該次的 `report.md` 另存一份到
`cases/baselines/<描述性名稱>.md`，那個位置才會進 git。

## 已知限制

- 每次執行都是真的呼叫 Gemini API，會消耗額度且需要等待（一個
  含 7 筆案例、其中一筆會跑滿 rewrite 重試的測試集，大約數分鐘）。
  不要在無關的小修改後就跑全套，只在動到 graph 控制流程或 prompt
  文字時才需要。
- `force_end` 的偵測目前靠回答內文比對固定模板，比較脆弱（見上方
  log 訊號對照表）。
- ambiguous 候選案例（例如 `direct_lookup_ambiguous`）的「正確
  答案」本來就含糊——這是法律名稱本身真有歧義，不是程式錯誤，
  比對時不要把「grading 沒選對候選」當成 bug，重點是有沒有正確
  拆出候選查詢。
