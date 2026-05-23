# Edge 詳細規格

所有 Edge 皆帶通用屬性：

```
source_pcode        : str   # 產生此邊的來源法律 pcode
source_article_no   : str   # 產生此邊的來源條文，e.g. "第 184 條"
source_paragraph    : str   # 來源項次，無則 ""
law_modified_date   : str   # 來源法律的 LawModifiedDate
created_at          : str   # ISO 8601 系統時間
```

---

## 結構邊

### CONTAINS Phase 1

**方向**：`Law/Division → Division/Article`

**法學依據**：
- 中央法規標準法第 8 條：法律內容分編、章、節，再到條。
- 資料來源：ChLaw.json 的 LawArticles 陣列，ArticleType 為 "C"（Division）與 "A"（Article）。

**屬性**：

```
relation         : str   # "contains"（固定值）
```

**範例**：
```
Law("B0000001") --CONTAINS--> Division("B0000001#div#0")   # 民法 → 第一編總則
Division("B0000001#div#1") --CONTAINS--> Article("B0000001#第 1 條")
```

---

### CITES Phase 1

**方向**：`Article → Article`

**法學依據**：
- 立法技術：條文間以「依本法第 X 條」、「第 X 條至第 Y 條」等方式建立明確引用。
- 已實作：CitationExtractor 解析四種引用格式（範圍、並列、本法自引、跨法律）。
- 引用格式確認：條文內文全部使用中文數字，實測 25,737 次中文 vs 0 次阿拉伯數字。

**屬性**：

```
relation         : str   # "cites"（固定值）
citation_type    : str   # "range"（至）| "parallel"（及）|
                         # "self_ref"（本法）| "cross_law"（跨法律）|
                         # "bare"（裸露引用）| "relative"（前條/次條）
```

**範例**：
```
Article("A0000002#第 1 條") --CITES--> Article("A0000001#第 4 條")
# 憲法增修條文第1條 引用 憲法第4條
```

---

## 法律間關係邊

### AMENDS Phase 1.5

**方向**：`Law → Law`

**法學依據**：
- 中央法規標準法第 20 條：法律修正程序，修正後需公布施行。
- 憲法第 174 條：憲法修正程序。
- 實例：中華民國憲法增修條文（A0000002）修正中華民國憲法（A0000001）。
  增修條文第 1 條明確指出「不適用憲法第四條、第一百七十四條之規定」。

**資料來源**：需從 `LawHistories`（沿革）欄位解析，或從法律名稱規律辨識（含「增修」）。

**屬性**：

```
relation         : str   # "amends"（固定值）
amended_articles : str   # 被修正的條號範圍，e.g. "第25至34條"（可為空）
effective_date   : str   # 修正生效日（YYYYMMDD）
```

---

### IMPLEMENTS Phase 1.5

**方向**：`Law → Law`（施行法/細則 → 母法）

**法學依據**：
- 中央法規標準法第 6 條：應以法律規定之事項，不得以命令定之。
- 施行法/細則的法律名稱通常有規律：`{母法名稱}施行法` 或 `{母法名稱}施行細則`。
- 實例：民法施行法（B0000002）→ 民法（B0000001）。

**資料來源**：從法律名稱規律辨識（含「施行法」或「施行細則」），需對應到母法 pcode。

**屬性**：

```
relation         : str   # "implements"（固定值）
```

---

### AUTHORIZED_BY Phase 1.5

**方向**：`Article → Article`（子法授權條文 → 母法授權條文）

**法學依據**：
- 中央法規標準法第 7 條：各機關依其法定職權或基於法律授權訂定之命令，須有法律依據。
- 中央法規標準法第 11 條：法律不得牴觸憲法；命令不得牴觸憲法或法律。
- 實例：中華民國領海及鄰接區法第 5 條：「由行政院訂定，並得分批公告之」。
  → 後續訂定的辦法應有 AUTHORIZED_BY 邊指向此條文。

**資料來源**：需從條文內容解析授權文字（e.g. 「由...訂定」、「依...辦理」）。

**屬性**：

```
relation         : str   # "authorized_by"（固定值）
delegated_to     : str   # 被授權機關，e.g. "行政院"（可為空）
```

---

### SUPERSEDES Phase 1.5

**方向**：`Law → Law`（新法 → 被廢止的舊法）

**法學依據**：
- 中央法規標準法第 21 條：法律廢止方式，包含明示廢止與默示廢止。
- 廢止的舊法在 ChLaw.json 中 `LawAbandonNote` 欄位有值。

**資料來源**：`LawAbandonNote` 欄位 + 法律沿革。

**屬性**：

```
relation         : str   # "supersedes"（固定值）
supersede_date   : str   # 廢止日期（YYYYMMDD）
```

---

## 語意邊（Phase 2，需 LLM 抽取）

### HAS_SUBJECT Phase 2

**方向**：`Article → LegalSubject`

**法學依據**：Karl Larenz 規範結構理論，條文規範的行為主體（Normadressat）。

**屬性**：
```
relation         : str   # "has_subject"
```

---

### HAS_ACT Phase 2

**方向**：`Article → LegalAct`

**法學依據**：法律行為理論（民法總則第二章），法律事實 vs 法律行為。

**屬性**：
```
relation         : str   # "has_act"
```

---

### HAS_OBJECT Phase 2

**方向**：`Article → LegalObject`

**法學依據**：法律關係的客體，包含物（民法第 66-68 條）與權利。

**屬性**：
```
relation         : str   # "has_object"
```

---

### HAS_CONDITION Phase 2

**方向**：`Article → Condition`

**法學依據**：Tatbestand（構成要件），法律效果成立的前提條件。
主觀要件（故意/過失）與客觀要件（不法行為）均包含。

**屬性**：
```
relation         : str   # "has_condition"
```

---

### HAS_EFFECT Phase 2

**方向**：`Article → LegalEffect`

**法學依據**：Rechtsfolge（法律效果），構成要件成就後的法律結果。

**屬性**：
```
relation         : str   # "has_effect"
```

---

### TRIGGERS Phase 2

**方向**：`Condition → LegalEffect`

**法學依據**：條件成就（Tatbestand 滿足）觸發法律效果（Rechtsfolge）。
這是法律規範的核心邏輯結構：「若 P 則 Q」（If Condition then Effect）。

**屬性**：
```
relation         : str   # "triggers"
is_negated       : bool  # True 表示但書（但...不在此限）
```

---

### PENALIZES Phase 2

**方向**：`Article → Article`（罰則條文 → 被規範行為所在的條文）

**法學依據**：
- 罰則通常集中在法律末章，引用前面的義務性條文作為違反對象。
- 刑法分則：每個犯罪構成要件條文對應的刑度。
- 民法：損害賠償條文（第 184 條）罰則性質指向義務性規定。

**資料來源**：條文內容中含「違反第 X 條」、「違反前條」等文字。

**屬性**：
```
relation         : str   # "penalizes"
penalty_type     : str   # "刑事" | "行政" | "民事賠償"
```
