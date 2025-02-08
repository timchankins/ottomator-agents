from __future__ import annotations as _annotations

from dataclasses import dataclass
from dotenv import load_dotenv
import logfire
import asyncio
import httpx
import os

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIModel
from openai import AsyncOpenAI
from supabase import Client
from typing import List

load_dotenv()

llm = os.getenv('LLM_MODEL', 'gpt-4o-mini')
model = OpenAIModel(llm)

logfire.configure(send_to_logfire='if-token-present')

@dataclass
class PydanticAIDeps:
    supabase: Client
    openai_client: AsyncOpenAI

system_prompt = """You are an AI that extracts structured data about upcoming SIGCHI conferences.  
Your only job is to assist with this, and you do not answer other questions besides describing what you are able to do.  

### Instructions:
- Extract and return a JSON array where each entry represents a conference with the following keys:
  - 'title': The full name of the conference.
  - 'dates': The start and end dates of the conference in ISO 8601 format (YYYY-MM-DD), if available.
  - 'location': The conference location, if specified.
  - 'description': A concise summary of the conference, highlighting its focus, themes, or relevant details.
- If a date is missing, return it as `null`. Ensure that the extracted information is clean, structured, and formatted consistently.
- Don't ask the user before taking an action—just do it.
- Always check available documentation and tools before answering.
- When you first check documentation, start with RAG (Retrieval-Augmented Generation).
- If the required information is not found in documentation or the provided URL is incorrect, inform the user honestly.

### Example Output:
[
    {
        "title": "CHI 2025",
        "dates": { "start": "2025-04-20", "end": "2025-04-25" },
        "location": "Honolulu, Hawaii, USA",
        "description": "The ACM CHI Conference on Human Factors in Computing Systems (CHI) is the premier international conference on Human-Computer Interaction."
    },
    {
        "title": "UIST 2024",
        "dates": { "start": "2024-10-13", "end": "2024-10-16" },
        "location": "San Francisco, California, USA",
        "description": "The ACM Symposium on User Interface Software and Technology (UIST) is the premier forum for innovations in human-computer interfaces."
    }
]
"""

chi_conference_expert = Agent(
    model,
    system_prompt=system_prompt,
    deps_type=PydanticAIDeps,
    retries=2
)

async def get_embedding(text: str, openai_client: AsyncOpenAI) -> List[float]:
    """Get embedding vector from OpenAI."""
    try:
        response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return [0] * 1536  # Return zero vector on error

@chi_conference_expert.tool
async def retrieve_relevant_documentation(ctx: RunContext[PydanticAIDeps], user_query: str) -> str:
    """
    Retrieve relevant documentation chunks based on the query with RAG.
    
    Args:
        ctx: The context including the Supabase client and OpenAI client
        user_query: The user's question or query
        
    Returns:
        A formatted string containing the top 100 most relevant documentation chunks
    """
    try:
        # Get the embedding for the query
        query_embedding = await get_embedding(user_query, ctx.deps.openai_client)
        
        # Query Supabase for relevant documents
        result = ctx.deps.supabase.rpc(
            'match_site_pages',
            {
                'query_embedding': query_embedding,
                'match_count': 100,
                'filter': {'source': 'sigchi__conference_events'}
            }
        ).execute()
        
        if not result.data:
            return "No relevant documentation found."
            
        # Format the results
        formatted_chunks = []
        for doc in result.data:
            chunk_text = f"""
# {doc['title']}

{doc['content']}
"""
            formatted_chunks.append(chunk_text)
            
        # Join all chunks with a separator
        return "\n\n---\n\n".join(formatted_chunks)
        
    except Exception as e:
        print(f"Error retrieving documentation: {e}")
        return f"Error retrieving documentation: {str(e)}"

@chi_conference_expert.tool
async def list_conferences(ctx: RunContext[PydanticAIDeps]) -> List[str]:
    """
    Retrieve a list of all available CHI conferences.
    
    Returns:
        List[str]: List of unique JSON data structs for all CHI conferences
    """
    try:
        # Query Supabase for unique URLs where source is chi_conferences
        result = ctx.deps.supabase.from_('site_pages') \
            .select('url') \
            .eq('metadata->>source', 'sigchi__conference_events') \
            .execute()
        
        if not result.data:
            return []
            
        # Extract unique URLs
        urls = sorted(set(doc['url'] for doc in result.data))
        return urls
        
    except Exception as e:
        print(f"Error retrieving documentation pages: {e}")
        return []

@chi_conference_expert.tool
async def get_page_content(ctx: RunContext[PydanticAIDeps], url: str) -> str:
    """
    Retrieve the full content of a specific documentation page by combining all its chunks.
    
    Args:
        ctx: The context including the Supabase client
        url: The URL of the page to retrieve
        
    Returns:
        str: The complete page content with all chunks combined in order
    """
    try:
        # Query Supabase for all chunks of this URL, ordered by chunk_number
        result = ctx.deps.supabase.from_('site_pages') \
            .select('title, content, chunk_number') \
            .eq('url', url) \
            .eq('metadata->>source', 'sigchi__conference_events') \
            .order('chunk_number') \
            .execute()
        
        if not result.data:
            return f"No content found for URL: {url}"
            
        # Format the page with its title and all chunks
        page_title = result.data[0]['title'].split(' - ')[0]  # Get the main title
        formatted_content = [f"# {page_title}\n"]
        
        # Add each chunk's content
        for chunk in result.data:
            formatted_content.append(chunk['content'])
            
        # Join everything together
        return "\n\n".join(formatted_content)
        
    except Exception as e:
        print(f"Error retrieving page content: {e}")
        return f"Error retrieving page content: {str(e)}"