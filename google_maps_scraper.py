"""
Scrapes Google Maps search results using the SerpApi service based on search queries
provided in a CSV file. It handles pagination to retrieve all results, aggregates
the data, deduplicates it based on 'place_id', and saves the final list of unique
places to an output CSV file.

Key functionalities:
- Reads search queries (keyword and location) from an input CSV file (default: 'search_queries.csv').
- Interacts with the SerpApi Google Maps search endpoint.
- Handles pagination in SerpApi responses to fetch all available results for each query.
- Aggregates results from multiple queries and pages.
- Deduplicates the aggregated results using the 'place_id' to ensure unique entries.
- Saves the consolidated and deduplicated data to 'google_maps_results.csv'.
- Uses comprehensive logging for monitoring and error tracking.

Dependencies:
- pandas: For data manipulation, especially for reading and creating CSV files.
- requests: For making HTTP requests to the SerpApi service.
- python-dotenv (implicitly, for os.getenv): The script expects the SERPAPI_API_KEY
  to be available as an environment variable, often managed with a .env file.

Setup:
- Ensure 'search_queries.csv' exists in the same directory or provide a path.
  It must contain 'keyword' and 'location' columns.
- Set the 'SERPAPI_API_KEY' environment variable with your valid SerpApi API key.
"""
import pandas as pd
import os
import requests
from urllib.parse import urlparse, parse_qs
import time
import logging

# Configure basic logging
# This setup provides a timestamp, log level, and message for each log entry.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def read_search_queries(file_path='search_queries.csv'):
    """
    Reads search queries from a specified CSV file.

    The CSV file must contain 'keyword' and 'location' columns.

    Args:
        file_path (str, optional): The path to the CSV file.
                                   Defaults to 'search_queries.csv'.

    Returns:
        pandas.DataFrame: A DataFrame containing the search queries, with
                          'keyword' and 'location' columns. Returns an empty
                          DataFrame if the file is empty but valid.

    Raises:
        FileNotFoundError: If the specified `file_path` does not exist.
        ValueError: If the CSV file does not contain the required 'keyword' or
                    'location' columns.
        pd.errors.EmptyDataError: If the CSV file is empty (contains no data or only headers).
        Exception: For other unexpected errors during file reading.
    """
    logging.info(f"Attempting to read search queries from: {file_path}")
    try:
        df = pd.read_csv(file_path)
        logging.info(f"Successfully read {len(df)} queries from {file_path}")

        # Validate required columns
        if 'keyword' not in df.columns or 'location' not in df.columns:
            logging.error(f"CSV file '{file_path}' must contain 'keyword' and 'location' columns.")
            raise ValueError(f"CSV file '{file_path}' must contain 'keyword' and 'location' columns.")
        return df
    except FileNotFoundError:
        logging.error(f"The file '{file_path}' was not found.")
        raise  # Re-raise the exception to be handled by the caller
    except pd.errors.EmptyDataError:
        logging.error(f"The file '{file_path}' is empty or contains only headers.")
        raise # Re-raise for specific handling if needed
    except Exception as e:
        logging.error(f"An unexpected error occurred while reading '{file_path}': {e}")
        raise # Re-raise for general error handling

