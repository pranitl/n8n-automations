import os
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path
import time
import re

# Load environment variables (API keys)
load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("Error: GOOGLE_GEMINI_API_KEY not found. Please set it in your .env file.")
    exit()

genai.configure(api_key=GEMINI_API_KEY)

# Configuration
INPUT_CSV_PATH = "Google Map Scraper - Results.csv"
OUTPUT_CSV_PATH = "Google_Map_Scraper_Results_Categorized_Analyzed.csv" # New output file name
SCREENSHOTS_DIR = Path("screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Initialize Gemini model
try:
    # Using a model that supports vision and good instruction following.
    # gemini-1.5-flash is generally good.
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print(f"Error initializing Gemini model: {e}")
    print("Please ensure your API key is valid and the model name is correct.")
    exit()

def sanitize_filename(url_or_name: str) -> str:
    """Sanitizes a string to be a valid filename component."""
    s = str(url_or_name)
    s = s.replace("http://", "").replace("https://", "").replace("www.", "")
    s = re.sub(r'[^\w\.-]', '_', s)
    return s[:100]

def take_screenshot(url: str, filepath: Path) -> bool:
    """Takes a screenshot of a given URL and saves it."""
    if not isinstance(url, str) or not (url.startswith('http://') or url.startswith('https://')):
        print(f"Invalid or missing URL for screenshot: {url}. Skipping.")
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                viewport={'width': 1280, 'height': 1024}
            )
            page = context.new_page()
            page.goto(url, timeout=90000, wait_until="networkidle")
            time.sleep(5)
            page.screenshot(path=filepath, full_page=True)
            browser.close()
            print(f"Screenshot saved for {url} at {filepath}")
            return True
    except PlaywrightTimeoutError:
        print(f"Timeout error while trying to load {url}. Skipping screenshot.")
        return False
    except Exception as e:
        print(f"Error taking screenshot for {url}: {e}")
        return False

def analyze_website_aesthetic_categorized(image_path: Path) -> tuple[str, str]:
    """
    Sends screenshot to Gemini for categorized aesthetic analysis.
    Returns a tuple: (category, explanation)
    """
    if not image_path.exists():
        return "Error", "Screenshot not available for analysis."

    valid_categories = ["Ugly", "Passable", "Modern"]
    category = "Uncategorized"
    explanation = "Analysis failed or format incorrect."

    try:
        print(f"Analyzing {image_path.name} with Gemini for categorization...")
        image_part = {
            "mime_type": "image/png",
            "data": image_path.read_bytes()
        }
        
        # New prompt for categorized output
        prompt = f"""
        Your task is to classify the website's aesthetic based on the attached screenshot.
        Choose exclusively from one of the following three categories:
        1. Ugly
        2. Passable
        3. Modern

        After assigning a category, provide a brief one or two-sentence explanation for your choice,
        focusing on visual design elements like layout, color scheme, typography, and overall presentation.

        Please format your response EXACTLY as follows:
        Category: [Chosen Category]
        Explanation: [Your brief explanation]

        Example:
        Category: Modern
        Explanation: The website uses a clean layout, contemporary typography, and a pleasing color scheme.
        """
        
        # Generation Configuration to encourage more deterministic output (optional, but can help)
        # generation_config = genai.types.GenerationConfig(
        #    temperature=0.2, # Lower temperature for more deterministic output
        #    # max_output_tokens=100 # If you want to limit response length
        # )
        # response = model.generate_content([prompt, image_part], generation_config=generation_config)
        
        response = model.generate_content([prompt, image_part])
        
        response_text = response.text.strip()
        
        # Parse the response
        category_match = re.search(r"Category:\s*(Ugly|Passable|Modern)", response_text, re.IGNORECASE)
        explanation_match = re.search(r"Explanation:\s*(.*)", response_text, re.DOTALL | re.IGNORECASE)

        if category_match:
            extracted_cat = category_match.group(1).capitalize() # Capitalize to match our list
            if extracted_cat in valid_categories:
                category = extracted_cat
            else:
                # This case should be rare if the model follows instructions
                category = "Invalid Category from LLM" 
                print(f"Warning: LLM provided an invalid category: {extracted_cat}")
        else:
            # Fallback: if "Category:" line is missing, try to find keywords directly
            # This is a weaker fallback
            if "ugly" in response_text.lower(): category = "Ugly"
            elif "passable" in response_text.lower(): category = "Passable"
            elif "modern" in response_text.lower(): category = "Modern"
            else: category = "Uncategorized - Format Error"
            print(f"Warning: 'Category:' line not found in LLM response. Fallback attempt: {category}")


        if explanation_match:
            explanation = explanation_match.group(1).strip()
        elif category != "Uncategorized - Format Error": # If category was found but explanation wasn't formatted
             explanation = "Explanation not found in expected format, but category assigned."
        else: # Neither category nor explanation found in expected format
            explanation = f"Raw LLM Response (format error): {response_text[:200]}..." # Store part of raw response

        return category, explanation

    except Exception as e:
        print(f"Error analyzing image {image_path.name} with Gemini: {e}")
        if 'response' in locals() and hasattr(response, 'prompt_feedback') and response.prompt_feedback:
            print(f"Gemini Prompt Feedback: {response.prompt_feedback}")
        return "Error", f"Gemini analysis exception: {str(e)}"


