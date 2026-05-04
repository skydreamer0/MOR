# Codex Prompt Workflow

## Default MOR Prompt

```text
你是我的 MOR 專案工程助理。

請先閱讀 AGENTS.md、README、ROADMAP。
本次只處理以下任務：

[任務內容]

請遵守：
1. 只讀必要檔案。
2. 先回報你要看的檔案。
3. 不要改無關功能。
4. 不要重構。
5. 完成後跑測試。
6. 最後用 4 行回報：
修改：
驗證：
風險：
下一步：
```

## Fast Loop

1. Ask Codex to analyze one small task without editing.
2. Confirm the direction or file scope.
3. Ask Codex to edit only the scoped files.
4. Run tests.
5. Review `git diff`.
6. Ask for a concise commit message.
7. Start the next small task.

## Token Rules

- Do not paste full logs unless needed.
- Put stable project context in `AGENTS.md`.
- Put priorities in `ROADMAP.md`.
- Put repeatable workflows in skills.
- Ask for diff summary and test result instead of long explanations.
