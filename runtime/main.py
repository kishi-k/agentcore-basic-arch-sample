import os
import requests
from dotenv import load_dotenv
from bedrock_agentcore.identity.auth import requires_access_token
import logging
from dotenv import load_dotenv
import asyncio
import json

# Import Strands Agents SDK
from strands import Agent
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from pydantic import BaseModel, Field


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


GATEWAY_ENDPOINT = os.getenv("GATEWAY_ENDPOINT", "endpoint")
GATEWAY_SCOPE = os.getenv("GATEWAY_SCOPE", "scope")
IDENTITY_OAUTH_PROVIDER = os.getenv("IDENTITY_OAUTH_PROVIDER", "provider")

logger.info((GATEWAY_ENDPOINT, GATEWAY_SCOPE, IDENTITY_OAUTH_PROVIDER))


class RepoInfo(BaseModel):
    name: str = Field(description="The repogitory name")
    url: str = Field(description="The url of repo")
    stars: int = Field(description="The number of stars")
    summary: str = Field(description="The summary of repo")


app = BedrockAgentCoreApp()


def create_streamable_http_transport(url, token):
    return streamablehttp_client(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )


def fetch_access_token(client_id, client_secret, token_url):
    response = requests.post(
        token_url,
        data=f"grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return response.json()["access_token"]


ACCESS_TOKEN = ""


@requires_access_token(
    provider_name=IDENTITY_OAUTH_PROVIDER,
    scopes=[GATEWAY_SCOPE],
    auth_flow="M2M",
    force_authentication=False,
)
async def get_access_token(*, access_token: str):
    global ACCESS_TOKEN
    ACCESS_TOKEN = access_token


def run_agent(prompt: str):
    try:
        # 直接Cognitoからアクセストークンを取得
        # access_token = fetch_access_token(CLIENT_ID, CLIENT_SECRET, TOKEN_URL)
        asyncio.run(get_access_token(access_token=""))

        logger.info(f"Access token obtained: {ACCESS_TOKEN[:20]}...")

        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

        mcp_client = MCPClient(
            lambda: streamablehttp_client(
                url=f"{GATEWAY_ENDPOINT}/mcp", headers=headers
            )
        )

        with mcp_client:
            tools = mcp_client.list_tools_sync()
            logger.info(f"Tools retrieved: {len(tools)} tools available")

            agent = Agent(
                model="anthropic.claude-3-5-haiku-20241022-v1:0",
                tools=tools,
                system_prompt="""
                You are an AI assistant for searching GitHub repo and Issues. Help the user with their query.
                You have access to tools that can retrieve GitHub Platform data.
                """,
            )
            logger.info("Agent created successfully")

            agent(prompt)
            result = agent.structured_output(
                RepoInfo, "Extract structured information about Repo"
            )

            return result
    except Exception as e:
        logger.error(f"Error in run_agent: {e}")
        raise


@app.entrypoint
def invoke(payload):
    """
    Process requests from AgentCore Runtime with streaming support
    This is the entry point for the AgentCore Runtime
    """

    try:
        # Extract the user message from the payload
        user_message = payload.get(
            "prompt", "No prompt found in input, please provide a message"
        )
        logger.info(f"Received user message: {user_message}")

        result = run_agent(user_message)

        # result = agent(user_message) d
        if not result:
            raise Exception("no response")

        return result.model_dump_json()

    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"error": error_msg}


if __name__ == "__main__":
    app.run()
