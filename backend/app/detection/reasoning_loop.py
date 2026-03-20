"""Reasoning Loop Detector -- analyzes the logical structure of agent reasoning.

Unlike the Similarity Detector which compares surface-level text embeddings,
this detector analyzes the ARGUMENT STRUCTURE of agent outputs:

1. **Claim Extraction**: Identifies assertive statements -- sentences that make
   claims, propose actions, or draw conclusions. Uses syntactic heuristics
   (presence of action verbs, causal connectors, quantitative assertions)
   rather than simple keyword matching.

2. **Reasoning Graph Construction**: Builds a directed graph where nodes are
   normalized claims and edges represent evidential support relationships.
   When output B references concepts from output A's conclusions, an edge
   A -> B is created. When B's conclusions echo A's premises, a reverse
   edge B -> A is added, forming a potential cycle.

3. **Cycle Detection via DFS**: Runs Tarjan-style depth-first search to find
   strongly connected components (SCCs) in the reasoning graph. An SCC of
   size > 1 indicates circular reasoning: the agent's conclusions are
   supporting each other without external grounding.

4. **Reasoning Depth Analysis**: Measures how many *layers* of new reasoning
   each step introduces. Layer 0 = restating the problem. Layer 1 = direct
   inference. Layer 2+ = inference built on prior inferences. A declining
   depth signals the agent is "spinning its wheels" -- producing reasoning
   that doesn't go deeper than what it already established.

5. **Meta-reasoning Detection**: Identifies when the agent is "reasoning about
   reasoning" (e.g., "Let me reconsider my approach", "I should think about
   this differently") without producing new substantive claims. A high ratio
   of meta-reasoning to substantive claims is a strong loop indicator.

Scoring components:
- cycle_detected: 40 points (circular reasoning is a strong signal)
- reasoning_depth_decline: up to 30 points (scaled by severity)
- conclusion_repetition: up to 20 points (repeated final claims)
- meta_reasoning_ratio: up to 10 points (excessive self-reflection)

This is the core IP of the detection engine. It requires understanding of
argument mining, discourse analysis, and graph theory -- not just cosine
similarity on embeddings.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .base import BaseDetector, DetectionResult


# ---------------------------------------------------------------------------
# Linguistic patterns for claim / meta-reasoning extraction
# ---------------------------------------------------------------------------

# Causal and assertive connectors that signal a *claim*
_CLAIM_MARKERS = re.compile(
    r"\b(?:therefore|thus|hence|consequently|so\s+that|because|since|"
    r"implies|means\s+that|leads\s+to|results?\s+in|conclude|"
    r"should|must|need\s+to|will|would|can|is\s+(?:a|the|an)|"
    r"are\s+(?:the|a|an)|proves?|shows?|demonstrates?|indicates?|"
    r"suggests?|confirms?|reveals?|establishes?|determines?)\b",
    re.IGNORECASE,
)

# Quantitative assertion patterns (numbers, percentages, comparisons)
_QUANT_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?(?:\s*%|\s+percent)?\b|"
    r"\b(?:more|less|greater|fewer|higher|lower|increase|decrease|"
    r"maximum|minimum|optimal|average|total)\b",
    re.IGNORECASE,
)

# Meta-reasoning patterns -- the agent talking about its own process
_META_PATTERNS = re.compile(
    r"\b(?:let\s+me\s+(?:re)?(?:think|consider|reconsider|analyze|examine|revisit)|"
    r"I\s+(?:should|need\s+to|will)\s+(?:re)?(?:think|consider|reconsider|evaluate)|"
    r"on\s+(?:second|further)\s+thought|"
    r"(?:re)?(?:evaluating|assessing|reconsidering)\s+(?:my|the)\s+(?:approach|strategy|method)|"
    r"step(?:ping)?\s+back|"
    r"looking\s+at\s+this\s+(?:from|differently|again)|"
    r"perhaps\s+(?:I|we)\s+should|"
    r"alternative(?:ly)?|instead|"
    r"another\s+(?:approach|way|method|strategy)|"
    r"wait,?\s+(?:let|I)|"
    r"actually,?\s+(?:let|I|maybe)|"
    r"hmm|"
    r"thinking\s+about\s+(?:it|this)\s+(?:more|again|differently))\b",
    re.IGNORECASE,
)

# Sentence boundary splitter -- handles abbreviations, decimals, ellipses
_SENT_SPLIT = re.compile(
    r"(?<=[.!?])\s+(?=[A-Z])|"  # Standard sentence boundary
    r"(?<=\n)\s*(?=\S)|"  # Newline-separated
    r"(?<=\.\.\.)\s+(?=[A-Z])"  # Ellipsis boundary
)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex heuristics.

    Handles common abbreviations (Mr., Dr., e.g., i.e.) and decimal numbers
    to avoid false splits. Returns non-empty trimmed sentences.
    """
    # Protect common abbreviations from splitting
    protected = text
    for abbr in ("Mr.", "Mrs.", "Dr.", "Prof.", "Jr.", "Sr.", "e.g.", "i.e.", "vs.", "etc."):
        protected = protected.replace(abbr, abbr.replace(".", "\x00"))

    parts = _SENT_SPLIT.split(protected)
    sentences = []
    for part in parts:
        restored = part.replace("\x00", ".").strip()
        if len(restored) > 10:  # Skip trivially short fragments
            sentences.append(restored)
    return sentences


