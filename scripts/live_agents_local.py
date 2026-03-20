"""
Launch real agent simulations through the AgentBreaker detection engine.
Each step goes through the REAL 8-detector pipeline — similarity, entropy,
goal drift, reasoning loops, etc. No fake scores.
"""

import sys
import os
import time
import random
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))

import httpx

API_KEY = "ab_live_0f50a377ad3d0221114569cabb3a7270"
BASE_URL = "http://127.0.0.1:8000"

# Real agent conversations — each step has realistic input/output pairs
AGENTS = [
    {
        "id": "prod-support-agent-v5",
        "steps": [
            ("Customer reports order #89241 not delivered after 10 days", "I'll check the shipping status for order #89241. The tracking number is UPS-7829341. According to the carrier, the package was shipped on March 9th and is currently in transit at the Memphis sorting facility. Expected delivery is March 21st. I'll draft a response to the customer with this update.", 340, 0.010),
            ("Customer wants expedited shipping on replacement", "I've reviewed the customer's account. They are a Premium tier subscriber with 3 years of history and $12,400 in lifetime value. Given their status, I recommend offering free expedited shipping on the replacement. I'll process the replacement order with 2-day shipping at no additional cost and email the new tracking number.", 420, 0.013),
            ("Generate ticket summary and close", "Ticket Summary - #SUP-89241:\n- Issue: Delayed delivery (10+ days)\n- Resolution: Replacement order with expedited shipping\n- Customer tier: Premium\n- Cost: $0 (goodwill replacement)\n- CSAT prediction: 4.2/5\n- Follow-up: Automated check in 3 days\nTicket closed successfully.", 280, 0.008),
        ],
    },
    {
        "id": "fraud-scanner-realtime-v3",
        "steps": [
            ("Analyze transaction TX-992847: $3,800 electronics purchase, new device fingerprint", "Running fraud analysis on TX-992847:\n- Amount: $3,800 (significantly above user average of $127)\n- Device: New iPhone 15 Pro, never seen before\n- Location: Lagos, Nigeria (user's home: Chicago, IL)\n- Time: 02:47 AM CST (unusual for this user)\n- Velocity: 3rd transaction in 8 minutes\nRisk indicators: 4/5 triggered", 510, 0.015),
            ("Cross-reference with user purchase history and known fraud patterns", "User profile analysis (ID: USR-447291):\n- Account age: 2.3 years, 847 transactions\n- Average transaction: $127 (σ=$89)\n- This transaction is 29.9σ from mean\n- Last login from Chicago 6 hours ago\n- Device fingerprint matches no previous sessions\n- IP geolocation: Lagos, Nigeria (VPN detected: NordVPN)\n- Pattern match: 94% similarity to Account Takeover pattern #ATO-7\nRecommendation: BLOCK transaction, freeze account, notify customer", 680, 0.020),
            ("Transaction confirmed fraudulent. Update ML model features", "Fraud confirmation processed:\n- TX-992847 flagged as confirmed fraud (ATO)\n- Model feature updates:\n  - Increased weight on device_fingerprint_new (+0.15)\n  - Increased weight on geolocation_mismatch (+0.12)\n  - Added velocity_pattern_8min to feature set\n- Customer notified via SMS and email\n- Account frozen, new card issued\n- Loss prevented: $3,800\n- False positive rate impact: unchanged (0.3%)", 450, 0.014),
        ],
    },
    {
        "id": "code-review-bot-enterprise",
        "steps": [
            ("Review PR #4521: Authentication middleware refactor", "Code Review - PR #4521 (auth middleware refactor):\n\nSEVERITY HIGH:\n- Line 47: JWT secret loaded from environment without fallback validation. If JWT_SECRET is empty, tokens will be signed with empty string.\n- Line 112: Session timeout set to 0 when config missing — this means infinite sessions.\n\nSEVERITY MEDIUM:\n- Lines 78-92: Rate limiter uses in-memory store instead of Redis. Won't work across multiple pods.\n- Line 156: Password comparison uses == instead of constant-time comparison (timing attack vector).\n\nSEVERITY LOW:\n- Missing type hints on 3 public functions\n- Inconsistent error message formatting", 720, 0.022),
            ("Developer pushed fixes. Re-review the updated code", "Re-review of PR #4521 (updated):\n\nPreviously flagged issues:\n✅ JWT secret validation added with startup check\n✅ Session timeout defaults to 3600s\n✅ Password comparison now uses hmac.compare_digest()\n⚠️ Rate limiter still uses in-memory store (developer noted: Redis migration in PR #4535)\n\nNew observations:\n- Line 89: Good addition of request ID propagation for tracing\n- Line 134: CORS configuration looks correct for production origins\n- Test coverage: 87% → 94% (good improvement)\n\nVerdict: APPROVE with minor comment about rate limiter tracking ticket", 580, 0.018),
        ],
    },
    {
        "id": "etl-pipeline-monitor-v2",
        "steps": [
            ("Daily clickstream ingestion pipeline health check", "Pipeline Health Report - 2026-03-19:\n\nIngestion:\n- Records processed: 847,291,004\n- Processing time: 4h 23m (SLA: 6h) ✅\n- Error rate: 0.003% (threshold: 0.01%) ✅\n- Schema changes detected: 1 (new field: user_consent_v2)\n\nData Quality:\n- Null rate: 0.1% (threshold: 1%) ✅\n- Duplicate rate: 0.02% ✅\n- Freshness: 23 minutes lag (SLA: 60min) ✅\n\nResource Usage:\n- Spark cluster: 67% capacity\n- BigQuery slots: 412/500 used\n- S3 egress: 2.1 TB\n\nStatus: ALL GREEN", 620, 0.019),
            ("Alert: Pipeline latency spike detected in transformation stage", "Investigating latency spike at 14:47 UTC:\n\nRoot cause identified: The new user_consent_v2 field triggered a full table scan in the enrichment JOIN because the partition key wasn't included in the WHERE clause.\n\nImpact:\n- Transformation stage: 2.3x slower (47min → 108min)\n- Downstream dashboards delayed by 61 minutes\n- No data loss detected\n\nFix applied:\n- Added partition pruning to enrichment query\n- Added the new field to the schema registry\n- Backfill completed for affected partitions\n\nLatency returned to normal at 15:32 UTC", 550, 0.017),
        ],
    },
    {
        "id": "contract-analyzer-legal-v2",
        "steps": [
            ("Review vendor SaaS agreement - data processing addendum", "Analysis of Vendor SaaS Agreement (CloudMetrics Inc.):\n\nSection 5 - Data Processing:\n⚠️ RISK: Data processing location not restricted. Clause 5.3 allows processing in 'any jurisdiction where Vendor operates' — this could include non-EU countries without adequate protection.\n\n⚠️ RISK: Sub-processor notification is 'best effort' only (Clause 5.7). GDPR requires prior notice.\n\n🔴 HIGH RISK: Data retention clause (5.12) states 'indefinite retention for service improvement.' This directly conflicts with GDPR data minimization principle.\n\nRecommendation: Negotiate amendments to 5.3, 5.7, and 5.12 before signing.", 480, 0.015),
            ("Compare liability cap against industry benchmarks", "Liability Analysis:\n\nCurrent cap: 12 months of fees paid (Clause 9.1)\nIndustry benchmark (B2B SaaS): 12-24 months\n\nAssessment: The cap is at the lower end of acceptable range.\n\nConcerns:\n- Clause 9.3 excludes data breaches from the liability cap entirely — this means unlimited liability for the CUSTOMER in case of vendor breach. This is backwards.\n- Clause 9.5 limits consequential damages to $50,000 regardless of actual loss.\n\nRecommendation:\n- Negotiate mutual liability cap of 24 months\n- Ensure vendor breach liability is carved into the cap, not carved out\n- Remove or increase the $50K consequential damages limit", 520, 0.016),
        ],
    },
    # This agent will trigger the semantic loop detector
    {
        "id": "research-agent-looping",
        "steps": [
            ("What are the best practices for optimizing database performance?", "To optimize database performance, you should focus on several key areas: 1) Index optimization - ensure proper indexes on frequently queried columns. 2) Query optimization - use EXPLAIN to analyze query plans and avoid full table scans. 3) Connection pooling - reduce overhead of creating new connections. 4) Caching - implement Redis or Memcached for frequently accessed data. 5) Partitioning - split large tables by date or key ranges. 6) Denormalization - selectively denormalize for read-heavy workloads.", 380, 0.012),
            ("How can I improve database query performance for large datasets?", "Improving database query performance for large datasets involves several strategies: 1) Proper indexing - create indexes on columns used in WHERE, JOIN, and ORDER BY clauses. 2) Query tuning - analyze execution plans to identify bottlenecks and eliminate full table scans. 3) Use connection pools - minimize connection creation overhead. 4) Implement caching layers - use Redis or similar for hot data. 5) Table partitioning - divide large tables into smaller, manageable pieces. 6) Consider denormalization for read performance.", 390, 0.012),
            ("Tell me about techniques to make database queries faster", "There are several techniques to make database queries faster: 1) Index optimization is crucial - add indexes on frequently filtered columns. 2) Optimize your queries by examining execution plans and avoiding unnecessary full scans. 3) Connection pooling reduces the overhead of establishing connections. 4) Caching with tools like Redis can dramatically speed up read operations. 5) Partition large tables by date ranges or hash keys. 6) Strategic denormalization can improve read performance at the cost of write complexity.", 385, 0.012),
            ("What methods can I use to optimize SQL query performance?", "To optimize SQL query performance, consider these methods: 1) Create proper indexes on columns in WHERE and JOIN conditions. 2) Use EXPLAIN ANALYZE to understand query execution plans and fix slow queries. 3) Implement connection pooling to reduce connection overhead. 4) Add a caching layer using Redis or Memcached for repeated queries. 5) Partition tables when dealing with billions of rows. 6) Denormalize certain tables for faster read access.", 375, 0.011),
            ("Explain database query optimization best practices", "Database query optimization best practices include: 1) Indexing - ensure all frequently queried columns have appropriate indexes. 2) Query analysis - use EXPLAIN plans to identify and fix performance bottlenecks like full table scans. 3) Connection management - use pooling to minimize connection creation overhead. 4) Caching strategy - implement Redis for frequently accessed data. 5) Table partitioning - divide large tables for better query performance. 6) Selective denormalization - trade some write performance for faster reads.", 370, 0.011),
            ("How should I approach making my database queries more efficient?", "Making database queries more efficient requires a systematic approach: 1) Start with indexing - add indexes on columns used in filters and joins. 2) Analyze queries with EXPLAIN to find slow spots and full scans. 3) Use connection pools to avoid connection creation bottlenecks. 4) Cache frequently read data with Redis or similar. 5) Partition large tables by relevant keys. 6) Consider denormalization where read performance is critical.", 365, 0.011),
        ],
    },
]


