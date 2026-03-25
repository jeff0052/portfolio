# FounderPOS: AI-Driven Restaurant Operating System — Global Architecture Spec

Status: DRAFT
Date: 2026-03-26
Author: Jeff + Claude

---

## 1. System Identity

**FounderPOS = Transaction Foundation + AI Operator + Autonomous Agent**

A restaurant owner, alone, can drive an entire restaurant. AI handles operations, analysis, customer management, and external interactions. The owner only approves key decisions.

### 1.1 Core Principles

1. **Foundation must stand alone** — Without AI, it works as a traditional POS. This is the Day 1 product.
2. **AI is an Operator, not a feature** — AI is not "add a recommendation button." It is a full Operator that can read, analyze, and act on every module, on par with the human owner.
3. **Every restaurant is an Agent** — Each restaurant has an identity, a wallet, and the ability to interact with external agents autonomously.

### 1.2 One-Line Vision

> Traditional POS: the owner uses software to manage a restaurant.
> FounderPOS: the owner has an AI partner who manages the restaurant. The owner only approves.

---

## 2. Four-Layer Architecture

```
Layer 4 ─ Agent Identity + Wallet + Credit
           每家餐厅 = 1 Agent + 1 Wallet + 1 Credit Profile
           对外开放：预定/包场/合作/询价/融资
           Agent-to-Agent Protocol

Layer 3 ─ AI Operator Layer
           Restaurant AI Operator（内部运营大脑）
           角色：菜单顾问/营销顾问/会员顾问/经营顾问/出品顾问
           模式：Sense → Think → Propose → Approve → Act

Layer 2 ─ MCP Tool Layer
           每个域暴露为 MCP Tools
           统一 ActionContext（actor_type / decision_source / approval）
           FounderOS Office 和 Restaurant AI Operator 都通过这层操作

Layer 1 ─ Transaction Foundation
           Order / Catalog / CRM / Promotion / Settlement / Report / Store / Staff
           传统 CRUD + 业务逻辑，独立可用
```

### 2.1 Key Architectural Decisions

- **Layer 2 is the hub** — All operations (human and AI) pass through MCP Tools. Audit consistency is guaranteed by design.
- **Layer 3 never touches the database directly** — It must operate through Layer 2 Tools. Permissions and audit are naturally unified.
- **Layer 4 is the external projection of Layer 3** — The AI Operator's capabilities are exposed to external agents through a standard protocol.
- **Each layer is independently deployable** — A restaurant can run Layer 1 alone (traditional POS), add Layer 2+3 (AI-driven), or go full Layer 4 (autonomous agent).

---

## 3. Layer 1 — Transaction Foundation

### 3.1 Current State

The existing POS V2 backend (Spring Boot 3, JPA, Flyway, MySQL) already implements:

| Domain | Status | Key Entities |
|--------|--------|-------------|
| Catalog/SKU | Active | Product, Category, SKU, StoreSkuAvailability |
| Order | Active | ActiveTableOrder, SubmittedOrder, TableSession |
| Settlement | Active | SettlementRecord, PaymentAttempt, CashierSettlement |
| Promotion | Active | PromotionRule, PromotionHit, PricingBreakdown |
| Member/CRM | Active | Member, MemberAccount, MemberPointsLedger |
| Report | Active | DailySummary, SalesSummary |
| Store | Partial | Store, StoreTable |
| Staff | Placeholder | Empty package |
| GTO | Placeholder | Empty package |
| Platform Admin | Placeholder | Empty package |

### 3.2 Required Changes: ActionContext

Every write operation (create/update/delete) must carry a unified context:

```java
public record ActionContext(
    ActorType actorType,        // HUMAN | AI
    String actorId,             // "jeff" | "menu-advisor" | "external-agent-xxx"
    DecisionSource source,      // MANUAL | AI_RECOMMENDATION | AI_AUTO
    String recommendationId,    // nullable — links to AI suggestion
    ApprovalStatus approval,    // APPROVED | PENDING | REJECTED
    String reason               // "周三客流低于均值30%，建议满50减10"
)

enum ActorType { HUMAN, AI, EXTERNAL_AGENT }
enum DecisionSource { MANUAL, AI_RECOMMENDATION, AI_AUTO }
enum ApprovalStatus { APPROVED, PENDING, REJECTED, NOT_REQUIRED }
```

