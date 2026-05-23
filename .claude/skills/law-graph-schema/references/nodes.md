# Node 詳細規格

## Law（法律）Phase 1

**ID 格式**：`{pcode}`，e.g. `"A0000001"`

**法學依據**：
- 憲法第 170 條：「本憲法所稱之法律，謂經立法院通過，總統公布之法律。」
- 中央法規標準法第 2 條（pcode A0030133）：法律得定名為法、律、條例或通則。
- LawLevel 分類依全國法規資料庫：憲法、法律（含命令性質者）。

**屬性**：

```
# 識別
pcode            : str   # e.g. "A0000001"
law_name         : str   # e.g. "中華民國憲法"
law_level        : str   # "憲法" | "法律" | "命令"
law_category     : str   # e.g. "憲政" — 全國法規資料庫分類

# 版本資訊
law_modified_date: str   # e.g. "19470101"（YYYYMMDD，來自 LawModifiedDate）
law_effective_date: str  # 生效日期（YYYYMMDD）
law_abandon_note : str   # 廢止註記，有值代表已廢止

# 通用屬性（source_pcode = 自身 pcode，source_article_no = ""）
source_pcode        : str
source_article_no   : str   # ""
source_paragraph    : str   # ""
created_at          : str
```

---

## Division（編章節）Phase 1.5

**ID 格式**：`{pcode}#div#{seq}`，seq 為條文陣列中的流水號，e.g. `"B0000001#div#0"`

**法學依據**：
- 中央法規標準法第 8 條：法律條文應分條書寫，冠以條次；內容複雜者得分編、章、節、款、目。
- Akoma Ntoso (UN Legal Document Standard)：body > section > article 的層級對應本設計的 Division > Article。

**資料來源**：ArticleType = "C" 的條文，e.g. `"第 一 編 總則"`、`"第 一 章 法例"`

**屬性**：

```
# 識別
division_id      : str   # e.g. "B0000001#div#0"
division_level   : str   # "編" | "章" | "節" | "款" | "目"（從 content 解析）
division_title   : str   # e.g. "總則"（去除編章號後的標題）
division_no      : str   # e.g. "第 一 編"（原始文字）
seq              : int   # 在 LawArticles 陣列中的位置

# 通用屬性
source_pcode        : str
source_article_no   : str   # ""（Division 無條號）
source_paragraph    : str   # ""
law_modified_date   : str
created_at          : str
```

---

## Article（條文）Phase 1

**ID 格式**：`{pcode}#{article_no}`，e.g. `"B0000001#第 184 條"`

**法學依據**：
- 中央法規標準法第 8 條：法律條文應分條書寫，冠以條次。
- 現行資料：ArticleNo 格式為 `"第 N 條"`（含空格，阿拉伯數字）。

**屬性**：

```
# 識別
pcode            : str   # e.g. "B0000001"
law_name         : str   # e.g. "民法"
article_no       : str   # e.g. "第 184 條"
content          : str   # 條文全文

# 引用（Phase 1 已實作）
cited_articles   : list[str]  # ["B0000001#第 185 條", ...]

# 通用屬性
source_pcode        : str   # 同 pcode
source_article_no   : str   # 同 article_no
source_paragraph    : str   # ""（Article 層級不細分到項）
law_modified_date   : str
created_at          : str
```

---

## LegalSubject（行為主體）Phase 2

**ID 格式**：`{pcode}#{article_no}#subj#{seq}`

**法學依據**：
- Karl Larenz《法學方法論》（Methodenlehre der Rechtswissenschaft）：
  法律規範由「構成要件（Tatbestand）」與「法律效果（Rechtsfolge）」組成，
  構成要件中包含行為主體（Normadressat）的描述。
- 民法第 184 條範例：「因故意或過失，不法侵害他人之權利**者**」→ 行為人。
- 民法第 188 條範例：「**受僱人**因執行職務...」→ 受僱人。

**屬性**：

