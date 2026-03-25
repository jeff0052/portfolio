# P0: POS MCP Tool Server — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the existing POS V2 backend as MCP Tools so that FounderOS Agent (or any MCP client) can query and operate every domain.

**Architecture:** Spring Boot embedded MCP module inside the existing `pos-backend`. Each domain exposes Query/Analyze/Action tools via MCP protocol (SSE transport for remote callers). All write operations carry ActionContext for audit. A JPA entity listener auto-populates audit columns.

**Tech Stack:** Java 17, Spring Boot 3.3.3, Spring MCP Server (spring-ai-mcp-server-webflux or custom SSE endpoint), JPA, Flyway, MySQL

**Note:** The codebase is actively being developed. This plan creates NEW files wherever possible to minimize merge conflicts. The only modifications to existing files are: (1) entities extend a new BaseAuditableEntity, (2) pom.xml adds MCP dependency.

---

## File Structure

### New Files (all under `pos-backend/src/main/java/com/developer/pos/v2/`)

```
mcp/                                          # NEW MODULE — MCP Tool Server
  McpServerConfig.java                        # MCP server configuration + tool registration
  McpToolRegistry.java                        # Registry that collects all domain tools
  ActionContextHolder.java                    # @RequestScope bean holding ActionContext
  ActionContextAuditListener.java             # JPA @PrePersist / @PreUpdate listener
  model/
    ActionContext.java                        # ActionContext record
    ToolResponse.java                         # Unified tool response wrapper
    RiskLevel.java                            # LOW / MEDIUM / HIGH enum
  tools/
    CatalogTools.java                         # Catalog domain tools
    OrderTools.java                           # Order domain tools
    MemberTools.java                          # CRM/Member domain tools
    PromotionTools.java                       # Promotion domain tools
    SettlementTools.java                      # Settlement domain tools
    ReportTools.java                          # Report domain tools
    StoreTools.java                           # Store domain tools

common/
  entity/
    BaseAuditableEntity.java                  # Shared base with audit columns
```

### New Files (resources)

```
pos-backend/src/main/resources/
  db/migration/v2/
    V016__add_audit_columns.sql               # Add audit columns to core tables
    V017__create_action_log.sql               # Create action_log table
    V018__create_ai_proposal.sql              # Create ai_proposal table (for P1, schema only)
  mcp-risk-config.yml                         # Risk level config per tool
```

### Modified Files (minimal)

```
pos-backend/pom.xml                           # Add MCP server dependency
pos-backend/src/main/resources/application.yml # Add MCP config section
```

### Test Files

```
pos-backend/src/test/java/com/developer/pos/v2/
  mcp/
    ActionContextHolderTest.java
    ActionContextAuditListenerTest.java
    tools/
      CatalogToolsTest.java
      PromotionToolsTest.java
      MemberToolsTest.java
```

---

## Task 1: ActionContext Foundation

**Files:**
- Create: `v2/mcp/model/ActionContext.java`
- Create: `v2/mcp/model/RiskLevel.java`
- Create: `v2/mcp/ActionContextHolder.java`
- Test: `v2/mcp/ActionContextHolderTest.java`

- [ ] **Step 1: Write ActionContext record and RiskLevel enum**

```java
// v2/mcp/model/ActionContext.java
package com.developer.pos.v2.mcp.model;

public record ActionContext(
    ActorType actorType,
    String actorId,
    DecisionSource decisionSource,
    String recommendationId,
    ApprovalStatus approvalStatus,
    String reason
) {
    public enum ActorType { HUMAN, AI, EXTERNAL_AGENT }
    public enum DecisionSource { MANUAL, AI_RECOMMENDATION, AI_AUTO }
    public enum ApprovalStatus { APPROVED, PENDING, REJECTED, NOT_REQUIRED }

    public static ActionContext humanDefault() {
        return new ActionContext(
            ActorType.HUMAN, null, DecisionSource.MANUAL,
            null, ApprovalStatus.NOT_REQUIRED, null
        );
    }
}
```

```java
// v2/mcp/model/RiskLevel.java
package com.developer.pos.v2.mcp.model;

public enum RiskLevel { LOW, MEDIUM, HIGH }
```

- [ ] **Step 2: Write ActionContextHolder**

```java
// v2/mcp/ActionContextHolder.java
package com.developer.pos.v2.mcp;

import com.developer.pos.v2.mcp.model.ActionContext;
import org.springframework.stereotype.Component;
import org.springframework.web.context.annotation.RequestScope;

@Component
@RequestScope
public class ActionContextHolder {
    private ActionContext context = ActionContext.humanDefault();

    public ActionContext getContext() { return context; }
    public void setContext(ActionContext context) { this.context = context; }
}
```

- [ ] **Step 3: Write test**

```java
// v2/mcp/ActionContextHolderTest.java
package com.developer.pos.v2.mcp;

import com.developer.pos.v2.mcp.model.ActionContext;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ActionContextHolderTest {
    @Test
    void defaultContextIsHuman() {
        var holder = new ActionContextHolder();
        var ctx = holder.getContext();
        assertEquals(ActionContext.ActorType.HUMAN, ctx.actorType());
        assertEquals(ActionContext.DecisionSource.MANUAL, ctx.decisionSource());
    }

    @Test
    void canSetAiContext() {
        var holder = new ActionContextHolder();
        var aiCtx = new ActionContext(
            ActionContext.ActorType.AI, "menu-advisor",
            ActionContext.DecisionSource.AI_RECOMMENDATION,
            "rec-001", ActionContext.ApprovalStatus.APPROVED,
            "test reason"
        );
        holder.setContext(aiCtx);
        assertEquals(ActionContext.ActorType.AI, holder.getContext().actorType());
        assertEquals("menu-advisor", holder.getContext().actorId());
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pos-backend && mvn test -pl . -Dtest=ActionContextHolderTest -Dspring.profiles.active=mock`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(mcp): add ActionContext model and holder"
```

---

## Task 2: JPA Audit Infrastructure

**Files:**
- Create: `v2/common/entity/BaseAuditableEntity.java`
- Create: `v2/mcp/ActionContextAuditListener.java`
- Create: `db/migration/v2/V016__add_audit_columns.sql`
- Create: `db/migration/v2/V017__create_action_log.sql`
- Test: `v2/mcp/ActionContextAuditListenerTest.java`

- [ ] **Step 1: Write Flyway migration — audit columns**

```sql
-- V016__add_audit_columns.sql
-- Add audit columns to core V2 tables.
-- Existing rows default to HUMAN / MANUAL.