- Human from admin panel → `actorType=HUMAN, source=MANUAL`
- AI suggestion approved by owner → `actorType=AI, source=AI_RECOMMENDATION, approval=APPROVED`
- AI low-risk auto-execution → `actorType=AI, source=AI_AUTO, approval=NOT_REQUIRED`
- External agent request → `actorType=EXTERNAL_AGENT, source=MANUAL, approval=PENDING`

**Propagation Pattern:**

ActionContext flows as a `@RequestScope` Spring bean, populated at the entry point (MCP Tool handler or REST controller) and available to all services via injection:

```java
// Entry point: MCP Tool handler or REST controller populates ActionContext
@RequestScope
@Component
public class ActionContextHolder {
    private ActionContext context;
    // getters/setters
}

// Services inject it — no method signature changes needed
@Service
public class PromotionService {
    @Autowired private ActionContextHolder contextHolder;

    public PromotionRule createPromotion(CreatePromotionCommand cmd) {
        ActionContext ctx = contextHolder.getContext();
        // ... business logic ...
        // ctx is automatically written to audit columns via JPA @PrePersist listener
    }
}

// JPA entity listener writes audit columns automatically
@EntityListeners(ActionContextAuditListener.class)
public abstract class BaseAuditableEntity {
    private String actorType;
    private String actorId;
    private String decisionSource;
    private String changeReason;
}
```

For existing Android POS and QR web clients: the REST controllers default to `actorType=HUMAN, source=MANUAL` when no ActionContext header is provided. MCP Tool calls always include explicit context.

### 3.3 Required Changes: Risk Classification

Every write operation has a predefined risk level:

| Risk | AI Behavior | Examples |
|------|------------|---------|
| **Low** | Auto-execute, log only | Generate report summary, tag dormant members, analyze prep time |
| **Medium** | Generate draft → owner approves | Publish promotion, adjust menu price, change member tier rules |
| **High** | Suggest only, never auto-execute | Refund, payment config, GTO tax settings, financial parameters |

Risk levels are defined per-tool in a configuration file, not hardcoded. The owner can adjust thresholds (e.g., promote a Medium action to Low after gaining trust).

### 3.4 Database Schema Additions

Add to all core tables (or a unified audit table):

```sql
ALTER TABLE [core_tables] ADD COLUMN actor_type VARCHAR(32) DEFAULT 'HUMAN';
ALTER TABLE [core_tables] ADD COLUMN actor_id VARCHAR(64);
ALTER TABLE [core_tables] ADD COLUMN decision_source VARCHAR(32) DEFAULT 'MANUAL';
ALTER TABLE [core_tables] ADD COLUMN recommendation_id VARCHAR(64);
ALTER TABLE [core_tables] ADD COLUMN approval_status VARCHAR(32);
ALTER TABLE [core_tables] ADD COLUMN change_reason TEXT;
```

The existing `order_events` table (V004 migration) already has `actor_type`, `actor_id`, `decision_source` — extend this pattern to all domains.

---

## 4. Layer 2 — MCP Tool Layer

### 4.1 Tool Taxonomy

Each domain exposes Tools in three categories:

| Category | Purpose | Auth Required | Examples |
|----------|---------|--------------|---------|
| **Query** | Read data, no side effects | Read access | `get_daily_summary`, `list_members`, `get_avg_prep_time` |
| **Analyze** | Compute insights from data | Read access | `get_churn_risk_members`, `get_product_ranking`, `compare_periods` |
| **Action** | Mutate state | Write access + risk check | `create_promotion_draft`, `update_sku_price`, `approve_promotion` |

### 4.2 Domain Tool Map

**Catalog Domain:**
- Query: `list_products`, `get_sku_detail`, `get_menu_for_store`
- Analyze: `get_product_ranking`, `get_low_margin_skus`, `get_slow_moving_items`
- Action: `update_sku_price`, `toggle_sku_availability`, `create_combo_draft`

