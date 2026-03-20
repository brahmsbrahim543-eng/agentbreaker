"""AgentBreaker Native Integrations.

Each module provides drop-in classes that wrap the AgentBreaker analysis API
in the idiom of a specific cloud AI platform.  They are designed to be
importable and usable without running the full AgentBreaker backend -- the
only runtime dependency is ``httpx``.

Supported platforms
-------------------
- **Azure AI Foundry** -- ``azure.AzureAgentBreakerMiddleware``
- **Google Vertex AI** -- ``gcp.VertexAgentBreakerCallback``
- **Salesforce Agentforce** -- ``salesforce.AgentforceMonitor``
- **OpenAI Agents SDK** -- ``openai.OpenAIAgentGuard``
- **LangChain / LangGraph** -- ``langchain.LangChainAgentMonitor``
"""

from app.integrations.azure import (
    AzureAgentBreakerMiddleware,
    AutoGenMonitor,
    SemanticKernelPlugin,
)
from app.integrations.gcp import (
    ADKIntegration,
    GeminiAgentMonitor,
    VertexAgentBreakerCallback,
)
from app.integrations.salesforce import (
    AgentforceMonitor,
    EinsteinTrustLayerPlugin,
    FlowOrchestrationGuard,
)
from app.integrations.openai import OpenAIAgentGuard
from app.integrations.langchain import LangChainAgentMonitor, LangGraphIntegration

AVAILABLE_INTEGRATIONS: dict[str, dict] = {
    "azure": {
        "name": "Azure AI Foundry",
        "description": "Middleware for Azure AI Agent Service, Semantic Kernel, and AutoGen.",
        "classes": ["AzureAgentBreakerMiddleware", "SemanticKernelPlugin", "AutoGenMonitor"],
    },
    "gcp": {
        "name": "Google Vertex AI",
        "description": "Callbacks for Vertex AI Agent Builder, Gemini agents, and Google ADK.",
        "classes": ["VertexAgentBreakerCallback", "GeminiAgentMonitor", "ADKIntegration"],
    },
    "salesforce": {
        "name": "Salesforce Einstein / Agentforce",
        "description": "Monitors for Agentforce agents, Einstein Trust Layer, and Flow orchestration.",
        "classes": ["AgentforceMonitor", "EinsteinTrustLayerPlugin", "FlowOrchestrationGuard"],
    },
    "openai": {
        "name": "OpenAI Agents SDK",
        "description": "Guard for OpenAI Agents SDK (formerly Swarm) agent execution.",
        "classes": ["OpenAIAgentGuard"],
    },
    "langchain": {
        "name": "LangChain / LangGraph",
        "description": "Server-side monitoring for LangChain agents, chains, and LangGraph workflows.",
        "classes": ["LangChainAgentMonitor", "LangGraphIntegration"],
    },
}

__all__ = [
    "AVAILABLE_INTEGRATIONS",
    # Azure
    "AzureAgentBreakerMiddleware",
    "SemanticKernelPlugin",
    "AutoGenMonitor",
    # GCP
    "VertexAgentBreakerCallback",
    "GeminiAgentMonitor",
    "ADKIntegration",
    # Salesforce
    "AgentforceMonitor",
    "EinsteinTrustLayerPlugin",
    "FlowOrchestrationGuard",
    # OpenAI
    "OpenAIAgentGuard",
    # LangChain
    "LangChainAgentMonitor",
    "LangGraphIntegration",
]