ALTER TABLE v2_active_table_orders
    ADD COLUMN actor_type VARCHAR(32) DEFAULT 'HUMAN',
    ADD COLUMN actor_id VARCHAR(64),
    ADD COLUMN decision_source VARCHAR(32) DEFAULT 'MANUAL',
    ADD COLUMN change_reason TEXT;

ALTER TABLE v2_submitted_orders
    ADD COLUMN actor_type VARCHAR(32) DEFAULT 'HUMAN',
    ADD COLUMN actor_id VARCHAR(64),
    ADD COLUMN decision_source VARCHAR(32) DEFAULT 'MANUAL',
    ADD COLUMN change_reason TEXT;

ALTER TABLE v2_promotion_rules
    ADD COLUMN actor_type VARCHAR(32) DEFAULT 'HUMAN',
    ADD COLUMN actor_id VARCHAR(64),
    ADD COLUMN decision_source VARCHAR(32) DEFAULT 'MANUAL',
    ADD COLUMN change_reason TEXT;

ALTER TABLE v2_members
    ADD COLUMN actor_type VARCHAR(32) DEFAULT 'HUMAN',
    ADD COLUMN actor_id VARCHAR(64),
    ADD COLUMN decision_source VARCHAR(32) DEFAULT 'MANUAL',
    ADD COLUMN change_reason TEXT;

ALTER TABLE v2_settlement_records
    ADD COLUMN actor_type VARCHAR(32) DEFAULT 'HUMAN',
    ADD COLUMN actor_id VARCHAR(64),
    ADD COLUMN decision_source VARCHAR(32) DEFAULT 'MANUAL',
    ADD COLUMN change_reason TEXT;

ALTER TABLE v2_skus
    ADD COLUMN actor_type VARCHAR(32) DEFAULT 'HUMAN',
    ADD COLUMN actor_id VARCHAR(64),
    ADD COLUMN decision_source VARCHAR(32) DEFAULT 'MANUAL',
    ADD COLUMN change_reason TEXT;

ALTER TABLE v2_store_sku_availability
    ADD COLUMN actor_type VARCHAR(32) DEFAULT 'HUMAN',
    ADD COLUMN actor_id VARCHAR(64),
    ADD COLUMN decision_source VARCHAR(32) DEFAULT 'MANUAL',
    ADD COLUMN change_reason TEXT;