**Order Domain:**
- Query: `get_active_orders`, `get_order_history`, `get_table_status`
- Analyze: `get_avg_prep_time`, `get_table_turnover_rate`, `get_peak_hours`, `get_order_source_breakdown`
- Action: (orders are created by POS/QR, not by AI)

**CRM/Member Domain:**
- Query: `list_members`, `get_member_profile`, `get_member_transactions`
- Analyze: `get_churn_risk_members`, `get_high_value_members`, `get_member_tier_distribution`, `get_recharge_trends`
- Action: `update_member_tier`, `create_recall_campaign_draft`, `adjust_points_rule`

**Promotion Domain:**
- Query: `list_promotions`, `get_promotion_detail`, `get_active_promotions`
- Analyze: `get_promotion_impact`, `get_promotion_roi`, `simulate_promotion_effect`
- Action: `create_promotion_draft`, `approve_promotion`, `pause_promotion`, `extend_promotion`

**Settlement Domain:**
- Query: `get_daily_revenue`, `get_payment_breakdown`, `get_refund_history`
- Analyze: `get_revenue_trend`, `get_payment_method_distribution`, `detect_settlement_anomaly`
- Action: (settlements are triggered by cashier flow, not by AI)

**Report Domain:**
- Query: `get_daily_summary`, `get_weekly_summary`, `get_monthly_summary`
- Analyze: `get_gross_margin_trend`, `get_labor_cost_ratio`, `compare_periods`, `get_store_health_score`
- Action: `generate_trusted_report` (for RWA/credit use)

**Staff Domain:**
- Query: `get_shift_schedule`, `get_staff_list`, `get_cashier_sessions`
- Analyze: `get_labor_efficiency`, `predict_peak_staffing_needs`
- Action: `suggest_shift_arrangement`, `approve_shift`

**Store Domain:**
- Query: `get_store_config`, `get_table_layout`, `get_store_list`
- Analyze: `get_store_comparison` (multi-store)
- Action: `update_store_settings`, `update_table_config`

**Kitchen Domain (extends Order):**
- Query: `get_kitchen_queue`, `get_prep_time_by_sku`
- Analyze: `get_avg_prep_time_trend`, `get_return_reasons`, `get_bottleneck_skus`, `get_peak_load_analysis`
- Action: (kitchen operations are POS-driven, AI only observes and advises)

**GTO Domain:** Scoped out of P0-P2. Will be added as tools when the GTO backend module is implemented (currently placeholder). GTO is compliance-critical (HIGH risk) — AI will only generate reports, never auto-execute.

### 4.3 Unified Tool Call Contract

Every MCP Tool call follows this structure:

```json
{
  "tool": "create_promotion_draft",
  "params": {
    "store_id": "store-001",
    "type": "SPEND_THRESHOLD_DISCOUNT",
    "threshold_cents": 5000,
    "discount_cents": 1000,
    "valid_from": "2026-03-27",
    "valid_to": "2026-04-02"
  },
  "context": {
    "actor_type": "AI",
    "actor_id": "promo-advisor",
    "decision_source": "AI_RECOMMENDATION",
    "reason": "周三历史客流低于均值30%，建议满50减10刺激消费",
    "recommendation_id": "rec-20260326-001"
  }
}
```

Response includes execution result + audit trail:

```json
{
  "status": "PENDING_APPROVAL",
  "draft_id": "promo-draft-001",
  "risk_level": "MEDIUM",
  "requires_approval": true,
  "message": "Promotion draft created. Awaiting owner approval."
}
```

### 4.4 MCP Server Implementation

The MCP Tool Server is a standalone process that:
- Connects to the POS V2 backend via internal API (or directly to the database for read-only queries)
- Exposes tools via MCP protocol (stdio or SSE transport)
- Can be called by FounderOS Office Agent, Restaurant AI Operator, or any MCP-compatible client
- Handles authentication and authorization per-tool

**Technology Decision: Spring Boot Embedded MCP Server.**

Rationale: The POS backend is Java/Spring Boot. Adding a separate TypeScript MCP server introduces a network hop, serialization overhead, and a second deployment unit. Instead, the MCP Tool Server runs as a module inside the existing Spring Boot application, exposing tools via MCP protocol (stdio for local, SSE for remote). This keeps ActionContext propagation in-process and avoids the complexity of a separate service.