def main():
    if not Path(INPUT_CSV_PATH).exists():
        print(f"Error: Input CSV file '{INPUT_CSV_PATH}' not found.")
        return

    try:
        df = pd.read_csv(INPUT_CSV_PATH)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    if 'website' not in df.columns:
        print(f"Error: CSV must contain a 'website' column. Found columns: {df.columns.tolist()}")
        return
    
    # Initialize new columns
    df['aesthetic_category'] = "Not Processed"
    df['aesthetic_explanation'] = "Not Processed"
    df['screenshot_path'] = ""


    for index, row in df.iterrows():
        website_url = row.get('website')
        business_title = row.get('title', f"website_{index}")

        print(f"\nProcessing URL ({index+1}/{len(df)}): {website_url} for {business_title}")

        if pd.isna(website_url) or not isinstance(website_url, str) or not (website_url.startswith('http://') or website_url.startswith('https://')):
            print(f"Invalid or missing URL: '{website_url}'. Skipping analysis.")
            df.loc[index, 'aesthetic_category'] = "Invalid URL"
            df.loc[index, 'aesthetic_explanation'] = "URL was not valid for processing."
            df.loc[index, 'screenshot_path'] = ""
            continue

        safe_name_for_file = sanitize_filename(business_title if pd.notna(business_title) else website_url)
        screenshot_filename = f"{index}_{safe_name_for_file}.png"
        screenshot_path_obj = SCREENSHOTS_DIR / screenshot_filename
        
        category = "Error"
        explanation = "Screenshot failed or analysis error."
        screenshot_path_str = ""

        if take_screenshot(website_url, screenshot_path_obj):
            category, explanation = analyze_website_aesthetic_categorized(screenshot_path_obj)
            screenshot_path_str = str(screenshot_path_obj)
        else:
            category = "Error"
            explanation = "Screenshot failed."
            screenshot_path_str = ""
        
        df.loc[index, 'screenshot_path'] = screenshot_path_str
        df.loc[index, 'aesthetic_category'] = category
        df.loc[index, 'aesthetic_explanation'] = explanation
        
        # time.sleep(1) # Optional delay

    try:
        df.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8')
        print(f"\nAnalysis complete. Results saved to {OUTPUT_CSV_PATH}")
        print(f"Screenshots saved in '{SCREENSHOTS_DIR}' directory.")
    except Exception as e:
        print(f"Error saving output CSV: {e}")

if __name__ == "__main__":
    main()