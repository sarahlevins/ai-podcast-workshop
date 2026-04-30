from typing import Annotated

from pydantic import Field

def web_search(                                                                                     
    query: Annotated[str, Field(description="Search query")],
) -> str:                                                                                           
    from duckduckgo_search import DDGS                                                              
                                                                                                    
    try:                                                                                            
        results = DDGS().text(query, max_results=5)
        return "\n\n".join(                                                                         
            f"**{r['title']}**\n{r['href']}\n{r['body']}"
            for r in results                                                                        
        )                                                                                           
    except Exception as e:                                                                          
        return f"Error fetching web content: {str(e)}" 