If FounderOS needs to call remotely, the SSE transport endpoint (`/mcp/sse`) is exposed through the existing Nginx reverse proxy.

---

## 5. Layer 3 — AI Operator Layer

### 5.1 Operating Model: Sense → Think → Propose → Approve → Act

```
Sense:   Read Tools 持续感知经营数据
Think:   LLM 分析数据，识别问题和机会
Propose: 生成具体方案（草案），通过 Action Tools 创建 draft
Approve: 推送给老板审批（低风险可跳过）
Act:     审批通过后，通过 Action Tools 执行
```

### 5.2 Advisor Roles

One AI Operator, five role contexts (not five separate agents):

| Role | Senses | Outputs |
|------|--------|---------|
| **菜单顾问 (Menu Advisor)** | SKU sales, margins, return rate, prep time | "下架3道亏损菜" "推主推套餐" |
| **营销顾问 (Promo Advisor)** | Traffic trends, promotion ROI, seasonality | "周三满减草案" "节日活动方案" |
| **会员顾问 (CRM Advisor)** | Visit frequency, balance, churn risk | "召回30天未到店会员" "调整等级规则" |
| **经营顾问 (Ops Advisor)** | Daily/weekly P&L, margins, labor cost | "本周经营摘要" "异常预警" |
| **出品顾问 (Kitchen Advisor)** | Avg prep time, return reasons, peak load | "高峰期简化菜单" "出品瓶颈分析" |

### 5.3 Trigger Mechanisms

| Trigger | Example | Frequency |
|---------|---------|-----------|
| **Scheduled** | Daily morning briefing, weekly report | Cron-based |
| **Event-driven** | Prep time > threshold, member churn detected, promotion expires | Spring ApplicationEvent (see 5.3.1) |
| **Owner-initiated** | "最近生意怎么样" "帮我想个促销方案" | On-demand via chat |

### 5.4 Approval Flow

```
AI Operator generates proposal
        │
        ▼
  Risk level check
        │
   ┌────┼────┐
   ▼    ▼    ▼
  LOW  MED  HIGH
   │    │    │
   │    │    └→ Suggest only → Owner reads, acts manually
   │    └→ Create draft → Push to owner → Approve/Reject/Modify → Execute
   └→ Auto-execute → Log + notify owner after the fact
```

### 5.3.1 Event Mechanism

In-process Spring ApplicationEvent bus (no external message broker needed at this scale):

```java
// Domain services publish events
public class OrderService {
    @Autowired private ApplicationEventPublisher publisher;

    public void submitOrder(SubmitOrderCommand cmd) {
        // ... business logic ...
        publisher.publishEvent(new OrderSubmittedEvent(order));
    }
}

// AI Operator listens
@Component
public class KitchenAdvisorListener {
    @Async
    @EventListener
    public void onOrderSubmitted(OrderSubmittedEvent event) {
        // Check prep time, update running averages
        // If threshold exceeded → create AI proposal
    }
}
```

Events are also persisted to `order_events` table (wire JPA entity in P1) for audit and replay. If scale demands it later, extract to Redis Streams or Kafka — the ApplicationEvent interface remains the same.

### 5.4 Approval Flow

#### 5.4.1 Proposal State Machine

```
DRAFT → PENDING_APPROVAL → APPROVED → EXECUTED
                         → REJECTED → ARCHIVED
                         → EXPIRED (auto after 48h)
```

#### 5.4.2 Proposal Storage

New `ai_proposal` table:

```sql
CREATE TABLE ai_proposal (
    id VARCHAR(64) PRIMARY KEY,
    advisor_role VARCHAR(32),        -- MENU / PROMO / CRM / OPS / KITCHEN
    proposal_type VARCHAR(64),       -- CREATE_PROMOTION / ADJUST_PRICE / RECALL_MEMBERS
    target_domain VARCHAR(32),       -- promotion / catalog / member
    target_tool VARCHAR(64),         -- create_promotion_draft
    params_json JSON,                -- tool call parameters
    reason TEXT,                      -- AI explanation
    risk_level VARCHAR(16),          -- LOW / MEDIUM / HIGH
    status VARCHAR(32),              -- DRAFT / PENDING / APPROVED / REJECTED / EXPIRED / EXECUTED
    created_at TIMESTAMP,
    expires_at TIMESTAMP,            -- default: created_at + 48h
    reviewed_by VARCHAR(64),
    reviewed_at TIMESTAMP,
    executed_at TIMESTAMP
);
```

