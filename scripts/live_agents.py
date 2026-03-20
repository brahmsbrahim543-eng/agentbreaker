"""
Launch real AI agents that call Google Gemini and feed steps through AgentBreaker SDK.
Each agent runs a multi-step task, and AgentBreaker monitors for runaway behavior.
"""

import sys
import os
import time
import random
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))

import httpx
import google.generativeai as genai

# ---- Config ----
API_KEY = "ab_live_0f50a377ad3d0221114569cabb3a7270"
BASE_URL = "http://127.0.0.1:8000"
GOOGLE_API_KEY = "AIzaSyCYqqKuCd294JJLGOVtWyjh25BpRKyoHnA"

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# ---- Agent tasks ----
AGENT_TASKS = [
    {
        "id": "customer-support-bot-v4",
        "prompts": [
            "A customer says their order #45892 hasn't arrived after 2 weeks. Check the status and draft a response.",
            "The customer replied saying they want a refund. Process the refund request.",
            "Customer is asking about the refund timeline. Explain the 5-7 business day policy.",
            "Customer wants to know if they can get expedited shipping on a replacement order.",
            "Customer is satisfied. Close the ticket and generate a summary.",
        ],
    },
    {
        "id": "code-review-agent-v2",
        "prompts": [
            "Review this Python function for security issues: def login(user, pw): return db.query(f'SELECT * FROM users WHERE name={user} AND pass={pw}')",
            "The developer fixed the SQL injection. Now review for performance: the function queries the DB on every request without caching.",
            "Suggest a caching strategy using Redis with TTL-based invalidation.",
            "Review the updated code that uses Redis caching. Check for race conditions.",
            "Generate a final code review summary with severity ratings.",
        ],
    },
    {
        "id": "data-pipeline-orchestrator",
        "prompts": [
            "Design an ETL pipeline to ingest 50GB of daily clickstream data from S3 into BigQuery.",
            "The pipeline is failing on schema evolution. Suggest a strategy for handling new columns.",
            "Implement data quality checks: null rates, duplicate detection, freshness monitoring.",
            "The pipeline is running 3x slower than expected. Profile and suggest optimizations.",
            "Generate a pipeline health report for the last 24 hours.",
        ],
    },
    {
        "id": "fraud-detection-agent-v3",
        "prompts": [
            "Analyze transaction #TX-8847291: $4,200 purchase from unusual location at 3:17 AM.",
            "Cross-reference with the user's purchase history. Last 30 days: 12 transactions, avg $89.",
            "The velocity check shows 4 transactions in the last 10 minutes totaling $12,400. Assess risk.",
            "Generate a fraud risk score with confidence interval and recommend action.",
            "The transaction was confirmed fraudulent. Update the model features and log the incident.",
        ],
    },
    {
        "id": "legal-contract-reviewer",
        "prompts": [
            "Review the SaaS agreement in section 3.1 regarding data ownership and IP rights.",
            "Flag any clauses that conflict with GDPR data processing requirements.",
            "The indemnification clause in 7.2 seems overly broad. Suggest amendments.",
            "Compare the liability cap against industry standards for B2B SaaS contracts.",
            "Generate a redline summary with risk ratings for each flagged clause.",
        ],
    },
    {
        "id": "semantic-loop-agent",
        "prompts": [
            "What is the best way to optimize database queries for large datasets?",
            "Can you explain how to optimize database queries for better performance?",
            "Tell me about database query optimization techniques for large tables.",
            "How should I approach optimizing slow database queries?",
            "What are the best practices for database query performance tuning?",
            "Explain database query optimization strategies for handling big data.",
            "How to make database queries faster for large datasets?",
            "What methods can I use to optimize database queries?",
        ],
    },
]


def run_agent(task: dict):
    """Run a single agent through its task steps, tracking each via AgentBreaker."""
    agent_id = task["id"]
    client = httpx.Client(
        base_url=BASE_URL,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        timeout=30.0,
    )

    print(f"\n[AGENT] Starting: {agent_id}")

    context_size = 1000
    for i, prompt in enumerate(task["prompts"]):
        try:
            # Real Gemini API call
            start = time.time()
            response = model.generate_content(prompt)
            duration_ms = int((time.time() - start) * 1000)
            output_text = response.text[:2000] if response.text else "No response"
            tokens = response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else random.randint(200, 800)
            cost = tokens * 0.000001  # Gemini Flash pricing approx

            context_size += tokens

            # Track through AgentBreaker
            step_data = {
                "agent_id": agent_id,
                "input": prompt,
                "output": output_text,
                "tokens": tokens,
                "cost": cost,
                "tool": "gemini-2.0-flash",
                "duration_ms": duration_ms,
                "context_size": context_size,
            }

            result = client.post("/api/v1/ingest/step", json=step_data)
            if result.status_code == 200:
                data = result.json()
                score = data.get("risk_score", 0)
                action = data.get("action", "ok")
                warnings = data.get("warnings", [])

                status = "OK" if action == "ok" else ("WARN" if action == "warn" else "KILLED")
                print(f"  [{agent_id}] Step {i+1}/{len(task['prompts'])} | Risk: {score:.1f} | {status}")
                if warnings:
                    for w in warnings:
                        print(f"    ! {w}")

                if action == "kill":
                    print(f"  [KILLED] {agent_id} terminated at step {i+1}")
                    break
            else:
                print(f"  [{agent_id}] Step {i+1} API error: {result.status_code}")

            # Small delay between steps
            time.sleep(random.uniform(0.5, 1.5))

        except Exception as e:
            print(f"  [{agent_id}] Step {i+1} error: {e}")

            # Track the error step too
            try:
                error_data = {
                    "agent_id": agent_id,
                    "input": prompt,
                    "output": f"Error: {str(e)[:500]}",
                    "tokens": 0,
                    "cost": 0,
                    "error_message": str(e)[:500],
                }
                client.post("/api/v1/ingest/step", json=error_data)
            except:
                pass

            time.sleep(1)

    client.close()
    print(f"[AGENT] Finished: {agent_id}")


def main():
    print("=" * 60)
    print("AgentBreaker Live Agent Runner")
    print(f"Launching {len(AGENT_TASKS)} real AI agents with Google Gemini")
    print("=" * 60)

    # Run agents in parallel threads
    threads = []
    for task in AGENT_TASKS:
        t = threading.Thread(target=run_agent, args=(task,))
        threads.append(t)
        t.start()
        time.sleep(0.3)  # Stagger launches

    for t in threads:
        t.join()

    print("\n" + "=" * 60)
    print("All agents completed. Check the dashboard for live data.")
    print("=" * 60)


if __name__ == "__main__":
    main()
