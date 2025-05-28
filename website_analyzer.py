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
INPUT_CSV_PATH = "Google Map Scraper - Results.csv" # As per your provided file
OUTPUT_CSV_PATH = "Google_Map_Scraper_Results_Categorized_Explained_Analyzed.csv" # New output name
SCREENSHOTS_DIR = Path("screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Initialize Gemini model
try:
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
        image_file = genai.upload_file(path=image_path) # Use upload_file for gemini-1.5-flash

        # Updated prompt with detailed definitions for each category
        prompt = f"""
        Your task is to analyze the aesthetic of the website in the attached screenshot.
        First, classify the website's design into one of the following three categories only:
        1. Ugly
        2. Passable
        3. Modern

        Then, provide a brief one or two-sentence explanation for your classification.

        Definitions for Categorization:
        - Ugly: The website appears visually unappealing. This could be due to elements reminiscent of 1990s web design, use of outdated or clashing color schemes, poor typography choices, a cluttered or confusing layout, low-quality images, or other factors that make it aesthetically displeasing.
        - Passable: The website is functional but lacks a distinctive or impressive design. It might look like a standard boilerplate template (e.g., a basic, unmodified WordPress theme), have a very generic appearance, or use common stock elements without much customization. It's not offensive but not particularly engaging, innovative, or modern.
        - Modern: The website features a sleek, contemporary, and professional design. This often includes characteristics such as clean layouts, effective use of white space, high-quality and relevant imagery, current typography trends, a cohesive and pleasing color palette, intuitive navigation, and an overall polished and visually engaging presentation that feels up-to-date.

        Please format your response EXACTLY as follows, choosing only one category from the list above:
        Category: [Chosen Category: Ugly, Passable, or Modern]
        Explanation: [Your brief explanation based on the definitions and visual elements observed in the screenshot]

        Example if the website looked sleek and well-designed:
        Category: Modern
        Explanation: The website utilizes a minimalist design with ample white space, a contemporary font, and high-quality, relevant imagery, giving it a professional and up-to-date feel.

        Example if the website looked like a basic template:
        Category: Passable
        Explanation: The site appears to use a standard template structure with generic imagery and a simple color scheme. It's functional but not visually striking.

        Example if the website looked very outdated:
        Category: Ugly
        Explanation: The website uses a cluttered layout with clashing, bright colors and pixelated images, reminiscent of early web design or just not any decent looking website at all.
        """

        response = model.generate_content([prompt, image_file])
        genai.delete_file(image_file.name) # Clean up the uploaded file

        response_text = response.text.strip()

        # Parse the response
        category_match = re.search(r"Category:\s*(Ugly|Passable|Modern)", response_text, re.IGNORECASE)
        explanation_match = re.search(r"Explanation:\s*(.*)", response_text, re.DOTALL | re.IGNORECASE)

        if category_match:
            extracted_cat = category_match.group(1).capitalize()
            if extracted_cat in valid_categories:
                category = extracted_cat
            else:
                category = "Invalid Category from LLM"
                print(f"Warning: LLM provided an invalid category: {extracted_cat}")
        else:
            if "ugly" in response_text.lower(): category = "Ugly"
            elif "passable" in response_text.lower(): category = "Passable"
            elif "modern" in response_text.lower(): category = "Modern"
            else: category = "Uncategorized - Format Error"
            print(f"Warning: 'Category:' line not found in LLM response. Fallback attempt: {category}")

        if explanation_match:
            explanation = explanation_match.group(1).strip()
        elif category not in ["Uncategorized - Format Error", "Invalid Category from LLM", "Error"]:
             explanation = "Explanation not found in expected format, but category assigned."
        else:
            explanation = f"Raw LLM Response (format error or during fallback): {response_text[:250]}..."

        return category, explanation

    except Exception as e:
        print(f"Error analyzing image {image_path.name} with Gemini: {e}")
        if 'response' in locals() and hasattr(response, 'prompt_feedback') and response.prompt_feedback:
            print(f"Gemini Prompt Feedback: {response.prompt_feedback}")
        # Clean up file if an error occurs after upload
        if 'image_file' in locals() and image_file:
            try:
                genai.delete_file(image_file.name)
            except Exception as fe:
                print(f"Error cleaning up uploaded file {image_file.name}: {fe}")
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
        
        # time.sleep(1) # Optional delay between API calls

    try:
        df.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8')
        print(f"\nAnalysis complete. Results saved to {OUTPUT_CSV_PATH}")
        print(f"Screenshots saved in '{SCREENSHOTS_DIR}' directory.")
    except Exception as e:
        print(f"Error saving output CSV: {e}")

if __name__ == "__main__":
    main()