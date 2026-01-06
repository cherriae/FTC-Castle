
import logging
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.getcwd())

from app.scout.FTCScout import FTCScout

logging.basicConfig(level=logging.INFO)

def debug_team_events():
    scout = FTCScout()
    team_number = 19612 
    season = 2025
    
    print(f"1. Calling get_team({team_number})")
    team_info = scout.get_team(team_number)
    print(f"Team Info: {team_info}")

    print(f"\n2. Calling get_all_events({season}, search_text='{team_number}')")
    events = scout.get_all_events(season, search_text=str(team_number))
    
    if events:
        print(f"Found {len(events)} events:")
        for e in events:
            print(f"  Code: {e.get('code')}")
            print(f"  Name: {e.get('name')}")
            print(f"  Start: {e.get('start')}")
            print(f"  End: {e.get('end')}")
    else:
        print("No events found via search_text")

    # Try searching for the China event by name or region if possible
    # The text said "China FTC Shanghai"
    print(f"\n3. Searching for China events")
    # We can't search by name easily with the current wrapper unless we use search_text
    china_events = scout.get_all_events(season, search_text="Shanghai")
    if china_events:
        print(f"Found {len(china_events)} Shanghai events:")
        for e in china_events:
            print(f"  Code: {e.get('code')}")
            print(f"  Name: {e.get('name')}")
    
if __name__ == "__main__":
    debug_team_events()
