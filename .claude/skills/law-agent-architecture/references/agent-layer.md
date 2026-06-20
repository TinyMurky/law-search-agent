# LangGraph Agent 層

> **此文件已過時，請直接看 `law-rag-agent` skill。**
>
> 本文件描述的是舊版架構（`login → agent ⇆ tool → END`，Gemini 自由決定
> 呼叫哪些工具）。現行架構已改為帶品質回饋環的 Self-RAG 流程
> （`analyze_query → retrieve → grade_documents → generate`，
> 含 rewrite_query / force_end 等節點），State、Graph 流程、
> 介面合約均已不同，這裡的內容不要再參考。
>
> 完整且最新的 State 設計、Graph 流程、節點職責、Strategy Registry、
> 路由邏輯，請查閱 `law-rag-agent` skill（`SKILL.md` 與
> `references/nodes.md`）。
