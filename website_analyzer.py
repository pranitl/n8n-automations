import os
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
# import google.generativeai as genai # No longer needed for OpenRouter
from openai import OpenAI, APIError, RateLimitError, APIConnectionError, APITimeoutError # OpenAI client
import base64 # For encoding images
from dotenv import load_dotenv
from pathlib import Path
import time
import re
from PIL import Image
import logging

# --- Setup Logging ---
LOG_FILE = "website_analyzer_openrouter.log"
logging.basicConfig(
    level=logging.INFO, # Change to logging.DEBUG for more verbose output
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a'),
        logging.StreamHandler()
    ]
)
# --- End Logging Setup ---

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# Optional: Set a default model or get from .env
DEFAULT_OPENROUTER_MODEL = "google/gemini-2.0-flash-lite-001"

if not OPENROUTER_API_KEY:
    logging.error("Error: OPENROUTER_API_KEY not found. Please set it in your .env file.")
    exit()

# Configure OpenAI client for OpenRouter
# Good practice to set a referrer and a unique title for your app
# For local scripts, referrer can be a simple identifier.
# X-Title can be your project name.
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={ # Optional, but good practice for OpenRouter
        "HTTP-Referer": "https://github.com/yourusername/your-repo-name", # Replace with your actual repo or a project URL
        "X-Title": "Website Aesthetic Analyzer", # Replace with your app name
    },
)

# Configuration
INPUT_CSV_PATH = "Google Map Scraper - Results.csv"
OUTPUT_CSV_PATH = "Google_Map_Scraper_Results_OpenRouter_Analyzed.csv"
SCREENSHOTS_DIR = Path("screenshots") # Changed dir name
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

OPTIMIZED_IMAGE_MAX_WIDTH = 1280
OPTIMIZED_IMAGE_JPEG_QUALITY = 85

# OpenRouter Model Configuration - YOU CAN CHANGE THIS
OPENROUTER_MODEL_NAME = DEFAULT_OPENROUTER_MODEL # Use the default or override here
logging.info(f"Using OpenRouter model: {OPENROUTER_MODEL_NAME}")


def sanitize_filename(url_or_name: str) -> str:
    s = str(url_or_name)
    s = s.replace("http://", "").replace("https://", "").replace("www.", "")
    s = re.sub(r'[^\w\.-]', '_', s)
    return s[:100]

def optimize_screenshot(original_path: Path, optimized_path: Path, max_width: int, jpeg_quality: int) -> bool:
    logging.info(f"Starting optimization for {original_path.name} to {optimized_path.name}")
    opt_start_time = time.perf_counter()
    try:
        with Image.open(original_path) as img:
            logging.debug(f"Image {original_path.name} opened. Mode: {img.mode}, Size: {img.size}")
            if img.mode == 'RGBA' or img.mode == 'P':
                 img = img.convert('RGB')
                 logging.debug(f"Converted image {original_path.name} to RGB.")
            if img.width > max_width:
                aspect_ratio = img.height / img.width
                new_height = int(max_width * aspect_ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            img.save(optimized_path, "JPEG", quality=jpeg_quality, optimize=True) # Save as JPEG
            original_size_mb = original_path.stat().st_size / (1024 * 1024)
            optimized_size_mb = optimized_path.stat().st_size / (1024 * 1024)
            logging.info(f"Optimized {original_path.name} ({original_size_mb:.2f}MB) -> {optimized_path.name} ({optimized_size_mb:.2f}MB)")
        original_path.unlink() # Delete the temporary PNG
        logging.debug(f"Deleted temporary original screenshot: {original_path}")
        logging.info(f"Optimization for {original_path.name} successful. Took {time.perf_counter() - opt_start_time:.4f}s")
        return True
    except Exception as e:
        logging.error(f"Error optimizing image {original_path}: {e}", exc_info=True)
        return False

def take_and_optimize_screenshot(url: str, base_filepath_name: str,
                                 screenshots_dir: Path, max_width: int, jpeg_quality: int) -> Path | None:
    logging.info(f"Attempting screenshot and optimization for URL: {url}")
    overall_ss_opt_start_time = time.perf_counter()
    original_screenshot_path = screenshots_dir / f"{base_filepath_name}_temp.png"
    optimized_screenshot_path = screenshots_dir / f"{base_filepath_name}.jpg"

    if not isinstance(url, str) or not (url.startswith('http://') or url.startswith('https://')):
        logging.warning(f"Invalid or missing URL for screenshot: {url}. Skipping.")
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                viewport={'width': 1920, 'height': 3000}  # Increased height to capture more content
            )
            page = context.new_page()
            logging.debug(f"Navigating to {url}...")
            page_goto_start = time.perf_counter()
            page.goto(url, timeout=90000, wait_until="networkidle")
            logging.debug(f"Navigation to {url} complete. Took {time.perf_counter() - page_goto_start:.4f}s")
            time.sleep(3)

            # Scroll to the bottom to ensure all content loads (e.g., lazy-loaded images)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)  # Wait for content to load after scrolling
            page.evaluate("window.scrollTo(0, 0)")  # Scroll back to the top

            logging.debug(f"Taking screenshot for {url}...")
            screenshot_take_start = time.perf_counter()
            page.screenshot(path=original_screenshot_path, full_page=True)  # Still use full_page for simplicity
            logging.debug(f"Screenshot for {url} saved to {original_screenshot_path}. Took {time.perf_counter() - screenshot_take_start:.4f}s")
            browser.close()

        if optimize_screenshot(original_screenshot_path, optimized_screenshot_path, max_width, jpeg_quality):
            logging.info(f"Screenshot and optimization for {url} successful. Total time: {time.perf_counter() - overall_ss_opt_start_time:.4f}s")
            return optimized_screenshot_path
        else:
            logging.error(f"Optimization failed for {original_screenshot_path}. It might have been deleted.")
            return None
    except PlaywrightTimeoutError:
        logging.error(f"Playwright timeout for {url}.", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"General error taking/optimizing screenshot for {url}: {e}", exc_info=True)
        if original_screenshot_path.exists():
            try:
                original_screenshot_path.unlink()
            except OSError:
                pass
        return None

