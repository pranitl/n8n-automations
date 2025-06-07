#!/usr/bin/env python3
"""
Script to sort TikTok JSON data by playCount and optionally filter top X posts.
"""

import json
import sys
from pathlib import Path

def sort_and_filter_json(input_file, output_file=None, ascending=False, top_x=None):
    """
    Sort JSON items by playCount field and optionally filter top X posts.
    
    Args:
        input_file (str): Path to input JSON file
        output_file (str, optional): Path to output file. If None, overwrites input file.
        ascending (bool): If True, sort in ascending order. Default is descending.
        top_x (int, optional): If provided, only keep top X posts after sorting.
    """
    try:
        # Read the JSON file
        print(f"Reading {input_file}...")
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Check if the expected structure exists
        if 'items' not in data:
            print("Error: JSON file does not contain 'items' array")
            return False
        
        original_count = len(data['items'])
        print(f"Found {original_count} items to sort")
        
        # Sort the items by playCount
        print("Sorting by playCount...")
        data['items'].sort(key=lambda x: x.get('playCount', 0), reverse=not ascending)
        
        # Filter top X if requested
        if top_x and top_x > 0:
            if top_x < len(data['items']):
                print(f"Filtering to top {top_x} posts...")
                data['items'] = data['items'][:top_x]
            else:
                print(f"Requested {top_x} posts, but only {len(data['items'])} available. Keeping all posts.")
        
        # Determine output file
        if output_file is None:
            output_file = input_file
        
        # Write the sorted/filtered data back
        action = "sorted and filtered" if top_x else "sorted"
        print(f"Writing {action} data to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Show some statistics
        final_items = data['items']
        final_count = len(final_items)
        
        if final_items:
            highest_play_count = final_items[0].get('playCount', 0)
            lowest_play_count = final_items[-1].get('playCount', 0)
            print(f"\nProcessing complete!")
            print(f"Original items: {original_count:,}")
            print(f"Final items: {final_count:,}")
            print(f"Highest play count: {highest_play_count:,}")
            print(f"Lowest play count: {lowest_play_count:,}")
            
            if top_x and final_count < original_count:
                removed_count = original_count - final_count
                print(f"Removed {removed_count:,} posts (kept top {final_count:,})")
        
        return True
        
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found")
        return False
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format - {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def create_top_x_versions(input_file, base_output_name="content/top-"):
    """
    Create multiple filtered versions with different top X counts.
    
    Args:
        input_file (str): Path to input JSON file
        base_output_name (str): Base name for output files
    """
    # Common top X values that might be useful
    top_counts = [10, 25, 50, 100, 250]
    
    print("\nCreating multiple top X versions...")
    print("=" * 40)
    
    for count in top_counts:
        output_file = f"{base_output_name}{count}-tt.json"
        print(f"\nCreating top {count} version...")
        
        success = sort_and_filter_json(input_file, output_file, ascending=False, top_x=count)
        
        if success:
            print(f"✅ Created: {output_file}")
        else:
            print(f"❌ Failed to create: {output_file}")

def get_positive_integer(prompt, default=None):
    """Get a positive integer from user input with validation."""
    while True:
        try:
            user_input = input(prompt).strip()
            if not user_input and default is not None:
                return default
            
            value = int(user_input)
            if value > 0:
                return value
            else:
                print("Please enter a positive number.")
        except ValueError:
            print("Please enter a valid number.")

def main():
    # Default file path
    input_file = "content/top-250-tt.json"
    
    # Check if file exists
    if not Path(input_file).exists():
        print(f"Error: {input_file} not found")
        print("Please make sure the file exists or provide the correct path")
        return
    
    # Main menu
    print("TikTok JSON Sorter & Filter")
    print("=" * 30)
    print(f"Input file: {input_file}")
    
    print("\nOptions:")
    print("1. Sort only (keep all posts)")
    print("2. Sort and filter to top X posts")
    print("3. Create multiple top X versions (10, 25, 50, 100, 250)")
    
    mode = input("\nEnter choice (1, 2, or 3): ").strip()
    
    if mode == "3":
        # Create multiple versions
        confirm = input("\nThis will create 5 new files with different top X counts. Continue? (y/n): ").strip().lower()
        if confirm in ['y', 'yes']:
            create_top_x_versions(input_file)
        else:
            print("Operation cancelled.")
        return
    
    # For modes 1 and 2, get sorting preference
    choice = input("\nSort order:\n1. Descending (highest play count first) [default]\n2. Ascending (lowest play count first)\nEnter choice (1 or 2): ").strip()
    
    ascending = choice == "2"
    order_text = "ascending" if ascending else "descending"
    
    # Get top X filter if mode 2
    top_x = None
    if mode == "2":
        top_x = get_positive_integer("\nEnter number of top posts to keep (e.g., 50): ")
        print(f"Will keep top {top_x} posts")
    
    # Ask about output file
    output_choice = input(f"\nOutput options:\n1. Overwrite original file [default]\n2. Create new file\nEnter choice (1 or 2): ").strip()
    
    output_file = None
    if output_choice == "2":
        if mode == "2" and top_x:
            suggested_name = f"content/top-{top_x}-tt.json"
            output_file = input(f"Enter output filename (default: {suggested_name}): ").strip()
            if not output_file:
                output_file = suggested_name
        else:
            output_file = input("Enter output filename (e.g., content/top-250-tt-sorted.json): ").strip()
            if not output_file:
                output_file = "content/top-250-tt-sorted.json"
    
    # Show summary
    print(f"\nProcessing summary:")
    print(f"- Sort order: {order_text}")
    if top_x:
        print(f"- Filter to top: {top_x} posts")
    else:
        print(f"- Filter: None (keep all posts)")
    
    final_output = output_file if output_file else input_file
    print(f"- Output file: {final_output}")
    
    # Perform the sorting/filtering
    success = sort_and_filter_json(input_file, output_file, ascending, top_x)
    
    if success:
        print(f"\n✅ Success! Data saved to: {final_output}")
        
        # Offer to create additional top X versions
        if mode == "1":
            create_more = input("\nWould you like to create additional top X filtered versions? (y/n): ").strip().lower()
            if create_more in ['y', 'yes']:
                create_top_x_versions(final_output)
    else:
        print("\n❌ Processing failed!")

if __name__ == "__main__":
    main() 