"""
Basic usage of Volcengine Ark (Doubao) model.

Requirements:
    pip install agno[volcengine]

Set ARK_API_KEY environment variable:
    export ARK_API_KEY="your-api-key"
"""

from agno.agent import Agent
from agno.models.volcengine import Ark

agent = Agent(
    model=Ark(id="doubao-pro-32k"),
    markdown=True,
)

agent.print_response("Share a 2 sentence horror story")