```
subject_id       : str   # e.g. "B0000001#第 184 條#subj#0"
label            : str   # e.g. "行為人"、"受僱人"、"公務員"
subject_type     : str   # "自然人" | "法人" | "機關" | "不特定人"
raw_text         : str   # 條文原文片段，e.g. "因故意或過失...者"

# 通用屬性
source_pcode        : str
source_article_no   : str
source_paragraph    : str
law_modified_date   : str
created_at          : str
```

---

## LegalAct（法律行為）Phase 2

**ID 格式**：`{pcode}#{article_no}#act#{seq}`

**法學依據**：
- 民法總則第 71-166 條：法律行為（Rechtsgeschäft）為以意思表示為要素的行為。
- 侵權行為（民法第 184 條）：「不法侵害」為事實行為，亦納入此節點。
- 法律行為 vs 事實行為均以 LegalAct 表示，以 act_type 區分。

**屬性**：

```
act_id           : str   # e.g. "B0000001#第 184 條#act#0"
label            : str   # e.g. "不法侵害"、"締結契約"、"違反義務"
act_type         : str   # "法律行為" | "事實行為" | "行政行為"
raw_text         : str   # 條文原文片段

# 通用屬性
source_pcode        : str
source_article_no   : str
source_paragraph    : str
law_modified_date   : str
created_at          : str
```

---

## LegalObject（法律客體）Phase 2

**ID 格式**：`{pcode}#{article_no}#obj#{seq}`

**法學依據**：
- 民法第 184 條：「不法侵害他人之**權利**」→ 客體為「他人之權利」。
- 物權法（民法第三編）：物、智慧財產權等均為法律客體。

**屬性**：

```
object_id        : str   # e.g. "B0000001#第 184 條#obj#0"
label            : str   # e.g. "他人之權利"、"財產"、"名譽"
object_type      : str   # "權利" | "財產" | "人身" | "名譽" | "其他"
raw_text         : str   # 條文原文片段

# 通用屬性
source_pcode        : str
source_article_no   : str
source_paragraph    : str
law_modified_date   : str
created_at          : str
```

---

## Condition（構成要件）Phase 2

**ID 格式**：`{pcode}#{article_no}#cond#{seq}`

**法學依據**：
- Karl Larenz：Tatbestand（構成要件）= 法律效果成立所需的前提事實。
- 民法第 184 條第 1 項：「因**故意或過失**，**不法侵害**他人之權利」→ 兩個並列要件。
- 主觀要件（故意/過失）與客觀要件（不法行為）可以 condition_type 區分。

**屬性**：

```
condition_id     : str   # e.g. "B0000001#第 184 條#cond#0"
label            : str   # e.g. "故意或過失"、"不法侵害他人之權利"
condition_type   : str   # "主觀要件" | "客觀要件" | "程序要件"
raw_text         : str   # 條文原文片段

# 通用屬性
source_pcode        : str
source_article_no   : str
source_paragraph    : str
law_modified_date   : str
created_at          : str
```

---

## LegalEffect（法律效果）Phase 2

**ID 格式**：`{pcode}#{article_no}#effect#{seq}`

**法學依據**：
- Karl Larenz：Rechtsfolge（法律效果）= 構成要件成就後，法律所賦予的結果。
- 常見類型：
  - 請求權（民法第 184 條：損害賠償責任）
  - 形成權（民法第 114 條：撤銷）
  - 抗辯權（民法第 144 條：消滅時效抗辯）
  - 刑罰（刑法第 271 條：死刑、無期徒刑、10 年以上有期徒刑）

**屬性**：

```
effect_id        : str   # e.g. "B0000001#第 184 條#effect#0"
label            : str   # e.g. "負損害賠償責任"、"處死刑"
effect_type      : str   # "請求權" | "形成權" | "抗辯權" | "刑罰" | "行政制裁" | "其他"
raw_text         : str   # 條文原文片段

# 通用屬性
source_pcode        : str
source_article_no   : str
source_paragraph    : str
law_modified_date   : str
created_at          : str
```