def _extract_claims(text: str) -> list[str]:
    """Extract assertive claims from text.

    A claim is a sentence that:
    1. Contains a causal/assertive connector, OR
    2. Contains a quantitative assertion, OR
    3. Contains an action verb in declarative form

    Returns normalized lowercase claim strings for comparison.
    """
    sentences = _split_sentences(text)
    claims = []
    for sent in sentences:
        is_claim = bool(_CLAIM_MARKERS.search(sent)) or bool(_QUANT_PATTERN.search(sent))
        if is_claim:
            # Normalize: lowercase, collapse whitespace, strip punctuation edges
            normalized = re.sub(r"\s+", " ", sent.lower().strip())
            normalized = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", normalized)
            if normalized:
                claims.append(normalized)
    return claims


def _extract_claim_tokens(claim: str) -> set[str]:
    """Extract meaningful content tokens from a claim.

    Removes stop words and short tokens to get the semantic core of the claim.
    This is used for building the reasoning graph edges.
    """
    _STOP_WORDS = frozenset({
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "and", "but", "or",
        "nor", "not", "no", "so", "if", "then", "than", "that", "this",
        "these", "those", "it", "its", "i", "me", "my", "we", "our", "you",
        "your", "he", "she", "they", "them", "their", "let", "need",
    })
    tokens = set(re.findall(r"[a-z][a-z0-9]+", claim))
    return tokens - _STOP_WORDS


def _count_meta_reasoning(text: str) -> tuple[int, int]:
    """Count meta-reasoning sentences vs. total sentences.

    Returns (meta_count, total_count).
    """
    sentences = _split_sentences(text)
    total = len(sentences)
    meta = sum(1 for s in sentences if _META_PATTERNS.search(s))
    return meta, total


# ---------------------------------------------------------------------------
# Reasoning graph with cycle detection
# ---------------------------------------------------------------------------

class _ReasoningGraph:
    """Directed graph of claim relationships with cycle detection.

    Nodes are claim indices (int). Edges represent evidential support:
    edge (i, j) means claim i's content appears to support claim j's
    conclusions or vice versa.

    Cycle detection uses iterative DFS to find strongly connected
    components (Tarjan's algorithm variant). An SCC of size > 1
    indicates circular reasoning.
    """

    def __init__(self) -> None:
        self.adj: dict[int, list[int]] = defaultdict(list)
        self.nodes: set[int] = set()

    def add_node(self, node_id: int) -> None:
        self.nodes.add(node_id)

    def add_edge(self, src: int, dst: int) -> None:
        self.adj[src].append(dst)
        self.nodes.add(src)
        self.nodes.add(dst)

    def find_cycles(self) -> list[list[int]]:
        """Find all strongly connected components of size > 1 using
        iterative Tarjan's algorithm.

        Returns a list of cycles, where each cycle is a list of node IDs.
        An empty list means no circular reasoning was detected.
        """
        index_counter = [0]
        stack: list[int] = []
        on_stack: set[int] = set()
        index_map: dict[int, int] = {}
        lowlink: dict[int, int] = {}
        sccs: list[list[int]] = []

        def _strongconnect(v: int) -> None:
            # Iterative DFS using an explicit call stack to avoid recursion
            # limits on large graphs
            call_stack: list[tuple[int, int]] = [(v, 0)]
            index_map[v] = index_counter[0]
            lowlink[v] = index_counter[0]
            index_counter[0] += 1
            stack.append(v)
            on_stack.add(v)

            while call_stack:
                node, neighbor_idx = call_stack[-1]
                neighbors = self.adj.get(node, [])

                if neighbor_idx < len(neighbors):
                    call_stack[-1] = (node, neighbor_idx + 1)
                    w = neighbors[neighbor_idx]
                    if w not in index_map:
                        index_map[w] = index_counter[0]
                        lowlink[w] = index_counter[0]
                        index_counter[0] += 1
                        stack.append(w)
                        on_stack.add(w)
                        call_stack.append((w, 0))
                    elif w in on_stack:
                        lowlink[node] = min(lowlink[node], index_map[w])
                else:
                    # All neighbors processed -- check if this is an SCC root
                    if lowlink[node] == index_map[node]:
                        scc: list[int] = []
                        while True:
                            w = stack.pop()
                            on_stack.discard(w)
                            scc.append(w)
                            if w == node:
                                break
                        if len(scc) > 1:
                            sccs.append(scc)

                    call_stack.pop()
                    if call_stack:
                        parent = call_stack[-1][0]
                        lowlink[parent] = min(lowlink[parent], lowlink[node])

        for n in self.nodes:
            if n not in index_map:
                _strongconnect(n)

        return sccs