def encode_image_to_base64(image_path: Path) -> str:
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logging.error(f"Error encoding image {image_path} to base64: {e}", exc_info=True)
        return ""

def analyze_website_aesthetic_categorized(image_path: Path, model_name: str) -> tuple[str, str]:
    logging.info(f"Starting aesthetic analysis for image: {image_path.name} using OpenRouter model: {model_name}")
    analysis_start_time = time.perf_counter()

    if not image_path.exists():
        logging.error(f"Screenshot not available for analysis: {image_path}")
        return "Error", "Screenshot not available for analysis."

    valid_categories = ["Modern", "Acceptable", "Outdated"]
    category = "Uncategorized"
    explanation = "Analysis initially failed or format incorrect."
    
    base64_image = encode_image_to_base64(image_path)
    if not base64_image:
        return "Error", "Failed to encode image."

    max_retries = 3
    base_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            img_size_bytes = image_path.stat().st_size
            logging.info(f"Attempt {attempt + 1}/{max_retries} to analyze {image_path.name} ({img_size_bytes / 1024:.2f} KB) with {model_name}")

            prompt_text = """
            Analyze the aesthetic of the website in the attached screenshot and classify its design into one of three categories: 'Modern', 'Acceptable', or 'Outdated'. Then, provide a one or two-sentence explanation for your classification, focusing on specific visual elements.

            Definitions (based on 2025 web design standards):
            - Modern: The website looks highly professional and contemporary, incorporating advanced modern design trends such as effective use of white space, modern typography (e.g., sans-serif fonts with varied weights), a cohesive and visually appealing color scheme, high-quality images or graphics, contemporary UI elements (e.g., buttons with hover effects, gradients, or subtle animations), and clear indicators of responsive design (e.g., adaptable layouts, mobile-friendly elements). It feels cutting-edge and aligns with the best practices of 2025.
            - Acceptable: The website is functional and has a decent, professional aesthetic, with a clean and organized layout, legible typography, a cohesive color scheme, and at least some professional elements (e.g., high-quality images, structured navigation). It may lack advanced modern design trends but is not significantly dated or visually unappealing, making it acceptable by 2025 standards.
            - Outdated: The website appears dated and visually unappealing by 2025 standards, resembling designs from the early 2000s or 2010s. This includes websites with cluttered or overly basic layouts, lack of any professional aesthetic, low-quality or pixelated images, clashing or dated colors, poor typography, or an overall impression that feels unprofessional and significantly out-of-touch with current trends.

            Key Evaluation Criteria:
            - Modern Design Elements: Does the website use effective white space, modern typography, and contemporary UI elements (e.g., hover effects, gradients, animations) (Modern), or does it lack these but still look professional (Acceptable), or lack them entirely with a dated appearance (Outdated)?
            - Image Quality: Are images high-quality, relevant, and well-integrated (Modern or Acceptable), or are they low-quality, pixelated, or generic (Outdated)?
            - Color Scheme: Is the color scheme cohesive, visually appealing, and modern (Modern), professional but simple (Acceptable), or bland, clashing, or dated (Outdated)?
            - Typography: Are fonts modern, varied, and legible (Modern), basic but professional and legible (Acceptable), or plain, inconsistent, and dated (Outdated)?
            - Layout: Is the layout clean, intuitive, and well-structured with clear hierarchy (Modern), organized and functional (Acceptable), or cluttered, unbalanced, or overly simplistic (Outdated)?
            - Responsiveness Indicators: Does the layout suggest adaptability (e.g., flexible grids, mobile-friendly elements) (Modern), appear functional but rigid (Acceptable), or look broken or desktop-only (Outdated)?
            - Overall Impression: Does the website feel cutting-edge and aligned with 2025 standards (Modern), professional but not modern (Acceptable), or like it was built in the early 2000s or 2010s with significant flaws (Outdated)?

            Important Notes:
            - To be classified as 'Modern', a website must exhibit advanced modern design trends (e.g., hover effects, gradients, animations) and feel cutting-edge by 2025 standards.
            - 'Acceptable' websites are functional, professional, and have a decent aesthetic (e.g., clean layout, cohesive colors), even if they lack advanced modern elements. They should not feel significantly dated or unprofessional.
            - 'Outdated' websites must have significant aesthetic flaws (e.g., cluttered layouts, clashing colors, pixelated images) and feel unprofessional by 2025 standards, making them clear candidates for a redesign.
            - Prioritize the overall impression based on 2025 standards. If a website is functional and has a decent, professional aesthetic but lacks advanced modern elements, classify it as 'Acceptable'. Only classify as 'Outdated' if it has significant flaws and feels unprofessional or dated.

            Format your response EXACTLY as:
            Category: [Modern, Acceptable, or Outdated]
            Explanation: [Your brief explanation based on the screenshot, mentioning at least one specific visual element from the criteria]
            """
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ]

            logging.debug(f"Sending request to OpenRouter model {model_name}...")
            model_call_start_time = time.perf_counter()
            
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=200
            )
            
            model_call_duration = time.perf_counter() - model_call_start_time
            logging.info(f"OpenRouter model call for {image_path.name} took {model_call_duration:.4f}s (Attempt {attempt+1})")
            
            response_text = response.choices[0].message.content.strip()
            logging.debug(f"OpenRouter raw response for {image_path.name} (first 300 chars): {response_text[:300]}")
            
            category_match = re.search(r"Category:\s*(Modern|Acceptable|Outdated)", response_text, re.IGNORECASE)
            explanation_match = re.search(r"Explanation:\s*(.*)", response_text, re.DOTALL | re.IGNORECASE)

            if category_match:
                extracted_cat = category_match.group(1).capitalize()
                if extracted_cat in valid_categories:
                    category = extracted_cat
                else:
                    category = "Invalid Category from LLM"
                    logging.warning(f"LLM ({model_name}) provided an invalid category for {image_path.name}: {extracted_cat}")
            else:
                if "modern" in response_text.lower():
                    category = "Modern"
                elif "acceptable" in response_text.lower():
                    category = "Acceptable"
                elif "outdated" in response_text.lower():
                    category = "Outdated"
                else:
                    category = "Uncategorized - Format Error"
                logging.warning(f"'Category:' line not found for {image_path.name} from {model_name}. Fallback category: {category}")
            
            if explanation_match:
                explanation = explanation_match.group(1).strip()
            elif category not in ["Uncategorized - Format Error", "Invalid Category from LLM", "Error"]:
                explanation = "Explanation not found in expected format, but category assigned."
                logging.warning(f"Explanation format error for {image_path.name} from {model_name}, but category '{category}' assigned.")
            else:
                explanation = f"Raw LLM Response (format error): {response_text[:250]}..."

            # Post-processing check to ensure "Outdated" classifications have significant flaws
            if category == "Outdated":
                significant_flaws = ["cluttered", "clashing", "pixelated", "dated", "unprofessional", "poor", "inconsistent"]
                if not any(flaw in explanation.lower() for flaw in significant_flaws):
                    logging.warning(f"Reclassifying {image_path.name} as 'Acceptable': Explanation lacks significant aesthetic flaws.")
                    category = "Acceptable"
                    explanation = f"{explanation} (Reclassified as Acceptable due to lack of significant aesthetic flaws by 2025 standards.)"
            
            break  # Success, exit retry loop

        except (RateLimitError, APIConnectionError, APITimeoutError) as e:
            logging.warning(f"API call attempt {attempt + 1} for {image_path.name} failed with {type(e).__name__}: {e}")
            if attempt + 1 == max_retries:
                logging.error(f"All {max_retries} API call attempts failed for {image_path.name}.", exc_info=True)
                explanation = f"Failed API call after {max_retries} attempts: {e}"
                category = "Error"
                break
            delay = base_delay * (2 ** attempt) + (0.5 * base_delay * attempt)
            logging.info(f"Retrying API call in {delay:.2f} seconds...")
            time.sleep(delay)
        except APIError as e:
            logging.error(f"OpenRouter APIError on attempt {attempt + 1} for {image_path.name}: {e}", exc_info=True)
            explanation = f"OpenRouter APIError: {e}"
            category = "Error"
            break
        except Exception as e:
            logging.error(f"Unexpected error during OpenRouter analysis attempt {attempt + 1} for {image_path.name}: {e}", exc_info=True)
            explanation = f"Unexpected analysis error: {e}"
            category = "Error"
            break

    logging.info(f"Aesthetic analysis for {image_path.name} complete. Category: {category}. Total time: {time.perf_counter() - analysis_start_time:.4f}s")
    return category, explanation

