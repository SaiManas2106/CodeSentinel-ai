"""Prompt templates for CodeSentinel agents."""

from __future__ import annotations


def review_prompt(pr_diff: str, repo_context: str, pr_metadata: dict[str, str]) -> str:
    """Build review agent prompt."""
    return f"""
You are an expert code reviewer focused on correctness and maintainability.
Analyze the pull request diff and surrounding repository context.
Perform your hidden internal reasoning and output only JSON.

PR metadata:
{pr_metadata}

Repository context:
{repo_context}

PR diff:
{pr_diff}

Return JSON with:
- issues: array of objects {{category,severity,title,description,file_path,line}}
- suggestions: array of objects {{title,rationale,suggested_patch}}
- summary: concise paragraph
""".strip()


def security_prompt(pr_diff: str, repo_context: str) -> str:
    """Build security agent prompt with OWASP focus."""
    return f"""
You are a senior application security researcher.
Assess this PR for OWASP Top 10 issues, hardcoded credentials, SQL injection, XSS,
insecure dependencies, and known CVE patterns.
Use hidden reasoning and output only JSON.

Repository context:
{repo_context}

PR diff:
{pr_diff}

Return JSON:
- issues: array of security issues
- score: number 0-100
- summary: concise security summary
""".strip()


def standards_prompt(pr_diff: str, repo_context: str) -> str:
    """Build standards agent prompt."""
    return f"""
You are a principal engineer enforcing coding standards and clean architecture.
Check naming, complexity, docs quality, testability, SOLID principles.
Use hidden reasoning and return only JSON.

Repository context:
{repo_context}

PR diff:
{pr_diff}

Return JSON:
- issues: array
- suggestions: array
- score: number 0-100
- summary: concise standards summary
""".strip()


def aggregator_prompt(review_output: dict, security_output: dict, standards_output: dict) -> str:
    """Build aggregation prompt."""
    return f"""
You are the final review aggregator.
Combine outputs into a single strict JSON response.

Review output:
{review_output}

Security output:
{security_output}

Standards output:
{standards_output}

Output format:
{{
  "overall_score": float,
  "security_score": float,
  "standards_score": float,
  "quality_score": float,
  "summary": str,
  "issues": list,
  "suggestions": list,
  "model_used": str,
  "tokens_used": int
}}
""".strip()
