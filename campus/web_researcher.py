# ============================================================
# campus/web_researcher.py — Tavily Web Search Tool
# ============================================================
# Used for subject/academic questions and general campus queries
# that aren't workflow-specific (lab booking, leave, etc.).
# Falls back gracefully if Tavily key is absent.
# Supports role-aware response generation.
# ============================================================

import json
from campus import role_system

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False


def search(query: str, tavily_api_key: str, max_results: int = 5) -> dict:
    """
    Search the web using Tavily for a given query.

    Returns:
        {
          "success": bool,
          "query": str,
          "results": [{"title", "url", "content", "score"}],
          "answer": str  (Tavily's auto-synthesized answer, if available),
          "note": str    (fallback message if Tavily unavailable)
        }
    """
    if not TAVILY_AVAILABLE:
        return {
            "success": False,
            "query": query,
            "results": [],
            "answer": "",
            "note": "tavily-python not installed. Run: pip install tavily-python",
        }

    if not tavily_api_key or not tavily_api_key.strip() or "your_tavily" in tavily_api_key:
        return {
            "success": False,
            "query": query,
            "results": [],
            "answer": "",
            "note": "Tavily API key not configured. Please fill it in the Config part in the sidebar.",
        }

    try:
        client = TavilyClient(tavily_api_key.strip())
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=True,
        )

        results = []
        for r in response.get("results", []):
            results.append({
                "title":   r.get("title", ""),
                "url":     r.get("url", ""),
                "content": r.get("content", "")[:500],  # trim to 500 chars
                "score":   round(r.get("score", 0), 3),
            })

        return {
            "success":  True,
            "query":    query,
            "results":  results,
            "answer":   response.get("answer", ""),
            "note":     "",
        }

    except Exception as e:
        return {
            "success": False,
            "query":   query,
            "results": [],
            "answer":  "",
            "note":    f"Tavily search error: {str(e)}",
        }


def synthesize_answer(query: str, search_data: dict,
                       client, model: str, role: str = "student") -> str:
    """
    Use the LLM to synthesize a clean answer from Tavily results.
    Returns a role-aware, well-structured response.
    
    Args:
        query: The user's search query
        search_data: The search results from Tavily
        client: Groq client instance
        model: The LLM model to use
        role: The current user role (affects response tone and detail level)
    
    Returns:
        A synthesized answer string
    """
    if not search_data.get("success") or not search_data.get("results"):
        note = search_data.get("note", "No results found.")
        return (
            f"I searched the web for **{query}** but couldn't retrieve results.\n\n"
            f"Reason: {note}\n\n"
            "Please try rephrasing your question or check your Tavily API key in the Config part in the sidebar."
        )

    # Build context from search results
    context_parts = []

    # Tavily's own synthesized answer (often high quality)
    if search_data.get("answer"):
        context_parts.append(f"Web Summary: {search_data['answer']}")

    # Top search results
    for i, r in enumerate(search_data["results"][:4], 1):
        context_parts.append(
            f"Source {i} ({r['title']}):\n{r['content']}"
        )

    context = "\n\n".join(context_parts)

    # Get role-aware system prompt
    role_prompt = role_system.get_role_system_prompt(role, {"workflow_type": "web_search"})
    
    # Add role-specific instructions for web search responses
    if role == "student":
        response_guidance = (
            "Give a clear, accurate, and student-friendly answer. "
            "Structure the answer with headings or bullet points where helpful. "
            "Explain any technical terms used. "
            "Cite sources briefly at the end (title + URL). "
            "Keep the answer focused and under 400 words."
        )
    elif role == "teacher":
        response_guidance = (
            "Give a clear, accurate, and professional answer suitable for instructional use. "
            "Structure the answer with clear sections. "
            "Include relevant technical details. "
            "Cite sources (title + URL). "
            "Keep the answer focused and under 500 words. "
            "Note any important caveats or limitations in the research."
        )
    else:  # admin
        response_guidance = (
            "Give a concise, authoritative answer with focus on actionable insights. "
            "Structure the answer for quick comprehension. "
            "Include relevant metrics or data points from sources. "
            "Cite sources (title + URL). "
            "Keep the answer focused and under 400 words. "
            "Highlight any potential operational implications."
        )
    
    system_prompt = f"""{role_prompt}

You searched the web for information. Using the web search results below, {response_guidance}"""

    user_message = (
        f"Query: {query}\n\n"
        f"Web search results:\n{context}\n\n"
        "Please provide a clear, helpful answer."
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        answer = response.choices[0].message.content.strip()

        # Append source links
        sources = "\n\n**Sources:**\n" + "\n".join(
            f"- [{r['title']}]({r['url']})"
            for r in search_data["results"][:3]
            if r.get("url")
        )
        return answer + sources

    except Exception as e:
        # Fallback: return raw Tavily answer
        raw = search_data.get("answer", "No answer synthesized.")
        return f"{raw}\n\n*(LLM synthesis failed: {e})*"