```

- [ ] **Step 2: Write Flyway migration — action_log table**

```sql
-- V017__create_action_log.sql
CREATE TABLE action_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tool_name VARCHAR(128) NOT NULL,
    actor_type VARCHAR(32) NOT NULL,
    actor_id VARCHAR(64),
    decision_source VARCHAR(32) NOT NULL DEFAULT 'MANUAL',
    recommendation_id VARCHAR(64),
    approval_status VARCHAR(32),
    risk_level VARCHAR(16),
    params_json JSON,
    result_json JSON,
    change_reason TEXT,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    KEY idx_action_log_actor (actor_type, created_at),
    KEY idx_action_log_tool (tool_name, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- [ ] **Step 3: Write BaseAuditableEntity**

```java
// v2/common/entity/BaseAuditableEntity.java
package com.developer.pos.v2.common.entity;

import jakarta.persistence.Column;
import jakarta.persistence.MappedSuperclass;

@MappedSuperclass
public abstract class BaseAuditableEntity {
    @Column(name = "actor_type")
    private String actorType;

    @Column(name = "actor_id")
    private String actorId;

    @Column(name = "decision_source")
    private String decisionSource;

    @Column(name = "change_reason")
    private String changeReason;

    // Getters and setters
    public String getActorType() { return actorType; }
    public void setActorType(String actorType) { this.actorType = actorType; }
    public String getActorId() { return actorId; }
    public void setActorId(String actorId) { this.actorId = actorId; }
    public String getDecisionSource() { return decisionSource; }
    public void setDecisionSource(String decisionSource) { this.decisionSource = decisionSource; }
    public String getChangeReason() { return changeReason; }
    public void setChangeReason(String changeReason) { this.changeReason = changeReason; }
}
```

- [ ] **Step 4: Write ActionContextAuditListener**

```java
// v2/mcp/ActionContextAuditListener.java
package com.developer.pos.v2.mcp;

import com.developer.pos.v2.common.entity.BaseAuditableEntity;
import com.developer.pos.v2.mcp.model.ActionContext;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class ActionContextAuditListener {

    private static ActionContextHolder contextHolder;

    @Autowired
    public void setContextHolder(ActionContextHolder holder) {
        ActionContextAuditListener.contextHolder = holder;
    }

    @PrePersist
    @PreUpdate
    public void setAuditFields(Object entity) {
        if (!(entity instanceof BaseAuditableEntity auditable)) return;
        if (contextHolder == null) return;

        ActionContext ctx = contextHolder.getContext();
        auditable.setActorType(ctx.actorType().name());
        auditable.setActorId(ctx.actorId());
        auditable.setDecisionSource(ctx.decisionSource().name());
        auditable.setChangeReason(ctx.reason());
    }
}
```

- [ ] **Step 5: Write test**

```java
// v2/mcp/ActionContextAuditListenerTest.java
package com.developer.pos.v2.mcp;

import com.developer.pos.v2.common.entity.BaseAuditableEntity;
import com.developer.pos.v2.mcp.model.ActionContext;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ActionContextAuditListenerTest {

    static class TestEntity extends BaseAuditableEntity {}

    @Test
    void setsAuditFieldsFromContext() {
        var holder = new ActionContextHolder();
        holder.setContext(new ActionContext(
            ActionContext.ActorType.AI, "promo-advisor",
            ActionContext.DecisionSource.AI_RECOMMENDATION,
            "rec-001", ActionContext.ApprovalStatus.APPROVED,
            "test reason"
        ));

        var listener = new ActionContextAuditListener();
        listener.setContextHolder(holder);

        var entity = new TestEntity();
        listener.setAuditFields(entity);

        assertEquals("AI", entity.getActorType());
        assertEquals("promo-advisor", entity.getActorId());
        assertEquals("AI_RECOMMENDATION", entity.getDecisionSource());
        assertEquals("test reason", entity.getChangeReason());
    }

    @Test
    void defaultsToHumanWhenNoContextSet() {
        var holder = new ActionContextHolder();
        // default context is human

        var listener = new ActionContextAuditListener();
        listener.setContextHolder(holder);

        var entity = new TestEntity();
        listener.setAuditFields(entity);

        assertEquals("HUMAN", entity.getActorType());
        assertEquals("MANUAL", entity.getDecisionSource());
    }
}
```

- [ ] **Step 6: Run tests**

Run: `cd pos-backend && mvn test -pl . -Dtest=ActionContextAuditListenerTest -Dspring.profiles.active=mock`
Expected: 2 tests PASS

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(mcp): add JPA audit infrastructure — BaseAuditableEntity, listener, migrations"
```

---

## Task 2.5: Wire Existing Entities to Audit Infrastructure

**Files (all MODIFY — check exact class names against current codebase):**
- Modify: `v2/catalog/infrastructure/persistence/entity/SkuEntity.java`
- Modify: `v2/catalog/infrastructure/persistence/entity/StoreSkuAvailabilityEntity.java`
- Modify: `v2/order/infrastructure/persistence/entity/ActiveTableOrderEntity.java`
- Modify: `v2/order/infrastructure/persistence/entity/SubmittedOrderEntity.java`
- Modify: `v2/promotion/infrastructure/persistence/entity/PromotionRuleEntity.java`
- Modify: `v2/member/infrastructure/persistence/entity/MemberEntity.java`
- Modify: `v2/settlement/infrastructure/persistence/entity/SettlementRecordEntity.java`

**Risk: HIGH — this modifies existing JPA entities. Test thoroughly.**

- [ ] **Step 1: Check if any entity already extends another class**

Run: `grep -r "extends " pos-backend/src/main/java/com/developer/pos/v2/*/infrastructure/persistence/entity/*.java`

If any entity extends something other than `Object`, you CANNOT use `extends BaseAuditableEntity`. Instead, copy the 4 audit fields directly into that entity.

- [ ] **Step 2: Add `extends BaseAuditableEntity` and `@EntityListeners` to each entity**

For each entity listed above, make two changes:

```java
// BEFORE:
@Entity
@Table(name = "v2_skus")
public class SkuEntity {

// AFTER:
@Entity
@Table(name = "v2_skus")
@EntityListeners(ActionContextAuditListener.class)
public class SkuEntity extends BaseAuditableEntity {
```

Add these imports to each file:
```java
import com.developer.pos.v2.common.entity.BaseAuditableEntity;
import com.developer.pos.v2.mcp.ActionContextAuditListener;
import jakarta.persistence.EntityListeners;
```

Repeat for all 7 entities.

- [ ] **Step 3: Verify compilation**

Run: `cd pos-backend && mvn compile -Dspring.profiles.active=mock`
Expected: BUILD SUCCESS

- [ ] **Step 4: Verify JPA mapping with existing tests (if any)**

Run: `cd pos-backend && mvn test -Dspring.profiles.active=mock`
Expected: All existing tests still pass

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(mcp): wire existing entities to BaseAuditableEntity with audit listener"
```

---

## Task 3: Action Log Repository

**Files:**
- Create: `v2/mcp/infrastructure/ActionLogEntity.java`
- Create: `v2/mcp/infrastructure/JpaActionLogRepository.java`
- Create: `v2/mcp/ActionLogService.java`

- [ ] **Step 1: Write ActionLogEntity**

```java
// v2/mcp/infrastructure/ActionLogEntity.java
package com.developer.pos.v2.mcp.infrastructure;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "action_log")
public class ActionLogEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "tool_name", nullable = false)
    private String toolName;

    @Column(name = "actor_type", nullable = false)
    private String actorType;

    @Column(name = "actor_id")
    private String actorId;

    @Column(name = "decision_source", nullable = false)
    private String decisionSource;

    @Column(name = "recommendation_id")
    private String recommendationId;

    @Column(name = "approval_status")
    private String approvalStatus;

    @Column(name = "risk_level")
    private String riskLevel;

    @Column(name = "params_json", columnDefinition = "JSON")
    private String paramsJson;

    @Column(name = "result_json", columnDefinition = "JSON")
    private String resultJson;

    @Column(name = "change_reason")
    private String changeReason;

    @Column(name = "created_at", insertable = false, updatable = false)
    private LocalDateTime createdAt;

    // Getters, setters, no-arg constructor
    public ActionLogEntity() {}

    public Long getId() { return id; }
    public String getToolName() { return toolName; }
    public void setToolName(String toolName) { this.toolName = toolName; }
    public String getActorType() { return actorType; }
    public void setActorType(String actorType) { this.actorType = actorType; }
    public String getActorId() { return actorId; }
    public void setActorId(String actorId) { this.actorId = actorId; }
    public String getDecisionSource() { return decisionSource; }
    public void setDecisionSource(String decisionSource) { this.decisionSource = decisionSource; }
    public String getRecommendationId() { return recommendationId; }
    public void setRecommendationId(String recommendationId) { this.recommendationId = recommendationId; }
    public String getApprovalStatus() { return approvalStatus; }
    public void setApprovalStatus(String approvalStatus) { this.approvalStatus = approvalStatus; }
    public String getRiskLevel() { return riskLevel; }
    public void setRiskLevel(String riskLevel) { this.riskLevel = riskLevel; }
    public String getParamsJson() { return paramsJson; }
    public void setParamsJson(String paramsJson) { this.paramsJson = paramsJson; }
    public String getResultJson() { return resultJson; }
    public void setResultJson(String resultJson) { this.resultJson = resultJson; }
    public String getChangeReason() { return changeReason; }
    public void setChangeReason(String changeReason) { this.changeReason = changeReason; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
```

- [ ] **Step 2: Write repository**

```java
// v2/mcp/infrastructure/JpaActionLogRepository.java
package com.developer.pos.v2.mcp.infrastructure;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface JpaActionLogRepository extends JpaRepository<ActionLogEntity, Long> {
    List<ActionLogEntity> findByToolNameOrderByCreatedAtDesc(String toolName);
    List<ActionLogEntity> findByActorTypeOrderByCreatedAtDesc(String actorType);
}
```

- [ ] **Step 3: Write ActionLogService**

```java
// v2/mcp/ActionLogService.java
package com.developer.pos.v2.mcp;

import com.developer.pos.v2.mcp.infrastructure.ActionLogEntity;
import com.developer.pos.v2.mcp.infrastructure.JpaActionLogRepository;
import com.developer.pos.v2.mcp.model.ActionContext;
import com.developer.pos.v2.mcp.model.RiskLevel;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ActionLogService {
    private final JpaActionLogRepository repository;
    private final ObjectMapper objectMapper;

    public ActionLogService(JpaActionLogRepository repository, ObjectMapper objectMapper) {
        this.repository = repository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public void log(String toolName, ActionContext context, RiskLevel riskLevel,
                    Object params, Object result) {
        var entity = new ActionLogEntity();
        entity.setToolName(toolName);
        entity.setActorType(context.actorType().name());
        entity.setActorId(context.actorId());
        entity.setDecisionSource(context.decisionSource().name());
        entity.setRecommendationId(context.recommendationId());
        entity.setApprovalStatus(
            context.approvalStatus() != null ? context.approvalStatus().name() : null);
        entity.setRiskLevel(riskLevel.name());
        entity.setChangeReason(context.reason());
        try {
            entity.setParamsJson(objectMapper.writeValueAsString(params));
            entity.setResultJson(objectMapper.writeValueAsString(result));
        } catch (Exception e) {
            entity.setParamsJson("{}");
            entity.setResultJson("{}");
        }
        repository.save(entity);
    }
}
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(mcp): add action_log entity, repository, and service"
```

---

## Task 4: MCP Server Configuration

**Files:**
- Modify: `pos-backend/pom.xml` (add MCP dependency)
- Create: `v2/mcp/McpServerConfig.java`
- Create: `v2/mcp/model/ToolResponse.java`
- Modify: `application.yml` (add MCP section)

- [ ] **Step 1: Add MCP dependency to pom.xml**

Add to `<dependencies>` section of `pos-backend/pom.xml`:

```xml
<!-- MCP Server for AI tool integration -->
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-mcp-server-webmvc-spring-boot-starter</artifactId>
    <version>1.0.0-M6</version>
</dependency>
```

If Spring AI MCP is not stable enough, fallback: implement a minimal SSE endpoint manually (see Step 1b below).

**Step 1b (fallback): Manual SSE endpoint** — Skip this step if the Spring AI MCP starter works. If it doesn't compile or has compatibility issues with Spring Boot 3.3.3, implement a custom `/mcp/sse` endpoint using Spring WebMVC's `SseEmitter`. The tool registration pattern stays the same.

- [ ] **Step 2: Write ToolResponse**

```java
// v2/mcp/model/ToolResponse.java
package com.developer.pos.v2.mcp.model;

public record ToolResponse<T>(
    boolean success,
    T data,
    String error,
    RiskLevel riskLevel,
    String message
) {
    public static <T> ToolResponse<T> ok(T data) {
        return new ToolResponse<>(true, data, null, null, null);
    }

    public static <T> ToolResponse<T> ok(T data, String message) {
        return new ToolResponse<>(true, data, null, null, message);
    }

    public static <T> ToolResponse<T> pendingApproval(T data, RiskLevel risk, String message) {
        return new ToolResponse<>(true, data, null, risk, message);
    }

    public static <T> ToolResponse<T> error(String error) {
        return new ToolResponse<>(false, null, error, null, null);
    }
}
```

- [ ] **Step 3: Write McpServerConfig**

```java
// v2/mcp/McpServerConfig.java
package com.developer.pos.v2.mcp;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class McpServerConfig {

    // MCP server bean registration depends on which MCP library is used.
    // If using spring-ai-mcp-server:
    //   @Bean McpServer mcpServer(List<McpToolProvider> tools) { ... }
    //
    // If using manual SSE fallback:
    //   Register tools in McpToolRegistry and expose via /mcp/sse endpoint.
    //
    // Either way, every tool class (CatalogTools, PromotionTools, etc.)
    // is a Spring @Component that auto-registers.

    @Bean
    public McpToolRegistry mcpToolRegistry() {
        return new McpToolRegistry();
    }
}
```

- [ ] **Step 4: Write McpToolRegistry**

```java
// v2/mcp/McpToolRegistry.java
package com.developer.pos.v2.mcp;

import com.developer.pos.v2.mcp.model.RiskLevel;
import java.util.*;
import java.util.function.Function;

public class McpToolRegistry {

    public record ToolDefinition(
        String name,
        String description,
        String domain,
        String category,       // QUERY, ANALYZE, ACTION
        RiskLevel riskLevel,   // only for ACTION tools
        Function<Map<String, Object>, Object> handler
    ) {}

    private final Map<String, ToolDefinition> tools = new LinkedHashMap<>();

    public void register(ToolDefinition tool) {
        tools.put(tool.name(), tool);
    }

    public Optional<ToolDefinition> getTool(String name) {
        return Optional.ofNullable(tools.get(name));
    }

    public List<ToolDefinition> listTools() {
        return List.copyOf(tools.values());
    }

    public List<ToolDefinition> listByDomain(String domain) {
        return tools.values().stream()
            .filter(t -> t.domain().equals(domain))
            .toList();
    }
}
```

- [ ] **Step 5: Add MCP config to application.yml**

```yaml
# Add to application.yml under the v2mysql profile
mcp:
  server:
    enabled: true
    transport: sse
    path: /mcp/sse
```

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(mcp): add MCP server config, tool registry, and ToolResponse model"
```

---

## Task 5: Catalog Domain Tools

**Files:**
- Create: `v2/mcp/tools/CatalogTools.java`
- Test: `v2/mcp/tools/CatalogToolsTest.java`

- [ ] **Step 1: Write CatalogTools**

```java
// v2/mcp/tools/CatalogTools.java
package com.developer.pos.v2.mcp.tools;

import com.developer.pos.v2.catalog.application.service.AdminCatalogReadService;
import com.developer.pos.v2.catalog.application.service.AdminCatalogWriteService;
import com.developer.pos.v2.mcp.ActionLogService;
import com.developer.pos.v2.mcp.McpToolRegistry;
import com.developer.pos.v2.mcp.McpToolRegistry.ToolDefinition;
import com.developer.pos.v2.mcp.model.RiskLevel;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Component;
import java.util.Map;

@Component
public class CatalogTools {

    private final McpToolRegistry registry;
    private final AdminCatalogReadService readService;
    private final AdminCatalogWriteService writeService;
    private final ActionLogService actionLog;

    public CatalogTools(McpToolRegistry registry,
                        AdminCatalogReadService readService,
                        AdminCatalogWriteService writeService,
                        ActionLogService actionLog) {
        this.registry = registry;
        this.readService = readService;
        this.writeService = writeService;
        this.actionLog = actionLog;
    }

    @PostConstruct
    public void registerTools() {
        registry.register(new ToolDefinition(
            "list_products",
            "List all products for a store, with category and SKU info",
            "catalog", "QUERY", null,
            this::listProducts
        ));

        registry.register(new ToolDefinition(
            "list_categories",
            "List all product categories for a merchant",
            "catalog", "QUERY", null,
            this::listCategories
        ));

        registry.register(new ToolDefinition(
            "toggle_sku_availability",
            "Enable or disable a SKU for a specific store",
            "catalog", "ACTION", RiskLevel.MEDIUM,
            this::toggleSkuAvailability
        ));
    }

    private Object listProducts(Map<String, Object> params) {
        Long storeId = toLong(params.get("store_id"));
        return readService.getProductsByStore(storeId);
    }

    private Object listCategories(Map<String, Object> params) {
        Long merchantId = toLong(params.get("merchant_id"));
        return readService.getCategories(merchantId);
    }

    private Object toggleSkuAvailability(Map<String, Object> params) {
        Long storeId = toLong(params.get("store_id"));
        Long skuId = toLong(params.get("sku_id"));
        Boolean available = (Boolean) params.get("available");
        // Delegate to write service — actual method name depends on current codebase
        return writeService.updateStoreSkuAvailability(storeId, skuId, available);
    }

    private Long toLong(Object value) {
        if (value instanceof Number n) return n.longValue();
        if (value instanceof String s) return Long.parseLong(s);
        throw new IllegalArgumentException("Cannot convert to Long: " + value);
    }
}
```

**Note:** The exact method names on `AdminCatalogReadService` and `AdminCatalogWriteService` must match the current codebase. The implementer should check the actual service class and adjust method calls accordingly.

- [ ] **Step 2: Write test**

```java
// v2/mcp/tools/CatalogToolsTest.java
package com.developer.pos.v2.mcp.tools;

import com.developer.pos.v2.mcp.McpToolRegistry;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CatalogToolsTest {

    @Test
    void registersExpectedTools() {
        var registry = new McpToolRegistry();
        // We can't construct CatalogTools without real services in a unit test,
        // so we test registry behavior directly
        registry.register(new McpToolRegistry.ToolDefinition(
            "list_products", "desc", "catalog", "QUERY", null, params -> null
        ));
        assertTrue(registry.getTool("list_products").isPresent());
        assertEquals("catalog", registry.getTool("list_products").get().domain());
        assertEquals("QUERY", registry.getTool("list_products").get().category());
    }

    @Test
    void listByDomainFiltersCorrectly() {
        var registry = new McpToolRegistry();
        registry.register(new McpToolRegistry.ToolDefinition(
            "list_products", "desc", "catalog", "QUERY", null, params -> null
        ));
        registry.register(new McpToolRegistry.ToolDefinition(
            "list_members", "desc", "member", "QUERY", null, params -> null
        ));

        assertEquals(1, registry.listByDomain("catalog").size());
        assertEquals(1, registry.listByDomain("member").size());
    }
}
```

- [ ] **Step 3: Run tests**

Run: `cd pos-backend && mvn test -pl . -Dtest=CatalogToolsTest -Dspring.profiles.active=mock`
Expected: 2 tests PASS

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(mcp): add catalog domain tools — list_products, list_categories, toggle_sku"
```

---

## Task 6: Promotion Domain Tools

**Files:**
- Create: `v2/mcp/tools/PromotionTools.java`
- Test: `v2/mcp/tools/PromotionToolsTest.java`

- [ ] **Step 1: Write PromotionTools**

```java
// v2/mcp/tools/PromotionTools.java
package com.developer.pos.v2.mcp.tools;

import com.developer.pos.v2.mcp.ActionLogService;
import com.developer.pos.v2.mcp.McpToolRegistry;
import com.developer.pos.v2.mcp.McpToolRegistry.ToolDefinition;
import com.developer.pos.v2.mcp.model.RiskLevel;
import com.developer.pos.v2.promotion.application.service.PromotionApplicationService;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Component;
import java.util.Map;

@Component
public class PromotionTools {

    private final McpToolRegistry registry;
    private final PromotionApplicationService promotionService;
    private final ActionLogService actionLog;

    public PromotionTools(McpToolRegistry registry,
                          PromotionApplicationService promotionService,
                          ActionLogService actionLog) {
        this.registry = registry;
        this.promotionService = promotionService;
        this.actionLog = actionLog;
    }

    @PostConstruct
    public void registerTools() {
        registry.register(new ToolDefinition(
            "list_promotions",
            "List all promotion rules for a merchant/store",
            "promotion", "QUERY", null,
            this::listPromotions
        ));

        registry.register(new ToolDefinition(
            "get_promotion_detail",
            "Get full detail of a specific promotion rule including conditions and rewards",
            "promotion", "QUERY", null,
            this::getPromotionDetail
        ));

        registry.register(new ToolDefinition(
            "create_promotion_draft",
            "Create a new promotion rule draft. Requires owner approval before activation.",
            "promotion", "ACTION", RiskLevel.MEDIUM,
            this::createPromotionDraft
        ));
    }

    private Object listPromotions(Map<String, Object> params) {
        Long merchantId = toLong(params.get("merchant_id"));
        return promotionService.listPromotionRules(merchantId);
    }

    private Object getPromotionDetail(Map<String, Object> params) {
        Long ruleId = toLong(params.get("rule_id"));
        return promotionService.getPromotionRule(ruleId);
    }

    private Object createPromotionDraft(Map<String, Object> params) {
        // Build UpsertPromotionRuleRequest from params
        // This will depend on the actual request structure in the codebase
        // The implementer should check PromotionV2Controller for the pattern
        return Map.of(
            "status", "PENDING_APPROVAL",
            "message", "Promotion draft created. Awaiting owner approval."
        );
    }

    private Long toLong(Object value) {
        if (value instanceof Number n) return n.longValue();
        if (value instanceof String s) return Long.parseLong(s);
        throw new IllegalArgumentException("Cannot convert to Long: " + value);
    }
}
```

- [ ] **Step 2: Write test (registry-level)**

```java
// v2/mcp/tools/PromotionToolsTest.java
package com.developer.pos.v2.mcp.tools;

import com.developer.pos.v2.mcp.McpToolRegistry;
import com.developer.pos.v2.mcp.model.RiskLevel;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PromotionToolsTest {

    @Test
    void actionToolsHaveRiskLevel() {
        var registry = new McpToolRegistry();
        registry.register(new McpToolRegistry.ToolDefinition(
            "create_promotion_draft", "desc", "promotion", "ACTION",
            RiskLevel.MEDIUM, params -> null
        ));
        var tool = registry.getTool("create_promotion_draft").orElseThrow();
        assertEquals(RiskLevel.MEDIUM, tool.riskLevel());
        assertEquals("ACTION", tool.category());
    }
}
```

- [ ] **Step 3: Run test, commit**

```bash
cd pos-backend && mvn test -pl . -Dtest=PromotionToolsTest -Dspring.profiles.active=mock
git add -A && git commit -m "feat(mcp): add promotion domain tools — list, detail, create_draft"
```

---

## Task 7: Member/CRM Domain Tools

**Files:**
- Create: `v2/mcp/tools/MemberTools.java`

- [ ] **Step 1: Write MemberTools**

```java
// v2/mcp/tools/MemberTools.java
package com.developer.pos.v2.mcp.tools;

import com.developer.pos.v2.member.application.service.MemberApplicationService;
import com.developer.pos.v2.mcp.ActionLogService;
import com.developer.pos.v2.mcp.McpToolRegistry;
import com.developer.pos.v2.mcp.McpToolRegistry.ToolDefinition;
import com.developer.pos.v2.mcp.model.RiskLevel;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Component;
import java.util.Map;

@Component
public class MemberTools {

    private final McpToolRegistry registry;
    private final MemberApplicationService memberService;
    private final ActionLogService actionLog;

    public MemberTools(McpToolRegistry registry,
                       MemberApplicationService memberService,
                       ActionLogService actionLog) {
        this.registry = registry;
        this.memberService = memberService;
        this.actionLog = actionLog;
    }

    @PostConstruct
    public void registerTools() {
        registry.register(new ToolDefinition(
            "list_members",
            "List all members for a merchant, with account and points info",
            "member", "QUERY", null,
            this::listMembers
        ));

        registry.register(new ToolDefinition(
            "get_member_profile",
            "Get full profile of a member including account balance, points, tier, and transaction history",
            "member", "QUERY", null,
            this::getMemberProfile
        ));

        registry.register(new ToolDefinition(
            "get_churn_risk_members",
            "Identify members who have not visited in N days (default 30). Returns members sorted by last visit date.",
            "member", "ANALYZE", null,
            this::getChurnRiskMembers
        ));

        registry.register(new ToolDefinition(
            "update_member_tier",
            "Change a member's tier level. Requires owner approval.",
            "member", "ACTION", RiskLevel.MEDIUM,
            this::updateMemberTier
        ));
    }

    private Object listMembers(Map<String, Object> params) {
        Long merchantId = toLong(params.get("merchant_id"));
        return memberService.listMembers(merchantId);
    }

    private Object getMemberProfile(Map<String, Object> params) {
        Long memberId = toLong(params.get("member_id"));
        return memberService.getMemberDetail(memberId);
    }

    private Object getChurnRiskMembers(Map<String, Object> params) {
        Long merchantId = toLong(params.get("merchant_id"));
        int days = params.containsKey("days") ? ((Number) params.get("days")).intValue() : 30;
        // This requires a new query on MemberApplicationService
        // The implementer should add: findMembersNotVisitedSince(merchantId, days)
        return Map.of("todo", "implement findMembersNotVisitedSince on MemberApplicationService");
    }

    private Object updateMemberTier(Map<String, Object> params) {
        return Map.of(
            "status", "PENDING_APPROVAL",
            "message", "Member tier update requires owner approval."
        );
    }

    private Long toLong(Object value) {
        if (value instanceof Number n) return n.longValue();
        if (value instanceof String s) return Long.parseLong(s);
        throw new IllegalArgumentException("Cannot convert to Long: " + value);
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "feat(mcp): add member/CRM domain tools — list, profile, churn_risk, update_tier"
```

---

## Task 8: Order, Settlement, Report, Store Domain Tools

**Files:**
- Create: `v2/mcp/tools/OrderTools.java`
- Create: `v2/mcp/tools/SettlementTools.java`
- Create: `v2/mcp/tools/ReportTools.java`
- Create: `v2/mcp/tools/StoreTools.java`

- [ ] **Step 1: Write OrderTools**

```java
// v2/mcp/tools/OrderTools.java
package com.developer.pos.v2.mcp.tools;

import com.developer.pos.v2.mcp.ActionLogService;
import com.developer.pos.v2.mcp.McpToolRegistry;
import com.developer.pos.v2.mcp.McpToolRegistry.ToolDefinition;
import com.developer.pos.v2.order.application.service.ActiveTableOrderApplicationService;
import com.developer.pos.v2.order.application.service.MerchantOrderReadService;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Component;
import java.util.Map;

@Component
public class OrderTools {
    private final McpToolRegistry registry;
    private final ActiveTableOrderApplicationService orderService;
    private final MerchantOrderReadService orderReadService;
    private final ActionLogService actionLog;

    public OrderTools(McpToolRegistry registry,
                      ActiveTableOrderApplicationService orderService,
                      MerchantOrderReadService orderReadService,
                      ActionLogService actionLog) {
        this.registry = registry;
        this.orderService = orderService;
        this.orderReadService = orderReadService;
        this.actionLog = actionLog;
    }

    @PostConstruct
    public void registerTools() {
        registry.register(new ToolDefinition(
            "get_active_orders",
            "Get all currently active table orders for a store",
            "order", "QUERY", null,
            params -> orderReadService.getActiveOrders(toLong(params.get("store_id")))
        ));

        registry.register(new ToolDefinition(
            "get_order_history",
            "Get submitted/settled orders for a store within a date range",
            "order", "QUERY", null,
            params -> orderReadService.getOrderHistory(
                toLong(params.get("store_id")),
                (String) params.get("date_from"),
                (String) params.get("date_to")
            )
        ));

        registry.register(new ToolDefinition(
            "get_table_status",
            "Get current status of all tables in a store (occupied/available/pending settlement)",
            "order", "QUERY", null,
            params -> orderReadService.getTableStatus(toLong(params.get("store_id")))
        ));
    }

    private Long toLong(Object value) {
        if (value instanceof Number n) return n.longValue();
        if (value instanceof String s) return Long.parseLong(s);
        throw new IllegalArgumentException("Cannot convert to Long: " + value);
    }
}
```

**Note:** `MerchantOrderReadService` may not have `getActiveOrders`, `getOrderHistory`, `getTableStatus` methods. The implementer should check and add as needed — these are read-only queries that wrap existing JPA repositories.

- [ ] **Step 2: Write SettlementTools**

```java
// v2/mcp/tools/SettlementTools.java
package com.developer.pos.v2.mcp.tools;

import com.developer.pos.v2.mcp.ActionLogService;
import com.developer.pos.v2.mcp.McpToolRegistry;
import com.developer.pos.v2.mcp.McpToolRegistry.ToolDefinition;
import com.developer.pos.v2.settlement.application.service.CashierSettlementApplicationService;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Component;
import java.util.Map;

@Component
public class SettlementTools {
    private final McpToolRegistry registry;
    private final CashierSettlementApplicationService settlementService;
    private final ActionLogService actionLog;

    public SettlementTools(McpToolRegistry registry,
                           CashierSettlementApplicationService settlementService,
                           ActionLogService actionLog) {
        this.registry = registry;
        this.settlementService = settlementService;
        this.actionLog = actionLog;
    }

    @PostConstruct
    public void registerTools() {
        registry.register(new ToolDefinition(
            "get_daily_revenue",
            "Get total revenue for a store on a given date, broken down by payment method",
            "settlement", "QUERY", null,
            params -> settlementService.getDailyRevenue(
                toLong(params.get("store_id")), (String) params.get("date"))
        ));

        registry.register(new ToolDefinition(
            "get_payment_breakdown",
            "Get payment method distribution (card/QR/cash) for a store in a date range",
            "settlement", "ANALYZE", null,
            params -> settlementService.getPaymentBreakdown(
                toLong(params.get("store_id")),
                (String) params.get("date_from"),
                (String) params.get("date_to"))
        ));

        registry.register(new ToolDefinition(
            "get_refund_history",
            "List refund records for a store in a date range",
            "settlement", "QUERY", null,
            params -> settlementService.getRefundHistory(
                toLong(params.get("store_id")),
                (String) params.get("date_from"),
                (String) params.get("date_to"))
        ));
    }

    private Long toLong(Object value) {
        if (value instanceof Number n) return n.longValue();
        if (value instanceof String s) return Long.parseLong(s);
        throw new IllegalArgumentException("Cannot convert to Long: " + value);
    }
}
```

**Note:** `getDailyRevenue`, `getPaymentBreakdown`, `getRefundHistory` may not exist on `CashierSettlementApplicationService`. The implementer should add these read-only query methods wrapping `JpaSettlementRecordRepository` and `JpaPaymentAttemptRepository`.

- [ ] **Step 3: Write ReportTools**

```java
// v2/mcp/tools/ReportTools.java
package com.developer.pos.v2.mcp.tools;

import com.developer.pos.v2.mcp.ActionLogService;
import com.developer.pos.v2.mcp.McpToolRegistry;
import com.developer.pos.v2.mcp.McpToolRegistry.ToolDefinition;
import com.developer.pos.v2.report.application.service.ReportReadService;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Component;
import java.util.Map;

@Component
public class ReportTools {
    private final McpToolRegistry registry;
    private final ReportReadService reportService;
    private final ActionLogService actionLog;

    public ReportTools(McpToolRegistry registry,
                       ReportReadService reportService,
                       ActionLogService actionLog) {
        this.registry = registry;
        this.reportService = reportService;
        this.actionLog = actionLog;
    }

    @PostConstruct
    public void registerTools() {
        registry.register(new ToolDefinition(
            "get_daily_summary",
            "Get daily business summary: revenue, order count, avg ticket size, table turnover",
            "report", "QUERY", null,
            params -> reportService.getDailySummary(
                toLong(params.get("store_id")), (String) params.get("date"))
        ));

        registry.register(new ToolDefinition(
            "get_product_ranking",
            "Rank products by sales volume or revenue for a store in a date range",
            "report", "ANALYZE", null,
            params -> reportService.getProductRanking(
                toLong(params.get("store_id")),
                (String) params.get("date_from"),
                (String) params.get("date_to"),
                (String) params.getOrDefault("sort_by", "revenue"))
        ));

        registry.register(new ToolDefinition(
            "compare_periods",
            "Compare two date ranges for a store: revenue, orders, avg ticket, growth rate",
            "report", "ANALYZE", null,
            params -> reportService.comparePeriods(
                toLong(params.get("store_id")),
                (String) params.get("period1_from"), (String) params.get("period1_to"),
                (String) params.get("period2_from"), (String) params.get("period2_to"))
        ));
    }

    private Long toLong(Object value) {
        if (value instanceof Number n) return n.longValue();
        if (value instanceof String s) return Long.parseLong(s);
        throw new IllegalArgumentException("Cannot convert to Long: " + value);
    }
}
```

**Note:** `getDailySummary`, `getProductRanking`, `comparePeriods` may need to be added to `ReportReadService`.

- [ ] **Step 4: Write StoreTools**

```java
// v2/mcp/tools/StoreTools.java
package com.developer.pos.v2.mcp.tools;

import com.developer.pos.v2.mcp.ActionLogService;
import com.developer.pos.v2.mcp.McpToolRegistry;
import com.developer.pos.v2.mcp.McpToolRegistry.ToolDefinition;
import com.developer.pos.v2.store.infrastructure.persistence.repository.JpaStoreRepository;
import com.developer.pos.v2.store.infrastructure.persistence.repository.JpaStoreTableRepository;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Component;
import java.util.Map;

@Component
public class StoreTools {
    private final McpToolRegistry registry;
    private final JpaStoreRepository storeRepository;
    private final JpaStoreTableRepository tableRepository;
    private final ActionLogService actionLog;

    public StoreTools(McpToolRegistry registry,
                      JpaStoreRepository storeRepository,
                      JpaStoreTableRepository tableRepository,
                      ActionLogService actionLog) {
        this.registry = registry;
        this.storeRepository = storeRepository;
        this.tableRepository = tableRepository;
        this.actionLog = actionLog;
    }

    @PostConstruct
    public void registerTools() {
        registry.register(new ToolDefinition(
            "get_store_list",
            "List all stores for a merchant",
            "store", "QUERY", null,
            params -> storeRepository.findByMerchantId(toLong(params.get("merchant_id")))
        ));

        registry.register(new ToolDefinition(
            "get_table_layout",
            "Get all tables for a store with current status",
            "store", "QUERY", null,
            params -> tableRepository.findByStoreId(toLong(params.get("store_id")))
        ));

        registry.register(new ToolDefinition(
            "get_store_config",
            "Get store configuration and settings",
            "store", "QUERY", null,
            params -> storeRepository.findById(toLong(params.get("store_id")))
                .orElse(null)
        ));
    }

    private Long toLong(Object value) {
        if (value instanceof Number n) return n.longValue();
        if (value instanceof String s) return Long.parseLong(s);
        throw new IllegalArgumentException("Cannot convert to Long: " + value);
    }
}
```

**Note:** Store domain has no application service layer — it only has entities and repositories. StoreTools injects repositories directly, consistent with the current codebase where the store module is minimal.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat(mcp): add order, settlement, report, store domain tools"
```

---

## Task 9: MCP SSE Endpoint (REST Controller)

**Files:**
- Create: `v2/mcp/interfaces/McpEndpointController.java`

- [ ] **Step 1: Write the SSE endpoint controller**

```java
// v2/mcp/interfaces/McpEndpointController.java
package com.developer.pos.v2.mcp.interfaces;

import com.developer.pos.v2.common.response.ApiResponse;
import com.developer.pos.v2.mcp.ActionContextHolder;
import com.developer.pos.v2.mcp.ActionLogService;
import com.developer.pos.v2.mcp.McpToolRegistry;
import com.developer.pos.v2.mcp.model.ActionContext;
import com.developer.pos.v2.mcp.model.RiskLevel;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v2/mcp")
public class McpEndpointController {

    private final McpToolRegistry registry;
    private final ActionContextHolder contextHolder;
    private final ActionLogService actionLogService;
    private final ObjectMapper objectMapper;

    public McpEndpointController(McpToolRegistry registry,
                                  ActionContextHolder contextHolder,
                                  ActionLogService actionLogService,
                                  ObjectMapper objectMapper) {
        this.registry = registry;
        this.contextHolder = contextHolder;
        this.actionLogService = actionLogService;
        this.objectMapper = objectMapper;
    }

    /**
     * List all available tools with metadata.
     */
    @GetMapping("/tools")
    public ApiResponse<List<ToolInfo>> listTools(
            @RequestParam(required = false) String domain) {
        var tools = domain != null
            ? registry.listByDomain(domain)
            : registry.listTools();

        var infos = tools.stream().map(t -> new ToolInfo(
            t.name(), t.description(), t.domain(), t.category(),
            t.riskLevel() != null ? t.riskLevel().name() : null
        )).toList();

        return ApiResponse.success(infos);
    }

    /**
     * Execute a tool by name.
     */
    @PostMapping("/tools/{toolName}/execute")
    public ApiResponse<Object> executeTool(
            @PathVariable String toolName,
            @RequestBody ToolExecuteRequest request) {

        var toolOpt = registry.getTool(toolName);
        if (toolOpt.isEmpty()) {
            return new ApiResponse<>(404, "Tool not found: " + toolName, null);
        }

        var tool = toolOpt.get();

        // Set ActionContext for this request
        if (request.context() != null) {
            contextHolder.setContext(request.context());
        }

        // Execute
        try {
            Object result = tool.handler().apply(request.params());

            // Log action tools
            if ("ACTION".equals(tool.category())) {
                actionLogService.log(
                    toolName,
                    contextHolder.getContext(),
                    tool.riskLevel() != null ? tool.riskLevel() : RiskLevel.LOW,
                    request.params(),
                    result
                );
            }

            return ApiResponse.success(result);
        } catch (Exception e) {
            return new ApiResponse<>(500, e.getMessage(), null);
        }
    }

    record ToolInfo(String name, String description, String domain,
                    String category, String riskLevel) {}

    record ToolExecuteRequest(
        Map<String, Object> params,
        ActionContext context
    ) {}
}
```

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "feat(mcp): add REST endpoint for tool listing and execution"
```

