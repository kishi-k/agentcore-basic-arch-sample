"""
外部API活用 Lambda MCP サーバー
AWS Bedrock AgentCore Gateway用
JSONPlaceholder + GitHub API を使用したITサポート機能
"""

import json
import urllib.request
import urllib.parse
import logging
from typing import Dict, List, Any, Optional

# ログ設定
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AgentCore Gateway 用 Lambda MCP サーバー
    外部API（JSONPlaceholder + GitHub API）を使用したITサポート機能
    """

    try:
        if context and context.client_context:
            logger.info(f"Context: {context.client_context}")
            tool_name = context.client_context.custom.get(
                "bedrockAgentCoreToolName", ""
            )

            # Remove any prefix added by Gateway (format: targetName___toolName)
            if "___" in tool_name:
                tool_name = tool_name.split("___")[-1]
        elif "tool_name" in event:
            tool_name = event.get("tool_name", "")
        else:
            # 未対応形式
            logger.info(f"Not supported request")

            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "error": "サポートされていないリクエスト形式です",
                        "supported_formats": [
                            'Direct: {"tool_name": "search_users", "parameters": {...}}',
                            'MCP: {"method": "tools/call", "params": {"name": "search_users", "arguments": {...}}}',
                        ],
                    },
                    ensure_ascii=False,
                ),
            }

        logger.info(f"Processing tool: {tool_name}")

        if tool_name == "search_github_repos":
            response = search_github_repos(event)
        else:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "error": f"未知のツール: {tool_name}",
                        "available_tools": [
                            "search_users",
                            "search_github_repos",
                            "get_user_posts",
                            "search_github_issues",
                        ],
                    },
                    ensure_ascii=False,
                ),
            }

        logger.info(f"実行結果: {json.dumps(response, ensure_ascii=False)}")

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json; charset=utf-8"},
            "body": json.dumps(response, ensure_ascii=False),
        }

    except Exception as e:
        logger.info(f"エラー: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": f"内部エラーが発生しました: {str(e)}"}, ensure_ascii=False
            ),
        }


def search_github_repos(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """GitHub APIでリポジトリを検索"""

    query = parameters.get("query", "")
    language = parameters.get("language", "")
    limit = parameters.get("limit", 5)

    if not query:
        return {
            "tool_name": "search_github_repos",
            "error": "クエリパラメータが必要です",
            "example": '{"query": "react", "language": "javascript", "limit": 5}',
        }

    try:
        logger.info(f"リポジトリ検索: {query}, 言語: {language}")

        # GitHub Search API を使用
        search_query = query
        if language:
            search_query += f" language:{language}"

        url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(search_query)}&sort=stars&order=desc&per_page={limit}"

        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("User-Agent", "IT-Support-Agent/1.0")

        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())

        repos = []
        for repo in data.get("items", []):
            repos.append(
                {
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo.get("description", ""),
                    "language": repo.get("language", ""),
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "issues": repo.get("open_issues_count", 0),
                    "url": repo["html_url"],
                    "clone_url": repo["clone_url"],
                    "created_at": repo["created_at"],
                    "updated_at": repo["updated_at"],
                }
            )

        return {
            "tool_name": "search_github_repos",
            "query": query,
            "language_filter": language if language else None,
            "total_results": data.get("total_count", 0),
            "repositories": repos,
        }

    except Exception as e:
        logger.error(f"リポジトリ検索エラー: {str(e)}")
        return {
            "tool_name": "search_github_repos",
            "error": f"リポジトリ検索に失敗しました: {str(e)}",
            "message": "GitHub APIに接続できません",
        }