#### 5.4.3 Approval API

```
GET  /api/v2/proposals                    -- list pending proposals
GET  /api/v2/proposals/{id}               -- proposal detail with AI reasoning
POST /api/v2/proposals/{id}/approve       -- approve and execute
POST /api/v2/proposals/{id}/reject        -- reject with reason
POST /api/v2/proposals/{id}/modify        -- modify params then approve
```

Expired proposals (48h timeout) are auto-archived. The AI Operator can re-propose with updated reasoning if conditions still warrant action.

Owner receives approvals via:
- FounderOS dashboard (if connected)
- WeChat/Telegram notification (lightweight)
- Merchant admin panel (web)
- POS terminal notification (in-store)

### 5.5 Integration with FounderOS

The AI Operator is orchestrated by FounderOS Office Agent:
- FounderOS FPMS manages task priorities across all verticals
- Restaurant AI Operator registers as a set of MCP Tools under FounderOS
- FounderOS provides the LLM orchestration layer — the POS does not embed its own LLM calls
- If running standalone (without FounderOS), a lightweight local orchestrator can drive the same Tools

```
With FounderOS:
  FounderOS Office Agent → MCP (SSE) → POS MCP Module → POS Backend Services

Standalone:
  POS AI Scheduler (Spring @Scheduled) → POS MCP Module → POS Backend Services
  Owner chat → POS AI Chat endpoint → Claude API → POS MCP Module → POS Backend Services
```

**Standalone Mode Design:**

Standalone mode runs entirely within the Spring Boot process:

1. **Scheduled analysis** — `@Scheduled` Spring jobs run daily/weekly, call Claude API with advisor role prompts + data from Query tools, store proposals in `ai_proposal` table.
2. **Owner chat** — A REST endpoint (`/api/v2/ai/chat`) accepts owner questions, calls Claude API with restaurant context, returns answers or creates proposals.
3. **Event-driven** — Same `@EventListener` pattern described in 5.3.1, triggers Claude API calls when thresholds are breached.
4. **Memory** — Advisor conversation history stored in `ai_advisor_context` table (advisor_role, context_json, updated_at). Refreshed daily with latest operational data.

This is a P1 deliverable. The standalone orchestrator is lightweight (no separate process, no message broker) and uses the same MCP Tool interface that FounderOS would call externally.

---

## 6. Layer 4 — Agent Identity + Wallet + Credit

### 6.1 Restaurant Agent

Each restaurant deployed on FounderPOS gets an autonomous agent:

```
Restaurant Agent "老王烧烤"
├── Identity
│   ├── name, address, cuisine_type, style
│   ├── operating_hours, capacity, price_range
│   └── agent_id (globally unique)
├── Wallet
│   ├── Collection: receive payments from customers
│   ├── Settlement: reconcile with platforms (Meituan, Eleme)
│   ├── Disbursement: pay suppliers, staff
│   └── Budget: AI marketing spend limits
├── Credit Profile
│   ├── Trusted Business Report (hardware-signed, AI-generated)
│   ├── Credit Score (revenue stability, growth, seasonality)
│   └── RWA Issuance Capability (short-term debt / revenue share tokens)
├── Capabilities (what this agent can do)
│   ├── accept_reservation: true
│   ├── accept_private_event: true
│   ├── accept_delivery: true
│   ├── accept_group_buy: true
│   └── accept_supplier_quotes: true
└── Protocol
    └── Exposed interaction endpoints for external agents
```

### 6.2 External Interaction Scenarios