---

## Task 10: Integration Test

**Files:**
- Create: `v2/mcp/McpIntegrationTest.java`

- [ ] **Step 1: Write integration test**

```java
// v2/mcp/McpIntegrationTest.java
package com.developer.pos.v2.mcp;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.ActiveProfiles;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("v2mysql")  // requires running MySQL
class McpIntegrationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private McpToolRegistry registry;

    @Test
    void allDomainToolsRegistered() {
        var tools = registry.listTools();
        // Verify all domains have at least one tool
        var domains = tools.stream().map(McpToolRegistry.ToolDefinition::domain).distinct().toList();
        assertTrue(domains.contains("catalog"), "catalog tools missing");
        assertTrue(domains.contains("order"), "order tools missing");
        assertTrue(domains.contains("member"), "member tools missing");
        assertTrue(domains.contains("promotion"), "promotion tools missing");
        assertTrue(domains.contains("settlement"), "settlement tools missing");
        assertTrue(domains.contains("report"), "report tools missing");
        assertTrue(domains.contains("store"), "store tools missing");
    }

    @Test
    void listToolsEndpointWorks() {
        var response = restTemplate.getForObject(
            "http://localhost:" + port + "/api/v2/mcp/tools",
            String.class
        );
        assertNotNull(response);
        assertTrue(response.contains("list_products"));
    }
}
```

