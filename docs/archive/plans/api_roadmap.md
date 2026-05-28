# MOR API Roadmap (API 架構藍圖)

目前 MOR 系統高度依賴 Flask Server-side Rendering (Jinja2)。此 API 藍圖的目標是逐步分離前後端邏輯，過渡至更純粹的 RESTful API，為未來的單頁應用程式 (SPA) 或第三方串接打下基礎。

## Phase 1: 歷史趨勢與獨立資料端點 (Trend Data API)
**目標：解耦複雜的圖表資料，採非同步載入提升頁面初始速度。**
- [ ] `GET /api/v1/forecast/trends`
  - 參數：`year`, `month`, `product_code` (可選)
  - 回傳：過去 6 個月的序列資料 (JSON)。
  - 用途：前端收到 HTML 後，非同步呼叫此 API 渲染 Sparklines。

## Phase 2: 快照管理端點 (Snapshot API)
**目標：以 RESTful 風格管理版本。**
- [ ] `POST /api/v1/snapshots`
  - Body: `{ "year": 2026, "month": 5, "name": "5月定稿版", "type": "Final" }`
  - 動作：建立當前狀態的歷史快照。
- [ ] `GET /api/v1/snapshots`
  - 參數：`year`, `month`
  - 回傳：該月份所有可用的快照列表。
- [ ] `GET /api/v1/snapshots/{id}/items`
  - 回傳：特定快照內的所有預估細項。

## Phase 3: 回測與準確度端點 (Backtesting API)
**目標：提供標準化的報表資料介面。**
- [ ] `GET /api/v1/analysis/accuracy`
  - 參數：`year`, `month` (要查詢的實際月份)
  - 回傳：該月的實際銷售與上個月預估的對比結果、MAPE 值。

## Phase 4: 全面前後端分離 (Full Decoupling)
**目標：將目前的表單提交完全轉換為 JSON API。**
- [ ] `GET /api/v1/forecast/workbench`
  - 取代 `index.html` 的後端渲染，直接回傳整個工作台所需的 JSON Tree。
- [ ] `PUT /api/v1/items/{product_code}/config`
  - 取代 `/items/save` 批次表單，實作單一品項設定的即時更新。