| External Agent | Interaction | Example |
|---------------|-------------|---------|
| **Customer Agent** | Inquiry / Reserve / Order | "周六晚上8人有位吗？人均预算150" |
| **Enterprise Agent** | Private event / Team building | "30人团建，预算5000，有方案吗" |
| **Supplier Agent** | Quote / Purchase | "明天需要50斤牛肉，给个价" |
| **Platform Agent** | Listing / Promotion / Settlement | Meituan/Eleme agent auto-sync |
| **Investor Agent** | Due diligence / RWA purchase | "查看可信经营报告和信用评分" |

### 6.3 Interaction Risk Model

```
External Agent request → Restaurant Agent receives
                              │
                              ▼
                        AI Operator analyzes
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                  LOW       MED       HIGH
                   │         │         │
                   │         │         └→ Forward to owner
                   │         └→ Generate proposal → owner approves
                   └→ Auto-reply (e.g., "有位，已预留")
```

Example flow — "周六20人包场多少钱":
1. External agent sends request to Restaurant Agent
2. AI Operator queries: historical private event data, Saturday reservation status, ingredient costs
3. AI generates proposal: "建议报价3800，含10道菜+酒水，毛利预估42%"
4. Push to owner → owner approves/modifies price → Restaurant Agent replies

### 6.4 Wallet Architecture

The wallet integrates with the existing unified payment architecture (doc 39):

```
Wallet
├── Inbound
│   ├── POS payments (DCS card, VibeCash QR, Cash)
│   ├── QR ordering payments
│   ├── Delivery platform settlements
│   └── RWA investor payments (Phase 5)
├── Outbound
│   ├── Supplier payments
│   ├── Staff payroll
│   ├── Platform commissions
│   ├── AI marketing budget spend
│   └── RWA debt repayment (Phase 5)
├── Controls
│   ├── Daily spend limits (per category)
│   ├── AI autonomous spend ceiling
│   ├── Owner approval threshold
│   └── Multi-sig for high-value transfers
└── Reconciliation
    ├── Auto-reconcile all channels daily
    ├── Flag discrepancies
    └── Generate financial summary for credit scoring
```

---

## 7. Phase 5 — Credit Layer (RWA Integration)

### 7.1 Connection to RWS Platform

FounderPOS connects to the RWS (POS Hardware Trust Layer RWA Platform) as data source:

```
FounderPOS                          RWS Platform
┌─────────────┐                    ┌──────────────────┐
│ POS Backend  │──hardware-signed──→│ Data Collection  │
│ (transactions│  transaction data  │ Layer            │
│  on Sunmi    │                    ├──────────────────┤
│  hardware)   │                    │ Data Processing  │
├─────────────┤                    │ + Analysis       │
│ AI Operator  │──trusted report───→├──────────────────┤
│ (generates   │  (AI-generated,   │ Report Generation│
│  analysis)   │   hardware-backed)│ Layer            │
├─────────────┤                    ├──────────────────┤
│ Credit       │←─credit score─────│ Credit Scoring   │
│ Profile      │←─RWA status───────│ + RWA Issuance   │
└─────────────┘                    └──────────────────┘
```

### 7.2 Credit Data Flow

```
1. POS records transactions (Sunmi hardware digital signature)
2. AI Operator analyzes operations → generates trusted business report
3. Report submitted to RWS platform (hardware signature verification)
4. RWS generates credit score (revenue stability, growth, seasonality)
5. Restaurant qualifies for RWA issuance (short-term debt / revenue share)
6. Funds received via Wallet
7. AI Operator uses funds for expansion / procurement
8. New operations generate more data → positive cycle
```

### 7.3 AI Operator Role in Credit

The AI Operator enhances the credit process:

| Function | What AI Does |
|----------|-------------|
| **Report Generation** | Auto-generate monthly trusted business report with multi-dimensional analysis |
| **Credit Optimization** | Suggest operational improvements to raise credit score |
| **Debt Management** | Track repayment schedule, alert owner on upcoming obligations |
| **Investor Relations** | Auto-respond to investor agent due diligence queries (with owner approval) |
| **Risk Monitoring** | Alert if operations trend threatens credit standing |

---

## 8. Phase 5+ — Restaurant Agent Network

### 8.1 Network Value

When multiple restaurants run FounderPOS, the network provides collective intelligence:

| Value | Description |
|-------|-------------|
| **Anonymous Benchmarking** | "同区域同菜系餐厅毛利中位数62%，你55%" |
| **Trend Alerts** | "你这区域本周外卖单普遍下降15%，不只是你" |
| **Best Practices** | "类似餐厅做会员充值最有效的方案是..." |
| **Collective Bargaining** | Multiple restaurants negotiate with suppliers together |
| **Overflow Routing** | "我们满了，推荐隔壁同菜系" |
| **Shared Workforce** | Temp staff agents dispatched across multiple stores |

### 8.2 Data Sharing Model

- **Opt-in** — Each restaurant chooses what to share
- **Anonymous** — No restaurant identity exposed in aggregate data
- **Value exchange** — Share more data → get richer insights
- **Privacy-first** — Raw transaction data never leaves the restaurant; only aggregate metrics are shared

### 8.3 Multi-Store Operator

One owner managing multiple restaurants:

```
Owner Dashboard (FounderOS)
├── Restaurant A [Agent] → AI Operator → autonomous
├── Restaurant B [Agent] → AI Operator → autonomous
├── Restaurant C [Agent] → AI Operator → autonomous
└── Cross-store analytics + consolidated approvals
```

Each store runs its own AI Operator independently. The owner sees a consolidated view and can batch-approve across stores.

---

## 9. Delivery Roadmap

| Phase | Content | Depends On | Estimated Effort |
|-------|---------|------------|-----------------|
| **P0** | **POS MCP Tool Server** — Wrap existing V2 backend as MCP Tools, add ActionContext | Existing V2 backend | 2-3 weeks |
| **P1** | **AI Operator** — 5 advisor roles, approval flow, scheduled + event triggers | P0 | 4-6 weeks |
| **P2** | **Agent + Wallet** — Restaurant identity, wallet integration, basic external interaction | P0 + P1 | 4-6 weeks |
| **P3** | **Agent-to-Agent Protocol** — Standard protocol for external agent interaction | P2 | 3-4 weeks |
| **P4** | **Restaurant Agent Network** — Anonymous benchmarking, collective intelligence | P3 + scale | 6-8 weeks |
| **P5** | **Credit Layer** — RWS integration, trusted reports, credit scoring, RWA issuance | P2 + RWS platform | Aligned with RWS timeline |

### 9.1 P0 Deliverables

- MCP Tool Server (Spring Boot embedded module, SSE transport for remote)
- ActionContext added to all V2 service methods
- Risk classification config for all write operations
- Audit trail (action_log table) for all Tool calls
- Integration test: FounderOS Office Agent can call POS Tools

### 9.2 P1 Deliverables

- 5 advisor role prompt definitions
- Scheduled analysis jobs (daily briefing, weekly report)
- Event-driven triggers (order_events → AI analysis)
- Approval flow (draft → approve → execute)
- Owner notification channel (at least one: web/WeChat/Telegram)

### 9.3 P2 Deliverables

- Restaurant Agent identity model
- Wallet integration with unified payment architecture
- Basic external interaction: reservation, inquiry
- Agent registration with FounderOS

### 9.4 P3 Deliverables

- Agent-to-Agent interaction protocol definition
- Supported interaction types: reserve, inquire, quote, negotiate
- Authentication and trust model between agents
- Rate limiting and abuse prevention

### 9.5 P4 Deliverables

- Anonymous data aggregation pipeline
- Benchmarking API (compare against peers)
- Trend detection and alerting
- Collective bargaining coordination

### 9.6 P5 Deliverables

- RWS platform integration (data push + report generation)
- Credit score display in merchant dashboard
- RWA issuance flow (via licensed partner)
- Debt management in Wallet

---