def main():
    script_start_time = time.perf_counter()
    logging.info(f"--- Starting website_analyzer.py (OpenRouter mode) script ---")
    logging.info(f"Using OpenRouter model: {OPENROUTER_MODEL_NAME}")

    if not Path(INPUT_CSV_PATH).exists():
        logging.error(f"Input CSV file '{INPUT_CSV_PATH}' not found.")
        return
    try:
        df = pd.read_csv(INPUT_CSV_PATH)
        logging.info(f"Successfully loaded {len(df)} rows from {INPUT_CSV_PATH}")
    except Exception as e:
        logging.error(f"Error reading CSV file '{INPUT_CSV_PATH}': {e}", exc_info=True)
        return
    if 'website' not in df.columns:
        logging.error(f"CSV must contain a 'website' column. Found: {df.columns.tolist()}")
        return

    df['aesthetic_category'] = "Not Processed"
    df['aesthetic_explanation'] = "Not Processed"
    df['screenshot_path'] = ""
    df['openrouter_model_used'] = OPENROUTER_MODEL_NAME # Add column for model used

    total_rows = len(df)
    for index, row in df.iterrows():
        loop_start_time = time.perf_counter()
        website_url = row.get('website')
        business_title = row.get('title', f"website_{index}")
        logging.info(f"Processing URL {index+1}/{total_rows}: {website_url} for '{business_title}'")

        if pd.isna(website_url) or not isinstance(website_url, str) or not (website_url.startswith('http://') or website_url.startswith('https://')):
            logging.warning(f"Invalid or missing URL: '{website_url}' for '{business_title}'. Skipping analysis.")
            df.loc[index, 'aesthetic_category'] = "Invalid URL"
            df.loc[index, 'aesthetic_explanation'] = "URL was not valid for processing."
            continue

        safe_name_for_file_base = f"{index}_{sanitize_filename(business_title if pd.notna(business_title) else website_url)}"
        optimized_screenshot_file_path = take_and_optimize_screenshot(
            website_url, safe_name_for_file_base, SCREENSHOTS_DIR,
            OPTIMIZED_IMAGE_MAX_WIDTH, OPTIMIZED_IMAGE_JPEG_QUALITY
        )

        category, explanation = "Error", "Screenshot/Optimization failed."
        screenshot_path_str = ""

        if optimized_screenshot_file_path and optimized_screenshot_file_path.exists():
            screenshot_path_str = str(optimized_screenshot_file_path)
            category, explanation = analyze_website_aesthetic_categorized(optimized_screenshot_file_path, OPENROUTER_MODEL_NAME)
        elif not optimized_screenshot_file_path:
             logging.warning(f"No valid screenshot for {website_url}, analysis skipped.")
        
        df.loc[index, 'screenshot_path'] = screenshot_path_str
        df.loc[index, 'aesthetic_category'] = category
        df.loc[index, 'aesthetic_explanation'] = explanation
        
        logging.info(f"Processed URL {index+1}/{total_rows} ({website_url}) in {time.perf_counter() - loop_start_time:.4f}s. Category: {category}")
    try:
        df.to_csv(OUTPUT_CSV_PATH, index=False, encoding='utf-8')
        logging.info(f"Analysis complete. Results saved to {OUTPUT_CSV_PATH}")
    except Exception as e:
        logging.error(f"Error saving output CSV '{OUTPUT_CSV_PATH}': {e}", exc_info=True)
    
    logging.info(f"--- website_analyzer.py (OpenRouter mode) script finished. Total duration: {time.perf_counter() - script_start_time:.4f}s ---")

if __name__ == "__main__":
    main()