# ---------------------------------------------------------------------------
# Main detector
# ---------------------------------------------------------------------------

class ReasoningLoopDetector(BaseDetector):
    """Detects circular reasoning and stagnant argument structure.

    Analyzes the logical flow of agent outputs by extracting claims,
    building a reasoning graph, detecting cycles, and measuring
    reasoning depth over time.
    """

    name = "reasoning_loop"
    default_weight = 0.15

    async def analyze(
        self, steps: list[dict[str, Any]], thresholds: dict | None = None
    ) -> DetectionResult:
        thresholds = thresholds or {}
        window = thresholds.get("reasoning_loop_window", 6)

        recent_steps = steps[-window:]
        outputs: list[str] = []
        for step in recent_steps:
            text = (step.get("output_text") or "").strip()
            if text:
                outputs.append(text)

        if len(outputs) < 2:
            return DetectionResult(
                score=0.0,
                detail="Not enough outputs to analyze reasoning structure",
            )

        # ----- Phase 1: Extract claims from each output -----
        step_claims: list[list[str]] = []
        step_claim_tokens: list[list[set[str]]] = []
        for output in outputs:
            claims = _extract_claims(output)
            step_claims.append(claims)
            step_claim_tokens.append([_extract_claim_tokens(c) for c in claims])

        # ----- Phase 2: Build reasoning graph -----
        graph = _ReasoningGraph()
        global_claim_id = 0
        claim_id_map: list[list[int]] = []  # step_idx -> list of global claim IDs

        for step_idx, claims in enumerate(step_claims):
            ids = []
            for _ in claims:
                graph.add_node(global_claim_id)
                ids.append(global_claim_id)
                global_claim_id += 1
            claim_id_map.append(ids)

        # Build edges based on token overlap between claims across steps
        # Edge from claim A (step i) to claim B (step j, j > i) if B's tokens
        # substantially overlap with A's tokens (B references A's concepts).
        # Also add reverse edge if A's tokens overlap with B's (circular support).
        _OVERLAP_THRESHOLD = 0.45

        all_flat_tokens: list[set[str]] = []
        all_flat_ids: list[int] = []
        all_flat_step_idx: list[int] = []

        for step_idx, (ids, token_sets) in enumerate(
            zip(claim_id_map, step_claim_tokens)
        ):
            for cid, toks in zip(ids, token_sets):
                all_flat_tokens.append(toks)
                all_flat_ids.append(cid)
                all_flat_step_idx.append(step_idx)

        for i in range(len(all_flat_ids)):
            for j in range(i + 1, len(all_flat_ids)):
                if all_flat_step_idx[i] == all_flat_step_idx[j]:
                    continue  # Skip same-step comparisons

                tokens_i = all_flat_tokens[i]
                tokens_j = all_flat_tokens[j]
                if not tokens_i or not tokens_j:
                    continue

                overlap = tokens_i & tokens_j
                # Forward reference: j references i's concepts
                fwd_ratio = len(overlap) / len(tokens_j) if tokens_j else 0
                # Backward reference: i references j's concepts
                bwd_ratio = len(overlap) / len(tokens_i) if tokens_i else 0

                if fwd_ratio >= _OVERLAP_THRESHOLD:
                    graph.add_edge(all_flat_ids[i], all_flat_ids[j])
                if bwd_ratio >= _OVERLAP_THRESHOLD:
                    graph.add_edge(all_flat_ids[j], all_flat_ids[i])

        # ----- Phase 3: Detect cycles -----
        cycles = graph.find_cycles()
        cycle_detected = len(cycles) > 0
        largest_cycle_size = max((len(c) for c in cycles), default=0)

        # ----- Phase 4: Reasoning depth analysis -----
        # Depth = number of unique new claim-tokens introduced per step,
        # normalized by the cumulative vocabulary. A declining curve means
        # the agent is not going deeper.
        cumulative_tokens: set[str] = set()
        depth_scores: list[float] = []

        for token_sets in step_claim_tokens:
            step_all_tokens: set[str] = set()
            for ts in token_sets:
                step_all_tokens |= ts

            new_tokens = step_all_tokens - cumulative_tokens
            denominator = max(len(step_all_tokens), 1)
            depth = len(new_tokens) / denominator
            depth_scores.append(depth)
            cumulative_tokens |= step_all_tokens

        # Compute depth decline: negative slope of depth_scores
        depth_decline = 0.0
        if len(depth_scores) >= 2:
            # Simple linear regression slope
            n = len(depth_scores)
            x_mean = (n - 1) / 2.0
            y_mean = sum(depth_scores) / n
            numerator = sum(
                (i - x_mean) * (depth_scores[i] - y_mean) for i in range(n)
            )
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            slope = numerator / denominator if denominator != 0 else 0.0
            # Negative slope = declining depth
            depth_decline = max(0.0, -slope)

        # ----- Phase 5: Conclusion repetition -----
        # Check if the LAST claim of each step repeats across steps
        final_claims: list[str] = []
        for claims in step_claims:
            if claims:
                final_claims.append(claims[-1])

        conclusion_repetition = 0.0
        if len(final_claims) >= 2:
            # Pairwise Jaccard similarity of final claims' tokens
            final_token_sets = [_extract_claim_tokens(c) for c in final_claims]
            jaccard_scores: list[float] = []
            for i in range(len(final_token_sets)):
                for j in range(i + 1, len(final_token_sets)):
                    ti, tj = final_token_sets[i], final_token_sets[j]
                    if ti or tj:
                        jaccard = len(ti & tj) / len(ti | tj) if (ti | tj) else 0
                        jaccard_scores.append(jaccard)
            conclusion_repetition = (
                sum(jaccard_scores) / len(jaccard_scores) if jaccard_scores else 0.0
            )

        # ----- Phase 6: Meta-reasoning ratio -----
        total_meta = 0
        total_sentences = 0
        for output in outputs:
            meta, total = _count_meta_reasoning(output)
            total_meta += meta
            total_sentences += total

        meta_ratio = total_meta / max(total_sentences, 1)

        # ----- Composite score -----
        score = 0.0
        score += 40.0 if cycle_detected else 0.0
        score += min(depth_decline * 300, 30.0)  # Scale decline to 0-30
        score += conclusion_repetition * 20.0  # 0-20
        score += min(meta_ratio * 40, 10.0)  # 0-10

        score = round(min(score, 100.0), 2)

        # Flag threshold
        flag_threshold = thresholds.get("reasoning_loop", 35)
        flag = "reasoning_loop" if score >= flag_threshold else None

        detail_parts = []
        if cycle_detected:
            detail_parts.append(
                f"{len(cycles)} cycle(s) detected (largest: {largest_cycle_size} claims)"
            )
        if depth_decline > 0.05:
            detail_parts.append(f"reasoning depth declining (slope: -{depth_decline:.3f})")
        if conclusion_repetition > 0.3:
            detail_parts.append(
                f"conclusion repetition {conclusion_repetition:.2f}"
            )
        if meta_ratio > 0.3:
            detail_parts.append(f"meta-reasoning ratio {meta_ratio:.2f}")

        detail = "; ".join(detail_parts) if detail_parts else "No reasoning loop signals"

        return DetectionResult(
            score=score,
            flag=flag,
            detail=detail,
            metadata={
                "cycles_found": len(cycles),
                "largest_cycle_size": largest_cycle_size,
                "cycle_node_ids": [c for c in cycles],
                "depth_scores": depth_scores,
                "depth_decline_slope": depth_decline,
                "conclusion_repetition": conclusion_repetition,
                "meta_reasoning_ratio": meta_ratio,
                "total_claims_extracted": sum(len(c) for c in step_claims),
                "graph_nodes": len(graph.nodes),
                "graph_edges": sum(len(v) for v in graph.adj.values()),
            },
        )