## 10. Technology Stack Summary

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Layer 1 (Backend) | Java 17 / Spring Boot 3 / JPA / Flyway / MySQL | Existing, stable, proven |
| Layer 1 (Android) | Kotlin / Jetpack Compose / Hilt / Retrofit | Existing POS terminal app |
| Layer 1 (Web) | TypeScript / React / Vite | Existing admin panels |
| Layer 2 (MCP Server) | Spring Boot embedded module (MCP4J or custom) | In-process, no extra deployment unit |
| Layer 3 (with FounderOS) | FounderOS Office Agent + FPMS via MCP SSE | Reuse existing orchestration |
| Layer 3 (Standalone) | Spring @Scheduled + Claude API | In-process, no separate service |
| Layer 4 (Agent) | Agent protocol (TBD: A2A / custom) | Standard interoperability |
| Layer 4 (Wallet) | Unified Payment Domain (existing architecture) | Extend, don't rebuild |
| Layer 5 (Credit) | RWS Platform (Python / FastAPI) | Existing RWS design |

---

## 11. What This Changes About the Current Codebase

### 11.1 Must Change (P0)

- Add `ActionContext` to all V2 Service method signatures
- Add audit columns to core database tables
- Create `action_log` table for unified audit trail
- Build MCP Tool Server wrapping V2 endpoints
- Define risk classification config file

### 11.2 Should Change (P1)

- Wire `order_events` table to JPA entity (currently schema-only)
- Add event publishing to key domain operations (order submitted, settlement completed, member created)
- Create advisor prompt templates

### 11.3 Can Stay As-Is

- V2 DDD package structure (already clean)
- Android POS app (consumes V2 API, no changes needed)
- QR ordering web (no changes needed)
- Existing V1 code (deprecated, will be removed over time)
- Docker/Nginx infrastructure

---

## 12. Success Metrics

| Phase | Metric | Target |
|-------|--------|--------|
| P0 | FounderOS Agent can call all POS Tools | 100% tool coverage |
| P1 | Owner receives daily AI briefing | Automated, no manual trigger |
| P1 | AI-generated promotion proposals | ≥3 per week |
| P2 | External reservation via agent | End-to-end flow works |
| P3 | Agent-to-Agent interaction | ≥2 external agent types supported |
| P4 | Network benchmarking | ≥10 restaurants contributing data |
| P5 | First RWA issuance | 1 restaurant successfully funded |

---

## 13. Error Handling and Degradation

### 13.1 Graceful Degradation

| Failure | Behavior |
|---------|----------|
| MCP module error | POS continues as Layer 1 (traditional mode). REST endpoints still work. AI features unavailable. |
| Claude API down | Scheduled analysis skipped. Owner chat returns "AI temporarily unavailable." Proposals queue for next cycle. |
| AI returns hallucinated parameters | Action tools validate all inputs before execution. Invalid tool calls are rejected with error logged to `ai_proposal` table. |
| Proposal notification fails | Proposal stays in `PENDING_APPROVAL` status. Owner can see it in admin panel. Retry notification on next cycle. |

### 13.2 Idempotency

All Action tools must be idempotent. Pattern: check current state before mutating. If the target state already matches the requested change, return success without re-executing.

### 13.3 Security Model

| Caller | Auth Mechanism | Tool Access |
|--------|---------------|-------------|
| POS Android app | JWT (existing auth) | Layer 1 REST only |
| Merchant Admin | JWT (existing auth) | Layer 1 REST only |
| FounderOS Agent | MCP + API key (per-restaurant) | Layer 2 all tools |
| Standalone Orchestrator | In-process (no auth needed) | Layer 2 all tools |
| External Agent (P3) | Agent-to-Agent token + rate limit | Layer 2 subset (query + limited action) |

MCP API keys are managed per-restaurant in `mcp_api_key` table. Each key has a scope (read-only, read-write, admin) and rate limits.

---

## 14. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| AI generates bad recommendations | Owner loses trust | Medium/High actions always require approval; low-risk actions are reversible |
| MCP Tool Server becomes bottleneck | Performance degradation | Read tools can bypass MCP and query DB directly; write tools are lower volume |
| Owner ignores AI suggestions | AI value not realized | Start with daily briefing (passive value), earn trust before proposing actions |
| External agent abuse | Spam, DDoS, scams | Rate limiting, trust scoring, owner approval for all financial interactions |
| Wallet security | Financial loss | Multi-sig for high value, AI spend ceiling, daily reconciliation |
| RWA regulatory risk | Legal exposure | Use licensed partner for issuance, never handle securities directly |