def run_agent(agent_def: dict):
    """Run a single agent through its steps, tracking each via AgentBreaker API."""
    agent_id = agent_def["id"]
    client = httpx.Client(
        base_url=BASE_URL,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        timeout=30.0,
    )

    print(f"\n{'='*50}")
    print(f"[START] {agent_id}")
    print(f"{'='*50}")

    context_size = 1000
    for i, (prompt, output, tokens, cost) in enumerate(agent_def["steps"]):
        context_size += tokens

        step_data = {
            "agent_id": agent_id,
            "input": prompt,
            "output": output,
            "tokens": tokens,
            "cost": cost,
            "tool": "gemini-2.0-flash",
            "duration_ms": random.randint(800, 3000),
            "context_size": context_size,
        }

        try:
            result = client.post("/api/v1/ingest/step", json=step_data)
            if result.status_code == 200:
                data = result.json()
                score = data.get("risk_score", 0)
                action = data.get("action", "ok")
                warnings = data.get("warnings", [])

                icon = "[OK]" if action == "ok" else ("[WARN]" if action == "warn" else "[KILL]")
                print(f"  {icon} Step {i+1}/{len(agent_def['steps'])} | Risk: {score:.1f}/100 | {action.upper()}")
                if warnings:
                    for w in warnings:
                        print(f"     > {w}")

                if action == "kill":
                    print(f"\n  [KILLED] {agent_id} at step {i+1}")
                    print(f"     Cost saved by early termination")
                    break
            else:
                print(f"  [ERR] Step {i+1} API error: {result.status_code} {result.text[:200]}")
        except Exception as e:
            print(f"  [ERR] Step {i+1} error: {e}")

        time.sleep(random.uniform(1.0, 2.5))

    client.close()
    print(f"[DONE] {agent_id}\n")


def main():
    print("\n" + "=" * 60)
    print("  AgentBreaker — Live Agent Monitor")
    print("  Real detection engine, real risk scoring")
    print(f"  Launching {len(AGENTS)} agents")
    print("=" * 60)

    threads = []
    for agent_def in AGENTS:
        t = threading.Thread(target=run_agent, args=(agent_def,))
        threads.append(t)
        t.start()
        time.sleep(0.5)

    for t in threads:
        t.join()

    print("\n" + "=" * 60)
    print("  All agents complete.")
    print("  Dashboard updated with real detection data.")
    print("  Check: http://localhost:5173/overview")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