def search_google_maps(api_key, keyword, location, start=0):
    """
    Performs a search on Google Maps using SerpApi for a specific page of results.

    Args:
        api_key (str): The SerpApi API key for authentication.
        keyword (str): The search term (e.g., "restaurants", "coffee shops").
        location (str): The location for the search (e.g., "New York", "London").
        start (int, optional): The starting index for pagination. SerpApi uses this
                               to return subsequent pages of results. Defaults to 0.

    Returns:
        dict or None: A dictionary representing the JSON response from SerpApi if the
                      request is successful (HTTP 200). Returns `None` if the request
                      fails due to network issues, API errors, or other exceptions.

    Raises:
        requests.exceptions.RequestException: Can be raised by `requests.get` for
                                              various network problems, though this
                                              function catches it and returns None.
    """
    # Parameters for the SerpApi request
    params = {
        'engine': 'google_maps',  # Specifies the Google Maps search engine
        'q': f"{keyword} in {location}",  # The combined search query
        'type': 'search',  # Specifies the type of search
        'start': start,  # Parameter for pagination
        'api_key': api_key  # API key for authentication
    }
    logging.info(f"Searching Google Maps via SerpApi for: '{keyword} in {location}', start index: {start}")
    try:
        response = requests.get('https://serpapi.com/search.json', params=params)
        # Check if the request was successful
        if response.status_code == 200:
            logging.info(f"Successfully fetched data for '{keyword} in {location}', start: {start}")
            return response.json()  # Return the parsed JSON response
        else:
            logging.error(f"SerpApi Error for '{keyword} in {location}', start: {start}: HTTP {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        # Handles network errors, timeout, etc.
        logging.error(f"Request failed for '{keyword} in {location}', start: {start}: {e}")
        return None
    except Exception as e:
        # Catch any other unexpected errors during the API call
        logging.error(f"An unexpected error occurred during API call for '{keyword} in {location}', start: {start}: {e}")
        return None


def get_all_google_maps_results(api_key, keyword, location):
    """
    Retrieves all 'local_results' from Google Maps using SerpApi, handling pagination.

    This function repeatedly calls `search_google_maps` to fetch all pages of
    results for a given keyword and location pair.

    Args:
        api_key (str): The SerpApi API key.
        keyword (str): The search keyword.
        location (str): The location for the search.

    Returns:
        list: A list of dictionaries, where each dictionary represents a 'local_result'
              item from the SerpApi response. Returns an empty list if no results
              are found or if an error occurs during the process.
    """
    all_results = []
    current_start = 0  # Initial start index for pagination
    logging.info(f"Starting to fetch all results for query: Keyword='{keyword}', Location='{location}'")

    while True:
        page_data = search_google_maps(api_key, keyword, location, start=current_start)

        if page_data:
            local_results_on_page = page_data.get('local_results', [])
            if local_results_on_page:
                all_results.extend(local_results_on_page)
                logging.info(f"Fetched {len(local_results_on_page)} results from page with start={current_start} for '{keyword} in {location}'.")
            else:
                logging.info(f"No 'local_results' on page with start={current_start} for '{keyword} in {location}'.")
            
            # Check for pagination to get the next set of results
            serpapi_pagination = page_data.get('serpapi_pagination')
            if serpapi_pagination and 'next' in serpapi_pagination:
                next_page_url = serpapi_pagination['next']
                # Parse the 'next' URL to extract the 'start' parameter for the next page
                parsed_url = urlparse(next_page_url)
                query_params = parse_qs(parsed_url.query)
                
                if 'start' in query_params:
                    try:
                        # Update current_start for the next iteration
                        current_start = int(query_params['start'][0])
                    except ValueError:
                        logging.error(f"Could not parse 'start' parameter from next page URL: {next_page_url}. Stopping pagination for this query.")
                        break  # Exit loop if 'start' is not a valid integer
                else:
                    # If 'start' is not in the next page URL, it implies the end of results.
                    logging.info(f"No 'start' parameter in 'next' pagination URL: {next_page_url}. Assuming end of results for this query.")
                    break  # Exit loop
            else:
                # No 'next' link in pagination, so assume it's the last page
                logging.info(f"No 'next' page in pagination for '{keyword} in {location}'. Assuming end of results.")
                break 
        else:
            # API call failed for the current page
            logging.warning(f"Failed to fetch page for start={current_start} for '{keyword} in {location}'. Stopping pagination for this query.")
            break 
    
    logging.info(f"Collected {len(all_results)} results in total for '{keyword} in {location}' after handling pagination.")
    return all_results

if __name__ == "__main__":
    logging.info("Starting Google Maps scraping process.")
    master_results_list = []  # To store results from all queries

    # --- Load API Key ---
    serpapi_api_key = os.getenv('SERPAPI_API_KEY')
    if not serpapi_api_key:
        logging.error("SERPAPI_API_KEY environment variable not found. Please set it before running the script. Exiting.")
        exit()  # Critical failure, cannot proceed
    else:
        logging.info("SERPAPI_API_KEY loaded successfully.")

    try:
        # --- Read input queries ---
        # Assumes 'search_queries.csv' is in the same directory or path is correctly specified.
        queries_df = read_search_queries() 
        
        if queries_df.empty:
            logging.info("Search queries CSV is empty. No data to process.")
        else:
            logging.info(f"Processing {len(queries_df)} search queries from CSV.")
            # --- Process each query ---
            for index, row in queries_df.iterrows():
                keyword = row['keyword']
                location = row['location']
                
                # Fetch all results for the current keyword and location, handling pagination
                query_results = get_all_google_maps_results(serpapi_api_key, keyword, location)
                
                if query_results:
                    master_results_list.extend(query_results) # Add results to the master list
                
                # Polite delay between queries to avoid overwhelming the API
                if index < len(queries_df) - 1: # Avoid sleeping after the last query
                    logging.info(f"Sleeping for 1 second before processing the next query...")
                    time.sleep(1) 

            logging.info("--- All Queries Processed ---")
            
            # --- Consolidate and Deduplicate Results ---
            if master_results_list:
                df_master = pd.DataFrame(master_results_list)
                
                # Deduplication based on 'place_id'
                if not df_master.empty and 'place_id' in df_master.columns:
                    logging.info(f"Total rows before deduplication: {len(df_master)}")
                    df_master.drop_duplicates(subset=['place_id'], keep='first', inplace=True)
                    logging.info(f"Total rows after deduplication (based on 'place_id'): {len(df_master)}")
                elif 'place_id' not in df_master.columns and not df_master.empty:
                    # Warning if 'place_id' is missing, as it's crucial for deduplication
                    logging.warning("'place_id' column not found in the results. Deduplication based on 'place_id' cannot be performed.")
                elif df_master.empty and master_results_list: 
                     logging.info("DataFrame became empty after attempting to create it, possibly due to issues with result structure or all items being duplicates without a clear place_id.")

                logging.info(f"Total unique places collected from all queries: {len(df_master)}")
                # logging.info("Head of the master DataFrame:\n%s", df_master.head().to_string()) # Can be uncommented for verbose output

                # --- Save to CSV ---
                if not df_master.empty:
                    try:
                        output_filename = 'google_maps_results.csv'
                        df_master.to_csv(output_filename, index=False, encoding='utf-8')
                        logging.info(f"Successfully saved {len(df_master)} unique places to {output_filename}")
                    except Exception as e:
                        logging.error(f"Error saving DataFrame to CSV ('{output_filename}'): {e}")
                elif master_results_list: # Results were fetched, but DataFrame is empty after deduplication
                    logging.info("DataFrame is empty after deduplication, so nothing was saved to CSV.")
                else: # No results were fetched at all
                    logging.info("No results were collected from any query, so nothing was saved to CSV.")

            else:
                # If master_results_list is empty after all queries
                logging.info("No results found for any of the search queries provided.")

    # --- Error Handling for Main Block ---
    except FileNotFoundError:
        # Specifically for read_search_queries if the file isn't found
        logging.error("The 'search_queries.csv' file was not found. Please ensure it exists in the script's directory or specify the correct path.")
    except ValueError as ve: 
        # Specifically for errors like missing columns in read_search_queries
        logging.error(f"A configuration or data error occurred: {ve}")
    except pd.errors.EmptyDataError:
        # Specifically for read_search_queries if the CSV is empty
        logging.error("The 'search_queries.csv' file is empty (no data or only headers). Please provide queries.")
    except Exception as e:
        # Catch-all for any other unexpected errors during the main process
        logging.error(f"An unexpected error occurred in the main processing block: {e}", exc_info=True) # exc_info=True logs stack trace
    
    logging.info("Google Maps scraping process finished.")