- [ ] **Step 2: Run integration test (requires MySQL)**

Run: `cd pos-backend && mvn test -pl . -Dtest=McpIntegrationTest -Dspring.profiles.active=v2mysql`
Expected: 2 tests PASS (requires Docker MySQL running)

- [ ] **Step 3: Final commit**

```bash
git add -A && git commit -m "feat(mcp): add integration test for MCP tool server"
```

---

## Task 11: Ai Proposal Table (Schema Only, for P1)

**Files:**
- Create: `db/migration/v2/V018__create_ai_proposal.sql`

- [ ] **Step 1: Write migration**

```sql
-- V018__create_ai_proposal.sql
-- Schema for P1 AI Operator approval flow. Not used in P0.
CREATE TABLE ai_proposal (
    id VARCHAR(64) PRIMARY KEY,
    advisor_role VARCHAR(32) NOT NULL,
    proposal_type VARCHAR(64) NOT NULL,
    target_domain VARCHAR(32) NOT NULL,
    target_tool VARCHAR(64) NOT NULL,
    params_json JSON,
    reason TEXT,
    risk_level VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    expires_at DATETIME(6),
    reviewed_by VARCHAR(64),
    reviewed_at DATETIME(6),
    executed_at DATETIME(6),
    KEY idx_proposal_status (status, created_at),
    KEY idx_proposal_role (advisor_role, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "feat(mcp): add ai_proposal table schema for P1 approval flow"
```

