
# Law Ingestion 模組說明

## 資料來源

- `raw_data/laws/ChLaw.json`：全國法規資料庫，UTF-8 BOM 編碼，包含 1,343 部法律
- 頂層結構：`{ "UpdateDate": "...", "Laws": [...] }`

---

## LawReader 與 CitationExtractor 的關係

兩者是**生產者 → 消費者**關係，由呼叫端（`cmd/load_laws/main.py`）串起來。
流程必須分兩階段，不能邊讀邊解析：

```
LawReader.load()
    → list[Law]
        → LawReader.build_name_to_pcode(laws)
            → dict[law_name → pcode]
                → CitationExtractor(lookup)
                    → extractor.extract_from_law(law)  # 對每部法律跑一次
```

**為何要兩階段：** `CitationExtractor` 初始化時需要完整的 `law_name → pcode`
lookup table，才能辨識跨法律引用。若邊讀邊解析，後面的法律引用到尚未讀到的
法律就會 miss。

`LawReader` 只負責 I/O，`CitationExtractor` 只負責解析，兩者沒有直接依賴。

---

## 條文引用（cited_articles）解析規則

### 關鍵發現

條文內文**全部使用中文數字**引用，沒有任何阿拉伯數字（實測 25,737 次中文 vs 0 次阿拉伯）。
`ArticleNo` 欄位則使用阿拉伯數字加空格，例如 `"第 18 條"`。
因此 regex match 後必須將中文數字轉換成阿拉伯數字，才能對應到 `ArticleNo`。

### 四種引用格式

| 類型 | 範例 | 處理方式 |
|---|---|---|
| 跨法律引用 | `民法第七十條`、`政府採購法第四條` | 用 `law_name → pcode` lookup table 轉換 |
| 本法自引 | `本法第二十七條`、`本條例第四條` | 直接使用當前條文的 pcode |
| 範圍引用 | `第二十五條至第三十四條`、`第九十七條及第九十八條` | 展開成多個條目 |
| 相對引用 | `前條` | 用條文在 Law.articles 中的位置推算，只計算 ArticleType="A" 的條文 |

> `次條` 在實際資料中幾乎不出現，但實作時仍需支援。
> `前二項`、`前項` 是**項**的相對引用，不是條，忽略不處理。

### cited_articles 格式

```
"{pcode}#{ArticleNo}"

範例：
"A0000001#第 1 條"
"B0000001#第 25 條"
```

### 解析流程

1. 所有 Law 全部載入後，建立 `law_name → pcode` lookup table
2. 對每個 ArticleType="A" 的條文執行 regex
3. 中文數字 → 阿拉伯數字轉換，組成 `{pcode}#第 N 條` 格式
4. 範圍引用（至/及）展開成多個條目
5. 相對引用（前條/次條）用條文在 ordered articles 中的 index 推算
6. 結果寫入 `Article.cited_articles`

> **注意**：`及` 有兩種意思（`第九條及第十條` vs 一般連接詞），需確認前後都是條號才展開。

### 跨法律引用的 lookup 問題

部分引用的法律名稱可能：
- 使用簡稱（`公司法` 而非全名）→ 資料中 1,343 部法律都是正式名稱，簡稱可能 match 不到
- 引用的法律不在 ChLaw.json 中（例如已廢止法律）→ lookup 失敗時略過，不建立邊

---

## 中文數字轉換

需支援範圍：1 ～ 約 2000（法條編號上限）

特殊格式：
- `一百零三` → 103
- `一百十條` → 110（台灣法律慣用，省略「一百」後的「零」）
- `二十` → 20
- `十` → 10

---

## 驗證策略

1. **單元測試**：對中文數字轉換器和每種 regex pattern 分別做 parametrize 測試
2. **整合測試**：用已知有大量引用的法律驗證（例如憲法增修條文引用憲法）
3. **Sanity check**：全部跑完後統計 cited_articles 總數，太少代表 regex 有問題
