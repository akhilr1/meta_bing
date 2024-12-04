from typing import Dict, Any, TypeVar
from termcolor import colored
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from .agent_base import ToolCallingAgent, StateT
# from agent_base import ToolCallingAgent, StateT
# StateT = TypeVar('StateT', bound=Dict[str, Any])

class BingSearchAgent(ToolCallingAgent[StateT]):
    """
    # Functionality:
    This agent performs Bing web searches based on a list of queries you provide. It returns a formatted list of organic search results, including the query, title, link, and sitelinks for each result.

    ## Inputs:
    - **queries**: A list of search query strings.
    - **location**: Geographic location code for the search (e.g., 'us', 'gb', 'nl', 'ca'). Defaults to 'us'.

    ## Outputs:
    - A formatted string representing the organic search engine results page (SERP), including:
        - Query
        - Title
        - Link
        - Sitelinks

    ## Important Notes:
    - This tool **only** provides search result summaries; it does **not** access or retrieve content from the linked web pages.
    """

    def __init__(self, name: str, model: str = "gpt-4", server: str = "openai", temperature: float = 0, api_key: str = "", endpoint: str = ""):
        super().__init__(name, model=model, server=server, temperature=temperature)
        self.location = "us"  # Default location for search
        self.api_key = api_key  # Bing API key
        # self.api_key = "1310bd588649492eb45927da4769d447"  # Bing API key
        self.endpoint = endpoint  # Bing endpoint URL
        # self.endpoint = "https://api.bing.microsoft.com/v7.0/search"  # Bing endpoint URL
        print(f"BingSearchAgent '{self.name}' initialized.")
        
    def get_guided_json(self, state: StateT = None) -> Dict[str, Any]:
        """
        Define the guided JSON schema expecting a list of search queries.
        """
        guided_json_schema = {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "description": "A search query string."
                    },
                    "description": "A list of search query strings."
                },
                "location": {
                    "type": "string",
                    "description": (
                        "The geographic location for the search results. "
                        "Available locations: 'us', 'gb', 'nl', 'ca'."
                    )
                }
            },
            "required": ["queries", "location"],
            "additionalProperties": False
        }
        return guided_json_schema


    def bing_search(self, query: str, location: str) -> Dict[str, Any]:
        """
        Perform the Bing search for a given query and location.
        """
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        params = {
            "q": query,
            "mkt": location,
            "count": 10  # Get 10 results
        }
        
        try:
            response = requests.get(self.endpoint, headers=headers, params=params)
            response.raise_for_status()
            results = response.json()
            
            simplified_results = []
            if 'webPages' in results and 'value' in results['webPages']:
                for item in results['webPages']['value']:
                    title = item.get('name', 'No Title')
                    link = item.get('url', '#')
                    sitelinks = []  # Assuming Bing does not provide sitelinks directly
                    
                    simplified_results.append({
                        'query': query,
                        'title': title,
                        'link': link,
                        'sitelinks': sitelinks
                    })
                return {'organic_results': simplified_results}
            else:
                print("No 'webPages' results found.")
                return {'organic_results': []}

        except requests.exceptions.HTTPError as http_err:
            return {'error': f"HTTP error occurred: {http_err}"}
        except requests.exceptions.RequestException as req_err:
            return {'error': f"Request error occurred: {req_err}"}
        except Exception as ex:
            return {'error': str(ex)}

    def format_search_results(self, search_results: Dict[str, Any]) -> str:
        """
        Formats the search results dictionary into a readable string.

        Args:
            search_results (Dict[str, Any]): The dictionary containing search results.

        Returns:
            str: A formatted string with the query, title, link, and sitelinks.
        """
        formatted_strings = []
        organic_results = search_results.get('organic_results', [])

        for result in organic_results:
            query = result.get('query', 'No Query')
            title = result.get('title', 'No Title')
            link = result.get('link', 'No Link')

            # Start formatting the result
            result_string = f"Query: {query}\nTitle: {title}\nLink: {link}"

            # Handle sitelinks if they exist (currently empty for Bing)
            sitelinks = result.get('sitelinks', [])
            if sitelinks:
                sitelinks_strings = []
                for sitelink in sitelinks:
                    sitelink_title = sitelink.get('title', 'No Title')
                    sitelink_link = sitelink.get('link', 'No Link')
                    sitelinks_strings.append(f"    - {sitelink_title}: {sitelink_link}")
                sitelinks_formatted = "\nSitelinks:\n" + "\n".join(sitelinks_strings)
                result_string += sitelinks_formatted
            else:
                result_string += "\nSitelinks: None"

            # Add a separator between results
            formatted_strings.append(result_string + "\n" + "-" * 40)

        # Combine all formatted results into one string
        final_string = "\n".join(formatted_strings)
        return final_string

    def execute_tool(self, tool_response: Dict[str, Any], state: StateT = None) -> Any:
        """
        Execute the search tool using the provided tool response.
        Returns the search results as a concatenated string.
        """
        queries = tool_response.get("queries")
        location = tool_response.get("location", self.location)
        
        if not queries:
            raise ValueError("Search queries are missing from the tool response")
        
        print(f"{self.name} is searching for queries: {queries} in location: {location}")

        # Collect all formatted result strings
        search_results_list = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_query = {executor.submit(self.bing_search, query, location): query for query in queries}
            
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    result = future.result()
                    formatted_result_str = self.format_search_results(result)
                    search_results_list.append(formatted_result_str)
                except Exception as exc:
                    print(f"Exception occurred while searching for query '{query}': {exc}")
                    error_message = f"Error for query '{query}': {exc}"
                    search_results_list.append(error_message)

        # Combine all search results into a single string
        combined_results = "\n".join(search_results_list)
        
        print(colored(f"DEBUG: {self.name} search results: {combined_results} \n\n Type:{type(combined_results)}", "green"))

        return combined_results


if __name__ == "__main__":
    BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"
    BING_API_KEY = "1310bd588649492eb45927da4769d447"

    agent = BingSearchAgent("TestBingAgent", api_key=BING_API_KEY , endpoint=BING_ENDPOINT)

    test_tool_response = {
        "queries": ["Python programming", "Machine learning basics"],
        "location": "us"
    }

    test_state = {}

    try:
        results = agent.execute_tool(test_tool_response, test_state)
        print("Search Results:")
        print(results)
    except Exception as e:
        print(f"An error occurred: {e}")













##################################################################################################################################################