---

## Summary

| Task | What | Files | Estimated Time |
|------|------|-------|---------------|
| 1 | ActionContext model + holder | 3 new | 10 min |
| 2 | JPA audit infrastructure | 5 new | 20 min |
| 2.5 | Wire existing entities to audit | 7 modify | 15 min |
| 3 | Action log repository | 3 new | 10 min |
| 4 | MCP server config + registry | 4 new | 15 min |
| 5 | Catalog tools | 2 new | 15 min |
| 6 | Promotion tools | 2 new | 15 min |
| 7 | Member/CRM tools | 1 new | 10 min |
| 8 | Order/Settlement/Report/Store tools | 4 new | 30 min |
| 9 | MCP REST endpoint | 1 new | 15 min |
| 10 | Integration test | 1 new | 10 min |
| 11 | ai_proposal schema (P1 prep) | 1 new | 5 min |
| **Total** | | **~27 new + 7 modify** | **~3 hours** |

**Design decision on audit columns:** Core entity tables get 4 minimal columns (`actor_type`, `actor_id`, `decision_source`, `change_reason`) — enough to know who did what and why. The full context (`recommendation_id`, `approval_status`, `risk_level`, `params_json`, `result_json`) lives in the `action_log` table. This keeps entity schema simple while preserving complete audit history.

All new files minimize merge conflicts with the actively-developed codebase. Task 2.5 (entity modifications) is the only high-risk change — verify compilation and existing tests carefully.
